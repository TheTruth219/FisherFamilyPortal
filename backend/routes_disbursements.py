import uuid
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Response
from typing import Optional
from core import (
    CategoryCreate,
    DEFAULT_CATEGORIES,
    DISB_METHODS,
    DISB_STATUSES,
    DisbursementCreate,
    DisbursementUpdate,
    FundUpdate,
    _audit,
    _disbursement_email_html,
    _iso_now,
    _pdf_attachment,
    _receipt_pdf,
    _send_email,
    _statement_email_html,
    _statement_pdf,
    _store_receipt,
    api_router,
    db,
    get_current_user,
    get_object,
    is_staff,
    logger,
    member_name,
    require_admin,
)

# ---------- categories ----------
@api_router.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    cats = await db.disb_categories.find({}, {"_id": 0}).to_list(500)
    names = {c["name"] for c in cats} | set(DEFAULT_CATEGORIES)
    return sorted(names)


@api_router.post("/categories")
async def add_category(body: CategoryCreate, user: dict = Depends(require_admin)):
    await db.disb_categories.update_one({"name": body.name}, {"$setOnInsert": {"name": body.name}}, upsert=True)
    return {"ok": True, "name": body.name}


# ---------- disbursements ----------
@api_router.get("/disbursements")
async def list_disbursements(user: dict = Depends(get_current_user), member_id: Optional[str] = Query(None),
                             status: Optional[str] = Query(None), date_from: Optional[str] = Query(None),
                             date_to: Optional[str] = Query(None)):
    q = {}
    if not is_staff(user):
        q["member_id"] = user["id"]
    elif member_id:
        q["member_id"] = member_id
    if status:
        q["status"] = status
    if date_from:
        q.setdefault("date", {})["$gte"] = date_from
    if date_to:
        q.setdefault("date", {})["$lte"] = date_to
    return await db.disbursements.find(q, {"_id": 0}).sort("date", -1).to_list(2000)


@api_router.get("/disbursements/summary")
async def disbursements_summary(user: dict = Depends(get_current_user)):
    q = {} if is_staff(user) else {"member_id": user["id"]}
    items = await db.disbursements.find(q, {"_id": 0}).to_list(5000)
    by_status, per_member = {}, {}
    for i in items:
        by_status[i["status"]] = by_status.get(i["status"], 0) + i["amount_cents"]
        pm = per_member.setdefault(i["member_id"], {"member_name": i.get("member_name", ""), "total": 0, "count": 0})
        pm["total"] += i["amount_cents"]
        pm["count"] += 1
    return {"total_cents": sum(i["amount_cents"] for i in items), "count": len(items),
            "by_status": by_status, "per_member": per_member}


