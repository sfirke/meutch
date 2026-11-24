"""Announcement endpoints for API v1. Creating announcements stays in the web admin."""

from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.operational import mutation_limit, read_limit
from app.api.v1.schemas.announcements import (
    AnnouncementDismissResponseSchema,
    CurrentAnnouncementResponseSchema,
)
from app.models import Announcement
from app.services.exceptions import InvalidActionError
from app.utils.announcements import current_announcement_for, record_dismissal

CURRENT_ANNOUNCEMENT_RESPONSE_SCHEMA = CurrentAnnouncementResponseSchema()
ANNOUNCEMENT_DISMISS_RESPONSE_SCHEMA = AnnouncementDismissResponseSchema()


@bp.get("/announcements/current")
@jwt_required()
@read_limit()
def get_current_announcement():
    """Return the announcement the web banner would show the caller, if any."""
    announcement = current_announcement_for(current_user)
    return CURRENT_ANNOUNCEMENT_RESPONSE_SCHEMA.dump({"announcement": announcement})


@bp.post("/announcements/<uuid:announcement_id>/dismiss")
@jwt_required()
@mutation_limit()
def dismiss_announcement(announcement_id):
    """Dismiss an announcement for the caller. Dismissing twice is fine."""
    announcement = db.get_or_404(Announcement, announcement_id)
    if not announcement.dismissible:
        raise InvalidActionError("This announcement can't be dismissed.")
    record_dismissal(current_user, announcement)
    return ANNOUNCEMENT_DISMISS_RESPONSE_SCHEMA.dump({"dismissed": True})
