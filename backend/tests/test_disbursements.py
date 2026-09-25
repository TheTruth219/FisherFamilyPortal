"""Backend tests for Admin Disbursements + Statements + Timezone + Stripe (Phase 0/1/2).

Uses password login for the three seeded users:
  admin: thetruth219@gmail.com / FisherAdmin#2026
  member: victoria@fisherfamily.com / Fisher#2026
  business_member: james@fisherfamily.com / Fisher#2026
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN = ("thetruth219@gmail.com", "FisherAdmin#2026")
MEMBER = ("victoria@fisherfamily.com", "Fisher#2026")
BIZ = ("james@fisherfamily.com", "Fisher#2026")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def member_s():
    return _login(*MEMBER)


@pytest.fixture(scope="module")
def biz_s():
    return _login(*BIZ)


@pytest.fixture(scope="module")
def victoria_id():
    m = _db.members.find_one({"email": MEMBER[0]})
    assert m
    return m["id"]


# -------- Auth / login --------
class TestLogin:
    def test_admin_password_login(self):
        s = _login(*ADMIN)
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        assert me["email"] == ADMIN[0]
        assert me["role"] == "admin"
        assert "timezone" in me
        assert "onboarding_status" in me

    def test_member_login(self):
        s = _login(*MEMBER)
        assert s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()["role"] == "member"

    def test_biz_login(self):
        s = _login(*BIZ)
        assert s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()["role"] == "business_member"

    def test_bad_password_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN[0], "password": "wrong"}, timeout=15)
        assert r.status_code in (401, 429)


# -------- Fund --------
class TestFund:
    def test_admin_can_read_fund(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/fund", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "total_funded_cents" in d
        assert "remaining_cents" in d
        # dispersed field may be named total_dispersed_cents or dispersed_cents
        assert any(k in d for k in ("total_dispersed_cents", "dispersed_cents"))

    def test_member_cannot_read_fund(self, member_s):
        r = member_s.get(f"{BASE_URL}/api/fund", timeout=15)
        assert r.status_code == 403

    def test_biz_can_read_fund(self, biz_s):
        # business_member is staff → allowed
        r = biz_s.get(f"{BASE_URL}/api/fund", timeout=15)
        assert r.status_code == 200


# -------- Categories --------
class TestCategories:
    def test_list_categories(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/categories", timeout=15)
        assert r.status_code == 200
        cats = r.json()
        assert isinstance(cats, list)
        assert len(cats) > 0


# -------- Disbursements list / summary / RBAC --------
class TestDisbursementsList:
    def test_admin_sees_all(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/disbursements", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        for it in items:
            assert "_id" not in it
            for k in ("id", "member_id", "amount_cents", "status", "date"):
                assert k in it

    def test_member_only_sees_own(self, member_s, victoria_id):
        r = member_s.get(f"{BASE_URL}/api/disbursements", timeout=15)
        assert r.status_code == 200
        items = r.json()
        for it in items:
            assert it["member_id"] == victoria_id

    def test_biz_sees_all(self, biz_s):
        r = biz_s.get(f"{BASE_URL}/api/disbursements", timeout=15)
        assert r.status_code == 200

    def test_filter_by_status(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/disbursements?status=recorded", timeout=15)
        assert r.status_code == 200
        for it in r.json():
            assert it["status"] == "recorded"

    def test_filter_by_member(self, admin_s, victoria_id):
        r = admin_s.get(f"{BASE_URL}/api/disbursements?member_id={victoria_id}", timeout=15)
        assert r.status_code == 200
        for it in r.json():
            assert it["member_id"] == victoria_id

    def test_filter_by_date(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/disbursements?date_from=2000-01-01&date_to=2100-01-01", timeout=15)
        assert r.status_code == 200

    def test_summary(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/disbursements/summary", timeout=15)
        assert r.status_code == 200
        s = r.json()
        for k in ("total_cents", "count", "by_status", "per_member"):
            assert k in s


# -------- Create / update / audit / receipt / statement --------
class TestDisbursementCRUD:
    created_ids = []

    @classmethod
    def teardown_class(cls):
        for did in cls.created_ids:
            _db.disbursements.delete_one({"id": did})
            _db.audit_log.delete_many({"disbursement_id": did})

    def test_member_cannot_create(self, member_s, victoria_id):
        r = member_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": victoria_id, "amount": 10, "date": "2026-01-15",
            "category": "Reunion Assistance", "reason": "test", "method": "ach",
            "send_email": False
        }, timeout=15)
        assert r.status_code == 403

    def test_biz_cannot_create(self, biz_s, victoria_id):
        r = biz_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": victoria_id, "amount": 10, "date": "2026-01-15",
            "category": "Reunion Assistance", "reason": "test", "method": "ach",
            "send_email": False
        }, timeout=15)
        assert r.status_code == 403

    def test_admin_create_and_persist(self, admin_s, victoria_id):
        payload = {"member_id": victoria_id, "amount": 123.45, "currency": "USD",
                   "date": "2026-01-15", "category": "TEST_Category",
                   "reason": "TEST_reason", "method": "ach", "notes": "TEST",
                   "send_email": False}
        r = admin_s.post(f"{BASE_URL}/api/disbursements", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["amount_cents"] == 12345
        assert d["status"] == "recorded"
        assert d["member_id"] == victoria_id
        assert d["category"] == "TEST_Category"
        assert "_id" not in d
        self.__class__.created_ids.append(d["id"])

        # GET verifies persistence
        got = admin_s.get(f"{BASE_URL}/api/disbursements", timeout=15).json()
        assert any(x["id"] == d["id"] for x in got)

        # custom category was added
        cats = admin_s.get(f"{BASE_URL}/api/categories", timeout=15).json()
        assert "TEST_Category" in cats

    def test_admin_update_amount_and_status(self, admin_s, victoria_id):
        if not self.__class__.created_ids:
            pytest.skip("no created disbursement")
        did = self.__class__.created_ids[0]
        r = admin_s.patch(f"{BASE_URL}/api/disbursements/{did}",
                          json={"amount": 200.00, "status": "paid"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["amount_cents"] == 20000
        assert d["status"] == "paid"

    def test_audit_log_has_create_and_edit(self, admin_s):
        if not self.__class__.created_ids:
            pytest.skip("no created disbursement")
        did = self.__class__.created_ids[0]
        r = admin_s.get(f"{BASE_URL}/api/audit/{did}", timeout=15)
        assert r.status_code == 200
        entries = r.json()
        actions = {e["action"] for e in entries}
        assert "create" in actions
        assert "edit" in actions
        for e in entries:
            assert "_id" not in e

    def test_member_cannot_view_audit(self, member_s):
        if not self.__class__.created_ids:
            pytest.skip()
        did = self.__class__.created_ids[0]
        r = member_s.get(f"{BASE_URL}/api/audit/{did}", timeout=15)
        assert r.status_code == 403

    def test_receipt_pdf(self, admin_s):
        if not self.__class__.created_ids:
            pytest.skip()
        did = self.__class__.created_ids[0]
        r = admin_s.get(f"{BASE_URL}/api/disbursements/{did}/receipt", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_invalid_amount_422(self, admin_s, victoria_id):
        r = admin_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": victoria_id, "amount": 0, "date": "2026-01-15",
            "category": "x", "reason": "x", "method": "ach", "send_email": False
        }, timeout=15)
        assert r.status_code == 422

    def test_invalid_method_422(self, admin_s, victoria_id):
        r = admin_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": victoria_id, "amount": 5, "date": "2026-01-15",
            "category": "x", "reason": "x", "method": "bogus", "send_email": False
        }, timeout=15)
        assert r.status_code == 422

    def test_unknown_member_404(self, admin_s):
        r = admin_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": str(uuid.uuid4()), "amount": 5, "date": "2026-01-15",
            "category": "x", "reason": "x", "method": "ach", "send_email": False
        }, timeout=15)
        assert r.status_code == 404


# -------- Member acknowledge + receipt scope --------
class TestMemberScoped:
    def test_member_can_acknowledge_own(self, admin_s, member_s, victoria_id):
        # admin creates a disbursement for victoria
        r = admin_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": victoria_id, "amount": 20, "date": "2026-01-15",
            "category": "TEST_ack", "reason": "ack", "method": "ach", "send_email": False
        }, timeout=20)
        did = r.json()["id"]
        try:
            r2 = member_s.post(f"{BASE_URL}/api/disbursements/{did}/acknowledge", timeout=15)
            assert r2.status_code == 200
            assert r2.json()["acknowledged"] is True

            # member can fetch her own receipt PDF
            r3 = member_s.get(f"{BASE_URL}/api/disbursements/{did}/receipt", timeout=20)
            assert r3.status_code == 200
            assert r3.headers.get("content-type", "").startswith("application/pdf")

            # member statement for herself
            r4 = member_s.get(f"{BASE_URL}/api/disbursements/statement/{victoria_id}", timeout=20)
            assert r4.status_code == 200
            assert r4.headers.get("content-type", "").startswith("application/pdf")
        finally:
            _db.disbursements.delete_one({"id": did})
            _db.audit_log.delete_many({"disbursement_id": did})

    def test_member_cannot_acknowledge_other(self, admin_s, member_s):
        # find a disbursement not belonging to victoria
        items = admin_s.get(f"{BASE_URL}/api/disbursements", timeout=15).json()
        vid = _db.members.find_one({"email": MEMBER[0]})["id"]
        others = [x for x in items if x["member_id"] != vid]
        if not others:
            pytest.skip("no non-victoria disbursements seeded")
        did = others[0]["id"]
        r = member_s.post(f"{BASE_URL}/api/disbursements/{did}/acknowledge", timeout=15)
        assert r.status_code == 403

    def test_member_cannot_view_other_statement(self, member_s, admin_s):
        # get any other member id
        vid = _db.members.find_one({"email": MEMBER[0]})["id"]
        other = _db.members.find_one({"id": {"$ne": vid}, "email": {"$ne": MEMBER[0]}})
        if not other:
            pytest.skip()
        r = member_s.get(f"{BASE_URL}/api/disbursements/statement/{other['id']}", timeout=15)
        assert r.status_code == 403


# -------- Timezone --------
class TestTimezone:
    def test_patch_timezone_valid(self, member_s):
        r = member_s.patch(f"{BASE_URL}/api/auth/timezone",
                           json={"timezone": "America/New_York", "confirm": True}, timeout=15)
        assert r.status_code == 200
        me = member_s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        assert me["timezone"] == "America/New_York"

    def test_patch_timezone_invalid_422(self, member_s):
        r = member_s.patch(f"{BASE_URL}/api/auth/timezone",
                           json={"timezone": "Not/A_Zone"}, timeout=15)
        assert r.status_code == 422

    def test_timezone_requires_auth(self):
        r = requests.patch(f"{BASE_URL}/api/auth/timezone",
                           json={"timezone": "UTC"}, timeout=15)
        assert r.status_code == 401


# -------- Stripe --------
class TestStripe:
    def test_status_endpoint(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/stripe/connect/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "onboarding_status" in d
        assert "payouts_enabled" in d

    def test_onboard_endpoint_handles_gracefully(self, admin_s):
        r = admin_s.post(f"{BASE_URL}/api/stripe/connect/onboard", timeout=20)
        # Expected: 400 JSON telling user to enable Connect in Stripe Dashboard, OR 200 if enabled
        assert r.status_code in (200, 400), r.text
        # Must be JSON (not Cloudflare HTML 502)
        ctype = r.headers.get("content-type", "")
        assert "application/json" in ctype, f"expected JSON, got {ctype}: {r.text[:200]}"
        body = r.json()
        if r.status_code == 400:
            assert "detail" in body
            assert "connect" in body["detail"].lower()

    def test_onboard_status_not_connected(self, admin_s):
        r = admin_s.get(f"{BASE_URL}/api/stripe/connect/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "onboarding_status" in d

    def test_tax_self(self, member_s, victoria_id):
        r = member_s.get(f"{BASE_URL}/api/stripe/tax/{victoria_id}", timeout=15)
        assert r.status_code == 200


# -------- Email resend guardrail --------
class TestResendEmail:
    """
    Demo members have @fisherfamily.com placeholder emails which the Resend email
    provider rejects as undeliverable → 400. To verify a real success path, we send
    to the admin's real deliverable address (thetruth219@gmail.com).
    """
    _admin_did = None

    @classmethod
    def teardown_class(cls):
        if cls._admin_did:
            _db.disbursements.delete_one({"id": cls._admin_did})
            _db.audit_log.delete_many({"disbursement_id": cls._admin_did})

    def test_resend_receipt_demo_member_400_expected(self, admin_s):
        # Demo victoria — undeliverable placeholder address → 400
        items = admin_s.get(f"{BASE_URL}/api/disbursements", timeout=15).json()
        demo = [i for i in items if i.get("member_email", "").endswith("@fisherfamily.com")]
        if not demo:
            pytest.skip("no demo member disbursement")
        did = demo[0]["id"]
        r = admin_s.post(f"{BASE_URL}/api/disbursements/{did}/send-email", timeout=30)
        # placeholder is rejected as undeliverable → 400 with JSON detail
        assert r.status_code in (200, 400), r.text
        if r.status_code == 400:
            assert "detail" in r.json()

    def test_receipt_email_to_admin_success(self, admin_s):
        # Admin's real deliverable email — should succeed with attachment
        me = admin_s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        admin_id = me["id"]
        # Create disbursement for the admin (real deliverable address)
        c = admin_s.post(f"{BASE_URL}/api/disbursements", json={
            "member_id": admin_id, "amount": 1.00, "date": "2026-01-15",
            "category": "TEST_email", "reason": "TEST_admin_email_delivery",
            "method": "ach", "notes": "TEST_attach", "send_email": False
        }, timeout=20)
        assert c.status_code == 200, c.text
        did = c.json()["id"]
        self.__class__._admin_did = did

        r = admin_s.post(f"{BASE_URL}/api/disbursements/{did}/send-email", timeout=45)
        assert r.status_code == 200, f"expected 200 to deliverable admin email, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("to") == me["email"]

    def test_statement_email_to_admin_success(self, admin_s):
        me = admin_s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        r = admin_s.post(f"{BASE_URL}/api/disbursements/statement/{me['id']}/send-email", timeout=45)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("ok") is True

