"""Backend API tests for Fisher Family Portal — magic-link auth iteration."""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for tests run with only backend .env; try the frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"].lower()
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]


def _mint_token_for(email: str) -> str:
    """Insert a fresh magic-link token for the given member's email and return the raw token."""
    member = _db.members.find_one({"email": email.lower()})
    assert member, f"No member with email {email}"
    raw = secrets.token_urlsafe(32)
    _db.magic_link_tokens.insert_one({
        "token_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "user_id": member["id"],
        "email": member["email"],
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=20),
        "used": False,
    })
    return raw


def _login_session(email: str) -> requests.Session:
    s = requests.Session()
    raw = _mint_token_for(email)
    r = s.post(f"{BASE_URL}/api/auth/verify", json={"token": raw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def admin_session():
    return _login_session(ADMIN_EMAIL)


# ---------- request-link ----------
class TestRequestLink:
    GENERIC = "If that email belongs to an authorized family member, a sign-in link has been sent."

    def test_authorized_email_returns_generic(self):
        r = requests.post(f"{BASE_URL}/api/auth/request-link",
                          json={"email": ADMIN_EMAIL}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("message") == self.GENERIC

    def test_unauthorized_email_returns_same_generic(self):
        r = requests.post(f"{BASE_URL}/api/auth/request-link",
                          json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("message") == self.GENERIC

    def test_invalid_email_format_422(self):
        r = requests.post(f"{BASE_URL}/api/auth/request-link",
                          json={"email": "not-an-email"}, timeout=15)
        assert r.status_code == 422


# ---------- verify + me + logout ----------
class TestVerify:
    def test_verify_sets_cookie_and_returns_member(self):
        s = requests.Session()
        raw = _mint_token_for(ADMIN_EMAIL)
        r = s.post(f"{BASE_URL}/api/auth/verify", json={"token": raw}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "access_token" in s.cookies

        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert me.status_code == 200
        assert me.json()["email"] == ADMIN_EMAIL

    def test_token_is_single_use(self):
        raw = _mint_token_for(ADMIN_EMAIL)
        r1 = requests.post(f"{BASE_URL}/api/auth/verify", json={"token": raw}, timeout=15)
        assert r1.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/auth/verify", json={"token": raw}, timeout=15)
        assert r2.status_code == 400
        assert "invalid or has expired" in r2.json().get("detail", "").lower()

    def test_garbage_token_400(self):
        r = requests.post(f"{BASE_URL}/api/auth/verify", json={"token": "garbage_" + uuid.uuid4().hex}, timeout=15)
        assert r.status_code == 400

    def test_me_without_cookie_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401

    def test_logout_clears_cookie(self):
        s = _login_session(ADMIN_EMAIL)
        r = s.post(f"{BASE_URL}/api/auth/logout", timeout=15)
        assert r.status_code == 200


# ---------- protected endpoints ----------
class TestProtected:
    def test_content_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/content", timeout=15).status_code == 401

    def test_members_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/members", timeout=15).status_code == 401

    def test_content_as_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200
        assert "alerts" in r.json()


# ---------- Member management ----------
class TestMemberAdmin:
    _created_ids = []

    @classmethod
    def teardown_class(cls):
        for mid in cls._created_ids:
            _db.members.delete_one({"id": mid})

    def test_list_members_as_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/members", timeout=15)
        assert r.status_code == 200
        emails = [m["email"] for m in r.json()]
        assert ADMIN_EMAIL in emails

    def test_create_member_and_verify_persistence(self, admin_session):
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        r = admin_session.post(f"{BASE_URL}/api/members", json={
            "email": email, "first_name": "TEST", "last_name": "User", "role": "member"
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        created = r.json()
        assert created["email"] == email
        assert created["role"] == "member"
        assert created["is_active"] is True
        self._created_ids.append(created["id"])

        # verify persistence via GET list
        r2 = admin_session.get(f"{BASE_URL}/api/members", timeout=15)
        assert any(m["email"] == email for m in r2.json())

    def test_duplicate_email_409(self, admin_session):
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        r1 = admin_session.post(f"{BASE_URL}/api/members", json={
            "email": email, "first_name": "A", "last_name": "B", "role": "member"
        }, timeout=15)
        assert r1.status_code in (200, 201)
        self._created_ids.append(r1.json()["id"])
        r2 = admin_session.post(f"{BASE_URL}/api/members", json={
            "email": email, "first_name": "A", "last_name": "B", "role": "member"
        }, timeout=15)
        assert r2.status_code == 409

    def test_patch_role_and_deactivate(self, admin_session):
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        c = admin_session.post(f"{BASE_URL}/api/members", json={
            "email": email, "first_name": "P", "last_name": "Q", "role": "member"
        }, timeout=15)
        mid = c.json()["id"]
        self._created_ids.append(mid)

        r = admin_session.patch(f"{BASE_URL}/api/members/{mid}",
                                json={"role": "committee_member"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "committee_member"

        r2 = admin_session.patch(f"{BASE_URL}/api/members/{mid}",
                                 json={"is_active": False}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["is_active"] is False

    def test_resend_invite(self, admin_session):
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        c = admin_session.post(f"{BASE_URL}/api/members", json={
            "email": email, "first_name": "R", "last_name": "S", "role": "member"
        }, timeout=15)
        mid = c.json()["id"]
        self._created_ids.append(mid)
        r = admin_session.post(f"{BASE_URL}/api/members/{mid}/resend-invite", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_admin_cannot_deactivate_self(self, admin_session):
        me = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        r = admin_session.patch(f"{BASE_URL}/api/members/{me['id']}",
                                json={"is_active": False}, timeout=15)
        assert r.status_code == 400


# ---------- non-admin authorization ----------
class TestNonAdminAuthz:
    _mid = None

    @classmethod
    def setup_class(cls):
        # Create a member directly in DB to test authorization without needing admin login here
        email = f"test_member_{uuid.uuid4().hex[:8]}@example.com"
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()), "email": email, "first_name": "M", "last_name": "R",
            "role": "member", "is_active": True, "token_version": 0,
            "created_at": now, "updated_at": now,
        }
        _db.members.insert_one(member)
        cls._mid = member["id"]
        cls._email = email

    @classmethod
    def teardown_class(cls):
        if cls._mid:
            _db.members.delete_one({"id": cls._mid})

    @pytest.fixture
    def member_session(self):
        return _login_session(self._email)

    def test_member_cannot_list_members(self, member_session):
        r = member_session.get(f"{BASE_URL}/api/members", timeout=15)
        assert r.status_code == 403

    def test_member_cannot_create_member(self, member_session):
        r = member_session.post(f"{BASE_URL}/api/members", json={
            "email": "x@x.com", "first_name": "x", "last_name": "y", "role": "member"
        }, timeout=15)
        assert r.status_code == 403

    def test_member_cannot_put_content(self, member_session):
        r = member_session.put(f"{BASE_URL}/api/content", json={"content": {}}, timeout=15)
        assert r.status_code == 403

    def test_member_can_get_content(self, member_session):
        r = member_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200

    def test_deactivation_revokes_existing_session(self, member_session):
        # Confirm session works
        r0 = member_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r0.status_code == 200
        # Admin deactivates this member (bumps token_version)
        admin = _login_session(ADMIN_EMAIL)
        r1 = admin.patch(f"{BASE_URL}/api/members/{self._mid}",
                         json={"is_active": False}, timeout=15)
        assert r1.status_code == 200
        # Old session should be rejected
        r2 = member_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r2.status_code in (401, 403)
        # Reactivate for cleanup safety
        admin.patch(f"{BASE_URL}/api/members/{self._mid}", json={"is_active": True}, timeout=15)


# ---------- contact ----------
class TestContact:
    def test_contact_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/contact", json={
            "name": "T", "email": "t@t.com", "topic": "x", "message": "y"
        }, timeout=15)
        assert r.status_code == 401

    def test_contact_submit_as_admin(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_User", "email": "test@example.com", "phone": "555",
            "topic": "Reunion", "message": "Hello"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- help requests inbox (admin) ----------
class TestHelpRequests:
    _created_help_ids = []
    _member_id = None
    _member_email = None

    @classmethod
    def setup_class(cls):
        email = f"test_helpmember_{uuid.uuid4().hex[:8]}@example.com"
        now = datetime.now(timezone.utc).isoformat()
        m = {"id": str(uuid.uuid4()), "email": email, "first_name": "H", "last_name": "M",
             "role": "member", "is_active": True, "token_version": 0,
             "created_at": now, "updated_at": now}
        _db.members.insert_one(m)
        cls._member_id = m["id"]
        cls._member_email = email

    @classmethod
    def teardown_class(cls):
        for hid in cls._created_help_ids:
            _db.contact_messages.delete_one({"id": hid})
        if cls._member_id:
            _db.members.delete_one({"id": cls._member_id})

    def test_help_requests_requires_admin(self):
        # unauth
        r = requests.get(f"{BASE_URL}/api/help-requests", timeout=15)
        assert r.status_code == 401
        # authenticated member
        member_s = _login_session(self._member_email)
        r2 = member_s.get(f"{BASE_URL}/api/help-requests", timeout=15)
        assert r2.status_code == 403

    def test_member_submits_contact_appears_in_inbox_and_no_mongo_id(self, admin_session):
        member_s = _login_session(self._member_email)
        topic = f"TEST_help_{uuid.uuid4().hex[:8]}"
        r = member_s.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_Member", "email": self._member_email, "phone": "",
            "topic": topic, "message": "Please help with test"
        }, timeout=15)
        assert r.status_code == 200
        hid = r.json()["id"]
        self._created_help_ids.append(hid)

        # Admin fetches inbox
        r2 = admin_session.get(f"{BASE_URL}/api/help-requests", timeout=15)
        assert r2.status_code == 200
        items = r2.json()
        assert isinstance(items, list)
        # newest first: our item should be at or near top
        match = next((it for it in items if it.get("id") == hid), None)
        assert match is not None
        assert match["topic"] == topic
        assert match.get("status") == "new"
        # NO Mongo _id leaked
        for it in items:
            assert "_id" not in it

    def test_status_workflow_patch(self, admin_session):
        # create one help request via contact
        member_s = _login_session(self._member_email)
        r = member_s.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_Member", "email": self._member_email,
            "topic": "TEST_status", "message": "workflow"
        }, timeout=15)
        hid = r.json()["id"]
        self._created_help_ids.append(hid)

        for st in ("in_progress", "resolved", "new"):
            p = admin_session.patch(f"{BASE_URL}/api/help-requests/{hid}",
                                    json={"status": st}, timeout=15)
            assert p.status_code == 200
        # persisted
        items = admin_session.get(f"{BASE_URL}/api/help-requests", timeout=15).json()
        match = next(it for it in items if it["id"] == hid)
        assert match["status"] == "new"

    def test_patch_invalid_status_422(self, admin_session):
        # create one
        member_s = _login_session(self._member_email)
        r = member_s.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST", "email": self._member_email,
            "topic": "TEST_invalid", "message": "x"
        }, timeout=15)
        hid = r.json()["id"]
        self._created_help_ids.append(hid)
        p = admin_session.patch(f"{BASE_URL}/api/help-requests/{hid}",
                                json={"status": "bogus"}, timeout=15)
        assert p.status_code == 422

    def test_patch_missing_id_404(self, admin_session):
        p = admin_session.patch(f"{BASE_URL}/api/help-requests/{uuid.uuid4()}",
                                json={"status": "new"}, timeout=15)
        assert p.status_code == 404

    def test_member_cannot_patch_help_request(self, admin_session):
        # create one as admin submission
        r = admin_session.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST", "email": "t@t.com",
            "topic": "TEST_403", "message": "x"
        }, timeout=15)
        hid = r.json()["id"]
        self._created_help_ids.append(hid)
        member_s = _login_session(self._member_email)
        p = member_s.patch(f"{BASE_URL}/api/help-requests/{hid}",
                           json={"status": "resolved"}, timeout=15)
        assert p.status_code == 403


