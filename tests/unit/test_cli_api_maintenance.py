"""Unit tests for the `flask api` maintenance commands."""

import uuid
from datetime import UTC, datetime, timedelta

from app import db
from app.cli import cleanup_expired_tokens
from app.models import ApiTokenBlocklist
from tests.factories import UserFactory


def _blocklist_entry(user, expires_at):
    entry = ApiTokenBlocklist(
        jti=str(uuid.uuid4()),
        user_id=user.id,
        token_type="access",
        expires_at=expires_at,
    )
    db.session.add(entry)
    return entry


class TestCleanupExpiredTokens:
    def test_removes_only_entries_past_the_cutoff(self, app, runner):
        with app.app_context():
            user = UserFactory()
            now = datetime.now(UTC)

            stale = _blocklist_entry(user, now - timedelta(days=30))
            recent = _blocklist_entry(user, now - timedelta(days=1))
            unexpired = _blocklist_entry(user, now + timedelta(days=1))
            db.session.commit()
            stale_jti, recent_jti, unexpired_jti = stale.jti, recent.jti, unexpired.jti

            result = runner.invoke(cleanup_expired_tokens, ["--older-than-days", "7"])

            assert result.exit_code == 0
            remaining = {entry.jti for entry in ApiTokenBlocklist.query.all()}
            assert stale_jti not in remaining
            assert recent_jti in remaining
            assert unexpired_jti in remaining

    def test_reports_when_there_is_nothing_to_remove(self, app, runner):
        with app.app_context():
            user = UserFactory()
            _blocklist_entry(user, datetime.now(UTC) + timedelta(days=1))
            db.session.commit()

            result = runner.invoke(cleanup_expired_tokens, ["--older-than-days", "7"])

            assert result.exit_code == 0
            assert "No expired token blocklist entries" in result.output

    def test_reports_how_many_entries_were_removed(self, app, runner):
        with app.app_context():
            user = UserFactory()
            _blocklist_entry(user, datetime.now(UTC) - timedelta(days=30))
            db.session.commit()

            result = runner.invoke(cleanup_expired_tokens, ["--older-than-days", "7"])

            assert result.exit_code == 0
            assert "Removed 1 expired token blocklist entry" in result.output
