"""Schemas for viewing another member's profile."""

from marshmallow import fields, validate

from app.api.v1.schemas.base import ApiSchema
from app.api.v1.schemas.messaging import CircleConversationContextSchema
from app.api.v1.schemas.profile import UserWebLinkSchema
from app.utils.profile_visibility import (
    PROFILE_ACCESS_ADMIN,
    PROFILE_ACCESS_CIRCLE,
    PROFILE_ACCESS_CONVERSATION,
    PROFILE_ACCESS_JOIN_REQUEST,
    PROFILE_ACCESS_SELF,
)

_USER_WEB_LINKS_SCHEMA = UserWebLinkSchema(many=True)


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
        """Return external links in display order."""
        ordered_links = sorted(user.web_links, key=lambda link: link.display_order)
        return _USER_WEB_LINKS_SCHEMA.dump(ordered_links)


class PublicUserProfileResponseSchema(ApiSchema):
    """Wrapper for another member's profile response."""

    user = fields.Nested(PublicUserProfileSchema(), required=True)
    shared_circles = fields.Nested(CircleConversationContextSchema(), many=True, required=True)
    access_reason = fields.String(
        required=True,
        validate=validate.OneOf(
            [
                PROFILE_ACCESS_SELF,
                PROFILE_ACCESS_ADMIN,
                PROFILE_ACCESS_CIRCLE,
                PROFILE_ACCESS_CONVERSATION,
                PROFILE_ACCESS_JOIN_REQUEST,
            ]
        ),
    )
