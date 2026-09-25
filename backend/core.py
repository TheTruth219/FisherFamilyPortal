from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid
import hashlib
import base64
import re
import ipaddress
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import jwt
import requests
import httpx
import bcrypt
import stripe
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors as _rc
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


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


async def _send_email(to_email: str, subject: str, html: str, attachments: Optional[list] = None) -> bool:
    if not EMAIL_KEY or EMAIL_KEY.startswith("{"):
        logger.error("Email not configured (EMERGENT_EMAIL_KEY missing)")
        return False
    _assert_safe_email(subject, html)
    try:
        payload = {"to": [to_email], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
        if attachments:
            payload["attachments"] = attachments
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                headers={"X-Email-Key": EMAIL_KEY},
                                json=payload)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def _pdf_attachment(filename: str, pdf_bytes: bytes) -> dict:
    return {"filename": filename, "content": base64.b64encode(pdf_bytes).decode()}


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
def get_jwt_secret() -> str:    return os.environ["JWT_SECRET"]


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
        "timezone": m.get("timezone") or "America/Chicago",
        "timezone_confirmed": bool(m.get("timezone_confirmed", False)),
        "stripe_account_id": m.get("stripe_account_id"),
        "onboarding_status": m.get("onboarding_status", "not_connected"),
        "payouts_enabled": bool(m.get("payouts_enabled", False)),
        "phone": m.get("phone", ""), "street": m.get("street", ""),
        "city": m.get("city", ""), "state": m.get("state", ""), "zip": m.get("zip", ""),
        "bio": m.get("bio", ""), "birthday": m.get("birthday", ""),
        "family_branch": m.get("family_branch", ""), "occupation": m.get("occupation", ""),
        "photo_file_id": m.get("photo_file_id"),
        "photo_url": (f"/api/files/{m['photo_file_id']}" if m.get("photo_file_id") else None),
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


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=80)
    last_name: Optional[str] = Field(None, max_length=80)
    phone: Optional[str] = Field(None, max_length=40)
    street: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=1000)
    birthday: Optional[str] = Field(None, max_length=20)
    family_branch: Optional[str] = Field(None, max_length=120)
    occupation: Optional[str] = Field(None, max_length=120)


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


class PasswordLogin(BaseModel):
    email: EmailStr
    password: str


class SetPassword(BaseModel):
    password: str = Field(..., min_length=8, max_length=200)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


GENERIC_LINK_RESPONSE = {"message": "If that email belongs to an authorized family member, a sign-in link has been sent."}


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


def _meeting_time_display(mtg: dict, member_tz: str) -> Optional[dict]:
    """Convert a meeting's structured start/end (in its source timezone) into the member's
    timezone. Returns {'member','source','same'} display strings, or None if unstructured."""
    date_s = (mtg.get("meetingDate") or "").strip()
    start_s = (mtg.get("startTime") or "").strip()
    if not date_s or not start_s:
        return None
    from zoneinfo import ZoneInfo
    try:
        src = ZoneInfo(mtg.get("timezone") or "America/Chicago")
        mem = ZoneInfo(member_tz or "America/Chicago")
        d = datetime.strptime(date_s, "%Y-%m-%d").date()
        sh, sm = (int(x) for x in start_s.split(":")[:2])
        start_src = datetime(d.year, d.month, d.day, sh, sm, tzinfo=src)
        end_s = (mtg.get("endTime") or "").strip()
        end_src = None
        if end_s:
            eh, em = (int(x) for x in end_s.split(":")[:2])
            end_src = datetime(d.year, d.month, d.day, eh, em, tzinfo=src)
            if end_src <= start_src:
                end_src = start_src + timedelta(hours=1)
    except Exception:
        return None

    def span(a, b):
        if b and b.date() == a.date():
            return f'{a.strftime("%A, %B %-d · %-I:%M %p")}–{b.strftime("%-I:%M %p")} {a.strftime("%Z")}'
        if b:
            return f'{a.strftime("%A, %B %-d · %-I:%M %p %Z")} – {b.strftime("%A, %B %-d · %-I:%M %p %Z")}'
        return a.strftime("%A, %B %-d · %-I:%M %p %Z")

    member_str = span(start_src.astimezone(mem), end_src.astimezone(mem) if end_src else None)
    source_str = span(start_src.astimezone(src), end_src.astimezone(src) if end_src else None)
    return {"member": member_str, "source": source_str, "same": member_str == source_str}



