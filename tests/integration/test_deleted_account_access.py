"""A deleted account can no longer sign in, keep a session, or act through the API."""

from datetime import UTC, datetime

import pytest

from app import db
from app.models import ApiTokenFamily, User
from app.services import account_service
from conftest import TEST_PASSWORD, login_user
from tests.factories import UserFactory

from .api_test_helpers import auth_headers

DELETE_CONFIRMATION = {"confirmation": "DELETE MY ACCOUNT"}


@pytest.fixture(autouse=True)
def _push_request_context():
    """Replace pytest-flask's test-long request context.

    With it, every request in a test shares one app context, so the signed-in user
    and the database session are cached between requests. These tests need each
    request to resolve its user afresh, as it does in production.
    """
    yield


def _create_user(app, **kwargs):
    """Create a user and return (id, email)."""
    with app.app_context():
        user = UserFactory(**kwargs)
        db.session.commit()
        return user.id, user.email


def _delete_with_service(app, user_id):
    """Delete through the shared workflow and return the rewritten email."""
    with app.app_context():
        user = db.session.get(User, user_id)
        account_service.delete_user_account(user)
        return user.email


def _mark_deleted(app, user_id):
    """Flag a row as deleted the way accounts removed before this fix were left."""
    with app.app_context():
        user = db.session.get(User, user_id)
        user.is_deleted = True
        user.deleted_at = datetime.now(UTC)
        user.email = f"deleted_{user.id}@deleted.meutch"
        db.session.commit()
        return user.email


def _get_user(app, user_id):
    with app.app_context():
        user = db.session.get(User, user_id)
        db.session.expunge(user)
        return user


def _live_family_count(app, user_id):
    with app.app_context():
        return ApiTokenFamily.query.filter_by(user_id=user_id, revoked_at=None).count()


def _api_login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.get_json()


def _assert_signed_out(client, path="/profile"):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def _assert_api_session_refused(client, tokens):
    me_response = client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    refresh_response = client.post(
        "/api/v1/auth/refresh", headers=auth_headers(tokens["refresh_token"])
    )
    assert me_response.status_code == 401
    assert refresh_response.status_code == 401
    assert "access_token" not in refresh_response.get_json()


