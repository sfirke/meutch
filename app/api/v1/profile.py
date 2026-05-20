"""Current-user profile and settings endpoints for API v1."""

import logging

from flask_jwt_extended import get_jwt, jwt_required

from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_request_data
from app.api.v1.schemas.profile import (
    CurrentUserProfileResponseSchema,
    CurrentUserSettingsResponseSchema,
    DeleteAccountResponseSchema,
    DeleteAccountSchema,
    LocationUpdateResponseSchema,
    LocationUpdateSchema,
    ProfileUpdateResponseSchema,
    ProfileUpdateSchema,
    SettingsUpdateSchema,
)
from app.services import account_service, api_token_service, location_service, profile_service

logger = logging.getLogger(__name__)

CURRENT_USER_PROFILE_RESPONSE_SCHEMA = CurrentUserProfileResponseSchema()
CURRENT_USER_SETTINGS_RESPONSE_SCHEMA = CurrentUserSettingsResponseSchema()
PROFILE_UPDATE_REQUEST_SCHEMA = ProfileUpdateSchema()
PROFILE_UPDATE_RESPONSE_SCHEMA = ProfileUpdateResponseSchema()
SETTINGS_UPDATE_REQUEST_SCHEMA = SettingsUpdateSchema()
LOCATION_UPDATE_REQUEST_SCHEMA = LocationUpdateSchema()
LOCATION_UPDATE_RESPONSE_SCHEMA = LocationUpdateResponseSchema()
DELETE_ACCOUNT_REQUEST_SCHEMA = DeleteAccountSchema()
DELETE_ACCOUNT_RESPONSE_SCHEMA = DeleteAccountResponseSchema()


def _serialize_existing_links(user):
    return [
        {
            "platform": link.platform_type,
            "custom_name": link.platform_name,
            "url": link.url,
        }
        for link in sorted(user.web_links, key=lambda user_link: user_link.display_order)
    ]


@bp.get("/me/profile")
@jwt_required()
def get_current_user_profile():
    """Return the authenticated user's profile details."""
    return CURRENT_USER_PROFILE_RESPONSE_SCHEMA.dump({"user": current_user})


@bp.patch("/me/profile")
@jwt_required()
def update_current_user_profile():
    """Update the authenticated user's profile details."""
    data = load_request_data(PROFILE_UPDATE_REQUEST_SCHEMA)
    profile_result = profile_service.update_profile(
        current_user,
        about_me=data.get("about_me", current_user.about_me),
        links=data.get("links", _serialize_existing_links(current_user)),
        profile_image=data.get("profile_image"),
        delete_image=data["delete_image"],
    )
    return PROFILE_UPDATE_RESPONSE_SCHEMA.dump(
        {
            "user": current_user,
            "image_upload_failed": profile_result.image_upload_failed,
        }
    )


@bp.get("/me/settings")
@jwt_required()
def get_current_user_settings():
    """Return the authenticated user's current account settings."""
    return CURRENT_USER_SETTINGS_RESPONSE_SCHEMA.dump({"settings": current_user})


@bp.patch("/me/settings")
@jwt_required()
def update_current_user_settings():
    """Update the authenticated user's digest and vacation settings."""
    data = load_request_data(SETTINGS_UPDATE_REQUEST_SCHEMA)
    profile_service.update_digest_settings(
        current_user,
        vacation_mode=data["vacation_mode"],
        digest_frequency=data["digest_frequency"],
        digest_radius_miles=data["digest_radius_miles"],
        digest_include_giveaways=data["digest_include_giveaways"],
        digest_include_requests=data["digest_include_requests"],
        digest_include_circle_joins=data["digest_include_circle_joins"],
        digest_include_loans=data["digest_include_loans"],
        digest_giveaways_include_public=data["digest_giveaways_include_public"],
        digest_requests_include_public=data["digest_requests_include_public"],
    )
    return CURRENT_USER_SETTINGS_RESPONSE_SCHEMA.dump({"settings": current_user})


@bp.patch("/me/location")
@jwt_required()
def update_current_user_location():
    """Update or remove the authenticated user's location."""
    data = load_request_data(LOCATION_UPDATE_REQUEST_SCHEMA)
    status = location_service.update_user_location(current_user, **data)
    return LOCATION_UPDATE_RESPONSE_SCHEMA.dump(
        {
            "status": status,
            "user": {
                "has_location": current_user.is_geocoded,
                "geocoding_failed": current_user.geocoding_failed,
            },
        }
    )


@bp.delete("/me")
@jwt_required()
def delete_current_user_account():
    """Delete the authenticated user's account and revoke the active session."""
    load_request_data(DELETE_ACCOUNT_REQUEST_SCHEMA)
    account_service.delete_user_account(current_user)

    try:
        api_token_service.revoke_token_family(get_jwt())
    except Exception:
        logger.error("Token revocation failed after account deletion for user %s", current_user.id)

    return DELETE_ACCOUNT_RESPONSE_SCHEMA.dump({"deleted": True})
