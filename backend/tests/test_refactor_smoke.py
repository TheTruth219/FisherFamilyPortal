"""Post-refactor smoke test — verify all route modules still work after core.py split.

Covers: password login, /auth/me, logout, RBAC, content, members, directory,
disbursements CRUD + receipt PDF + statement PDF, fund/audit/categories, cron auth,
stripe graceful, files RBAC.
"""
import os
import requests
import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = "https://code-analyzer-549.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN = ("thetruth219@gmail.com", "FisherAdmin#2026")
MEMBER = ("victoria@fisherfamily.com", "Fisher#2026")
CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "").strip('"')


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def member():
    return _login(*MEMBER)


# ---------- Auth ----------
class TestAuth:
    def test_admin_login(self, admin):
        r = admin.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"].lower() == ADMIN[0].lower()
        assert r.json()["role"] == "admin"

    def test_member_login(self, member):
        r = member.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["role"] == "member"

    def test_bad_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN[0], "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_unauth_content_401(self):
        r = requests.get(f"{API}/content", timeout=10)
        assert r.status_code == 401

    def test_logout(self):
        s = _login(*MEMBER)
        r = s.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code in (200, 204)
        # session should be dead
        r2 = s.get(f"{API}/auth/me", timeout=10)
        assert r2.status_code == 401


# ---------- Members / RBAC ----------
class TestMembers:
    def test_admin_list_members(self, admin):
        r = admin.get(f"{API}/members", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) > 0

    def test_member_forbidden(self, member):
        r = member.get(f"{API}/members", timeout=10)
        assert r.status_code == 403

    def test_admin_patch_member_persists(self, admin):
        lst = admin.get(f"{API}/members", timeout=10).json()
        # pick a non-admin demo member
        target = next(m for m in lst if m["email"].endswith("@fisherfamily.com"))
        mid = target["id"]
        original_first = target.get("first_name", "")
        new_first = (original_first or "X") + "QA"
        r = admin.patch(f"{API}/members/{mid}", json={"first_name": new_first}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("first_name") == new_first
        r2 = admin.get(f"{API}/members", timeout=10)
        got = next(m for m in r2.json() if m["id"] == mid)
        assert got.get("first_name") == new_first
        admin.patch(f"{API}/members/{mid}", json={"first_name": original_first}, timeout=10)


# ---------- Content ----------
class TestContent:
    def test_get_content_authed(self, member):
        r = member.get(f"{API}/content", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_admin_put_content_noop(self, admin):
        cur = admin.get(f"{API}/content", timeout=10).json()
        r = admin.put(f"{API}/content", json={"content": cur}, timeout=15)
        assert r.status_code in (200, 204), r.text


# ---------- Files RBAC ----------
class TestFiles:
    def test_files_unauth(self):
        r = requests.get(f"{API}/files/nonexistent-id", timeout=10)
        assert r.status_code in (401, 403)

    def test_files_member_fake_id(self, member):
        r = member.get(f"{API}/files/nonexistent-id-xyz", timeout=10)
        # 403 (role gate) or 404 acceptable — must NOT be 500
        assert r.status_code in (403, 404)


# ---------- Profile + Directory ----------
class TestProfileDirectory:
    def test_patch_own_profile(self, member):
        r = member.patch(f"{API}/auth/profile", json={"phone": "555-0100"}, timeout=10)
        assert r.status_code == 200

    def test_directory_authed(self, member):
        r = member.get(f"{API}/directory", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        names = [m.get("name", "") for m in data]
        assert names == sorted(names, key=lambda s: s.lower())

    def test_profile_photo_rejects_nonimage(self, member):
        files = {"file": ("x.txt", b"hello", "text/plain")}
        r = member.post(f"{API}/auth/profile/photo", files=files, timeout=15)
        assert r.status_code in (400, 415, 422)


# ---------- Disbursements ----------
@pytest.fixture(scope="module")
def created_disbursement(admin, member):
    me = member.get(f"{API}/auth/me", timeout=10).json()
    payload = {
        "member_id": me["id"],
        "amount": 12.34,
        "date": "2026-01-15",
        "category": "General",
        "reason": "TEST refactor smoke",
        "send_email": False,
    }
    r = admin.post(f"{API}/disbursements", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    yield d
    admin.delete(f"{API}/disbursements/{d['id']}", timeout=10)


class TestDisbursements:
    def test_admin_create_disbursement(self, created_disbursement):
        assert created_disbursement.get("amount_cents") == 1234
        assert created_disbursement["id"]

    def test_summary(self, admin):
        r = admin.get(f"{API}/disbursements/summary", timeout=10)
        assert r.status_code == 200

    def test_list(self, admin, created_disbursement):
        r = admin.get(f"{API}/disbursements", timeout=10)
        assert r.status_code == 200
        assert any(d["id"] == created_disbursement["id"] for d in r.json())

    def test_patch(self, admin, created_disbursement):
        did = created_disbursement["id"]
        r = admin.patch(f"{API}/disbursements/{did}",
                        json={"reason": "TEST refactor smoke updated"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["reason"] == "TEST refactor smoke updated"

    def test_acknowledge(self, member, created_disbursement):
        did = created_disbursement["id"]
        r = member.post(f"{API}/disbursements/{did}/acknowledge", timeout=10)
        assert r.status_code in (200, 204)

    def test_receipt_pdf(self, admin, created_disbursement):
        did = created_disbursement["id"]
        r = admin.get(f"{API}/disbursements/{did}/receipt", timeout=20)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")

    def test_statement_pdf(self, member):
        me = member.get(f"{API}/auth/me", timeout=10).json()
        r = member.get(f"{API}/disbursements/statement/{me['id']}", timeout=20)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")

    def test_member_scoping(self, member):
        r = member.get(f"{API}/disbursements", timeout=10)
        assert r.status_code == 200
        me = member.get(f"{API}/auth/me", timeout=10).json()
        for d in r.json():
            assert d["member_id"] == me["id"]


# ---------- Fund / Audit / Categories ----------
class TestFundAudit:
    def test_get_fund(self, admin):
        r = admin.get(f"{API}/fund", timeout=10)
        assert r.status_code == 200

    def test_categories_list(self, admin):
        r = admin.get(f"{API}/categories", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_audit_admin(self, admin, member):
        me = member.get(f"{API}/auth/me", timeout=10).json()
        r = admin.get(f"{API}/audit/{me['id']}", timeout=10)
        assert r.status_code == 200


# ---------- Cron ----------
class TestCron:
    def test_cron_no_secret_401(self):
        r = requests.post(f"{API}/cron/meeting-reminders", timeout=10)
        assert r.status_code == 401

    def test_cron_bad_secret_401(self):
        r = requests.post(f"{API}/cron/meeting-reminders",
                          headers={"Authorization": "Bearer wrong"}, timeout=10)
        assert r.status_code == 401


# ---------- Stripe graceful ----------
class TestStripe:
    def test_stripe_onboard_graceful(self, admin):
        r = admin.post(f"{API}/stripe/connect/onboard", timeout=15)
        assert r.status_code < 500, f"stripe onboard crashed: {r.status_code} {r.text}"

    def test_stripe_status_graceful(self, admin):
        r = admin.get(f"{API}/stripe/connect/status", timeout=10)
        assert r.status_code < 500

    def test_stripe_tax(self, admin, member):
        me = member.get(f"{API}/auth/me", timeout=10).json()
        r = admin.get(f"{API}/stripe/tax/{me['id']}", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
