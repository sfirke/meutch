"""Schemas for viewing another member's profile."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiSchema
from app.api.v1.schemas.messaging import CircleConversationContextSchema
from app.api.v1.schemas.profile import dump_web_links


class PublicUserProfileSchema(ApiSchema):
    """Profile fields any permitted viewer may see. No email, no items."""

    id = fields.UUID(required=True)
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    full_name = fields.String(required=True)
    profile_image_url = fields.String(allow_none=True)
    about_me = fields.String(allow_none=True)
    web_links = fields.Method("get_web_links")

    def get_web_links(self, user):
        return dump_web_links(user)


class PublicUserProfileResponseSchema(ApiSchema):
    """Wrapper for another member's profile response."""

    user = fields.Nested(PublicUserProfileSchema(), required=True)
    shared_circles = fields.Nested(CircleConversationContextSchema(), many=True, required=True)
    access_reason = fields.String(required=True)