async def send_meeting_reminder(to_email: str, mtg: dict, member: Optional[dict] = None) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not base.startswith("https://") or "@" not in (to_email or ""):
        logger.error("Meeting reminder skipped: bad config (FRONTEND_URL / recipient)")
        return False
    link = f"{base}/meetings"
    name = escape((mtg.get("name") or "Family Meeting").strip())
    first = escape(((member or {}).get("first_name") or "").strip())
    tzname = escape(((member or {}).get("timezone") or "").strip())
    greeting = f"Hello {first}," if first else "Hello,"

    def row(label, value):
        v = (value or "").strip()
        return f'<p style="font-size:16px;margin:4px 0"><strong>{label}:</strong> {escape(v)}</p>' if v else ""

    time_disp = _meeting_time_display(mtg, (member or {}).get("timezone") or "")
    if time_disp:
        rows = (row("Your local time", time_disp["member"])
                + ("" if time_disp["same"] else row("Meeting time (host)", time_disp["source"]))
                + row("Who should attend", mtg.get("attendees"))
                + row("Purpose", mtg.get("purpose")))
    else:
        rows = (row("Date", mtg.get("date") or mtg.get("meetingDate"))
                + row("Time", mtg.get("time"))
                + row("Who should attend", mtg.get("attendees"))
                + row("Purpose", mtg.get("purpose")))
    tz_note = (f'This reminder reached you the day before the meeting in your time zone ({tzname}).'
               if tzname else 'This reminder reached you the day before the meeting in your time zone.')
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<p style="font-size:16px">{greeting}</p>'
        f'<p style="font-size:16px">This is a friendly reminder that <strong>{name}</strong> is scheduled for <strong>tomorrow</strong>.</p>'
        f'{rows}'
        f'<p style="margin:24px 0"><a href="{escape(link)}" '
        f'style="background:#1e3a8a;color:#ffffff;padding:14px 28px;border-radius:8px;'
        f'text-decoration:none;font-size:16px;font-weight:bold">View meeting details</a></p>'
        f'<p style="font-size:12px;color:#94a3b8">{tz_note} Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return await _send_email(to_email, f"Reminder: {name} is tomorrow", html)


