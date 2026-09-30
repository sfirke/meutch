"""Activity log entries written by real HTTP requests.

The unit tests cover what each call site records. These cover the things only a real
request can settle: which surface the event came from, that the client's address and
request id are picked up, and that signing out still knows who signed out.
"""

import time

import pytest

from app import db
from app.forms_auth import issue_registration_started_token
from app.models import ActivityLog
from app.utils import activity_events
from app.utils.name_plausibility import implausible_name_reason
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

    def test_retrying_a_replayed_token_is_recorded_once(self, client, db_session):
        UserFactory(email="replay-twice@example.com")
        db_session.commit()

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "replay-twice@example.com", "password": TEST_PASSWORD},
        )
        original_refresh_token = login_response.get_json()["refresh_token"]
        client.post("/api/v1/auth/refresh", headers=auth_headers(original_refresh_token))

        for _ in range(2):
            replay_response = client.post(
                "/api/v1/auth/refresh", headers=auth_headers(original_refresh_token)
            )
            assert replay_response.status_code == 401

        assert len(_entries(activity_events.AUTH_TOKEN_REUSE_DETECTED)) == 1

    def test_a_stale_refresh_after_logout_is_not_a_replay(self, client, db_session):
        UserFactory(email="stale@example.com")
        db_session.commit()

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "stale@example.com", "password": TEST_PASSWORD},
        )
        refresh_token = login_response.get_json()["refresh_token"]

        logout_response = client.post("/api/v1/auth/logout", headers=auth_headers(refresh_token))
        assert logout_response.status_code == 200

        retry_response = client.post("/api/v1/auth/refresh", headers=auth_headers(refresh_token))
        assert retry_response.status_code == 401

        assert _entries(activity_events.AUTH_TOKEN_REUSE_DETECTED) == []


GENERATED_FIRST_NAME = "ZspMSWgBftjwEHvOnFjWgHCn"
GENERATED_LAST_NAME = "XgpaMpyjmoggqgJDEW"


class TestBlockedWebRegistration:
    @pytest.fixture(autouse=True)
    def min_fill_seconds(self, app):
        original = app.config["REGISTRATION_MIN_FILL_SECONDS"]
        app.config["REGISTRATION_MIN_FILL_SECONDS"] = 3
        yield
        app.config["REGISTRATION_MIN_FILL_SECONDS"] = original

    @staticmethod
    def _registration_data(app, **overrides):
        with app.app_context():
            started = issue_registration_started_token(now=time.time() - 10)
        data = {
            "email": "Signup@Example.com",
            "first_name": "Trap",
            "last_name": "Tester",
            "location_method": "skip",
            "age_confirm": True,
            "password": "trappassword123",
            "confirm_password": "trappassword123",
            "started": started,
        }
        data.update(overrides)
        return data

    @staticmethod
    def _blocked_entry():
        entries = _entries(activity_events.AUTH_REGISTER_BLOCKED)
        assert len(entries) == 1
        assert entries[0].source == ActivityLog.SOURCE_WEB
        assert entries[0].actor_user_id is None
        return entries[0]

    def test_a_filled_honeypot_is_recorded(self, app, client, db_session):
        client.post("/register", data=self._registration_data(app, website="http://spam.example"))

        assert self._blocked_entry().context == {
            "reason": "honeypot",
            "attempted_email": "Signup@Example.com",
        }

    def test_a_submission_right_after_the_page_loads_is_recorded(self, app, client, db_session):
        with app.app_context():
            started = issue_registration_started_token()

        client.post("/register", data=self._registration_data(app, started=started))

        assert self._blocked_entry().context["reason"] == "too_fast"

    def test_a_missing_start_time_is_recorded(self, app, client, db_session):
        client.post("/register", data=self._registration_data(app, started=""))

        assert self._blocked_entry().context["reason"] == "missing_start_time"

    def test_two_generated_names_record_one_entry(self, app, client, db_session):
        client.post(
            "/register",
            data=self._registration_data(
                app, first_name=GENERATED_FIRST_NAME, last_name=GENERATED_LAST_NAME
            ),
        )

        assert self._blocked_entry().context == {
            "reason": "implausible_name",
            "name_check": implausible_name_reason(GENERATED_FIRST_NAME),
            "attempted_email": "Signup@Example.com",
            "attempted_first_name": GENERATED_FIRST_NAME,
            "attempted_last_name": GENERATED_LAST_NAME,
        }

    def test_an_ordinary_validation_error_records_nothing(self, app, client, db_session):
        client.post("/register", data=self._registration_data(app, confirm_password="different"))

        assert _entries(activity_events.AUTH_REGISTER_BLOCKED) == []

    def test_a_successful_sign_up_records_nothing_blocked(self, app, client, db_session):
        response = client.post("/register", data=self._registration_data(app))

        assert response.status_code == 302
        assert _entries(activity_events.AUTH_REGISTER_BLOCKED) == []


class TestBlockedApiRegistration:
    @staticmethod
    def _register(client, **overrides):
        data = {
            "email": "apisignup@example.com",
            "first_name": "Api",
            "last_name": "Person",
            "password": "somepassword123",
            "location_method": "skip",
        }
        data.update(overrides)
        return client.post("/api/v1/auth/register", json=data)

    def test_a_generated_name_is_recorded_once(self, client, db_session):
        response = self._register(
            client, first_name=GENERATED_FIRST_NAME, last_name=GENERATED_LAST_NAME
        )
        assert response.status_code == 422

        entries = _entries(activity_events.AUTH_REGISTER_BLOCKED)
        assert len(entries) == 1
        assert entries[0].source == ActivityLog.SOURCE_API
        assert entries[0].actor_user_id is None
        assert entries[0].context == {
            "reason": "implausible_name",
            "name_check": implausible_name_reason(GENERATED_FIRST_NAME),
            "attempted_email": "apisignup@example.com",
            "attempted_first_name": GENERATED_FIRST_NAME,
            "attempted_last_name": GENERATED_LAST_NAME,
        }

    def test_a_generated_last_name_alone_is_recorded(self, client, db_session):
        self._register(client, last_name=GENERATED_LAST_NAME)

        entry = _entries(activity_events.AUTH_REGISTER_BLOCKED)[0]
        assert entry.context["name_check"] == implausible_name_reason(GENERATED_LAST_NAME)
        assert entry.context["attempted_first_name"] == "Api"
        assert entry.context["attempted_last_name"] == GENERATED_LAST_NAME

    def test_a_generated_name_sent_as_a_list_is_recorded(self, client, db_session):
        response = self._register(client, first_name=[GENERATED_FIRST_NAME])
        assert response.status_code == 422

        entry = _entries(activity_events.AUTH_REGISTER_BLOCKED)[0]
        assert entry.context["name_check"] == implausible_name_reason(GENERATED_FIRST_NAME)
        assert entry.context["attempted_first_name"] == GENERATED_FIRST_NAME

    def test_an_ordinary_validation_error_records_nothing(self, client, db_session):
        response = self._register(client, password="short")
        assert response.status_code == 422

        assert _entries(activity_events.AUTH_REGISTER_BLOCKED) == []
