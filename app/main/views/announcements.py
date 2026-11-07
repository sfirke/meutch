from urllib.parse import urlsplit
from uuid import UUID

from flask import abort, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.dialects.postgresql import insert

from app import db
from app.forms import EmptyForm
from app.main import bp as main_bp
from app.models import Announcement, AnnouncementDismissal
from app.utils.safe_redirect import is_safe_url


def _same_site_referrer():
    """The referring page as a local path, or None if it is missing or off-site."""
    if not request.referrer:
        return None
    parsed = urlsplit(request.referrer)
    if parsed.netloc != request.host:
        return None
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return target if is_safe_url(target) else None


@main_bp.route("/announcements/<uuid:announcement_id>/dismiss", methods=["POST"])
@login_required
def dismiss_announcement(announcement_id: UUID):
    announcement = db.get_or_404(Announcement, announcement_id)
    if not EmptyForm().validate_on_submit():
        abort(400)
    if not announcement.dismissible:
        abort(400)

    db.session.execute(
        insert(AnnouncementDismissal)
        .values(user_id=current_user.id, announcement_id=announcement.id)
        .on_conflict_do_nothing()
    )
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return {"dismissed": True}
    return redirect(_same_site_referrer() or url_for("main.index"))
