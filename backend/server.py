from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Header, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Any
from datetime import datetime, timezone, timedelta
import logging
import uuid
import bcrypt
import jwt
import requests

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
CONTENT_ID = "portal_content"
FAMILY_AUTH_ID = "family_auth"

# ---------- object storage ----------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "fisher-family-portal"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
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
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ---------- helpers ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_token(role: str, email: str = "") -> str:
    payload = {
        "role": role,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=604800, path="/",
    )


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
        return {"role": payload.get("role"), "email": payload.get("email", "")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
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
        return {"role": payload.get("role"), "email": payload.get("email", "")}
    except jwt.InvalidTokenError:
        return None


MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
    "json": "application/json", "csv": "text/csv", "txt": "text/plain",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------- models ----------
class MemberLogin(BaseModel):
    password: str


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class ContentUpdate(BaseModel):
    content: dict


class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    topic: str
    message: str


# ---------- auth routes ----------
@api_router.post("/auth/member-login")
async def member_login(body: MemberLogin, response: Response):
    doc = await db.settings.find_one({"_id": FAMILY_AUTH_ID})
    if not doc or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect family password. Please try again.")
    token = create_token("member")
    set_auth_cookie(response, token)
    return {"role": "member"}


@api_router.post("/auth/admin-login")
async def admin_login(body: AdminLogin, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect administrator credentials.")
    token = create_token("admin", email)
    set_auth_cookie(response, token)
    return {"role": "admin", "email": email}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# ---------- content routes ----------
@api_router.get("/content")
async def get_content(user: dict = Depends(get_current_user)):
    doc = await db.settings.find_one({"_id": CONTENT_ID})
    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")
    return doc["content"]


@api_router.put("/content")
async def update_content(body: ContentUpdate, user: dict = Depends(require_admin)):
    await db.settings.update_one(
        {"_id": CONTENT_ID},
        {"$set": {"content": body.content, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True}


# ---------- contact ----------
@api_router.post("/contact")
async def submit_contact(body: ContactMessage, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.contact_messages.insert_one(doc)
    return {"ok": True, "id": doc["id"]}


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
        "id": file_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(doc)
    backend_base = os.environ.get("FRONTEND_URL", "")
    return {
        "id": file_id,
        "filename": file.filename,
        "size": doc["size"],
        "content_type": content_type,
        "url": f"{backend_base}/api/files/{file_id}",
    }


@api_router.get("/files/{file_id}")
async def download_file(
    file_id: str,
    request: Request,
    authorization: str = Header(None),
    auth: str = Query(None),
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token and auth:
        token = auth
    if not token:
        token = request.cookies.get("access_token")
    if user_from_token(token) is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.files.find_one({"id": file_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, content_type = get_object(record["storage_path"])
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=502, detail="Storage download failed.")
    filename = record.get("original_filename", "file")
    return Response(
        content=data,
        media_type=record.get("content_type", content_type),
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
            "registrationDeadline": P, "paymentDeadline": P,
            "adultFee": P, "childFee": P,
            "registrationLink": "#", "paymentLink": "#", "hotelLink": "#",
            "contactRole": "Reunion Committee",
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
            "structure": [
                {"id": str(uuid.uuid4()), "entity": P, "group": P, "role": P, "authority": P, "contact": P},
            ],
            "obligations": [
                {"id": str(uuid.uuid4()), "purpose": P, "amount": P, "responsible": P, "dueDate": P, "method": P, "contact": "Family Treasurer"},
            ],
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
            "reunion": [
                {"id": str(uuid.uuid4()), "name": "Reunion Registration Fee", "purpose": "Covers reunion attendance",
                 "amount": P, "whoPays": "Each attending household", "dueDate": P, "link": "#",
                 "instructions": "Payment instructions to be added.", "confirmation": "You will receive a confirmation.",
                 "contactRole": "Family Treasurer"},
            ],
            "business": [
                {"id": str(uuid.uuid4()), "name": "Family Business Contribution", "purpose": "Supports shared family business obligations",
                 "amount": P, "whoPays": "Business members", "dueDate": P, "link": "#",
                 "instructions": "Payment instructions to be added.", "confirmation": "You will receive a confirmation.",
                 "contactRole": "Family Treasurer"},
            ],
        },
        "meetings": {
            "upcoming": [
                {"id": str(uuid.uuid4()), "name": "Family Business Meeting", "date": P, "time": P,
                 "location": "#", "attendees": "Business members", "purpose": "To be announced",
                 "agenda": "Agenda to be posted.", "documents": "#", "rsvpDeadline": P},
            ],
            "past": [
                {"id": str(uuid.uuid4()), "date": P, "name": "Previous Meeting", "minutes": "#",
                 "decisions": "To be added", "actionItems": "To be added", "documents": "#"},
            ],
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
    }


@app.on_event("startup")
async def startup():
    # indexes
    await db.users.create_index("email", unique=True)
    # admin seed
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email, "password_hash": hash_password(admin_password),
            "name": "Portal Administrator", "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    # family password seed
    fam = await db.settings.find_one({"_id": FAMILY_AUTH_ID})
    if fam is None:
        await db.settings.insert_one({"_id": FAMILY_AUTH_ID, "password_hash": hash_password(os.environ["FAMILY_PASSWORD"])})
    # content seed
    content_doc = await db.settings.find_one({"_id": CONTENT_ID})
    if content_doc is None:
        await db.settings.insert_one({"_id": CONTENT_ID, "content": default_content(),
                                      "updated_at": datetime.now(timezone.utc).isoformat()})
    # object storage
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    logger.info("Startup seeding complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
