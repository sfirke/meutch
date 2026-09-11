"""Unit tests for removing accounts that never confirmed their email address."""

from datetime import UTC, datetime, timedelta

from app import db
from app.cli import check_loan_reminders, purge_unconfirmed
from app.models import User
from tests.factories import UserFactory


def _user(*, days_old, confirmed=False, deleted=False):
    user = UserFactory(email_confirmed=confirmed, is_deleted=deleted)
    user.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_old)
    return user


class TestPurgeUnconfirmed:
    def test_removes_only_old_unconfirmed_accounts(self, app, runner):
        with app.app_context():
            stale = _user(days_old=15)
            recent = _user(days_old=13)
            confirmed = _user(days_old=400, confirmed=True)
            admin_deleted = _user(days_old=400, deleted=True)
            db.session.commit()
            stale_email = stale.email
            kept_emails = {recent.email, confirmed.email, admin_deleted.email}

            result = runner.invoke(purge_unconfirmed, [])

            assert result.exit_code == 0
            assert stale_email in result.output
            remaining = {user.email for user in User.query.all()}
            assert stale_email not in remaining
            assert kept_emails <= remaining

    def test_reports_when_there_is_nothing_to_remove(self, app, runner):
        with app.app_context():
            _user(days_old=1)
            db.session.commit()

            result = runner.invoke(purge_unconfirmed, [])

            assert result.exit_code == 0
            assert "No unconfirmed accounts to remove" in result.output

    def test_daily_job_removes_old_unconfirmed_accounts(self, app, runner):
        with app.app_context():
            stale = _user(days_old=15)
            db.session.commit()
            stale_id = stale.id

            result = runner.invoke(check_loan_reminders, [])

            assert result.exit_code == 0, result.output
            assert "Removed 1 unconfirmed account" in result.output
            assert db.session.get(User, stale_id) is None