class TestDeletedAccountWeb:
    def test_web_session_ends_when_an_admin_deletes_the_account(self, app, client):
        _, admin_email = _create_user(app, is_admin=True)
        member_id, member_email = _create_user(app)

        login_user(client, member_email)
        assert client.get("/profile").status_code == 200

        admin_client = app.test_client()
        login_user(admin_client, admin_email)
        response = admin_client.post(f"/admin/users/{member_id}/delete", follow_redirects=True)
        assert b"has been deleted" in response.data

        _assert_signed_out(client)

    def test_web_session_ends_for_an_already_deleted_row(self, app, client):
        member_id, member_email = _create_user(app)
        login_user(client, member_email)
        assert client.get("/profile").status_code == 200

        _mark_deleted(app, member_id)

        _assert_signed_out(client)

    def test_web_session_on_another_browser_ends_after_self_deletion(self, app, client):
        member_id, member_email = _create_user(app)
        other_browser = app.test_client()
        login_user(client, member_email)
        login_user(other_browser, member_email)

        response = client.post("/delete_account", data=DELETE_CONFIRMATION, follow_redirects=True)
        assert response.status_code == 200
        assert _get_user(app, member_id).is_deleted is True

        _assert_signed_out(client)
        _assert_signed_out(other_browser)

    @pytest.mark.parametrize("delete", [_delete_with_service, _mark_deleted])
    def test_web_login_refused_after_deletion(self, app, client, delete):
        member_id, _ = _create_user(app)
        deleted_email = delete(app, member_id)

        response = login_user(client, deleted_email)

        assert b"Invalid email or password" in response.data
        _assert_signed_out(client)
        assert _get_user(app, member_id).failed_login_attempts == 0

    def test_deleted_admin_cannot_reach_admin_routes(self, app, client):
        admin_id, admin_email = _create_user(app, is_admin=True)
        _, other_admin_email = _create_user(app, is_admin=True)

        login_user(client, admin_email)
        assert client.get("/admin/").status_code == 200

        other_admin_client = app.test_client()
        login_user(other_admin_client, other_admin_email)
        other_admin_client.post(f"/admin/users/{admin_id}/delete", follow_redirects=True)

        deleted_admin = _get_user(app, admin_id)
        assert deleted_admin.is_deleted is True
        assert deleted_admin.is_admin is False
        _assert_signed_out(client, "/admin/")

    def test_already_deleted_admin_row_cannot_reach_admin_routes(self, app, client):
        admin_id, admin_email = _create_user(app, is_admin=True)
        login_user(client, admin_email)
        assert client.get("/admin/").status_code == 200

        deleted_email = _mark_deleted(app, admin_id)

        assert _get_user(app, admin_id).is_admin is True
        _assert_signed_out(client, "/admin/")
        login_user(client, deleted_email)
        _assert_signed_out(client, "/admin/")

    def test_password_reset_link_stops_working_for_an_already_deleted_row(self, app, client):
        member_id, _ = _create_user(app)
        with app.app_context():
            token = db.session.get(User, member_id).generate_password_reset_token()
            db.session.commit()
        _mark_deleted(app, member_id)

        response = client.post(
            f"/reset-password/{token}",
            data={"password": "a-new-password-123", "confirm_password": "a-new-password-123"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        member = _get_user(app, member_id)
        assert member.password_reset_token == token
        assert member.check_password(TEST_PASSWORD) is True

    def test_confirmation_link_stops_working_for_an_already_deleted_row(self, app, client):
        member_id, _ = _create_user(app, email_confirmed=False)
        with app.app_context():
            token = db.session.get(User, member_id).generate_confirmation_token()
            db.session.commit()
        _mark_deleted(app, member_id)

        client.post(f"/confirm/{token}", follow_redirects=True)

        assert _get_user(app, member_id).email_confirmed is False

    def test_password_reset_request_sends_nothing_for_a_deleted_account(self, app, client):
        member_id, _ = _create_user(app)
        deleted_email = _mark_deleted(app, member_id)

        client.post("/forgot-password", data={"email": deleted_email}, follow_redirects=True)

        assert _get_user(app, member_id).password_reset_token is None


class TestDeletedAccountApi:
    def test_api_session_refused_after_admin_deletion(self, app, client):
        _, admin_email = _create_user(app, is_admin=True)
        member_id, member_email = _create_user(app)
        tokens = _api_login(client, member_email)

        admin_client = app.test_client()
        login_user(admin_client, admin_email)
        admin_client.post(f"/admin/users/{member_id}/delete", follow_redirects=True)

        assert _get_user(app, member_id).is_deleted is True
        assert _live_family_count(app, member_id) == 0
        _assert_api_session_refused(client, tokens)

    def test_api_session_refused_after_web_self_deletion(self, app, client):
        member_id, member_email = _create_user(app)
        tokens = _api_login(client, member_email)

        web_client = app.test_client()
        login_user(web_client, member_email)
        web_client.post("/delete_account", data=DELETE_CONFIRMATION, follow_redirects=True)

        assert _get_user(app, member_id).is_deleted is True
        assert _live_family_count(app, member_id) == 0
        _assert_api_session_refused(client, tokens)

    def test_other_device_api_session_refused_after_api_self_deletion(self, app, client):
        member_id, member_email = _create_user(app)
        this_device = _api_login(client, member_email)
        other_device = _api_login(client, member_email)

        response = client.delete(
            "/api/v1/me",
            headers=auth_headers(this_device["access_token"]),
            json=DELETE_CONFIRMATION,
        )
        assert response.status_code == 200

        assert _live_family_count(app, member_id) == 0
        _assert_api_session_refused(client, other_device)
        _assert_api_session_refused(client, this_device)

    def test_api_session_refused_for_an_already_deleted_row(self, app, client):
        member_id, member_email = _create_user(app)
        tokens = _api_login(client, member_email)

        _mark_deleted(app, member_id)

        # The session family is still live here, so the user lookup is what refuses it.
        assert _live_family_count(app, member_id) == 1
        _assert_api_session_refused(client, tokens)

    @pytest.mark.parametrize("delete", [_delete_with_service, _mark_deleted])
    def test_api_login_refused_like_an_unknown_email(self, app, client, delete):
        member_id, _ = _create_user(app)
        deleted_email = delete(app, member_id)

        deleted_response = client.post(
            "/api/v1/auth/login", json={"email": deleted_email, "password": TEST_PASSWORD}
        )
        unknown_response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": TEST_PASSWORD},
        )

        assert deleted_response.status_code == unknown_response.status_code == 401
        assert deleted_response.get_json() == unknown_response.get_json()
