"""Tests for picking which announcement banner a user sees."""

from datetime import UTC, datetime, timedelta

from flask_login import AnonymousUserMixin

from app.models import Announcement
from app.utils.announcements import current_announcement_for
from tests.factories import AnnouncementDismissalFactory, AnnouncementFactory, UserFactory


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


class TestCurrentAnnouncementFor:
    def test_anonymous_user_gets_none(self, db_session):
        AnnouncementFactory()
        db_session.commit()

        assert current_announcement_for(AnonymousUserMixin()) is None

    def test_returns_active_announcement_with_no_end(self, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory(ends_at=None)
        db_session.commit()

        assert current_announcement_for(user) == announcement

    def test_excludes_future_start(self, db_session):
        user = UserFactory()
        AnnouncementFactory(starts_at=_now() + timedelta(hours=1))
        db_session.commit()

        assert current_announcement_for(user) is None

    def test_excludes_past_end(self, db_session):
        user = UserFactory()
        AnnouncementFactory(ends_at=_now() - timedelta(seconds=1))
        db_session.commit()

        assert current_announcement_for(user) is None

    def test_dismissal_hides_it_only_for_that_user(self, db_session):
        user = UserFactory()
        other_user = UserFactory()
        announcement = AnnouncementFactory()
        AnnouncementDismissalFactory(user=user, announcement=announcement)
        db_session.commit()

        assert current_announcement_for(user) is None
        assert current_announcement_for(other_user) == announcement

    def test_returns_newest_then_next_after_dismissal(self, db_session):
        user = UserFactory()
        older = AnnouncementFactory(starts_at=_now() - timedelta(days=2))
        newer = AnnouncementFactory(starts_at=_now() - timedelta(days=1))
        db_session.commit()

        assert current_announcement_for(user) == newer

        AnnouncementDismissalFactory(user=user, announcement=newer)
        db_session.commit()

        assert current_announcement_for(user) == older


class TestAnnouncementStatus:
    def test_statuses(self, db_session):
        now = _now()
        scheduled = AnnouncementFactory(starts_at=now + timedelta(days=1))
        active = AnnouncementFactory()
        ended = AnnouncementFactory(ends_at=now - timedelta(minutes=1))
        ended_before_start = AnnouncementFactory(
            starts_at=now + timedelta(days=1), ends_at=now - timedelta(minutes=1)
        )
        db_session.commit()

        assert scheduled.status == Announcement.STATUS_SCHEDULED
        assert active.status == Announcement.STATUS_ACTIVE
        assert active.is_active
        assert ended.status == Announcement.STATUS_ENDED
        assert ended_before_start.status == Announcement.STATUS_ENDED
