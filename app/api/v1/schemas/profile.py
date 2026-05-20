"""Current-user profile and settings schemas for API v1."""

from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import (
    ApiBoolean,
    ApiDateTime,
    ApiSchema,
    ApiUploadedFile,
    validate_location_method_fields,
)
from app.api.v1.schemas.users import UserIdentitySchema
from app.models import User, UserWebLink


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


class UserWebLinkWriteSchema(ApiSchema):
    """Write payload for an ordered external profile link."""

    platform = fields.String(
        required=True,
        validate=validate.OneOf([choice[0] for choice in UserWebLink.PLATFORM_CHOICES]),
    )
    custom_name = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=50),
    )
    url = fields.Url(required=True, validate=validate.Length(max=500))

    @validates_schema
    def validate_custom_name(self, data, **kwargs):
        if data["platform"] == "other":
            custom_name = data.get("custom_name")
            if custom_name is None or not custom_name.strip():
                raise ValidationError(
                    {"custom_name": ['This field is required when platform is "other".']}
                )


class ProfileUpdateSchema(ApiSchema):
    """Write payload for the authenticated user's profile."""

    about_me = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )
    delete_image = ApiBoolean(load_default=False)
    profile_image = ApiUploadedFile(load_default=None, allow_none=True)
    links = fields.List(fields.Nested(UserWebLinkWriteSchema()), load_default=list)


class SettingsUpdateSchema(ApiSchema):
    """Write payload for digest settings and vacation mode."""

    vacation_mode = ApiBoolean(required=True)
    digest_frequency = fields.String(
        required=True,
        validate=validate.OneOf(User.DIGEST_FREQUENCY_CHOICES),
    )
    digest_radius_miles = fields.Integer(required=True, validate=validate.Range(min=1, max=50))
    digest_include_giveaways = ApiBoolean(required=True)
    digest_include_requests = ApiBoolean(required=True)
    digest_include_circle_joins = ApiBoolean(required=True)
    digest_include_loans = ApiBoolean(required=True)
    digest_giveaways_include_public = ApiBoolean(required=True)
    digest_requests_include_public = ApiBoolean(required=True)


class LocationUpdateSchema(ApiSchema):
    """Write payload for the authenticated user's location."""

    location_method = fields.String(
        required=True,
        validate=validate.OneOf(["address", "coordinates", "remove"]),
    )
    street = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=200))
    city = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    state = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    zip_code = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=20),
    )
    country = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=100),
    )
    latitude = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=-90, max=90),
    )
    longitude = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=-180, max=180),
    )

    @validates_schema
    def validate_location_fields(self, data, **kwargs):
        validate_location_method_fields(data)


class DeleteAccountSchema(ApiSchema):
    """Write payload for confirmed account deletion."""

    confirmation = fields.String(required=True, validate=validate.Length(max=50))

    @validates_schema
    def validate_confirmation(self, data, **kwargs):
        if data["confirmation"] != "DELETE MY ACCOUNT":
            raise ValidationError(
                {"confirmation": ['You must type "DELETE MY ACCOUNT" exactly to confirm deletion.']}
            )
