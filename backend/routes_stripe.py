import os
import stripe
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from core import (
    ROLE_LEVEL,
    STRIPE_1099_THRESHOLD_CENTS,
    _audit,
    _iso_now,
    api_router,
    db,
    get_current_user,
    logger,
    require_admin,
)

# ---------- Stripe Connect (Phase 2) ----------
@api_router.post("/stripe/connect/onboard")
async def stripe_onboard(user: dict = Depends(get_current_user)):
    member = await db.members.find_one({"id": user["id"]})
    account_id = member.get("stripe_account_id")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    try:
        if not account_id:
            acct = stripe.Account.create(type="express", country="US", email=member["email"],
                                         capabilities={"transfers": {"requested": True}}, business_type="individual",
                                         metadata={"member_id": user["id"]})
            account_id = acct.id
            await db.members.update_one({"id": user["id"]}, {"$set": {"stripe_account_id": account_id, "onboarding_status": "pending"}})
        link = stripe.AccountLink.create(account=account_id, type="account_onboarding",
                                         refresh_url=f"{base}/account?stripe=refresh", return_url=f"{base}/account?stripe=return",
                                         collection_options={"fields": "eventually_due"})
        return {"url": link.url, "stripe_account_id": account_id}
    except Exception as e:
        msg = str(e)
        logger.error(f"Stripe onboard failed: {msg}")
        if "signed up for Connect" in msg or "platform" in msg.lower():
            raise HTTPException(status_code=400, detail="Stripe Connect is not enabled on the platform account yet. "
                                "Claim the Stripe sandbox, then enable Connect in your Stripe Dashboard "
                                "(Connect settings) and try again.")
        raise HTTPException(status_code=400, detail=f"Stripe onboarding could not start: {msg[:180]}")


@api_router.get("/stripe/connect/status")
async def stripe_status(user: dict = Depends(get_current_user)):
    member = await db.members.find_one({"id": user["id"]})
    account_id = member.get("stripe_account_id")
    if not account_id:
        return {"onboarding_status": "not_connected", "payouts_enabled": False, "charges_enabled": False}
    try:
        acct = stripe.Account.retrieve(account_id)
        pe, ce = bool(acct.get("payouts_enabled")), bool(acct.get("charges_enabled"))
        status = "onboarded" if pe else "pending"
        await db.members.update_one({"id": user["id"]}, {"$set": {"payouts_enabled": pe, "charges_enabled": ce, "onboarding_status": status}})
        return {"onboarding_status": status, "payouts_enabled": pe, "charges_enabled": ce, "requirements": acct.get("requirements", {})}
    except Exception as e:
        return {"onboarding_status": member.get("onboarding_status", "pending"), "payouts_enabled": member.get("payouts_enabled", False),
                "charges_enabled": member.get("charges_enabled", False), "error": str(e)[:180]}


@api_router.post("/stripe/payouts/{disbursement_id}")
async def stripe_payout(disbursement_id: str, user: dict = Depends(require_admin)):
    d = await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Disbursement not found")
    member = await db.members.find_one({"id": d["member_id"]})
    if not member or not member.get("stripe_account_id"):
        raise HTTPException(status_code=400, detail="Member has not started Stripe onboarding.")
    if not member.get("payouts_enabled"):
        raise HTTPException(status_code=400, detail="Member is not payout-eligible yet (KYC incomplete).")
    if d["status"] == "paid":
        raise HTTPException(status_code=409, detail="Disbursement is already paid.")
    try:
        transfer = stripe.Transfer.create(amount=d["amount_cents"], currency=d["currency"].lower(),
                                          destination=member["stripe_account_id"], transfer_group=f"disbursement:{disbursement_id}",
                                          idempotency_key=f"transfer:{disbursement_id}")
        payout = stripe.Payout.create(amount=d["amount_cents"], currency=d["currency"].lower(),
                                      stripe_account=member["stripe_account_id"], idempotency_key=f"payout:{disbursement_id}")
        await db.disbursements.update_one({"id": disbursement_id}, {"$set": {"status": "paid", "transfer_id": transfer.id,
                                          "payout_id": payout.id, "method": "stripe", "updated_at": _iso_now()}})
        await _audit(disbursement_id, "payout", user, {"transfer_id": transfer.id, "payout_id": payout.id, "status": "paid"})
        return await db.disbursements.find_one({"id": disbursement_id}, {"_id": 0})
    except Exception as e:
        logger.error(f"Payout failed: {e}")
        await db.disbursements.update_one({"id": disbursement_id}, {"$set": {"status": "failed", "failure_code": str(e)[:200], "updated_at": _iso_now()}})
        raise HTTPException(status_code=400, detail=f"Payout failed: {str(e)[:180]}")


@api_router.get("/stripe/tax/{member_id}")
async def stripe_tax(member_id: str, user: dict = Depends(get_current_user)):
    if member_id != user["id"] and ROLE_LEVEL.get(user.get("role"), 1) < 3:
        raise HTTPException(status_code=403, detail="Not authorized")
    year = datetime.now(timezone.utc).year
    items = await db.disbursements.find({"member_id": member_id, "status": "paid"}, {"_id": 0, "amount_cents": 1, "date": 1}).to_list(5000)
    this_year = [i for i in items if (i.get("date", "")[:4] == str(year))]
    gross = sum(i["amount_cents"] for i in this_year)
    return {"tax_year": year, "gross_paid_cents": gross, "transaction_count": len(this_year),
            "threshold_cents": STRIPE_1099_THRESHOLD_CENTS, "exceeds_threshold": gross >= STRIPE_1099_THRESHOLD_CENTS}


@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if secret:
        try:
            event = stripe.Webhook.construct_event(raw, sig, secret)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid webhook")
    else:
        import json
        try:
            event = json.loads(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid payload")
    eid = event.get("id")
    if eid:
        try:
            await db.ledger_events.insert_one({"stripe_event_id": eid, "event_type": event.get("type"), "received_at": _iso_now()})
        except Exception:
            return {"ok": True}
    typ = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    if typ == "account.updated":
        await db.members.update_one({"stripe_account_id": obj.get("id")}, {"$set": {
            "payouts_enabled": obj.get("payouts_enabled", False),
            "onboarding_status": "onboarded" if obj.get("payouts_enabled") else "pending"}})
    elif typ in ("payout.paid", "payout.failed", "payout.canceled"):
        st = {"payout.paid": "paid", "payout.failed": "failed", "payout.canceled": "failed"}[typ]
        upd = {"status": st, "updated_at": _iso_now()}
        if obj.get("failure_code"):
            upd["failure_code"] = obj["failure_code"]
        await db.disbursements.update_one({"payout_id": obj.get("id")}, {"$set": upd})
    elif typ == "transfer.reversed":
        await db.disbursements.update_many({"transfer_id": obj.get("id")}, {"$set": {"status": "failed", "failure_code": "transfer_reversed", "updated_at": _iso_now()}})
    return {"ok": True}
