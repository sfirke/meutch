"""Current-user profile and settings endpoints for API v1."""

from flask_jwt_extended import jwt_required

from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.schemas.profile import (
    CurrentUserProfileResponseSchema,
    CurrentUserSettingsResponseSchema,
)

CURRENT_USER_PROFILE_RESPONSE_SCHEMA = CurrentUserProfileResponseSchema()
CURRENT_USER_SETTINGS_RESPONSE_SCHEMA = CurrentUserSettingsResponseSchema()


@bp.get("/me/profile")
@jwt_required()
def get_current_user_profile():
    """Return the authenticated user's profile details."""
    return CURRENT_USER_PROFILE_RESPONSE_SCHEMA.dump({"user": current_user})


@bp.get("/me/settings")
@jwt_required()
def get_current_user_settings():
    """Return the authenticated user's current account settings."""
    return CURRENT_USER_SETTINGS_RESPONSE_SCHEMA.dump({"settings": current_user})
