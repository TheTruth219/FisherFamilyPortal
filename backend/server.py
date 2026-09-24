from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Header, Query, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging
import uuid
import secrets
import hashlib
import re
import ipaddress
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import jwt
import requests
import httpx

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
CONTENT_ID = "portal_content"
ROLES = ["member", "business_member", "committee_member", "admin"]
MAGIC_LINK_TTL_MIN = 20
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

# ---------- object storage ----------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "fisher-family-portal"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
storage_key = None


def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ---------- managed email (Resend) ----------
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME") or "Fisher Family Portal"

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def _send_email(to_email: str, subject: str, html: str) -> bool:
    if not EMAIL_KEY or EMAIL_KEY.startswith("{"):
        logger.error("Email not configured (EMERGENT_EMAIL_KEY missing)")
        return False
    _assert_safe_email(subject, html)
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                headers={"X-Email-Key": EMAIL_KEY},
                                json={"to": [to_email], "subject": subject, "html": html,
                                      "from_name": EMAIL_FROM_NAME})
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def _magic_link_html(first_name: str, link: str, invited: bool) -> str:
    greeting = f"Hello {escape(first_name)}," if first_name else "Hello,"
    intro = ("You have been given access to the Fisher Family Portal — the private space for "
             "authorized family members." if invited else
             "We received a request to sign in to the Fisher Family Portal.")
    return (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<p style="font-size:16px">{greeting}</p>'
        f'<p style="font-size:16px">{intro}</p>'
        f'<p style="margin:24px 0"><a href="{escape(link)}" '
        f'style="background:#1e3a8a;color:#ffffff;padding:14px 28px;border-radius:8px;'
        f'text-decoration:none;font-size:16px;font-weight:bold">Sign in to the portal</a></p>'
        f'<p style="font-size:14px;color:#475569">This secure link expires in {MAGIC_LINK_TTL_MIN} minutes '
        f'and can be used once. If you did not request it, you can ignore this email.</p>'
        f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. '
        f'We never ask for your password by email.</p>'
        f'</td></tr></table>'
    )


async def send_magic_link_email(to_email: str, first_name: str, token: str, invited: bool = False) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    link = f"{base}/auth/verify?token={token}"
    if not base.startswith("https://"):
        if urlparse(base).hostname in ("localhost", "127.0.0.1", "::1"):
            logger.warning("Email not https; magic link: %s", link)
        else:
            logger.error("FRONTEND_URL is not a valid https origin; cannot send magic link")
        return False
    subject = ("Your invitation to the Fisher Family Portal" if invited
               else "Your Fisher Family Portal sign-in link")
    return await _send_email(to_email, subject, _magic_link_html(first_name, link, invited))