@api_router.post("/disbursements")
async def create_disbursement(body: DisbursementCreate, background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    if body.method not in DISB_METHODS:
        raise HTTPException(status_code=422, detail="Invalid method")
    member = await db.members.find_one({"id": body.member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    cents = round(body.amount * 100)
    if cents <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")
    d = {"id": str(uuid.uuid4()), "member_id": member["id"], "member_name": member_name(member),
         "member_email": member["email"], "amount_cents": cents, "currency": body.currency.upper(),
         "date": body.date, "category": body.category, "reason": body.reason, "method": body.method,
         "authorized_by": user["id"], "authorized_by_name": member_name(user), "status": "recorded",
         "notes": body.notes, "acknowledged": False, "acknowledged_at": None, "receipt_path": None,
         "transfer_id": None, "payout_id": None, "failure_code": None, "email_sent_at": None,
         "created_at": _iso_now(), "updated_at": _iso_now()}
    await db.disbursements.insert_one(d)
    d.pop("_id", None)
    await _audit(d["id"], "create", user, {"amount_cents": cents, "status": "recorded"})
    if body.category:
        await db.disb_categories.update_one({"name": body.category}, {"$setOnInsert": {"name": body.category}}, upsert=True)
    await _store_receipt(d)
    if body.send_email:
        async def _send():
            try:
                att = [_pdf_attachment(f"receipt-{d['id'][:8]}.pdf", _receipt_pdf(d))]
                if await _send_email(member["email"], "Fisher Family Portal — Disbursement Receipt", _disbursement_email_html(member_name(member), d), attachments=att):
                    await db.disbursements.update_one({"id": d["id"]}, {"$set": {"email_sent_at": _iso_now()}})
            except Exception as e:
                logger.error(f"disbursement email failed: {e}")
        background_tasks.add_task(_send)
    return await db.disbursements.find_one({"id": d["id"]}, {"_id": 0})


@api_router.patch("/disbursements/{disbursement_id}")
async def update_disbursement(disbursement_id: str, body: DisbursementUpdate, user: dict = Depends(require_admin)):
    existing = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Disbursement not found")
    updates, changes, data = {}, {}, body.model_dump()
    if data.get("amount") is not None:
        nc = round(data["amount"] * 100)
        if nc <= 0:
            raise HTTPException(status_code=422, detail="Amount must be positive")
        if nc != existing["amount_cents"]:
            changes["amount_cents"] = {"old": existing["amount_cents"], "new": nc}
            updates["amount_cents"] = nc
    for f in ("date", "category", "reason", "method", "status", "notes"):
        v = data.get(f)
        if v is not None and v != existing.get(f):
            if f == "status" and v not in DISB_STATUSES:
                raise HTTPException(status_code=422, detail="Invalid status")
            if f == "method" and v not in DISB_METHODS:
                raise HTTPException(status_code=422, detail="Invalid method")
            changes[f] = {"old": existing.get(f), "new": v}
            updates[f] = v
    if not updates:
        return existing
    updates["updated_at"] = _iso_now()
    await db.disbursements.update_one({"id": disbursement_id}, {"$set": updates})
    await _audit(disbursement_id, "edit", user, changes)
    fresh = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    await _store_receipt(fresh)
    return fresh


@api_router.post("/disbursements/{disbursement_id}/acknowledge")
async def acknowledge_disbursement(disbursement_id: str, user: dict = Depends(get_current_user)):
    d = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Disbursement not found")
    if d["member_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only acknowledge your own disbursements.")
    await db.disbursements.update_one({"id": disbursement_id}, {"$set": {"acknowledged": True, "acknowledged_at": _iso_now()}})
    await _audit(disbursement_id, "acknowledge", user, {"acknowledged": True})
    return await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})


@api_router.post("/disbursements/{disbursement_id}/send-email")
async def resend_disbursement_email(disbursement_id: str, user: dict = Depends(require_admin)):
    d = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Disbursement not found")
    att = [_pdf_attachment(f"receipt-{d['id'][:8]}.pdf", _receipt_pdf(d))]
    ok = await _send_email(d["member_email"], "Fisher Family Portal — Disbursement Receipt", _disbursement_email_html(d["member_name"], d), attachments=att)
    if not ok:
        raise HTTPException(status_code=400, detail="Email could not be sent (email not configured).")
    await db.disbursements.update_one({"id": disbursement_id}, {"$set": {"email_sent_at": _iso_now()}})
    return {"ok": True, "to": d["member_email"]}


@api_router.get("/disbursements/{disbursement_id}/receipt")
async def disbursement_receipt(disbursement_id: str, user: dict = Depends(get_current_user)):
    d = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Disbursement not found")
    if d["member_id"] != user["id"] and not is_staff(user):
        raise HTTPException(status_code=403, detail="Not authorized")
    pdf = None
    if d.get("receipt_path"):
        try:
            pdf, _ = get_object(d["receipt_path"])
        except Exception:
            pdf = None
    if not pdf:
        pdf = _receipt_pdf(d)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="receipt-{disbursement_id[:8]}.pdf"'})


@api_router.get("/disbursements/statement/{member_id}")
async def member_statement(member_id: str, user: dict = Depends(get_current_user)):
    if member_id != user["id"] and not is_staff(user):
        raise HTTPException(status_code=403, detail="Not authorized")
    member = await db.members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    items = await db.disbursements.find({"member_id": member_id}, {"_id": 0}).sort("date", -1).to_list(2000)
    pdf = _statement_pdf(member_name(member), items)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="statement-{member_id[:8]}.pdf"'})


@api_router.post("/disbursements/statement/{member_id}/send-email")
async def send_statement_email(member_id: str, user: dict = Depends(require_admin)):
    member = await db.members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    items = await db.disbursements.find({"member_id": member_id}, {"_id": 0}).sort("date", -1).to_list(2000)
    total = sum(i["amount_cents"] for i in items)
    att = [_pdf_attachment(f"statement-{member_id[:8]}.pdf", _statement_pdf(member_name(member), items))]
    ok = await _send_email(member["email"], "Fisher Family Portal — Your Statement", _statement_email_html(member_name(member), total, len(items)), attachments=att)
    if not ok:
        raise HTTPException(status_code=400, detail="Email could not be sent (email not configured).")
    return {"ok": True, "to": member["email"]}


@api_router.get("/audit/{disbursement_id}")
async def get_audit(disbursement_id: str, user: dict = Depends(require_admin)):
    return await db.audit_log.find({"disbursement_id": disbursement_id}, {"_id": 0}).sort("at", -1).to_list(500)


# ---------- fund tracker ----------
@api_router.get("/fund")
async def get_fund(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(status_code=403, detail="Not authorized")
    doc = await db.fund.find_one({"id": "business"}, {"_id": 0})
    total_funded = doc["total_funded_cents"] if doc else 0
    items = await db.disbursements.find({}, {"_id": 0, "amount_cents": 1, "status": 1}).to_list(5000)
    dispersed = sum(i["amount_cents"] for i in items)
    paid = sum(i["amount_cents"] for i in items if i["status"] == "paid")
    return {"total_funded_cents": total_funded, "total_dispersed_cents": dispersed, "total_paid_cents": paid,
            "remaining_cents": total_funded - dispersed, "disbursement_count": len(items)}


@api_router.put("/fund")
async def set_fund(body: FundUpdate, user: dict = Depends(require_admin)):
    await db.fund.update_one({"id": "business"}, {"$set": {"total_funded_cents": round(body.total_funded * 100), "updated_at": _iso_now()}}, upsert=True)
    return await get_fund(user)