async def process_meeting_reminders():
    """Per-member timezone fan-out: each active member gets their own reminder the day
    before a meeting, computed in THEIR timezone and sent at/after their local reminder hour.
    Runs hourly (see .emergent/crons.yml); idempotent per member+meeting+local-date."""
    doc = await db.settings.find_one({"_id": CONTENT_ID})
    if not doc:
        return
    content = doc.get("content", {})
    notif = content.get("notifications") or {}
    if not notif.get("enabled", True):
        logger.info("Meeting reminders: notifications disabled; nothing sent")
        return
    upcoming = [m for m in ((content.get("meetings") or {}).get("upcoming") or [])
                if (m.get("meetingDate") or "").strip()]
    if not upcoming:
        logger.info("Meeting reminders: no dated upcoming meetings; nothing to do")
        return
    from zoneinfo import ZoneInfo
    try:
        reminder_hour = int(notif.get("reminderHour", 9))
    except (TypeError, ValueError):
        reminder_hour = 9
    reminder_hour = min(max(reminder_hour, 0), 23)

    members = await db.members.find({"is_active": True}).to_list(1000)
    sent = 0
    for member in members:
        email = (member.get("email") or "").strip()
        if "@" not in email:
            continue
        try:
            tz = ZoneInfo(member.get("timezone") or "America/Chicago")
        except Exception:
            tz = ZoneInfo("America/Chicago")
        now_local = datetime.now(tz)
        if now_local.hour < reminder_hour:
            continue  # too early in this member's day; a later hourly run will catch it
        tomorrow = (now_local.date() + timedelta(days=1)).isoformat()
        for mtg in upcoming:
            if (mtg.get("meetingDate") or "").strip() != tomorrow:
                continue
            key = f"{mtg.get('id')}:{member['id']}:{tomorrow}"
            res = await db.reminders_sent.update_one(
                {"_id": key}, {"$setOnInsert": {"at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            if res.matched_count:  # already sent to this member for this meeting/date
                continue
            ok = await send_meeting_reminder(email, mtg, member)
            if ok:
                sent += 1
            logger.info(f"Meeting reminder fan-out {key} ok={ok}")
    logger.info(f"Meeting reminders: {sent} email(s) sent across {len(members)} active member(s)")


# ---------- MS Teams meeting invites (.ics) ----------
class MeetingInvite(BaseModel):
    name: str = Field(..., max_length=200)
    meetingDate: str  # YYYY-MM-DD
    startTime: str    # HH:MM (24h)
    endTime: str      # HH:MM (24h)
    timezone: str
    teamsLink: str = Field(..., max_length=2000)
    purpose: Optional[str] = ""
    agenda: Optional[str] = ""


def _ics_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_meeting_ics(inv: dict) -> str:
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(inv.get("timezone") or "America/Chicago")
    except Exception:
        tz = ZoneInfo("America/Chicago")
    d = datetime.strptime(inv["meetingDate"], "%Y-%m-%d").date()
    sh, sm = (int(x) for x in inv["startTime"].split(":")[:2])
    eh, em = (int(x) for x in inv["endTime"].split(":")[:2])
    start_local = datetime(d.year, d.month, d.day, sh, sm, tzinfo=tz)
    end_local = datetime(d.year, d.month, d.day, eh, em, tzinfo=tz)
    if end_local <= start_local:
        end_local = start_local + timedelta(hours=1)

    def z(dt):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    link = (inv.get("teamsLink") or "").strip()
    desc = []
    if inv.get("purpose"):
        desc.append(f"Purpose: {inv['purpose']}")
    if inv.get("agenda"):
        desc.append(f"Agenda: {inv['agenda']}")
    if link:
        desc.append(f"Join Microsoft Teams meeting: {link}")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Fisher Family Portal//EN",
        "CALSCALE:GREGORIAN", "METHOD:REQUEST", "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@fisherfamilyportal", f"DTSTAMP:{now}",
        f"DTSTART:{z(start_local)}", f"DTEND:{z(end_local)}",
        f"SUMMARY:{_ics_escape(inv.get('name') or 'Family Meeting')}",
        f"DESCRIPTION:{_ics_escape(chr(10).join(desc))}",
    ]
    if link:
        lines.append("LOCATION:Microsoft Teams Meeting")
        lines.append(f"URL:{link}")
    lines += ["STATUS:CONFIRMED", "SEQUENCE:0", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


async def send_meeting_invite(to_email: str, inv: dict) -> bool:
    if "@" not in (to_email or ""):
        logger.error("Meeting invite skipped: bad recipient")
        return False
    name = escape(inv.get("name") or "Family Meeting")
    link = (inv.get("teamsLink") or "").strip()
    tzname = escape(inv.get("timezone") or "")
    try:
        nice_date = datetime.strptime(inv["meetingDate"], "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except Exception:
        nice_date = inv.get("meetingDate", "")
    time_str = escape(f"{inv.get('startTime', '')}\u2013{inv.get('endTime', '')} ({tzname})")
    join_btn = (f'<p style="margin:24px 0"><a href="{escape(link)}" '
                f'style="background:#4b53bc;color:#fff;padding:14px 28px;border-radius:8px;'
                f'text-decoration:none;font-size:16px;font-weight:bold">Join Microsoft Teams meeting</a></p>'
                if link else "")
    rows = (f'<p style="font-size:16px;margin:4px 0"><strong>Date:</strong> {escape(nice_date)}</p>'
            f'<p style="font-size:16px;margin:4px 0"><strong>Time:</strong> {time_str}</p>')
    if inv.get("purpose"):
        rows += f'<p style="font-size:16px;margin:4px 0"><strong>Purpose:</strong> {escape(inv["purpose"])}</p>'
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<p style="font-size:16px">Hello Fisher family,</p>'
        f'<p style="font-size:16px">You are invited to <strong>{name}</strong>.</p>'
        f'{rows}{join_btn}'
        f'<p style="font-size:14px;color:#475569">A calendar invitation is attached (invite.ics) — open it to add this meeting to your calendar.</p>'
        f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    ics = build_meeting_ics(inv)
    attachment = {"filename": "invite.ics", "content": base64.b64encode(ics.encode("utf-8")).decode()}
    return await _send_email(to_email, f"Invitation: {name} \u2014 {nice_date}", html, attachments=[attachment])



# ==================== Disbursements · Statements · Stripe Connect · Timezone ====================
stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
STRIPE_1099_THRESHOLD_CENTS = 60000
DISB_STATUSES = {"recorded", "paid", "failed"}
DISB_METHODS = {"check", "zelle", "wire", "ach", "cash", "stripe"}
DEFAULT_CATEGORIES = ["Distribution", "Salary", "Reimbursement", "Dividend", "Loan Repayment",
                      "Gift", "Education", "Medical", "Emergency Support", "Bonus"]


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def member_name(m: dict) -> str:
    return (f"{m.get('first_name', '')} {m.get('last_name', '')}").strip() or m.get("email", "Member")


def _money(cents: int, cur: str = "USD") -> str:
    return f"${cents / 100:,.2f} {cur}"


def is_staff(user: dict) -> bool:
    return ROLE_LEVEL.get(user.get("role"), 1) >= 2


class TimezoneUpdate(BaseModel):
    timezone: str
    confirm: bool = True


class DisbursementCreate(BaseModel):
    member_id: str
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    date: str
    category: str
    reason: str = ""
    method: str = "check"
    notes: str = ""
    send_email: bool = True


class DisbursementUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    date: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None
    method: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class FundUpdate(BaseModel):
    total_funded: float = Field(..., ge=0)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


# ---------- PDF generation ----------
_NAVY = _rc.HexColor("#0F172A")
_BLUE = _rc.HexColor("#1E3A8A")
_CREAM = _rc.HexColor("#F3F1EC")
_SLATE = _rc.HexColor("#475569")
_LINE = _rc.HexColor("#E5E2D9")


def _pdf_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Brand", parent=s["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=_NAVY, spaceAfter=2, leading=24))
    s.add(ParagraphStyle("Kick", parent=s["Normal"], fontName="Helvetica", fontSize=8, textColor=_BLUE, spaceAfter=14, leading=12))
    s.add(ParagraphStyle("DTitle", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=15, textColor=_NAVY, spaceBefore=8, spaceAfter=4))
    s.add(ParagraphStyle("Meta", parent=s["Normal"], fontName="Helvetica", fontSize=9, textColor=_SLATE, leading=13))
    s.add(ParagraphStyle("Foot", parent=s["Normal"], fontName="Helvetica-Oblique", fontSize=8, textColor=_SLATE, leading=12, spaceBefore=6))
    return s


def _receipt_pdf(d: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch, leftMargin=0.9 * inch, rightMargin=0.9 * inch)
    s = _pdf_styles()
    story = [Paragraph("FISHER FAMILY PORTAL", s["Brand"]), Paragraph("FAMILY OFFICE TREASURY", s["Kick"]),
             HRFlowable(width="100%", thickness=1.2, color=_NAVY, spaceAfter=14),
             Paragraph("Disbursement Receipt", s["DTitle"]),
             Paragraph(f"Receipt No. {d['id'][:8].upper()}", s["Meta"]), Spacer(1, 12)]
    rows = [["Member", d.get("member_name", "")], ["Amount", _money(d["amount_cents"], d.get("currency", "USD"))],
            ["Date", (d.get("date") or "")[:10]], ["Category", d.get("category", "")],
            ["Reason", d.get("reason", "") or "—"], ["Method", (d.get("method") or "").title()],
            ["Authorized by", d.get("authorized_by_name", "")], ["Status", (d.get("status") or "").title()]]
    if d.get("notes"):
        rows.append(["Notes", d["notes"]])
    t = Table(rows, colWidths=[1.6 * inch, 4.2 * inch])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica"), ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                           ("FONTSIZE", (0, 0), (-1, -1), 10), ("TEXTCOLOR", (0, 0), (0, -1), _SLATE),
                           ("TEXTCOLOR", (1, 0), (1, -1), _NAVY), ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_rc.white, _CREAM]),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE), ("TOPPADDING", (0, 0), (-1, -1), 9),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story += [t, Spacer(1, 30), HRFlowable(width="100%", thickness=0.5, color=_LINE, spaceAfter=6),
              Paragraph("This receipt documents a disbursement from the Fisher family business account. "
                        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}. Confidential.", s["Foot"])]
    doc.build(story)
    return buf.getvalue()


def _statement_pdf(name: str, items: list) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch, leftMargin=0.9 * inch, rightMargin=0.9 * inch)
    s = _pdf_styles()
    story = [Paragraph("FISHER FAMILY PORTAL", s["Brand"]), Paragraph("FAMILY OFFICE TREASURY", s["Kick"]),
             HRFlowable(width="100%", thickness=1.2, color=_NAVY, spaceAfter=14),
             Paragraph("Member Statement", s["DTitle"]), Paragraph(f"{name} · All Time", s["Meta"]), Spacer(1, 14)]
    total = sum(x["amount_cents"] for x in items)
    data = [["Date", "Category", "Method", "Status", "Amount"]]
    for x in sorted(items, key=lambda z: z.get("date", ""), reverse=True):
        data.append([(x.get("date") or "")[:10], x.get("category", ""), (x.get("method") or "").title(),
                     (x.get("status") or "").title(), _money(x["amount_cents"], x.get("currency", "USD"))])
    data.append(["", "", "", "Total", _money(total)])
    t = Table(data, colWidths=[1.0 * inch, 1.7 * inch, 1.0 * inch, 1.0 * inch, 1.4 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), _NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), _rc.white),
                           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("FONTNAME", (0, 1), (-1, -2), "Helvetica"), ("ALIGN", (4, 0), (4, -1), "RIGHT"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -2), [_rc.white, _CREAM]), ("LINEBELOW", (0, 1), (-1, -2), 0.4, _LINE),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("TEXTCOLOR", (0, -1), (-1, -1), _NAVY),
                           ("LINEABOVE", (0, -1), (-1, -1), 1, _NAVY), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [t, Spacer(1, 22), HRFlowable(width="100%", thickness=0.5, color=_LINE, spaceAfter=6),
              Paragraph(f"Running statement of all disbursements. Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}. "
                        "Fisher Family Portal — Confidential.", s["Foot"])]
    doc.build(story)
    return buf.getvalue()


