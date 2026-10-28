from datetime import UTC, datetime

from app import db
from app.models import Announcement, AnnouncementDismissal


def current_announcement_for(user):
    """The newest active announcement this user has not dismissed, or None."""
    if not user.is_authenticated:
        return None

    now = datetime.now(UTC).replace(tzinfo=None)
    dismissed = (
        db.select(AnnouncementDismissal.announcement_id)
        .where(
            AnnouncementDismissal.announcement_id == Announcement.id,
            AnnouncementDismissal.user_id == user.id,
        )
        .exists()
    )
    return db.session.scalars(
        db.select(Announcement)
        .where(Announcement.active_clause(now), ~dismissed)
        .order_by(Announcement.starts_at.desc(), Announcement.id.desc())
        .limit(1)
    ).first()
