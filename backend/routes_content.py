from datetime import datetime, timezone
from fastapi import BackgroundTasks, Depends, HTTPException
from core import (
    CONTENT_ID,
    ContentUpdate,
    MeetingInvite,
    all_notifiable_ids,
    api_router,
    collect_notifiable,
    db,
    get_current_user,
    item_is_meaningful,
    require_admin,
    sample_content,
    send_content_notification,
    send_meeting_invite,
)

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



@api_router.post("/meetings/invite")
async def send_teams_meeting_invite(body: MeetingInvite, user: dict = Depends(require_admin)):
    doc = await db.settings.find_one({"_id": CONTENT_ID})
    notif = ((doc or {}).get("content", {}) or {}).get("notifications") or {}
    list_email = (notif.get("listEmail") or "").strip()
    if "@" not in list_email:
        raise HTTPException(status_code=400, detail="Set the family distribution-list email in Members \u2192 Notifications before sending invites.")
    inv = body.model_dump()
    if not inv.get("teamsLink", "").strip().lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Enter a valid Microsoft Teams join link (starting with https://).")
    ok = await send_meeting_invite(list_email, inv)
    if not ok:
        raise HTTPException(status_code=400, detail="Invite could not be sent. Check the email configuration and try again.")
    return {"ok": True, "sent_to": list_email}
