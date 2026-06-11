"""Authentication API schemas."""

from marshmallow import fields, validate, validates_schema

from app.api.v1.schemas.base import ApiDateTime, ApiSchema, validate_location_method_fields
from app.api.v1.schemas.users import UserIdentitySchema
from app.models import User


class LoginRequestSchema(ApiSchema):
    """Credential payload for API login."""

    email = fields.Email(required=True, validate=validate.Length(max=120))
    password = fields.String(required=True, validate=validate.Length(min=8, max=100))


class RegisterRequestSchema(ApiSchema):
    """Registration payload for API account creation."""

    email = fields.Email(required=True, validate=validate.Length(max=120))
    first_name = fields.String(required=True, validate=validate.Length(max=50))
    last_name = fields.String(required=True, validate=validate.Length(max=50))
    password = fields.String(required=True, validate=validate.Length(min=8, max=100))
    digest_frequency = fields.String(
        load_default=User.DIGEST_FREQUENCY_WEEKLY,
        validate=validate.OneOf(User.DIGEST_FREQUENCY_CHOICES),
    )
    location_method = fields.String(
        required=True,
        validate=validate.OneOf(["address", "coordinates", "skip"]),
    )
    street = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=200))
    city = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    state = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    zip_code = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=20))
    country = fields.String(load_default="USA", allow_none=True, validate=validate.Length(max=100))
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


class EmailRequestSchema(ApiSchema):
    """Single-email payload for confirmation and reset workflows."""

    email = fields.Email(required=True, validate=validate.Length(max=120))


class ResetPasswordRequestSchema(ApiSchema):
    """Password reset payload for API clients."""

    token = fields.String(required=True, validate=validate.Length(min=1, max=128))
    password = fields.String(required=True, validate=validate.Length(min=8, max=100))


class MessageResponseSchema(ApiSchema):
    """Simple message payload for non-resource auth responses."""

    message = fields.String(required=True)


class CurrentUserResponseSchema(ApiSchema):
    """Current-user wrapper for authenticated identity endpoints."""

    user = fields.Nested(UserIdentitySchema(), required=True)


class RegistrationResponseSchema(ApiSchema):
    """Registration result returned to API clients."""

    user = fields.Nested(UserIdentitySchema(), required=True)
    email_confirmation_sent = fields.Boolean(required=True)
    location_method = fields.String(required=True)
    geocoding_failed = fields.Boolean(required=True)


class TokenBundleSchema(ApiSchema):
    """Access and refresh tokens for a single API session."""

    access_token = fields.String(required=True)
    refresh_token = fields.String(required=True)
    token_type = fields.Constant("Bearer")
    access_token_expires_at = ApiDateTime(required=True)
    refresh_token_expires_at = ApiDateTime(required=True)
    user = fields.Nested(UserIdentitySchema(), required=True)