# ---------- disbursement emails ----------
def _disbursement_email_html(m_name: str, d: dict) -> str:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    link = f"{base}/my-statements"
    rows = "".join(
        f'<tr><td style="padding:6px 0;color:#475569;font-size:14px">{escape(k)}</td>'
        f'<td style="padding:6px 0;color:#0f172a;font-size:14px;font-weight:bold;text-align:right">{escape(v)}</td></tr>'
        for k, v in [("Amount", _money(d["amount_cents"], d.get("currency", "USD"))), ("Date", (d.get("date") or "")[:10]),
                     ("Category", d.get("category", "")), ("Reason", d.get("reason", "") or "—"),
                     ("Method", (d.get("method") or "").title()), ("Authorized by", d.get("authorized_by_name", "")),
                     ("Status", (d.get("status") or "").title())])
    return (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
            f'<p style="font-size:16px">Hello {escape(m_name)},</p>'
            f'<p style="font-size:16px">A disbursement has been recorded to your family account. Your official receipt (PDF) is attached to this email and is also available in the portal.</p>'
            f'<table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">{rows}</table>'
            f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#1e3a8a;color:#fff;padding:14px 28px;'
            f'border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold">View &amp; download receipt</a></p>'
            f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. We never ask for your password by email.</p>'
            f'</td></tr></table>')


