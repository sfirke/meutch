"""The activity log entries auth_service writes.

Sits beside test_account_lockout.py and reuses its shape, because the lockout path is
where the call sites are easiest to get subtly wrong.
"""

from app import db
from app.models import ActivityLog
from app.services import auth_service
from app.utils import activity_events
from conftest import TEST_PASSWORD
from tests.factories import UserFactory

WRONG_PASSWORD = "not-the-right-password"


def _event_types():
    """Every recorded event type, oldest first."""
    entries = db.session.query(ActivityLog).order_by(ActivityLog.occurred_at, ActivityLog.id).all()
    return [entry.event_type for entry in entries]


def _entries(event_type):
    return (
        db.session.query(ActivityLog)
        .filter_by(event_type=event_type)
        .order_by(ActivityLog.occurred_at, ActivityLog.id)
        .all()
    )


class TestSignInEvents:
    def test_a_successful_sign_in_is_recorded_against_the_account(self, app):
        with app.app_context():
            user = UserFactory(email="good@example.com")
            db.session.commit()

            auth_service.authenticate_user("good@example.com", TEST_PASSWORD)

            entries = _entries(activity_events.AUTH_LOGIN_SUCCEEDED)
            assert len(entries) == 1
            # The route has not called login_user() yet, so this only works because
            # the service passes the actor explicitly.
            assert entries[0].actor_user_id == user.id
            assert entries[0].subject_user_id == user.id

    def test_a_failed_sign_in_records_the_address_as_typed(self, app):
        with app.app_context():
            UserFactory(email="typo@example.com")
            db.session.commit()

            auth_service.authenticate_user("TyPo@ExAmple.com", WRONG_PASSWORD)

            entry = _entries(activity_events.AUTH_LOGIN_FAILED)[0]
            assert entry.context["attempted_email"] == "TyPo@ExAmple.com"
            assert entry.context["account_exists"] is True
            assert entry.actor_user_id is None

    def test_an_unknown_address_is_recorded_with_no_subject(self, app):
        with app.app_context():
            auth_service.authenticate_user("you@gmial.com", WRONG_PASSWORD)

            entry = _entries(activity_events.AUTH_LOGIN_FAILED)[0]
            assert entry.context["attempted_email"] == "you@gmial.com"
            assert entry.context["account_exists"] is False
            assert entry.subject_user_id is None

    def test_an_unconfirmed_account_records_its_own_event(self, app):
        with app.app_context():
            UserFactory(email="unconfirmed@example.com", email_confirmed=False)
            db.session.commit()

            auth_service.authenticate_user("unconfirmed@example.com", TEST_PASSWORD)

            assert _event_types() == [activity_events.AUTH_LOGIN_REJECTED_UNCONFIRMED]


class TestLockoutEvents:
    def test_reaching_the_threshold_records_the_failures_and_then_the_lockout(self, app):
        """The ordering is the assertion that matters.

        auth.account.locked has to land after the fifth auth.login.failed, not instead
        of it -- a call site one branch too high loses the failure that triggered it.
        """
        with app.app_context():
            UserFactory(email="lockme@example.com")
            db.session.commit()

            for _ in range(auth_service.MAX_FAILED_LOGIN_ATTEMPTS):
                auth_service.authenticate_user("lockme@example.com", WRONG_PASSWORD)

            expected_failures = [activity_events.AUTH_LOGIN_FAILED] * (
                auth_service.MAX_FAILED_LOGIN_ATTEMPTS
            )
            assert _event_types() == expected_failures + [activity_events.AUTH_ACCOUNT_LOCKED]

            locked = _entries(activity_events.AUTH_ACCOUNT_LOCKED)[0]
            assert locked.context["lockout_count"] == 1

    def test_signing_in_while_locked_out_records_a_blocked_attempt(self, app):
        with app.app_context():
            UserFactory(email="blocked@example.com")
            db.session.commit()

            for _ in range(auth_service.MAX_FAILED_LOGIN_ATTEMPTS):
                auth_service.authenticate_user("blocked@example.com", WRONG_PASSWORD)

            # The right password is refused too while the lockout stands.
            auth_service.authenticate_user("blocked@example.com", TEST_PASSWORD)

            blocked = _entries(activity_events.AUTH_LOGIN_BLOCKED)
            assert len(blocked) == 1
            assert blocked[0].context["retry_after_minutes"] >= 1
            assert _event_types()[-1] == activity_events.AUTH_LOGIN_BLOCKED


class TestAccountLifecycleEvents:
    def test_registration_is_recorded(self, app):
        with app.app_context():
            auth_service.register_user(
                email="newcomer@example.com",
                first_name="New",
                last_name="Comer",
                password="testpassword123",
                digest_frequency="none",
                location_method="coordinates",
                latitude=40.7128,
                longitude=-74.0060,
            )

            entry = _entries(activity_events.AUTH_REGISTER_SUCCEEDED)[0]
            assert entry.context["location_method"] == "coordinates"
            assert entry.subject_user_id is not None

    def test_confirming_an_email_is_recorded(self, app):
        with app.app_context():
            user = UserFactory(email="confirmme@example.com", email_confirmed=False)
            token = user.generate_confirmation_token()
            db.session.commit()

            auth_service.confirm_email_token(token)

            assert _entries(activity_events.AUTH_EMAIL_CONFIRMED)[0].subject_user_id == user.id

    def test_a_reset_request_for_an_unknown_address_records_it(self, app):
        with app.app_context():
            auth_service.request_password_reset("nobody@gmial.com")

            entry = _entries(activity_events.AUTH_PASSWORD_RESET_REQUESTED)[0]
            assert entry.context["attempted_email"] == "nobody@gmial.com"
            assert entry.context["account_exists"] is False
            assert entry.context["notification_sent"] is False
            assert entry.subject_user_id is None

    def test_a_reset_request_for_a_real_account_records_the_subject(self, app):
        with app.app_context():
            user = UserFactory(email="resetme@example.com")
            db.session.commit()

            auth_service.request_password_reset("resetme@example.com")

            entry = _entries(activity_events.AUTH_PASSWORD_RESET_REQUESTED)[0]
            assert entry.context["account_exists"] is True
            assert entry.subject_user_id == user.id

    def test_completing_a_reset_is_recorded(self, app):
        with app.app_context():
            user = UserFactory(email="finishreset@example.com")
            token = user.generate_password_reset_token()
            db.session.commit()

            auth_service.reset_password(token, "a-brand-new-password")

            assert _entries(activity_events.AUTH_PASSWORD_RESET_COMPLETED)[0].actor_user_id == (
                user.id
            )
