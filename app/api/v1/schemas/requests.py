"""Request read schemas for API v1."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.users import UserSummarySchema


class RequestConversationMessageSchema(ApiSchema):
    """Minimal message preview for request detail reads."""

    id = fields.UUID(required=True)
    body = fields.String(required=True)
    timestamp = ApiDateTime(required=True)
    is_read = fields.Boolean(required=True)


class RequestConversationSummarySchema(ApiSchema):
    """Conversation preview shown on a request detail for the owner."""

    other_user = fields.Nested(UserSummarySchema(), required=True)
    latest_message = fields.Nested(RequestConversationMessageSchema(), required=True)


class ItemRequestSummarySchema(ApiSchema):
    """Serialized request resource for list and detail reads."""

    id = fields.UUID(required=True)
    title = fields.String(required=True)
    description = fields.String(allow_none=True)
    seeking = fields.String(required=True)
    visibility = fields.String(required=True)
    status = fields.String(required=True)
    expires_at = ApiDateTime(required=True)
    fulfilled_at = ApiDateTime(allow_none=True)
    created_at = ApiDateTime(required=True)
    updated_at = ApiDateTime(required=True)
    user = fields.Nested(UserSummarySchema(), required=True)
    distance = fields.Method("get_distance", allow_none=True)

    def get_distance(self, item_request):
        return getattr(item_request, "api_distance", None)


class ItemRequestDetailResponseSchema(ApiSchema):
    """Wrapper for request detail responses."""

    request = fields.Nested(ItemRequestSummarySchema(), required=True)
    conversations = fields.Nested(RequestConversationSummarySchema(), many=True, required=True)
