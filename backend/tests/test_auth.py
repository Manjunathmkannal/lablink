"""
Unit + integration tests for authentication.
Tests: registration, login, JWT, refresh-token rotation,
       logout revocation, role guards, and password safety.
Uses mongomock – no real MongoDB required.
"""
import pytest
# client and mock_db fixtures come from conftest.py


# ── Model validation tests ─────────────────────────────────────────────────────

class TestUserModelValidation:
    def test_valid_payload_returns_no_errors(self):
        from app.models.user import validate_user_payload
        payload = {
            "name": "Alice",
            "email": "alice@example.com",
            "password": "Secret123",
            "role": "student",
        }
        assert validate_user_payload(payload) == []

    def test_missing_name(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload({"email": "a@b.com", "password": "Secret123"})
        assert any("name" in e for e in errors)

    def test_short_name(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload({"name": "A", "email": "a@b.com", "password": "Secret123"})
        assert any("name" in e for e in errors)

    def test_invalid_email(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload({"name": "Alice", "email": "not-an-email", "password": "Secret123"})
        assert any("email" in e for e in errors)

    def test_missing_email(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload({"name": "Alice", "password": "Secret123"})
        assert any("email" in e for e in errors)

    def test_short_password(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload({"name": "Alice", "email": "a@b.com", "password": "short"})
        assert any("password" in e for e in errors)

    def test_invalid_role(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload(
            {"name": "Alice", "email": "a@b.com", "password": "Secret123", "role": "superadmin"}
        )
        assert any("role" in e for e in errors)

    def test_no_password_required_when_flagged(self):
        from app.models.user import validate_user_payload
        errors = validate_user_payload(
            {"name": "Alice", "email": "a@b.com"},
            require_password=False,
        )
        assert errors == []


# ── Registration endpoint tests ────────────────────────────────────────────────

class TestRegister:
    def test_successful_registration(self, client):
        c, db = client
        resp = c.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@lablink.edu",
                "password": "Password123",
                "role": "student",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@lablink.edu"
        assert "password_hash" not in data["user"]
        assert "refresh_token" in resp.headers.get("Set-Cookie", "")

    def test_duplicate_email_rejected(self, client):
        c, db = client
        payload = {
            "name": "Test User",
            "email": "dup@lablink.edu",
            "password": "Password123",
            "role": "student",
        }
        c.post("/api/auth/register", json=payload)
        resp2 = c.post("/api/auth/register", json=payload)
        assert resp2.status_code == 400
        assert "already registered" in resp2.get_json().get("errors", [""])[0]

    def test_missing_fields_rejected(self, client):
        c, _ = client
        resp = c.post("/api/auth/register", json={"name": "No Email"})
        assert resp.status_code == 400
        errors = resp.get_json()["errors"]
        assert any("email" in e for e in errors)
        assert any("password" in e for e in errors)

    def test_password_not_in_response(self, client):
        c, _ = client
        resp = c.post(
            "/api/auth/register",
            json={"name": "Safe", "email": "safe@lablink.edu", "password": "Safe1234", "role": "student"},
        )
        body = resp.get_json()
        assert "password_hash" not in str(body)
        assert "password" not in str(body)


# ── Login endpoint tests ───────────────────────────────────────────────────────

class TestLogin:
    def _register(self, c, email="login_user@lablink.edu", password="Login@1234"):
        c.post(
            "/api/auth/register",
            json={"name": "Login User", "email": email, "password": password, "role": "student"},
        )

    def test_login_success(self, client):
        c, _ = client
        self._register(c)
        resp = c.post("/api/auth/login", json={"email": "login_user@lablink.edu", "password": "Login@1234"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in resp.headers.get("Set-Cookie", "")

    def test_wrong_password(self, client):
        c, _ = client
        self._register(c, email="wrongpw@lablink.edu")
        resp = c.post("/api/auth/login", json={"email": "wrongpw@lablink.edu", "password": "WrongPW999"})
        assert resp.status_code == 401

    def test_nonexistent_user_same_message(self, client):
        """Same error message for wrong user vs wrong password (no user enumeration)."""
        c, _ = client
        resp = c.post("/api/auth/login", json={"email": "ghost@lablink.edu", "password": "Ghost1234"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Invalid email or password"

    def test_missing_credentials(self, client):
        c, _ = client
        resp = c.post("/api/auth/login", json={})
        assert resp.status_code == 400


# ── JWT / protected endpoint tests ────────────────────────────────────────────

class TestJWT:
    def _register_and_login(self, c, email="jwt_test@lablink.edu"):
        c.post(
            "/api/auth/register",
            json={"name": "JWT User", "email": email, "password": "JWT@12345", "role": "student"},
        )
        resp = c.post("/api/auth/login", json={"email": email, "password": "JWT@12345"})
        return resp.get_json()["access_token"]

    def test_me_requires_token(self, client):
        c, _ = client
        resp = c.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client):
        c, _ = client
        token = self._register_and_login(c)
        resp = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json()["email"] == "jwt_test@lablink.edu"

    def test_invalid_token_rejected(self, client):
        c, _ = client
        resp = c.get("/api/auth/me", headers={"Authorization": "Bearer totallyinvalid"})
        assert resp.status_code == 401

    def test_no_bearer_prefix_rejected(self, client):
        c, _ = client
        resp = c.get("/api/auth/me", headers={"Authorization": "sometoken"})
        assert resp.status_code == 401


# ── Refresh token rotation tests ───────────────────────────────────────────────

class TestRefreshToken:
    def _register_and_login(self, c, email="refresh_test@lablink.edu"):
        c.post(
            "/api/auth/register",
            json={"name": "Refresh User", "email": email, "password": "Refresh@12345", "role": "student"},
        )
        return c.post("/api/auth/login", json={"email": email, "password": "Refresh@12345"})

    def test_refresh_issues_new_access_token(self, client):
        c, _ = client
        self._register_and_login(c)
        refresh_resp = c.post("/api/auth/refresh")
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.get_json()

    def test_no_cookie_returns_401(self, client):
        c, _ = client
        # Fresh client, no cookie planted
        resp = c.post("/api/auth/refresh")
        assert resp.status_code == 401


# ── Logout + revocation tests ──────────────────────────────────────────────────

class TestLogout:
    def _register_login_token(self, c, email="logout_test@lablink.edu"):
        c.post(
            "/api/auth/register",
            json={"name": "Logout User", "email": email, "password": "Logout@12345", "role": "student"},
        )
        resp = c.post("/api/auth/login", json={"email": email, "password": "Logout@12345"})
        return resp.get_json()["access_token"]

    def test_logout_succeeds(self, client):
        c, _ = client
        token = self._register_login_token(c)
        resp = c.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_refresh_after_logout_fails(self, client):
        c, _ = client
        token = self._register_login_token(c, email="postlogout@lablink.edu")
        c.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        # After logout, the refresh cookie is cleared; endpoint must return 401
        resp = c.post("/api/auth/refresh")
        assert resp.status_code == 401


# ── Role guard tests ───────────────────────────────────────────────────────────

class TestRoleGuard:
    def _get_token_for_role(self, c, role, email=None):
        email = email or f"{role}@roletest.edu"
        c.post(
            "/api/auth/register",
            json={"name": f"Role {role}", "email": email, "password": "RoleTest@1", "role": role},
        )
        resp = c.post("/api/auth/login", json={"email": email, "password": "RoleTest@1"})
        return resp.get_json()["access_token"]

    def test_student_cannot_access_admin_route(self, client):
        c, _ = client
        token = self._get_token_for_role(c, "student", "admin_test_s@test.edu")
        resp = c.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_can_access_admin_route(self, client):
        c, _ = client
        token = self._get_token_for_role(c, "admin", "admin_test_a@test.edu")
        resp = c.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_student_cannot_access_faculty_route(self, client):
        c, _ = client
        token = self._get_token_for_role(c, "student", "faculty_test_s@test.edu")
        resp = c.get("/api/faculty/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_faculty_can_access_faculty_route(self, client):
        c, _ = client
        token = self._get_token_for_role(c, "faculty", "faculty_test_f@test.edu")
        resp = c.get("/api/faculty/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_lab_assistant_cannot_access_admin(self, client):
        c, _ = client
        token = self._get_token_for_role(c, "lab_assistant", "labassist_test@test.edu")
        resp = c.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
