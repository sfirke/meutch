"""Integration tests for the API hardening added alongside account lockout."""

import io

from app import db
from app.services import auth_service
from tests.factories import UserFactory
from tests.integration.api_test_helpers import auth_headers, login_api_user


class TestApiResponseHeaders:
    def test_read_response_carries_version_and_security_headers(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        token = login_api_user(client, email)
        response = client.get("/api/v1/categories", headers=auth_headers(token))

        assert response.status_code == 200
        assert response.headers["X-API-Version"] == "v1"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"

    def test_error_response_also_carries_the_headers(self, client):
        response = client.get("/api/v1/categories")

        assert response.status_code == 401
        assert response.headers["X-API-Version"] == "v1"


class TestApiRequestBodyLimit:
    def test_oversized_json_body_is_rejected(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        token = login_api_user(client, email)
        oversized = "x" * (app.config["API_V1_MAX_CONTENT_LENGTH"] + 1024)

        response = client.post(
            "/api/v1/requests",
            headers=auth_headers(token),
            json={"title": "Need a drill", "description": oversized},
        )

        assert response.status_code == 413
        assert response.get_json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_normal_json_body_is_not_rejected(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        token = login_api_user(client, email)
        response = client.post(
            "/api/v1/requests",
            headers=auth_headers(token),
            json={"title": "Need a drill", "description": "A cordless one, please."},
        )

        assert response.status_code != 413

    def test_multipart_upload_larger_than_the_json_limit_is_allowed(self, client, app):
        """Photos routinely exceed the JSON body ceiling, so uploads must be exempt.

        Regression test: a global MAX_CONTENT_LENGTH rejected ordinary photo
        uploads on both the API and the web UI with a 413.
        """
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        token = login_api_user(client, email)
        payload = b"x" * (app.config["API_V1_MAX_CONTENT_LENGTH"] + 1024 * 1024)

        response = client.post(
            "/api/v1/items",
            headers=auth_headers(token),
            data={
                "name": "Camera",
                "description": "With a large photo attached.",
                "images": (io.BytesIO(payload), "photo.jpg"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code != 413


class TestApiLoginPasswordValidation:
    def test_login_accepts_a_password_shorter_than_the_current_minimum(self, client, app):
        """Accounts predating the 8-character minimum must still authenticate.

        Regression test: a min-length validator on the login schema rejected these
        users with a 422 before their credentials were ever checked.
        """
        short_password = "old123"
        assert len(short_password) < auth_service.PASSWORD_MIN_LENGTH

        with app.app_context():
            user = UserFactory()
            user.set_password(short_password)
            db.session.commit()
            email = user.email

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": short_password},
        )

        assert response.status_code == 200
        assert "access_token" in response.get_json()

    def test_registration_still_enforces_the_minimum(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newshort@example.com",
                "first_name": "New",
                "last_name": "Short",
                "password": "short12",
            },
        )

        assert response.status_code == 422


class TestApiLoginLockout:
    def test_locked_account_receives_a_lockout_message(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        for _ in range(auth_service.MAX_FAILED_LOGIN_ATTEMPTS):
            client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "testpassword123"},
        )

        assert response.status_code == 401
        body = response.get_json()
        assert "temporarily locked" in body["error"]["message"]
        assert body["error"]["details"]["retry_after_minutes"] == auth_service.INITIAL_LOCKOUT_MINUTES


class TestApiReadRateLimit:
    def test_read_endpoint_returns_429_after_the_read_limit_is_exceeded(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            email = user.email

        token = login_api_user(client, email)

        original_enabled = app.config["API_V1_RATE_LIMITS_ENABLED"]
        original_read_limit = app.config["API_V1_READ_RATE_LIMIT"]

        try:
            app.config["API_V1_RATE_LIMITS_ENABLED"] = True
            app.config["API_V1_READ_RATE_LIMIT"] = "1 per minute"

            first_response = client.get("/api/v1/tags", headers=auth_headers(token))
            limited_response = client.get("/api/v1/tags", headers=auth_headers(token))

            assert first_response.status_code == 200
            assert limited_response.status_code == 429
            assert limited_response.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        finally:
            app.config["API_V1_RATE_LIMITS_ENABLED"] = original_enabled
            app.config["API_V1_READ_RATE_LIMIT"] = original_read_limit
