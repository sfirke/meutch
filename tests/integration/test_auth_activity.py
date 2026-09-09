"""Activity log entries written by real HTTP requests.

The unit tests cover what each call site records. These cover the things only a real
request can settle: which surface the event came from, that the client's address and
request id are picked up, and that signing out still knows who signed out.
"""

from app import db
from app.models import ActivityLog
from app.utils import activity_events
from conftest import TEST_PASSWORD, login_user
from tests.factories import UserFactory
from tests.integration.api_test_helpers import auth_headers


def _entries(event_type):
    return (
        db.session.query(ActivityLog)
        .filter_by(event_type=event_type)
        .order_by(ActivityLog.occurred_at, ActivityLog.id)
        .all()
    )


class TestWebSignIn:
    def test_signing_in_records_a_web_event_with_the_client_address(self, client, db_session):
        UserFactory(email="webuser@example.com")
        db_session.commit()

        response = client.post(
            "/login",
            data={"email": "webuser@example.com", "password": TEST_PASSWORD},
            environ_base={"REMOTE_ADDR": "203.0.113.42"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        entry = _entries(activity_events.AUTH_LOGIN_SUCCEEDED)[0]
        assert entry.source == ActivityLog.SOURCE_WEB
        assert entry.ip_address == "203.0.113.42"
        assert entry.user_agent is not None

    def test_signing_out_records_who_signed_out(self, client, db_session):
        """logout_user() clears the session, so the actor has to be captured first."""
        user = UserFactory(email="byebye@example.com")
        db_session.commit()
        user_id = user.id

        login_user(client, "byebye@example.com")
        client.get("/logout", follow_redirects=True)

        entries = _entries(activity_events.AUTH_LOGOUT)
        assert len(entries) == 1
        assert entries[0].actor_user_id == user_id

    def test_signing_out_when_not_signed_in_records_nothing(self, client, db_session):
        client.get("/logout", follow_redirects=True)

        assert _entries(activity_events.AUTH_LOGOUT) == []

    def test_a_mistyped_address_is_stored_verbatim(self, client, db_session):
        client.post(
            "/login",
            data={"email": "you@gmial.com", "password": "whatever"},
            follow_redirects=True,
        )

        entry = _entries(activity_events.AUTH_LOGIN_FAILED)[0]
        assert entry.context["attempted_email"] == "you@gmial.com"
        assert entry.context["account_exists"] is False


class TestApiSignIn:
    def test_api_sign_in_is_recorded_as_an_api_event_with_the_request_id(self, client, db_session):
        UserFactory(email="apiuser@example.com")
        db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "apiuser@example.com", "password": TEST_PASSWORD},
            headers={"X-Request-ID": "test-request-id-1234"},
        )
        assert response.status_code == 200

        entry = _entries(activity_events.AUTH_LOGIN_SUCCEEDED)[0]
        assert entry.source == ActivityLog.SOURCE_API
        assert entry.request_id == "test-request-id-1234"

    def test_api_sign_out_records_the_actor(self, client, db_session):
        user = UserFactory(email="apibye@example.com")
        db_session.commit()
        user_id = user.id

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "apibye@example.com", "password": TEST_PASSWORD},
        )
        access_token = login_response.get_json()["access_token"]

        response = client.post("/api/v1/auth/logout", headers=auth_headers(access_token))
        assert response.status_code == 200

        entries = _entries(activity_events.AUTH_LOGOUT)
        assert len(entries) == 1
        assert entries[0].actor_user_id == user_id
        assert entries[0].source == ActivityLog.SOURCE_API

    def test_replaying_a_rotated_refresh_token_is_recorded(self, client, db_session):
        user = UserFactory(email="replay@example.com")
        db_session.commit()
        user_id = user.id

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "replay@example.com", "password": TEST_PASSWORD},
        )
        original_refresh_token = login_response.get_json()["refresh_token"]

        rotate_response = client.post(
            "/api/v1/auth/refresh", headers=auth_headers(original_refresh_token)
        )
        assert rotate_response.status_code == 200

        replay_response = client.post(
            "/api/v1/auth/refresh", headers=auth_headers(original_refresh_token)
        )
        assert replay_response.status_code == 401

        entries = _entries(activity_events.AUTH_TOKEN_REUSE_DETECTED)
        assert len(entries) == 1
        assert entries[0].subject_user_id == user_id
