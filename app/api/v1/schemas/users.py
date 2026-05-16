"""User-focused API schemas."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiSchema


class UserSummarySchema(ApiSchema):
    """Minimal user shape for nested read-side resources."""

    id = fields.UUID(required=True)
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    full_name = fields.String(required=True)
    profile_image_url = fields.String(allow_none=True)