def _statement_email_html(m_name: str, total_cents: int, count: int) -> str:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    link = f"{base}/my-statements"
    return (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
            f'<p style="font-size:16px">Hello {escape(m_name)},</p>'
            f'<p style="font-size:16px">Your Fisher Family account statement (PDF) is attached to this email and is also available in the portal.</p>'
            f'<p style="font-size:16px"><strong>Total disbursed:</strong> {escape(_money(total_cents))} &nbsp;·&nbsp; '
            f'<strong>Transactions:</strong> {count}</p>'
            f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#1e3a8a;color:#fff;padding:14px 28px;'
            f'border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold">View full statement</a></p>'
            f'<p style="font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. Sign in to view details.</p>'
            f'</td></tr></table>')


async def _audit(disbursement_id: str, action: str, actor: dict, changes: dict):
    await db.audit_log.insert_one({"id": str(uuid.uuid4()), "disbursement_id": disbursement_id, "action": action,
                                   "actor_id": actor["id"], "actor_name": member_name(actor), "changes": changes, "at": _iso_now()})


async def _store_receipt(d: dict):
    try:
        path = f"{APP_NAME}/receipts/{d['member_id']}/{d['id']}.pdf"
        put_object(path, _receipt_pdf(d), "application/pdf")
        await db.disbursements.update_one({"id": d["id"]}, {"$set": {"receipt_path": path}})
    except Exception as e:
        logger.error(f"receipt store failed: {e}")



# ---------- member profile + directory ----------
_PROFILE_FIELDS = ("first_name", "last_name", "phone", "street", "city", "state",
                   "zip", "bio", "birthday", "family_branch", "occupation")


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
        "notifications": {"listEmail": "", "enabled": True, "timezone": "America/New_York", "reminderHour": 9},
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
        "notifications": {"listEmail": "", "enabled": True, "timezone": "America/New_York", "reminderHour": 9},
    }

