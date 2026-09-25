import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from core import (
    CONTENT_ID,
    all_notifiable_ids,
    api_router,
    client,
    db,
    default_content,
    hash_password,
    init_storage,
    logger,
    member_name,
)

import routes_auth, routes_members, routes_content, routes_contact  # noqa: F401
import routes_files, routes_cron, routes_disbursements, routes_stripe  # noqa: F401

app = FastAPI()
app.include_router(api_router)

_cors_origins = os.environ.get("CORS_ORIGINS", "*")
_cors_kwargs = {"allow_credentials": True, "allow_methods": ["*"], "allow_headers": ["*"]}
if _cors_origins.strip() == "*":
    _cors_kwargs["allow_origin_regex"] = ".*"  # reflect any origin (required for credentialed cross-origin)
else:
    _cors_kwargs["allow_origins"] = [o.strip() for o in _cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.on_event("startup")
async def startup():
    await db.members.create_index("email", unique=True)
    await db.magic_link_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.magic_link_tokens.create_index("token_hash", unique=True)
    await db.magic_link_requests.create_index("email")
    await db.magic_link_requests.create_index("created_at", expireAfterSeconds=900)
    await db.cron_runs.create_index("created_at", expireAfterSeconds=604800)
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("email")
    await db.login_attempts.create_index("created_at", expireAfterSeconds=1800)
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
    admin_pw = os.environ.get("ADMIN_PASSWORD")
    if admin_pw:
        adm = await db.members.find_one({"email": admin_email})
        if adm and not adm.get("password_hash"):
            await db.members.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_pw)}})
    # additional production admin (idempotent, env-driven)
    prod_admin_email = (os.environ.get("PROD_ADMIN_EMAIL") or "").lower().strip()
    prod_admin_pw = os.environ.get("PROD_ADMIN_PASSWORD")
    if prod_admin_email:
        now = datetime.now(timezone.utc).isoformat()
        pa = await db.members.find_one({"email": prod_admin_email})
        if pa is None:
            await db.members.insert_one({
                "id": str(uuid.uuid4()), "email": prod_admin_email, "first_name": "Stephen",
                "last_name": "Fisher", "role": "admin", "is_active": True, "token_version": 0,
                "timezone": "America/Chicago", "created_at": now, "updated_at": now,
                **({"password_hash": hash_password(prod_admin_pw)} if prod_admin_pw else {}),
            })
        else:
            fix = {}
            if pa.get("role") != "admin" or not pa.get("is_active", True):
                fix.update({"role": "admin", "is_active": True})
            if prod_admin_pw and not pa.get("password_hash"):
                fix["password_hash"] = hash_password(prod_admin_pw)
            if fix:
                await db.members.update_one({"email": prod_admin_email}, {"$set": fix})
    for _de in ("victoria@fisherfamily.com", "james@fisherfamily.com"):
        _dm = await db.members.find_one({"email": _de})
        if _dm and not _dm.get("password_hash"):
            await db.members.update_one({"email": _de}, {"$set": {"password_hash": hash_password("Fisher#2026"), "timezone_confirmed": True}})
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
    # timezone backfill + disbursement demo seed
    await db.members.update_many({"timezone": {"$exists": False}}, {"$set": {"timezone": "America/Chicago"}})
    try:
        await db.ledger_events.create_index("stripe_event_id", unique=True)
    except Exception:
        pass
    if await db.disbursements.count_documents({}) == 0:
        admin_m = await db.members.find_one({"email": admin_email})
        demo = [
            {"email": "victoria@fisherfamily.com", "first_name": "Victoria", "last_name": "Fisher", "role": "member", "timezone": "America/Los_Angeles"},
            {"email": "james@fisherfamily.com", "first_name": "James", "last_name": "Fisher", "role": "business_member", "timezone": "America/Chicago"},
        ]
        resolved = {}
        for dm in demo:
            ex = await db.members.find_one({"email": dm["email"]})
            if not ex:
                nowi = datetime.now(timezone.utc).isoformat()
                ex = {"id": str(uuid.uuid4()), "is_active": True, "token_version": 0, "timezone_confirmed": True,
                      "password_hash": hash_password("Fisher#2026"),
                      "created_at": nowi, "updated_at": nowi, **dm}
                await db.members.insert_one(ex)
            resolved[dm["email"]] = ex
        if admin_m:
            samples = [
                (resolved["victoria@fisherfamily.com"], 250000, "Distribution", "Q1 quarterly distribution", "wire", "2026-01-15", "paid"),
                (resolved["victoria@fisherfamily.com"], 120000, "Education", "Tuition support", "check", "2026-02-20", "recorded"),
                (resolved["james@fisherfamily.com"], 300000, "Distribution", "Q1 quarterly distribution", "zelle", "2026-01-15", "paid"),
                (resolved["james@fisherfamily.com"], 50000, "Reimbursement", "Travel reimbursement", "ach", "2026-03-05", "failed"),
            ]
            for mem, cents, cat, reason, method, date, status in samples:
                nowi = datetime.now(timezone.utc).isoformat()
                await db.disbursements.insert_one({
                    "id": str(uuid.uuid4()), "member_id": mem["id"], "member_name": member_name(mem), "member_email": mem["email"],
                    "amount_cents": cents, "currency": "USD", "date": date, "category": cat, "reason": reason, "method": method,
                    "authorized_by": admin_m["id"], "authorized_by_name": member_name(admin_m), "status": status, "notes": "",
                    "acknowledged": False, "acknowledged_at": None, "receipt_path": None, "transfer_id": None, "payout_id": None,
                    "failure_code": None, "email_sent_at": None, "created_at": nowi, "updated_at": nowi})
            await db.fund.update_one({"id": "business"}, {"$set": {"total_funded_cents": 5000000}}, upsert=True)
    logger.info("Startup seeding complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
