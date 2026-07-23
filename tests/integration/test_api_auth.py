"""Integration tests for API JWT authentication endpoints."""

from datetime import timedelta

from flask_jwt_extended import create_access_token
from werkzeug.datastructures import MultiDict

from app import db
from app.models import ApiTokenFamily
from app.services import api_token_service
from tests.factories import UserFactory


def auth_headers(token):
    """Return Authorization headers for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


class TestApiAuth:
    """Exercise login, refresh, logout, and related auth workflows."""

    def test_login_returns_access_and_refresh_tokens(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["token_type"] == "Bearer"
        assert payload["access_token"]
        assert payload["refresh_token"]
        assert payload["user"]["email"] == user_email
        assert payload["user"]["email_confirmed"] is True

    def test_login_accepts_form_encoded_body(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/login",
            data=MultiDict(
                [
                    ("email", user_email),
                    ("password", "testpassword123"),
                ]
            ),
            content_type="application/x-www-form-urlencoded",
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_token"]
        assert payload["refresh_token"]
        assert payload["user"]["email"] == user_email

    def test_login_rejects_invalid_credentials(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert response.get_json() == {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Invalid email or password.",
                "details": {},
            }
        }

    def test_login_rejects_unconfirmed_user(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_login_returns_429_after_rate_limit_is_exceeded(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        original_rate_limit_enabled = app.config["API_V1_RATE_LIMITS_ENABLED"]
        original_login_limit = app.config["API_V1_AUTH_LOGIN_RATE_LIMIT"]

        try:
            app.config["API_V1_RATE_LIMITS_ENABLED"] = True
            app.config["API_V1_AUTH_LOGIN_RATE_LIMIT"] = "2 per minute"

            for _ in range(2):
                response = client.post(
                    "/api/v1/auth/login",
                    json={"email": user_email, "password": "wrongpassword"},
                )
                assert response.status_code == 401

            limited_response = client.post(
                "/api/v1/auth/login",
                json={"email": user_email, "password": "wrongpassword"},
            )

            assert limited_response.status_code == 429
            assert limited_response.get_json() == {
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "details": {},
                }
            }
        finally:
            app.config["API_V1_RATE_LIMITS_ENABLED"] = original_rate_limit_enabled
            app.config["API_V1_AUTH_LOGIN_RATE_LIMIT"] = original_login_limit

    def test_me_requires_jwt_even_when_web_session_exists(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()

        client.post(
            "/login",
            data={"email": user.email, "password": "testpassword123"},
            follow_redirects=True,
        )

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_api_login_does_not_create_web_session(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )

        assert login_response.status_code == 200

        response = client.get("/requests/", follow_redirects=False)

        assert response.status_code == 302
        assert "/login" in response.location

    def test_me_returns_current_user_for_valid_access_token(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email
            user_id = str(user.id)
            first_name = user.first_name
            last_name = user.last_name
            full_name = user.full_name
            profile_image_url = user.profile_image_url

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )
        access_token = login_response.get_json()["access_token"]

        response = client.get("/api/v1/auth/me", headers=auth_headers(access_token))

        assert response.status_code == 200
        assert response.get_json() == {
            "user": {
                "id": user_id,
                "email": user_email,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "profile_image_url": profile_image_url,
                "email_confirmed": True,
            }
        }

    def test_refresh_rotates_tokens_and_reuse_revokes_family(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )
        first_payload = login_response.get_json()

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers(first_payload["refresh_token"]),
        )

        assert refresh_response.status_code == 200
        second_payload = refresh_response.get_json()
        assert second_payload["refresh_token"] != first_payload["refresh_token"]
        assert second_payload["access_token"] != first_payload["access_token"]

        reuse_response = client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers(first_payload["refresh_token"]),
        )

        assert reuse_response.status_code == 401
        assert reuse_response.get_json()["error"]["code"] == "TOKEN_REVOKED"

        revoked_me_response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers(second_payload["access_token"]),
        )

        assert revoked_me_response.status_code == 401
        assert revoked_me_response.get_json()["error"]["code"] == "TOKEN_REVOKED"

    def test_logout_revokes_access_and_refresh_tokens(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )
        payload = login_response.get_json()

        logout_response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers(payload["access_token"]),
        )

        assert logout_response.status_code == 200
        assert logout_response.get_json() == {"message": "You have been logged out."}

        me_response = client.get("/api/v1/auth/me", headers=auth_headers(payload["access_token"]))
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers(payload["refresh_token"]),
        )

        assert me_response.status_code == 401
        assert me_response.get_json()["error"]["code"] == "TOKEN_REVOKED"
        assert refresh_response.status_code == 401
        assert refresh_response.get_json()["error"]["code"] == "TOKEN_REVOKED"

    def test_expired_access_token_returns_token_expired(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            api_token_service.issue_token_bundle(user)
            token_family = ApiTokenFamily.query.filter_by(user_id=user.id).one()
            expired_access_token = create_access_token(
                identity=str(user.id),
                additional_claims={"family_id": str(token_family.id)},
                expires_delta=timedelta(seconds=-1),
            )

        response = client.get("/api/v1/auth/me", headers=auth_headers(expired_access_token))

        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_register_creates_user_without_logging_them_in(self, client, app):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new-api-user@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "newpassword123",
                "location_method": "skip",
            },
        )

        assert response.status_code == 201
        payload = response.get_json()
        assert payload["email_confirmation_sent"] is True
        assert payload["user"]["email"] == "new-api-user@example.com"
        assert payload["user"]["email_confirmed"] is False

        protected_response = client.get("/requests/", follow_redirects=False)
        assert protected_response.status_code == 302
        assert "/login" in protected_response.location

    def test_forgot_password_is_generic_for_missing_accounts(self, client):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "missing@example.com"},
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "message": "If an account with that email exists, password reset instructions have been sent."
        }

    def test_reset_password_uses_existing_web_token_flow(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            token = user.generate_password_reset_token()
            db.session.commit()
            user_email = user.email

        reset_response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "updatedpassword123"},
        )

        assert reset_response.status_code == 200
        assert reset_response.get_json() == {
            "message": "Your password has been reset successfully."
        }

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "updatedpassword123"},
        )

        assert login_response.status_code == 200

    def test_reset_password_rejects_invalid_token(self, client):
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-real-token", "password": "newpassword123"},
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_RESET_TOKEN"

    def test_register_rejects_duplicate_email(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": user_email,
                "first_name": "Dupe",
                "last_name": "User",
                "password": "somepassword123",
                "location_method": "skip",
            },
        )

        assert response.status_code == 409
        payload = response.get_json()
        assert payload["error"]["code"] == "CONFLICT"
        assert payload["error"]["details"]["email_status"] == "confirmed"
        assert "already registered" in payload["error"]["message"].lower()
        assert "forgot-password" in payload["error"]["message"].lower()

    def test_register_rejects_duplicate_unconfirmed_email(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            db.session.commit()
            user_email = user.email

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": user_email,
                "first_name": "Dupe",
                "last_name": "User",
                "password": "somepassword123",
                "location_method": "skip",
            },
        )

        assert response.status_code == 409
        payload = response.get_json()
        assert payload["error"]["code"] == "CONFLICT"
        assert payload["error"]["details"]["email_status"] == "unconfirmed"
        assert (
            "not been confirmed" in payload["error"]["message"].lower()
            or "hasn't been confirmed" in payload["error"]["message"].lower()
        )
