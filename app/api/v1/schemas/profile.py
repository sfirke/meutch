"""Current-user profile and settings schemas for API v1."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.users import UserIdentitySchema


class UserWebLinkSchema(ApiSchema):
    """Serialized external profile link for a user."""

    id = fields.UUID(required=True)
    platform_type = fields.String(required=True)
    platform_name = fields.String(allow_none=True)
    display_name = fields.String(required=True)
    url = fields.String(required=True)
    display_order = fields.Integer(required=True)


_USER_WEB_LINKS_SCHEMA = UserWebLinkSchema(many=True)


class UserProfileSchema(UserIdentitySchema):
    """Expanded authenticated-user profile data."""

    about_me = fields.String(allow_none=True)
    created_at = ApiDateTime(required=True)
    has_location = fields.Method("get_has_location")
    geocoding_failed = fields.Boolean(required=True)
    web_links = fields.Method("get_web_links")

    def get_has_location(self, user):
        """Return whether the user has a saved geocoded location."""
        return user.is_geocoded

    def get_web_links(self, user):
        """Return ordered external links for the profile."""
        ordered_links = sorted(user.web_links, key=lambda link: link.display_order)
        return _USER_WEB_LINKS_SCHEMA.dump(ordered_links)


class CurrentUserProfileResponseSchema(ApiSchema):
    """Wrapper for the authenticated user's profile response."""

    user = fields.Nested(UserProfileSchema(), required=True)


class UserSettingsSchema(ApiSchema):
    """Current-user account settings exposed to API clients."""

    vacation_mode = fields.Boolean(required=True)
    digest_frequency = fields.String(required=True)
    digest_radius_miles = fields.Integer(required=True)
    digest_include_giveaways = fields.Boolean(required=True)
    digest_include_requests = fields.Boolean(required=True)
    digest_include_circle_joins = fields.Boolean(required=True)
    digest_include_loans = fields.Boolean(required=True)
    digest_giveaways_include_public = fields.Boolean(required=True)
    digest_requests_include_public = fields.Boolean(required=True)


class CurrentUserSettingsResponseSchema(ApiSchema):
    """Wrapper for the authenticated user's settings response."""

    settings = fields.Nested(UserSettingsSchema(), required=True)
