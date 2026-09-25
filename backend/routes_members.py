import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks, Depends, HTTPException
from core import (
    MAGIC_LINK_TTL_MIN,
    MemberCreate,
    MemberUpdate,
    ROLES,
    _hash_token,
    api_router,
    db,
    public_member,
    require_admin,
    send_magic_link_email,
)

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
