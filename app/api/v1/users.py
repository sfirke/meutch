"""Member profile endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.operational import read_limit
from app.api.v1.schemas.user_profiles import PublicUserProfileResponseSchema
from app.models import User
from app.utils.profile_visibility import PROFILE_ACCESS_SELF, profile_access_reason

PUBLIC_USER_PROFILE_RESPONSE_SCHEMA = PublicUserProfileResponseSchema()


@bp.get("/users/<uuid:user_id>")
@jwt_required()
@read_limit()
def get_user_profile(user_id):
    """Return another member's profile, or 404 when the viewer may not see it."""
    user = db.session.get(User, user_id)
    access_reason = profile_access_reason(current_user, user)
    if access_reason is None:
        abort(404)

    shared_circles = (
        [] if access_reason == PROFILE_ACCESS_SELF else current_user.shared_circles_with(user)
    )
    return PUBLIC_USER_PROFILE_RESPONSE_SCHEMA.dump(
        {"user": user, "shared_circles": shared_circles, "access_reason": access_reason}
    )
