"""Unit tests for the activity log writer.

The four things that matter here are the ones that would ship a working-looking
Activity tab that quietly drops events: the write has to survive the caller rolling
back, a failed write must not damage the caller, the actor has to be resolved from
whichever kind of request is in flight, and the PII guard has to drop what it
promises to drop without ever raising.
"""

from unittest.mock import patch

import pytest
from flask_login import login_user as flask_login_user

from app import db
from app.models import ActivityLog, User
from app.utils import activity_events
from app.utils.activity_log import log_event, sanitize_context
from tests.factories import UserFactory


def _rows(event_type=None):
    query = db.session.query(ActivityLog)
    if event_type is not None:
        query = query.filter_by(event_type=event_type)
    return query.order_by(ActivityLog.occurred_at, ActivityLog.id).all()


class TestTransactionIndependence:
    """The writer commits on its own connection, not through db.session."""

    def test_row_survives_a_caller_rollback(self, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()

            log_event(activity_events.AUTH_LOGIN_SUCCEEDED, actor=user, subject=user)
            db.session.rollback()

            entries = _rows()
            assert len(entries) == 1
            assert entries[0].actor_user_id == user.id

    def test_caller_pending_objects_are_not_committed_by_the_write(self, app):
        """The audit row must not drag the caller's unflushed work in with it.

        This is the other half of independence: log_event neither depends on the
        caller's transaction nor commits it.
        """
        with app.app_context():
            actor = UserFactory()
            db.session.commit()

            pending = User(
                email="pending@example.com",
                first_name="Pending",
                last_name="User",
            )
            pending.set_password("testpassword123")
            db.session.add(pending)

            log_event(activity_events.AUTH_LOGIN_SUCCEEDED, actor=actor, subject=actor)
            db.session.rollback()

            assert len(_rows()) == 1
            assert User.query.filter_by(email="pending@example.com").first() is None


class TestFailureIsolation:
    def test_a_failed_write_does_not_escape_or_poison_the_caller(self, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()

            with patch("sqlalchemy.engine.Engine.connect", side_effect=RuntimeError("boom")):
                log_event(activity_events.AUTH_LOGIN_SUCCEEDED, actor=user, subject=user)

            assert _rows() == []

            # The caller's own session is untouched and can still commit.
            user.first_name = "Renamed"
            db.session.commit()
            assert db.session.get(User, user.id).first_name == "Renamed"

    def test_disabled_by_configuration_writes_nothing(self, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()

            app.config["ACTIVITY_LOG_ENABLED"] = False
            try:
                log_event(activity_events.AUTH_LOGIN_SUCCEEDED, actor=user, subject=user)
            finally:
                app.config["ACTIVITY_LOG_ENABLED"] = True

            assert _rows() == []

    def test_an_unregistered_event_type_still_writes_its_row(self, app):
        with app.app_context():
            log_event("auth.not.a.real.event", actor=None)

            entries = _rows()
            assert len(entries) == 1
            assert entries[0].event_type == "auth.not.a.real.event"


class TestActorResolution:
    def test_no_request_context_records_a_cli_event_with_no_actor(self, app):
        """A CLI caller -- the nightly digest job, say -- must not explode on the
        request-only lookups.

        pytest-flask keeps a request context pushed for the whole of every test that
        uses the `app` fixture, so the absence of one has to be simulated rather than
        arranged.
        """
        with app.app_context():
            with patch("app.utils.activity_log.has_request_context", return_value=False):
                log_event(activity_events.AUTH_LOGIN_SUCCEEDED)

            entry = _rows()[0]
            assert entry.source == ActivityLog.SOURCE_CLI
            assert entry.actor_user_id is None
            assert entry.ip_address is None
            assert entry.user_agent is None

    def test_web_request_resolves_the_signed_in_user(self, app):
        with app.app_context():
            user = UserFactory(email="webactor@example.com")
            db.session.commit()
            user_id = user.id

        with app.test_request_context(
            "/some-page",
            environ_base={"REMOTE_ADDR": "203.0.113.7", "HTTP_USER_AGENT": "curl/8.4.0"},
        ):
            flask_login_user(db.session.get(User, user_id))
            log_event(activity_events.AUTH_LOGIN_SUCCEEDED)

            entry = _rows(activity_events.AUTH_LOGIN_SUCCEEDED)[-1]
            assert entry.actor_user_id == user_id
            assert entry.source == ActivityLog.SOURCE_WEB
            assert entry.ip_address == "203.0.113.7"
            assert entry.user_agent == "curl/8.4.0"

    def test_an_explicit_none_actor_beats_the_signed_in_user(self, app):
        """A sign-in attempt has no actor even if a session cookie is present.

        Passing actor=None has to mean "nobody has proved who they are", which is
        different from omitting the argument.
        """
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            user_id = user.id

        with app.test_request_context("/login"):
            flask_login_user(db.session.get(User, user_id))
            log_event(activity_events.AUTH_LOGIN_FAILED, actor=None)

            assert _rows(activity_events.AUTH_LOGIN_FAILED)[0].actor_user_id is None

    def test_api_path_is_detected_as_an_api_event(self, app):
        with app.test_request_context("/api/v1/auth/login"):
            log_event(activity_events.AUTH_LOGIN_FAILED, actor=None)

            assert _rows()[0].source == ActivityLog.SOURCE_API

    def test_an_unparseable_client_address_is_stored_as_null(self, app):
        """The address ultimately comes from a header, so it cannot be trusted to be
        an address at all -- and an INET column would raise DataError on the insert,
        losing the event."""
        with app.test_request_context("/login", environ_base={"REMOTE_ADDR": "not-an-address"}):
            log_event(activity_events.AUTH_LOGIN_FAILED, actor=None)

            entry = _rows()[0]
            assert entry.ip_address is None
            assert entry.event_type == activity_events.AUTH_LOGIN_FAILED


class TestSanitizeContext:
    @pytest.mark.parametrize(
        "key",
        ["first_name", "email_address", "reset_token", "message_body", "street", "latitude"],
    )
    def test_denied_keys_are_dropped(self, key):
        assert sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, {key: "x"}) is None

    @pytest.mark.parametrize(
        "key",
        [
            "user_agent",
            "attempt_count",
            "retry_after_minutes",
            "account_exists",
            "notification_sent",
        ],
    )
    def test_allowed_keys_survive(self, key):
        assert sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, {key: 1}) == {key: 1}

    def test_exempted_key_survives_only_on_its_own_event(self):
        payload = {"attempted_email": "you@gmial.com"}

        assert sanitize_context(activity_events.AUTH_LOGIN_FAILED, payload) == payload
        assert sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, payload) is None

    def test_nested_values_are_dropped_but_scalars_beside_them_are_kept(self):
        result = sanitize_context(
            activity_events.AUTH_LOGIN_SUCCEEDED,
            {"nested": {"a": 1}, "listed": [1, 2], "count": 3},
        )
        assert result == {"count": 3}

    def test_long_strings_are_truncated_rather_than_dropped(self):
        result = sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, {"reason": "x" * 500})
        assert len(result["reason"]) == 200

    def test_an_oversized_payload_is_dropped_whole(self):
        payload = {f"field_{index}": "y" * 200 for index in range(50)}
        assert sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, payload) is None

    def test_a_non_dict_context_is_dropped_without_raising(self):
        assert sanitize_context(activity_events.AUTH_LOGIN_SUCCEEDED, "not a dict") is None
