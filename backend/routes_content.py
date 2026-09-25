from datetime import datetime, timezone
from fastapi import BackgroundTasks, Depends, HTTPException
from core import (
    CONTENT_ID,
    ContentUpdate,
    all_notifiable_ids,
    api_router,
    collect_notifiable,
    db,
    get_current_user,
    item_is_meaningful,
    require_admin,
    sample_content,
    send_content_notification,
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
