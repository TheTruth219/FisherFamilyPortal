import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile
from core import (
    APP_NAME,
    GENERIC_LINK_RESPONSE,
    MAGIC_LINK_TTL_MIN,
    MIME_TYPES,
    PasswordLogin,
    ProfileUpdate,
    RequestLink,
    SetPassword,
    TimezoneUpdate,
    VerifyToken,
    _PROFILE_FIELDS,
    _hash_token,
    api_router,
    create_access_token,
    db,
    get_current_user,
    hash_password,
    logger,
    public_member,
    put_object,
    send_magic_link_email,
    set_auth_cookie,
    verify_password,
)

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


@api_router.post("/auth/login")
async def password_login(body: PasswordLogin, request: Request, response: Response):
    email = body.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    now = datetime.now(timezone.utc)
    window = now - timedelta(minutes=15)
    fails = await db.login_attempts.count_documents({"email": email, "created_at": {"$gt": window}})
    if fails >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait 15 minutes or use an email sign-in link.")
    member = await db.members.find_one({"email": email})
    ok = bool(member and member.get("is_active", True) and member.get("password_hash")
              and verify_password(body.password, member["password_hash"]))
    if not ok:
        await db.login_attempts.insert_one({"identifier": identifier, "email": email, "created_at": now})
        raise HTTPException(status_code=401, detail="Incorrect email or password. First-time members should use an email sign-in link, then set a password.")
    await db.login_attempts.delete_many({"email": email})
    token = create_access_token(member["id"], member["email"], member.get("token_version", 0))
    set_auth_cookie(response, token)
    return public_member(member)


@api_router.post("/auth/set-password")
async def set_password(body: SetPassword, user: dict = Depends(get_current_user)):
    await db.members.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(body.password),
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    member = await db.members.find_one({"id": user["id"]})
    result = public_member(member) if member else user
    result["has_password"] = bool(member and member.get("password_hash"))
    return result


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.patch("/auth/timezone")
async def set_timezone(body: TimezoneUpdate, user: dict = Depends(get_current_user)):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid timezone")
    await db.members.update_one({"id": user["id"]}, {"$set": {"timezone": body.timezone, "timezone_confirmed": bool(body.confirm)}})
    fresh = await db.members.find_one({"id": user["id"]})
    return public_member(fresh)


@api_router.patch("/auth/profile")
async def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    data = body.model_dump(exclude_unset=True)
    updates = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items() if k in _PROFILE_FIELDS}
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.members.update_one({"id": user["id"]}, {"$set": updates})
    fresh = await db.members.find_one({"id": user["id"]})
    return public_member(fresh)


@api_router.post("/auth/profile/photo")
async def upload_profile_photo(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    ext = (file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "")
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        raise HTTPException(status_code=400, detail="Please upload a JPG, PNG, GIF or WEBP image.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photo is too large (max 5 MB).")
    content_type = file.content_type or MIME_TYPES.get(ext, "image/jpeg")
    file_id = str(uuid.uuid4())
    path = f"{APP_NAME}/avatars/{file_id}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        logger.error(f"Avatar upload failed: {e}")
        raise HTTPException(status_code=400, detail="Photo upload failed. Please try again.")
    await db.files.insert_one({
        "id": file_id, "storage_path": result["path"], "original_filename": file.filename,
        "content_type": content_type, "size": result.get("size", len(data)),
        "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.members.update_one({"id": user["id"]}, {"$set": {"photo_file_id": file_id, "updated_at": datetime.now(timezone.utc).isoformat()}})
    fresh = await db.members.find_one({"id": user["id"]})
    return public_member(fresh)


@api_router.delete("/auth/profile/photo")
async def remove_profile_photo(user: dict = Depends(get_current_user)):
    await db.members.update_one({"id": user["id"]}, {"$unset": {"photo_file_id": ""}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    fresh = await db.members.find_one({"id": user["id"]})
    return public_member(fresh)


@api_router.get("/directory")
async def family_directory(user: dict = Depends(get_current_user)):
    docs = await db.members.find({"is_active": True}).to_list(1000)
    members = [public_member(m) for m in docs]
    members.sort(key=lambda m: (m.get("first_name", "").lower(), m.get("last_name", "").lower(), m.get("email", "")))
    return members
