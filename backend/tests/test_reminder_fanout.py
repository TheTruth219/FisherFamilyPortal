"""Verifies per-member timezone meeting-reminder fan-out. Run: python -m pytest backend/tests/test_reminder_fanout.py -q"""
import asyncio, uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import server  # noqa: F401  (loads the app + startup)
import core


async def _run():
    db = core.db
    CID = core.CONTENT_ID
    # snapshot original content to restore later
    orig = await db.settings.find_one({"_id": CID})
    orig_content = (orig or {}).get("content", {})

    members = await db.members.find({"is_active": True}).to_list(100)
    assert members, "need seeded members"

    # Build one meeting per DISTINCT member-local-tomorrow date so every member matches exactly one.
    per_member_tomorrow = {}
    meetings = {}
    for m in members:
        tz = ZoneInfo(m.get("timezone") or "America/Chicago")
        tmr = (datetime.now(tz).date() + timedelta(days=1)).isoformat()
        per_member_tomorrow[m["id"]] = tmr
        if tmr not in meetings:
            meetings[tmr] = {"id": f"test-mtg-{uuid.uuid4().hex[:8]}", "name": f"Test Meeting {tmr}",
                             "meetingDate": tmr, "time": "7:00 PM", "attendees": "All", "purpose": "QA"}

    # inject test content: reminderHour=0 so the local-hour gate always passes
    test_content = dict(orig_content)
    test_content["notifications"] = {**(orig_content.get("notifications") or {}), "enabled": True, "reminderHour": 0}
    test_content["meetings"] = {"upcoming": list(meetings.values()), "past": []}
    await db.settings.update_one({"_id": CID}, {"$set": {"content": test_content}}, upsert=True)

    # clean any prior reminder keys for our test meetings
    await db.reminders_sent.delete_many({"_id": {"$regex": "^test-mtg-"}})

    await core.process_meeting_reminders()

    # assert each member got exactly the reminder for the meeting on THEIR local tomorrow
    ok = True
    for m in members:
        if "@" not in (m.get("email") or ""):
            continue
        tmr = per_member_tomorrow[m["id"]]
        expected_mtg = meetings[tmr]["id"]
        key = f"{expected_mtg}:{m['id']}:{tmr}"
        hit = await db.reminders_sent.find_one({"_id": key})
        print(f"member={m['email']} tz={m.get('timezone')} tomorrow={tmr} key_present={bool(hit)}")
        if not hit:
            ok = False
        # ensure they were NOT sent a meeting for a different date
        for d, mt in meetings.items():
            if d == tmr:
                continue
            wrong = await db.reminders_sent.find_one({"_id": f"{mt['id']}:{m['id']}:{d}"})
            if wrong:
                print(f"  UNEXPECTED cross-date reminder for {m['email']} -> {d}")
                ok = False

    # idempotency: running again creates no new keys
    before = await db.reminders_sent.count_documents({"_id": {"$regex": "^test-mtg-"}})
    await core.process_meeting_reminders()
    after = await db.reminders_sent.count_documents({"_id": {"$regex": "^test-mtg-"}})
    print(f"idempotency before={before} after={after}")
    assert before == after, "second run must not resend"

    # gate test: reminderHour=23 should mostly suppress (skip if any member already at hour 23)
    # cleanup
    await db.reminders_sent.delete_many({"_id": {"$regex": "^test-mtg-"}})
    await db.settings.update_one({"_id": CID}, {"$set": {"content": orig_content}})
    assert ok, "some members did not receive the correct per-timezone reminder"
    print("PASS: per-member timezone fan-out verified; state restored")


def test_reminder_fanout():
    asyncio.get_event_loop().run_until_complete(_run())


if __name__ == "__main__":
    asyncio.run(_run())
