"""Backend tests for member profile CRUD, photo upload, and family directory."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://code-analyzer-549.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MEMBER = {"email": "victoria@fisherfamily.com", "password": "Fisher#2026"}
MEMBER2 = {"email": "james@fisherfamily.com", "password": "Fisher#2026"}
ADMIN = {"email": "thetruth219@gmail.com", "password": "FisherAdmin#2026"}


def login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def member_session():
    return login(MEMBER)


@pytest.fixture(scope="module")
def admin_session():
    return login(ADMIN)


# ---- Directory ----
class TestDirectory:
    def test_directory_requires_auth(self):
        r = requests.get(f"{API}/directory", timeout=15)
        assert r.status_code == 401

    def test_directory_member_access(self, member_session):
        r = member_session.get(f"{API}/directory", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        emails = [m["email"] for m in data]
        assert MEMBER["email"] in emails
        # sorted alphabetically by first name
        first_names = [(m.get("first_name") or "").lower() for m in data]
        assert first_names == sorted(first_names)
        # public_member fields present
        m = data[0]
        for k in ("email", "first_name", "last_name", "phone", "street", "city",
                  "state", "zip", "bio", "birthday", "family_branch", "occupation",
                  "photo_file_id", "photo_url"):
            assert k in m, f"missing field {k}"

    def test_directory_admin_access(self, admin_session):
        r = admin_session.get(f"{API}/directory", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---- Profile PATCH ----
class TestProfileUpdate:
    def test_patch_persists(self, member_session):
        payload = {
            "phone": "+1-555-0100",
            "street": "123 TEST Ln",
            "city": "Testville",
            "state": "CA",
            "zip": "90001",
            "bio": "TEST bio for pytest",
            "birthday": "1990-05-15",
            "family_branch": "Test Branch",
            "occupation": "QA Engineer",
        }
        r = member_session.patch(f"{API}/auth/profile", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k, v in payload.items():
            assert data.get(k) == v, f"{k}: expected {v}, got {data.get(k)}"

        # verify persistence via /auth/me
        r2 = member_session.get(f"{API}/auth/me", timeout=15)
        assert r2.status_code == 200
        me = r2.json()
        for k, v in payload.items():
            assert me.get(k) == v

    def test_patch_requires_auth(self):
        r = requests.patch(f"{API}/auth/profile", json={"phone": "x"}, timeout=15)
        assert r.status_code == 401

    def test_patch_only_updates_own_profile(self, member_session, admin_session):
        # admin updates their own occupation
        r = admin_session.patch(f"{API}/auth/profile", json={"occupation": "Admin TEST"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("occupation") == "Admin TEST"

        # member's occupation should not equal admin's
        r2 = member_session.get(f"{API}/auth/me", timeout=15)
        assert r2.json().get("occupation") != "Admin TEST"


# ---- Photo Upload/Remove ----
def _tiny_png_bytes():
    # 1x1 PNG
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


class TestProfilePhoto:
    def test_upload_and_serve(self, member_session):
        files = {"file": ("avatar.png", io.BytesIO(_tiny_png_bytes()), "image/png")}
        r = member_session.post(f"{API}/auth/profile/photo", files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("photo_file_id")
        assert data.get("photo_url", "").startswith("/api/files/")

        # Serve back the photo
        r2 = member_session.get(f"{BASE_URL}{data['photo_url']}", timeout=15)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/")

    def test_reject_non_image(self, member_session):
        files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
        r = member_session.post(f"{API}/auth/profile/photo", files=files, timeout=15)
        assert r.status_code == 400

    def test_remove_photo(self, member_session):
        # ensure a photo exists
        files = {"file": ("avatar.png", io.BytesIO(_tiny_png_bytes()), "image/png")}
        member_session.post(f"{API}/auth/profile/photo", files=files, timeout=30)

        r = member_session.delete(f"{API}/auth/profile/photo", timeout=15)
        assert r.status_code == 200
        assert r.json().get("photo_file_id") in (None, "")

    def test_upload_requires_auth(self):
        files = {"file": ("avatar.png", io.BytesIO(_tiny_png_bytes()), "image/png")}
        r = requests.post(f"{API}/auth/profile/photo", files=files, timeout=15)
        assert r.status_code == 401
