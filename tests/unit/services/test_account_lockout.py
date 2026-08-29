"""Unit tests for the failed-login lockout policy in auth_service."""

from datetime import UTC, datetime, timedelta

from app import db
from app.services import auth_service
from conftest import TEST_PASSWORD
from tests.factories import UserFactory

WRONG_PASSWORD = "not-the-right-password"


def _fail_login(email, times=1):
    """Submit `times` failed login attempts and return the last result."""
    result = None
    for _ in range(times):
        result = auth_service.authenticate_user(email, WRONG_PASSWORD)
    return result


def _locked_until_utc(user):
    """Return the user's lockout deadline as an aware UTC datetime."""
    return auth_service._normalize_utc(user.locked_until)


class TestAccountLockout:
    def test_failed_attempts_below_threshold_do_not_lock(self, app):
        with app.app_context():
            user = UserFactory(email="under@example.com")
            db.session.commit()

            result = _fail_login("under@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS - 1)

            assert result.status == auth_service.LOGIN_STATUS_INVALID_CREDENTIALS
            assert user.locked_until is None
            assert user.failed_login_attempts == auth_service.MAX_FAILED_LOGIN_ATTEMPTS - 1

    def test_threshold_reached_locks_the_account(self, app):
        with app.app_context():
            user = UserFactory(email="lockme@example.com")
            db.session.commit()

            _fail_login("lockme@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)

            assert user.locked_until is not None
            assert user.lockout_count == 1
            assert user.failed_login_attempts == 0

    def test_locked_account_reports_locked_after_reload_from_database(self, app):
        """Locking sets `locked_until` to a tz-aware UTC datetime, but the column
        (`db.DateTime`) has no timezone type, so a value read back from the database
        loses its tzinfo and comes back naive. The in-memory object from the request
        that performed the lockout still has the original aware value, so the bug
        only shows up once a *different* request loads the user fresh - which is
        what `db.session.expunge_all()` simulates here.

        Regression test: without `_normalize_utc`, comparing that naive `locked_until`
        against an aware `datetime.now(UTC)` raised TypeError ("can't compare
        offset-naive and offset-aware datetimes"), turning every login attempt against
        a locked account into a 500 instead of a LOCKED response. The assertion below
        is really "this call doesn't raise"; a LOCKED status confirms the lockout
        check still ran to completion rather than short-circuiting some other way.
        """
        with app.app_context():
            UserFactory(email="reload@example.com")
            db.session.commit()

            _fail_login("reload@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
            db.session.expunge_all()  # simulate a later request loading the user fresh from the DB

            result = auth_service.authenticate_user("reload@example.com", WRONG_PASSWORD)

            assert result.status == auth_service.LOGIN_STATUS_LOCKED

    def test_correct_password_is_still_refused_while_locked(self, app):
        with app.app_context():
            UserFactory(email="stilllocked@example.com")
            db.session.commit()

            _fail_login("stilllocked@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
            result = auth_service.authenticate_user("stilllocked@example.com", TEST_PASSWORD)

            assert result.status == auth_service.LOGIN_STATUS_LOCKED

    def test_locked_result_reports_minutes_until_retry(self, app):
        with app.app_context():
            user = UserFactory(email="countdown@example.com")
            db.session.commit()

            _fail_login("countdown@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
            result = auth_service.authenticate_user("countdown@example.com", WRONG_PASSWORD)

            assert result.retry_after_minutes == auth_service.INITIAL_LOCKOUT_MINUTES

            # A deadline a few seconds into the next minute still rounds up, so the
            # user is never told it's safe to retry before the lockout actually lifts.
            user.locked_until = datetime.now(UTC) + timedelta(minutes=1, seconds=1)
            db.session.commit()

            result = auth_service.authenticate_user("countdown@example.com", WRONG_PASSWORD)

            assert result.retry_after_minutes == 2

    def test_successive_lockouts_escalate_then_cap(self, app):
        with app.app_context():
            user = UserFactory(email="escalate@example.com")
            db.session.commit()

            observed = []
            for _ in range(4):
                _fail_login("escalate@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
                remaining = _locked_until_utc(user) - datetime.now(UTC)
                observed.append(round(remaining.total_seconds() / 60))
                # Simulate the lockout window elapsing before the next round.
                user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
                db.session.commit()

            assert observed == [15, 30, 60, 60]
            assert observed[-1] == auth_service.MAX_LOCKOUT_MINUTES

    def test_expired_lockout_allows_a_fresh_attempt(self, app):
        with app.app_context():
            user = UserFactory(email="expired@example.com")
            db.session.commit()

            _fail_login("expired@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
            user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()

            result = auth_service.authenticate_user("expired@example.com", TEST_PASSWORD)

            assert result.status == auth_service.LOGIN_STATUS_SUCCESS

    def test_successful_login_clears_lockout_state(self, app):
        with app.app_context():
            user = UserFactory(email="cleared@example.com")
            db.session.commit()

            _fail_login("cleared@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS)
            user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()

            auth_service.authenticate_user("cleared@example.com", TEST_PASSWORD)

            assert user.failed_login_attempts == 0
            assert user.lockout_count == 0
            assert user.locked_until is None

    def test_successful_login_resets_the_attempt_counter(self, app):
        with app.app_context():
            user = UserFactory(email="reset@example.com")
            db.session.commit()

            _fail_login("reset@example.com", auth_service.MAX_FAILED_LOGIN_ATTEMPTS - 1)
            auth_service.authenticate_user("reset@example.com", TEST_PASSWORD)

            assert user.failed_login_attempts == 0

    def test_unknown_email_does_not_raise(self, app):
        with app.app_context():
            result = auth_service.authenticate_user("nobody@example.com", WRONG_PASSWORD)

            assert result.status == auth_service.LOGIN_STATUS_INVALID_CREDENTIALS

    def test_lockout_minutes_double_up_to_the_cap(self, app):
        with app.app_context():
            assert auth_service._lockout_minutes(1) == auth_service.INITIAL_LOCKOUT_MINUTES
            assert auth_service._lockout_minutes(2) == 30
            assert auth_service._lockout_minutes(3) == auth_service.MAX_LOCKOUT_MINUTES
            assert auth_service._lockout_minutes(9) == auth_service.MAX_LOCKOUT_MINUTES