# ---------- auth helpers ----------
def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "email": email, "ver": token_version,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_member(m: dict) -> dict:
    return {
        "id": m["id"], "email": m["email"],
        "first_name": m.get("first_name", ""), "last_name": m.get("last_name", ""),
        "role": m.get("role", "member"), "is_active": m.get("is_active", True),
        "created_at": m.get("created_at"),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        member = await db.members.find_one({"id": payload["sub"]})
        if not member:
            raise HTTPException(status_code=401, detail="Account not found")
        if payload.get("ver", 0) != member.get("token_version", 0):
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
        if not member.get("is_active", True):
            raise HTTPException(status_code=403, detail="Your access has been deactivated. Contact the portal administrator.")
        return public_member(member)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def user_from_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return {"sub": payload.get("sub"), "email": payload.get("email", ""), "ver": payload.get("ver", 0)}
    except jwt.InvalidTokenError:
        return None


async def active_member_from_token(token: Optional[str]) -> Optional[dict]:
    payload = user_from_token(token)
    if not payload:
        return None
    member = await db.members.find_one({"id": payload["sub"]})
    if not member or not member.get("is_active", True):
        return None
    if payload.get("ver", 0) != member.get("token_version", 0):
        return None
    return member


ROLE_LEVEL = {"member": 1, "business_member": 2, "committee_member": 3, "admin": 4}
ACCESS_LEVEL = {"all members": 1, "business members": 2, "committee members": 3, "restricted": 4}
_FILE_ID_RE = re.compile(r"/api/files/([0-9a-fA-F-]{36})")


def _link_file_id(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    m = _FILE_ID_RE.search(link)
    return m.group(1) if m else None


def required_level_for_file(content: dict, file_id: str) -> int:
    """Access is authoritative from the document listings that reference the file.
    Returns the most restrictive level found (default 1 = all members)."""
    level = 1
    for d in content.get("documents", []) or []:
        if _link_file_id(d.get("link")) == file_id:
            level = max(level, ACCESS_LEVEL.get((d.get("access") or "").strip().lower(), 1))
    fb = content.get("familyBusiness", {}) or {}
    for d in fb.get("documents", []) or []:
        if _link_file_id(d.get("link")) == file_id:
            level = max(level, 3 if d.get("restricted") else 1)
    return level


MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "pdf": "application/pdf", "json": "application/json",
    "csv": "text/csv", "txt": "text/plain", "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------- models ----------
class RequestLink(BaseModel):
    email: EmailStr


class VerifyToken(BaseModel):
    token: str


class MemberCreate(BaseModel):
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    role: str = "member"


class MemberUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ContentUpdate(BaseModel):
    content: dict


class ContactMessage(BaseModel):
    name: str = Field(..., max_length=120)
    email: EmailStr
    phone: Optional[str] = Field("", max_length=40)
    topic: str = Field(..., max_length=200)
    message: str = Field(..., max_length=5000)


class HelpRequestUpdate(BaseModel):
    status: str


GENERIC_LINK_RESPONSE = {"message": "If that email belongs to an authorized family member, a sign-in link has been sent."}


# ---------- auth routes ----------
@api_router.post("/auth/request-link")
async def request_link(body: RequestLink, background_tasks: BackgroundTasks):
    email = body.email.lower().strip()
    now = datetime.now(timezone.utc)
    await db.magic_link_requests.insert_one({"email": email, "created_at": now})
    recent = await db.magic_link_requests.count_documents(
        {"email": email, "created_at": {"$gt": now - timedelta(minutes=15)}})
    app_recent = await db.magic_link_requests.count_documents(
        {"created_at": {"$gt": now - timedelta(minutes=10)}})
    if recent > 5 or app_recent > 9:
        return GENERIC_LINK_RESPONSE
    member = await db.members.find_one({"email": email})
    if member and member.get("is_active", True):
        raw = secrets.token_urlsafe(32)
        await db.magic_link_tokens.insert_one({
            "token_hash": _hash_token(raw), "user_id": member["id"], "email": email,
            "expires_at": now + timedelta(minutes=MAGIC_LINK_TTL_MIN), "used": False,
        })
        background_tasks.add_task(send_magic_link_email, member["email"], member.get("first_name", ""), raw, False)
    return GENERIC_LINK_RESPONSE


@api_router.post("/auth/verify")
async def verify(body: VerifyToken, response: Response):
    now = datetime.now(timezone.utc)
    rec = await db.magic_link_tokens.find_one_and_update(
        {"token_hash": _hash_token(body.token), "used": False, "expires_at": {"$gt": now}},
        {"$set": {"used": True}})
    if not rec:
        raise HTTPException(status_code=400, detail="This sign-in link is invalid or has expired. Please request a new one.")
    member = await db.members.find_one({"id": rec["user_id"]})
    if not member:
        raise HTTPException(status_code=400, detail="Account not found.")
    if not member.get("is_active", True):
        raise HTTPException(status_code=403, detail="Your access has been deactivated. Contact the portal administrator.")
    token = create_access_token(member["id"], member["email"], member.get("token_version", 0))
    set_auth_cookie(response, token)
    return public_member(member)


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# ---------- member management (admin) ----------
@api_router.get("/members")
async def list_members(user: dict = Depends(require_admin)):
    docs = await db.members.find().sort("created_at", 1).to_list(1000)
    return [public_member(m) for m in docs]


@api_router.post("/members")
async def create_member(body: MemberCreate, background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail="Invalid role")
    if await db.members.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="A member with that email already exists.")
    now = datetime.now(timezone.utc).isoformat()
    member = {
        "id": str(uuid.uuid4()), "email": email,
        "first_name": body.first_name.strip(), "last_name": body.last_name.strip(),
        "role": body.role, "is_active": True, "token_version": 0,
        "created_at": now, "updated_at": now,
    }
    await db.members.insert_one(member)
    raw = secrets.token_urlsafe(32)
    await db.magic_link_tokens.insert_one({
        "token_hash": _hash_token(raw), "user_id": member["id"], "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MIN), "used": False,
    })
    background_tasks.add_task(send_magic_link_email, email, member["first_name"], raw, True)
    return public_member(member)


@api_router.patch("/members/{member_id}")
async def update_member(member_id: str, body: MemberUpdate, user: dict = Depends(require_admin)):
    member = await db.members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    updates = {}
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail="Invalid role")
        if member["id"] == user["id"] and body.role != "admin":
            raise HTTPException(status_code=400, detail="You cannot remove your own administrator role.")
        updates["role"] = body.role
    if body.first_name is not None:
        updates["first_name"] = body.first_name.strip()
    if body.last_name is not None:
        updates["last_name"] = body.last_name.strip()
    if body.email is not None:
        new_email = body.email.lower().strip()
        if new_email != member["email"]:
            clash = await db.members.find_one({"email": new_email})
            if clash and clash["id"] != member_id:
                raise HTTPException(status_code=409, detail="Another member already uses that email.")
            updates["email"] = new_email
    if body.is_active is not None:
        updates["is_active"] = body.is_active
        if body.is_active is False and member["id"] == user["id"]:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        # revoke existing sessions when deactivating
        if body.is_active is False:
            updates["token_version"] = member.get("token_version", 0) + 1
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.members.update_one({"id": member_id}, {"$set": updates})
    fresh = await db.members.find_one({"id": member_id})
    return public_member(fresh)


