from sqlalchemy.dialects.postgresql import insert

from app import db
from app.models import Announcement, AnnouncementDismissal, utc_now_naive


def current_announcement_for(user):
    """The newest active announcement this user has not dismissed, or None."""
    if not user.is_authenticated:
        return None

    now = utc_now_naive()
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


def record_dismissal(user, announcement):
    """Mark the announcement dismissed for this user. Repeat calls are a no-op."""
    db.session.execute(
        insert(AnnouncementDismissal)
        .values(user_id=user.id, announcement_id=announcement.id)
        .on_conflict_do_nothing()
    )
    db.session.commit()
