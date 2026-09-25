import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from core import (
    ContactMessage,
    HelpRequestUpdate,
    api_router,
    db,
    get_current_user,
    require_admin,
)

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