@api_router.post("/members/{member_id}/resend-invite")
async def resend_invite(member_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    member = await db.members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not member.get("is_active", True):
        raise HTTPException(status_code=400, detail="Reactivate the member before sending a sign-in link.")
    raw = secrets.token_urlsafe(32)
    await db.magic_link_tokens.insert_one({
        "token_hash": _hash_token(raw), "user_id": member["id"], "email": member["email"],
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MIN), "used": False,
    })
    background_tasks.add_task(send_magic_link_email, member["email"], member.get("first_name", ""), raw, True)
    return {"ok": True}


# ---------- content ----------
_NOTIFY_PLACEHOLDERS = {"", "to be added", "new alert", "new meeting", "new payment",
                        "document link to be added", "previous meeting", "new matter",
                        "business matter title", "family business meeting"}


def collect_notifiable(content: dict) -> list:
    items = []
    for a in content.get("alerts", []) or []:
        items.append({"id": a.get("id"), "kind": "Announcement", "title": (a.get("topic") or "").strip()})
    m = content.get("meetings", {}) or {}
    for u in m.get("upcoming", []) or []:
        items.append({"id": u.get("id"), "kind": "Meeting", "title": (u.get("name") or "").strip()})
    for d in content.get("documents", []) or []:
        items.append({"id": d.get("id"), "kind": "Document", "title": (d.get("title") or "").strip()})
    return [it for it in items if it.get("id")]


def all_notifiable_ids(content: dict) -> list:
    return [it["id"] for it in collect_notifiable(content)]


def item_is_meaningful(it: dict) -> bool:
    return it["title"].strip().lower() not in _NOTIFY_PLACEHOLDERS


async def send_content_notification(to_email: str, items: list) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not base.startswith("https://"):
        logger.error("Content notification skipped: FRONTEND_URL is not https")
        return False
    if not to_email or "@" not in to_email:
        logger.error("Content notification skipped: invalid distribution list email")
        return False
    link = f"{base}/dashboard"
    groups = {}
    for it in items:
        groups.setdefault(it["kind"], []).append(it["title"])
    blocks = ""
    for kind, titles in groups.items():
        lis = "".join(f'<li style="margin:4px 0">{escape(t)}</li>' for t in titles)
        label = kind + ("s" if len(titles) > 1 else "")
        blocks += (f'<p style="font-size:16px;margin:16px 0 4px"><strong>New {escape(label)}</strong></p>'
                   f'<ul style="font-size:16px;color:#334155;margin:0;padding-left:20px">{lis}</ul>')
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<p style="font-size:16px">Hello Fisher family,</p>'
        f'<p style="font-size:16px">New information has been posted in the Fisher Family Portal:</p>'
        f'{blocks}'
        f'<p style="margin:24px 0"><a href="{escape(link)}" '
        f'style="background:#1e3a8a;color:#ffffff;padding:14px 28px;border-radius:8px;'
        f'text-decoration:none;font-size:16px;font-weight:bold">Open the family portal</a></p>'
        f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)} to the family distribution list. '
        f'Sign in with your own email to view the details.</p>'
        f'</td></tr></table>'
    )
    return await _send_email(to_email, "New in the Fisher Family Portal", html)


@api_router.get("/content")
async def get_content(user: dict = Depends(get_current_user)):
    doc = await db.settings.find_one({"_id": CONTENT_ID})
    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")
    return doc["content"]