# ---------- role-based file access ----------
class TestFileAccess:
    _member_ids = []
    _file_ids = []

    @classmethod
    def setup_class(cls):
        cls.members = {}
        now = datetime.now(timezone.utc).isoformat()
        for role in ("member", "business_member", "committee_member"):
            email = f"test_role_{role}_{uuid.uuid4().hex[:6]}@example.com"
            m = {"id": str(uuid.uuid4()), "email": email, "first_name": role, "last_name": "T",
                 "role": role, "is_active": True, "token_version": 0,
                 "created_at": now, "updated_at": now}
            _db.members.insert_one(m)
            cls._member_ids.append(m["id"])
            cls.members[role] = email

    @classmethod
    def teardown_class(cls):
        for mid in cls._member_ids:
            _db.members.delete_one({"id": mid})
        # cleanup files we injected
        for fid in cls._file_ids:
            _db.files.delete_one({"id": fid})
            _db.settings.update_one(
                {"_id": "portal_content"},
                {"$pull": {"content.documents": {"link": {"$regex": fid}}}}
            )

    def _inject_file_with_access(self, access_level: str) -> str:
        """Insert a fake file record and add a document referencing it with given access."""
        fid = str(uuid.uuid4())
        _db.files.insert_one({
            "id": fid, "storage_path": f"nonexistent/{fid}.bin",
            "original_filename": "test.bin", "content_type": "application/octet-stream",
            "size": 1, "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # add doc referencing this file to content
        doc = {"id": str(uuid.uuid4()), "title": f"TEST_{access_level}",
               "description": "test", "date": "", "updated": "",
               "access": access_level, "link": f"/api/files/{fid}", "category": "TEST"}
        _db.settings.update_one(
            {"_id": "portal_content"},
            {"$push": {"content.documents": doc}}
        )
        self._file_ids.append(fid)
        return fid

    def test_role_gating_on_file_download(self, admin_session):
        # Create files at each access level
        f_all = self._inject_file_with_access("All Members")
        f_biz = self._inject_file_with_access("Business Members")
        f_com = self._inject_file_with_access("Committee Members")
        f_res = self._inject_file_with_access("Restricted")

        sessions = {role: _login_session(email) for role, email in self.members.items()}
        sessions["admin"] = admin_session

        # Expected: role level >= required
        # member=1, business_member=2, committee_member=3, admin=4
        # All=1, Business=2, Committee=3, Restricted=4
        cases = [
            ("member", f_all, "allow"),
            ("member", f_biz, "deny"),
            ("member", f_res, "deny"),
            ("business_member", f_biz, "allow"),
            ("business_member", f_res, "deny"),
            ("committee_member", f_com, "allow"),
            ("committee_member", f_res, "deny"),
            ("admin", f_res, "allow"),
            ("admin", f_all, "allow"),
        ]
        for role, fid, expect in cases:
            r = sessions[role].get(f"{BASE_URL}/api/files/{fid}", timeout=15, allow_redirects=False)
            if expect == "deny":
                assert r.status_code == 403, f"role={role} fid={fid} expected 403 got {r.status_code}"
            else:
                # allow path: file record exists but storage_path is fake, so we expect 400 (storage download failed) NOT 403/401/404
                assert r.status_code in (200, 400), f"role={role} fid={fid} expected allow but got {r.status_code}: {r.text[:200]}"

    def test_file_download_requires_auth(self):
        fid = self._inject_file_with_access("All Members")
        r = requests.get(f"{BASE_URL}/api/files/{fid}", timeout=15)
        assert r.status_code == 401
