"""Backend API tests for Fisher Family Portal."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fisher-portal-hub.preview.emergentagent.com").rstrip("/")
FAMILY_PW = "fisher2026"
ADMIN_EMAIL = "admin@fisherfamily.portal"
ADMIN_PW = "FisherAdmin2026!"


@pytest.fixture
def member_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/member-login", json={"password": FAMILY_PW}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    return s


# ---------- Auth ----------
class TestAuth:
    def test_member_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/member-login", json={"password": FAMILY_PW}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("role") == "member"
        assert "access_token" in r.cookies

    def test_member_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/member-login", json={"password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_admin_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("role") == "admin"
        assert data.get("email") == ADMIN_EMAIL

    def test_admin_login_wrong(self):
        r = requests.post(f"{BASE_URL}/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": "bad"}, timeout=15)
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_authenticated(self, member_session):
        r = member_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json().get("role") == "member"

    def test_logout(self, member_session):
        r = member_session.post(f"{BASE_URL}/api/auth/logout", timeout=15)
        assert r.status_code == 200


# ---------- Content ----------
class TestContent:
    def test_get_content_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 401

    def test_get_content_as_member(self, member_session):
        r = member_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for key in ["alerts", "reunion", "familyBusiness", "payments", "meetings", "documents", "contacts"]:
            assert key in data, f"Missing content key: {key}"
        assert isinstance(data["alerts"], list) and len(data["alerts"]) >= 1

    def test_member_cannot_update_content(self, member_session):
        r = member_session.put(f"{BASE_URL}/api/content", json={"content": {}}, timeout=15)
        assert r.status_code == 403

    def test_admin_update_content_persists(self, admin_session):
        # Get current
        r = admin_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200
        content = r.json()
        original_year = content["reunion"].get("year", "")
        test_year = "TEST_2027"
        content["reunion"]["year"] = test_year
        # PUT
        rp = admin_session.put(f"{BASE_URL}/api/content", json={"content": content}, timeout=15)
        assert rp.status_code == 200
        # Verify persistence
        rv = admin_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert rv.json()["reunion"]["year"] == test_year
        # Restore
        content["reunion"]["year"] = original_year
        admin_session.put(f"{BASE_URL}/api/content", json={"content": content}, timeout=15)


# ---------- Contact ----------
class TestContact:
    def test_contact_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/contact", json={
            "name": "T", "email": "t@t.com", "topic": "x", "message": "y"
        }, timeout=15)
        assert r.status_code == 401

    def test_contact_submit(self, member_session):
        r = member_session.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_User", "email": "test@example.com", "phone": "555",
            "topic": "Reunion", "message": "Hello"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert "id" in r.json()