@api_router.put("/content")
async def update_content(body: ContentUpdate, background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    old = await db.settings.find_one({"_id": CONTENT_ID}) or {}
    notified = set(old.get("notified_item_ids", []))
    new_content = body.content
    new_items = [it for it in collect_notifiable(new_content)
                 if it["id"] not in notified and item_is_meaningful(it)]
    for it in new_items:
        notified.add(it["id"])
    await db.settings.update_one(
        {"_id": CONTENT_ID},
        {"$set": {"content": new_content, "notified_item_ids": list(notified),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    notif = new_content.get("notifications") or {}
    if new_items and notif.get("enabled", True) and notif.get("listEmail"):
        background_tasks.add_task(send_content_notification, notif["listEmail"], new_items)
    return {"ok": True, "notified": len(new_items)}


@api_router.post("/content/load-sample")
async def load_sample(user: dict = Depends(require_admin)):
    sample = sample_content()
    existing = await db.settings.find_one({"_id": CONTENT_ID})
    # preserve configured notification settings so demo data doesn't wipe them
    if existing:
        sample["notifications"] = (existing.get("content", {}) or {}).get("notifications") or sample["notifications"]
    await db.settings.update_one(
        {"_id": CONTENT_ID},
        {"$set": {"content": sample, "notified_item_ids": all_notifiable_ids(sample),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return {"ok": True}


# ---------- contact / help requests ----------
@api_router.post("/contact")
async def submit_contact(body: ContactMessage, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["status"] = "new"
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.contact_messages.insert_one(doc)
    return {"ok": True, "id": doc["id"]}


@api_router.get("/help-requests")
async def list_help_requests(user: dict = Depends(require_admin)):
    docs = await db.contact_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for d in docs:
        d.setdefault("status", "new")
    return docs


@api_router.patch("/help-requests/{req_id}")
async def update_help_request(req_id: str, body: HelpRequestUpdate, user: dict = Depends(require_admin)):
    if body.status not in ("new", "in_progress", "resolved"):
        raise HTTPException(status_code=422, detail="Invalid status")
    res = await db.contact_messages.update_one({"id": req_id}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Help request not found")
    return {"ok": True}


# ---------- files ----------
@api_router.post("/files/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    ext = (file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 25 MB).")
    content_type = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    file_id = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{file_id}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=502, detail="Storage upload failed. Please try again.")
    doc = {
        "id": file_id, "storage_path": result["path"], "original_filename": file.filename,
        "content_type": content_type, "size": result.get("size", len(data)),
        "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(doc)
    backend_base = os.environ.get("FRONTEND_URL", "")
    return {"id": file_id, "filename": file.filename, "size": doc["size"],
            "content_type": content_type, "url": f"{backend_base}/api/files/{file_id}"}


@api_router.get("/files/{file_id}")
async def download_file(file_id: str, request: Request, authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token and auth:
        token = auth
    if not token:
        token = request.cookies.get("access_token")
    member = await active_member_from_token(token)
    if member is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.files.find_one({"id": file_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    # Role-based access control: resolve required level from the document listing that references this file.
    content_doc = await db.settings.find_one({"_id": CONTENT_ID})
    content = (content_doc or {}).get("content", {})
    required = required_level_for_file(content, file_id)
    if ROLE_LEVEL.get(member.get("role"), 1) < required:
        raise HTTPException(status_code=403, detail="You don't have permission to open this document.")
    try:
        data, content_type = get_object(record["storage_path"])
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=502, detail="Storage download failed.")
    filename = record.get("original_filename", "file")
    return Response(content=data, media_type=record.get("content_type", content_type),
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


async def send_meeting_reminder(to_email: str, mtg: dict) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not base.startswith("https://") or "@" not in (to_email or ""):
        logger.error("Meeting reminder skipped: bad config (FRONTEND_URL / list email)")
        return False
    link = f"{base}/meetings"
    name = escape((mtg.get("name") or "Family Meeting").strip())

    def row(label, value):
        v = (value or "").strip()
        return f'<p style="font-size:16px;margin:4px 0"><strong>{label}:</strong> {escape(v)}</p>' if v else ""

    rows = (row("Date", mtg.get("date") or mtg.get("meetingDate"))
            + row("Time", mtg.get("time"))
            + row("Who should attend", mtg.get("attendees"))
            + row("Purpose", mtg.get("purpose")))
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<p style="font-size:16px">Hello Fisher family,</p>'
        f'<p style="font-size:16px">This is a friendly reminder that <strong>{name}</strong> is scheduled for <strong>tomorrow</strong>.</p>'
        f'{rows}'
        f'<p style="margin:24px 0"><a href="{escape(link)}" '
        f'style="background:#1e3a8a;color:#ffffff;padding:14px 28px;border-radius:8px;'
        f'text-decoration:none;font-size:16px;font-weight:bold">View meeting details</a></p>'
        f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)} to the family distribution list.</p>'
        f'</td></tr></table>'
    )
    return await _send_email(to_email, f"Reminder: {name} is tomorrow", html)


async def process_meeting_reminders():
    doc = await db.settings.find_one({"_id": CONTENT_ID})
    if not doc:
        return
    content = doc.get("content", {})
    notif = content.get("notifications") or {}
    if not (notif.get("enabled", True) and notif.get("listEmail")):
        logger.info("Meeting reminders: notifications disabled or no list email; nothing sent")
        return
    from zoneinfo import ZoneInfo
    tzname = (notif.get("timezone") or "America/New_York")
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        logger.warning(f"Unknown reminder timezone {tzname!r}; falling back to America/New_York")
        tz = ZoneInfo("America/New_York")
    tomorrow = (datetime.now(tz).date() + timedelta(days=1)).isoformat()
    upcoming = (content.get("meetings") or {}).get("upcoming") or []
    for mtg in upcoming:
        if (mtg.get("meetingDate") or "").strip() != tomorrow:
            continue
        key = f"{mtg.get('id')}:{tomorrow}"
        res = await db.reminders_sent.update_one(
            {"_id": key}, {"$setOnInsert": {"at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        if res.matched_count:  # already sent for this meeting/date
            continue
        await send_meeting_reminder(notif["listEmail"], mtg)
        logger.info(f"Meeting reminder sent for {key}")


@api_router.post("/cron/meeting-reminders")
async def cron_meeting_reminders(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not WEBHOOK_CRON_SECRET or not secrets.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("X-Webhook-Id") or ""
    if run_id:
        existing = await db.cron_runs.find_one({"_id": run_id})
        if existing:
            return {"ok": True, "duplicate": True}
        await db.cron_runs.insert_one({"_id": run_id, "created_at": datetime.now(timezone.utc)})
    background_tasks.add_task(process_meeting_reminders)
    return {"ok": True}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- seed ----------
def default_content() -> dict:
    P = "To be added"
    return {
        "alerts": [
            {"id": str(uuid.uuid4()), "topic": "Reunion Registration Is Open",
             "explanation": "Registration for the family reunion is now open.",
             "deadline": P, "action": "Register your household", "buttonLabel": "Register", "buttonLink": "#"},
            {"id": str(uuid.uuid4()), "topic": "Reunion Payment Is Due",
             "explanation": "Reunion fees are due by the payment deadline.",
             "deadline": P, "action": "Submit reunion payment", "buttonLabel": "Make a Payment", "buttonLink": "#"},
            {"id": str(uuid.uuid4()), "topic": "Family Business Meeting Scheduled",
             "explanation": "A family business meeting has been scheduled.",
             "deadline": P, "action": "Review agenda and RSVP", "buttonLabel": "View Meeting", "buttonLink": "#"},
            {"id": str(uuid.uuid4()), "topic": "Document Available for Review",
             "explanation": "A new document has been posted for member review.",
             "deadline": P, "action": "Review the document", "buttonLabel": "View Document", "buttonLink": "#"},
            {"id": str(uuid.uuid4()), "topic": "Member Response Requested",
             "explanation": "A member vote or response has been requested.",
             "deadline": P, "action": "Submit your response", "buttonLabel": "Respond", "buttonLink": "#"},
        ],
        "reunion": {
            "year": P, "dates": P, "location": P, "hotel": P,
            "registrationDeadline": P, "paymentDeadline": P, "adultFee": P, "childFee": P,
            "registrationLink": "#", "paymentLink": "#", "hotelLink": "#", "contactRole": "Reunion Committee",
            "overview": "Reunion details will be posted here as they become available.",
            "schedule": [{"id": str(uuid.uuid4()), "time": P, "item": "Schedule to be announced"}],
            "documents": [{"id": str(uuid.uuid4()), "title": "Reunion Packet", "link": "#"}],
            "faqs": [{"id": str(uuid.uuid4()), "q": "How do I register?", "a": "Registration details will be posted here."}],
        },
        "familyBusiness": {
            "intro": "This page provides authorized family members with current information about family business matters, responsibilities, decisions, payments, meetings, and supporting documents.",
            "matters": [
                {"id": str(uuid.uuid4()), "title": "Business Matter Title", "background": "Brief background to be added.",
                 "status": P, "action": P, "deadline": P, "responsible": "Family Business Representative", "documentLink": "#"},
            ],
            "structure": [{"id": str(uuid.uuid4()), "entity": P, "group": P, "role": P, "authority": P, "contact": P}],
            "obligations": [{"id": str(uuid.uuid4()), "purpose": P, "amount": P, "responsible": P, "dueDate": P, "method": P, "contact": "Family Treasurer"}],
            "documents": [
                {"id": str(uuid.uuid4()), "title": "Business Summary", "link": "#", "restricted": False},
                {"id": str(uuid.uuid4()), "title": "Meeting Minutes", "link": "#", "restricted": False},
                {"id": str(uuid.uuid4()), "title": "Financial Reports", "link": "#", "restricted": True},
                {"id": str(uuid.uuid4()), "title": "Property Documents", "link": "#", "restricted": True},
                {"id": str(uuid.uuid4()), "title": "Tax Documents", "link": "#", "restricted": True},
                {"id": str(uuid.uuid4()), "title": "Legal Documents", "link": "#", "restricted": True},
                {"id": str(uuid.uuid4()), "title": "Proposals", "link": "#", "restricted": False},
                {"id": str(uuid.uuid4()), "title": "Voting Materials", "link": "#", "restricted": False},
            ],
        },
        "payments": {
            "reunion": [{"id": str(uuid.uuid4()), "name": "Reunion Registration Fee", "purpose": "Covers reunion attendance",
                         "amount": P, "whoPays": "Each attending household", "dueDate": P, "link": "#",
                         "instructions": "Payment instructions to be added.", "confirmation": "You will receive a confirmation.",
                         "contactRole": "Family Treasurer"}],
            "business": [{"id": str(uuid.uuid4()), "name": "Family Business Contribution", "purpose": "Supports shared family business obligations",
                          "amount": P, "whoPays": "Business members", "dueDate": P, "link": "#",
                          "instructions": "Payment instructions to be added.", "confirmation": "You will receive a confirmation.",
                          "contactRole": "Family Treasurer"}],
        },
        "meetings": {
            "upcoming": [{"id": str(uuid.uuid4()), "name": "Family Business Meeting", "date": P, "time": P,
                          "location": "#", "attendees": "Business members", "purpose": "To be announced",
                          "agenda": "Agenda to be posted.", "documents": "#", "meetingDate": "", "rsvpDeadline": P}],
            "past": [{"id": str(uuid.uuid4()), "date": P, "name": "Previous Meeting", "minutes": "#",
                      "decisions": "To be added", "actionItems": "To be added", "documents": "#"}],
        },
        "documents": [
            {"id": str(uuid.uuid4()), "title": "Reunion Packet", "description": "General reunion information for all members.",
             "date": P, "updated": P, "access": "All Members", "link": "#", "category": "Reunion"},
            {"id": str(uuid.uuid4()), "title": "Business Summary", "description": "Overview of family business matters.",
             "date": P, "updated": P, "access": "Business Members", "link": "#", "category": "Family Business"},
            {"id": str(uuid.uuid4()), "title": "Meeting Minutes", "description": "Minutes from the most recent meeting.",
             "date": P, "updated": P, "access": "All Members", "link": "#", "category": "Meetings"},
            {"id": str(uuid.uuid4()), "title": "Financial Report", "description": "Summary financial report.",
             "date": P, "updated": P, "access": "Restricted", "link": "#", "category": "Financial"},
            {"id": str(uuid.uuid4()), "title": "Governance Document", "description": "Family governance guidelines.",
             "date": P, "updated": P, "access": "Committee Members", "link": "#", "category": "Legal and Governance"},
            {"id": str(uuid.uuid4()), "title": "Registration Form", "description": "Reunion registration form.",
             "date": P, "updated": P, "access": "All Members", "link": "#", "category": "Forms"},
        ],
        "contacts": [
            {"id": str(uuid.uuid4()), "role": "Portal Administrator", "description": "Login and access help.", "email": "admin@fisherfamily.portal"},
            {"id": str(uuid.uuid4()), "role": "Reunion Committee", "description": "Reunion questions.", "email": "reunion@fisherfamily.portal"},
            {"id": str(uuid.uuid4()), "role": "Family Treasurer", "description": "Payment questions.", "email": "treasurer@fisherfamily.portal"},
            {"id": str(uuid.uuid4()), "role": "Family Business Representative", "description": "Business questions.", "email": "business@fisherfamily.portal"},
            {"id": str(uuid.uuid4()), "role": "Document Administrator", "description": "Document requests.", "email": "documents@fisherfamily.portal"},
        ],
        "notifications": {"listEmail": "", "enabled": True, "timezone": "America/New_York"},
    }


def sample_content() -> dict:
    """Clearly-marked fictional demo data to showcase a fully populated portal."""
    def nid():
        return str(uuid.uuid4())
    return {
        "alerts": [
            {"id": nid(), "topic": "SAMPLE — 2027 Reunion Registration Is Open",
             "explanation": "Registration for the 2027 Fisher Family Reunion is now open. (Sample data)",
             "deadline": "June 1, 2027", "action": "Register your household",
             "buttonLabel": "Register", "buttonLink": "#"},
            {"id": nid(), "topic": "SAMPLE — Reunion Payment Due",
             "explanation": "Reunion fees are due before the payment deadline. (Sample data)",
             "deadline": "June 15, 2027", "action": "Submit your reunion payment",
             "buttonLabel": "Make a Payment", "buttonLink": "#"},
            {"id": nid(), "topic": "SAMPLE — Summer Business Meeting Scheduled",
             "explanation": "The annual family business meeting has been scheduled. (Sample data)",
             "deadline": "July 15, 2027", "action": "Review the agenda and RSVP",
             "buttonLabel": "View Meeting", "buttonLink": "#"},
            {"id": nid(), "topic": "SAMPLE — New Meeting Minutes Posted",
             "explanation": "Minutes from the spring meeting are available for review. (Sample data)",
             "deadline": "No deadline", "action": "Read the minutes",
             "buttonLabel": "View Document", "buttonLink": "#"},
        ],
        "reunion": {
            "year": "2027", "dates": "July 16–18, 2027",
            "location": "Lakeside Convention Center, Springfield (SAMPLE)",
            "hotel": "Grand Lakeside Hotel (SAMPLE)",
            "registrationDeadline": "June 1, 2027", "paymentDeadline": "June 15, 2027",
            "adultFee": "$85 per adult (sample)", "childFee": "$40 per child under 12 (sample)",
            "registrationLink": "#", "paymentLink": "#", "hotelLink": "#",
            "contactRole": "Reunion Committee",
            "overview": "SAMPLE DATA: Join us for the 2027 Fisher Family Reunion, a weekend of food, "
                        "fellowship, and fun. All details below are fictional examples to show how the "
                        "reunion page looks when fully filled in.",
            "schedule": [
                {"id": nid(), "time": "Fri 6:00 PM", "item": "Welcome dinner & registration (sample)"},
                {"id": nid(), "time": "Sat 10:00 AM", "item": "Family group photo (sample)"},
                {"id": nid(), "time": "Sat 12:00 PM", "item": "Lakeside picnic lunch (sample)"},
                {"id": nid(), "time": "Sat 7:00 PM", "item": "Awards banquet (sample)"},
                {"id": nid(), "time": "Sun 10:00 AM", "item": "Farewell brunch (sample)"},
            ],
            "documents": [
                {"id": nid(), "title": "SAMPLE Reunion Packet (PDF)", "link": "#"},
                {"id": nid(), "title": "SAMPLE Registration Form", "link": "#"},
            ],
            "faqs": [
                {"id": nid(), "q": "How do I register my family?",
                 "a": "SAMPLE: Use the Register button above and complete one form per household."},
                {"id": nid(), "q": "Are children required to pay?",
                 "a": "SAMPLE: Children under 12 pay the reduced child fee; infants are free."},
                {"id": nid(), "q": "What is the hotel room rate?",
                 "a": "SAMPLE: A discounted family rate is available at the Grand Lakeside Hotel until June 1."},
            ],
        },
        "familyBusiness": {
            "intro": "SAMPLE DATA: This section provides authorized family members with current information "
                     "about family business matters, responsibilities, decisions and supporting documents. "
                     "The items below are fictional examples.",
            "matters": [
                {"id": nid(), "title": "SAMPLE — Lakeside Property Maintenance",
                 "background": "The family-owned lakeside property is due for its annual maintenance review.",
                 "status": "In progress", "action": "Approve the maintenance budget",
                 "deadline": "August 30, 2027", "responsible": "Property Committee", "documentLink": "#"},
                {"id": nid(), "title": "SAMPLE — Scholarship Fund Renewal",
                 "background": "The annual family scholarship fund is up for renewal and member input is requested.",
                 "status": "Open for input", "action": "Submit nominations",
                 "deadline": "September 15, 2027", "responsible": "Scholarship Committee", "documentLink": "#"},
            ],
            "structure": [
                {"id": nid(), "entity": "Lakeside Property (SAMPLE)", "group": "Property Committee",
                 "role": "Oversight & upkeep", "authority": "Committee vote", "contact": "property@example.com"},
                {"id": nid(), "entity": "Scholarship Fund (SAMPLE)", "group": "Scholarship Committee",
                 "role": "Awards & renewals", "authority": "Committee vote", "contact": "scholarship@example.com"},
                {"id": nid(), "entity": "General Finances (SAMPLE)", "group": "Family Treasurer",
                 "role": "Bookkeeping", "authority": "Reports to committee", "contact": "treasurer@example.com"},
            ],
            "obligations": [
                {"id": nid(), "purpose": "Property insurance (SAMPLE)", "amount": "$1,200 / year (sample)",
                 "responsible": "Property Committee", "dueDate": "January 1, 2027",
                 "method": "Committee account", "contact": "treasurer@example.com"},
                {"id": nid(), "purpose": "Scholarship contribution (SAMPLE)", "amount": "Voluntary (sample)",
                 "responsible": "All members", "dueDate": "Rolling",
                 "method": "Payments page", "contact": "treasurer@example.com"},
            ],
            "documents": [
                {"id": nid(), "title": "SAMPLE Business Summary", "link": "#", "restricted": False},
                {"id": nid(), "title": "SAMPLE Spring Meeting Minutes", "link": "#", "restricted": False},
                {"id": nid(), "title": "SAMPLE Financial Report (Restricted)", "link": "#", "restricted": True},
                {"id": nid(), "title": "SAMPLE Property Documents (Restricted)", "link": "#", "restricted": True},
                {"id": nid(), "title": "SAMPLE Proposal: Scholarship Renewal", "link": "#", "restricted": False},
            ],
        },
        "payments": {
            "reunion": [
                {"id": nid(), "name": "SAMPLE — Reunion Registration Fee", "purpose": "Covers reunion attendance",
                 "amount": "$85 per adult (sample)", "whoPays": "Each attending household",
                 "dueDate": "June 15, 2027", "link": "#",
                 "instructions": "SAMPLE: Pay online via the button, or mail a check to the Treasurer.",
                 "confirmation": "You'll receive an emailed receipt.", "contactRole": "Family Treasurer"},
            ],
            "business": [
                {"id": nid(), "name": "SAMPLE — Scholarship Fund Contribution", "purpose": "Supports the family scholarship",
                 "amount": "Any amount (sample)", "whoPays": "Voluntary — all members",
                 "dueDate": "Rolling", "link": "#",
                 "instructions": "SAMPLE: Contributions are optional and tax-year dependent.",
                 "confirmation": "You'll receive an emailed receipt.", "contactRole": "Family Treasurer"},
            ],
        },
        "meetings": {
            "upcoming": [
                {"id": nid(), "name": "SAMPLE — 2027 Summer Business Meeting", "date": "July 16, 2027",
                 "time": "7:00 PM ET", "location": "#", "attendees": "All members welcome; business members voting",
                 "purpose": "Annual review and budget approval",
                 "agenda": "SAMPLE: 1) Welcome  2) Treasurer's report  3) Property budget vote  4) Scholarship renewal  5) Open floor",
                 "documents": "#", "meetingDate": "2027-07-16", "rsvpDeadline": "July 10, 2027"},
            ],
            "past": [
                {"id": nid(), "date": "March 12, 2027", "name": "SAMPLE — Spring Planning Meeting",
                 "minutes": "#", "decisions": "SAMPLE: Approved reunion dates and venue.",
                 "actionItems": "SAMPLE: Committee to finalize hotel block by April 1.", "documents": "#"},
            ],
        },
        "documents": [
            {"id": nid(), "title": "SAMPLE Reunion Packet", "description": "Everything you need for the 2027 reunion.",
             "date": "May 2027", "updated": "May 2027", "access": "All Members", "link": "#", "category": "Reunion"},
            {"id": nid(), "title": "SAMPLE Registration Form", "description": "Household registration form.",
             "date": "May 2027", "updated": "May 2027", "access": "All Members", "link": "#", "category": "Forms"},
            {"id": nid(), "title": "SAMPLE Spring Meeting Minutes", "description": "Minutes from the March meeting.",
             "date": "March 2027", "updated": "March 2027", "access": "All Members", "link": "#", "category": "Meetings"},
            {"id": nid(), "title": "SAMPLE Business Summary", "description": "Overview of current business matters.",
             "date": "April 2027", "updated": "April 2027", "access": "Business Members", "link": "#", "category": "Family Business"},
            {"id": nid(), "title": "SAMPLE Financial Report", "description": "Summary financial report (restricted).",
             "date": "April 2027", "updated": "April 2027", "access": "Restricted", "link": "#", "category": "Financial"},
            {"id": nid(), "title": "SAMPLE Governance Guidelines", "description": "Family governance guidelines.",
             "date": "2026", "updated": "2026", "access": "Committee Members", "link": "#", "category": "Legal and Governance"},
        ],
        "contacts": [
            {"id": nid(), "role": "Portal Administrator", "description": "Login and access help (sample).", "email": "admin@example.com"},
            {"id": nid(), "role": "Reunion Committee", "description": "Reunion questions (sample).", "email": "reunion@example.com"},
            {"id": nid(), "role": "Family Treasurer", "description": "Payment questions (sample).", "email": "treasurer@example.com"},
            {"id": nid(), "role": "Family Business Representative", "description": "Business questions (sample).", "email": "business@example.com"},
            {"id": nid(), "role": "Document Administrator", "description": "Document requests (sample).", "email": "documents@example.com"},
        ],
        "notifications": {"listEmail": "", "enabled": True, "timezone": "America/New_York"},
    }


@app.on_event("startup")
async def startup():
    await db.members.create_index("email", unique=True)
    await db.magic_link_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.magic_link_tokens.create_index("token_hash", unique=True)
    await db.magic_link_requests.create_index("email")
    await db.magic_link_requests.create_index("created_at", expireAfterSeconds=900)
    await db.cron_runs.create_index("created_at", expireAfterSeconds=604800)
    # admin seed (magic-link, no password)
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    existing = await db.members.find_one({"email": admin_email})
    if existing is None:
        now = datetime.now(timezone.utc).isoformat()
        await db.members.insert_one({
            "id": str(uuid.uuid4()), "email": admin_email, "first_name": "Portal",
            "last_name": "Administrator", "role": "admin", "is_active": True,
            "token_version": 0, "created_at": now, "updated_at": now,
        })
    elif existing.get("role") != "admin" or not existing.get("is_active", True):
        await db.members.update_one({"email": admin_email}, {"$set": {"role": "admin", "is_active": True}})
    # content seed
    content_doc = await db.settings.find_one({"_id": CONTENT_ID})
    if content_doc is None:
        seeded = default_content()
        await db.settings.insert_one({"_id": CONTENT_ID, "content": seeded,
                                      "notified_item_ids": all_notifiable_ids(seeded),
                                      "updated_at": datetime.now(timezone.utc).isoformat()})
    else:
        migrate = {}
        content = content_doc["content"]
        notif = content.get("notifications")
        if notif is None:
            content["notifications"] = {"listEmail": "", "enabled": True, "timezone": "America/New_York"}
            migrate["content"] = content
        elif "timezone" not in notif:
            notif["timezone"] = "America/New_York"
            migrate["content"] = content
        if "notified_item_ids" not in content_doc:
            # baseline: treat everything already present as already-announced
            migrate["notified_item_ids"] = all_notifiable_ids(content)
        if migrate:
            await db.settings.update_one({"_id": CONTENT_ID}, {"$set": migrate})
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    logger.info("Startup seeding complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
