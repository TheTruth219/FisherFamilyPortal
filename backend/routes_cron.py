import secrets
from datetime import datetime, timezone
from fastapi import BackgroundTasks, HTTPException, Request
from core import (
    WEBHOOK_CRON_SECRET,
    api_router,
    db,
    process_meeting_reminders,
)

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
