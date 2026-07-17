"""Messaging read schemas for API v1."""

from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.items import LoanSummarySchema
from app.api.v1.schemas.users import UserSummarySchema


class MessageSummarySchema(ApiSchema):
    """Serialized message for inbox summaries and thread reads."""

    id = fields.UUID(required=True)
    body = fields.String(required=True)
    timestamp = ApiDateTime(required=True)
    is_read = fields.Boolean(required=True)
    sender = fields.Nested(UserSummarySchema(), required=True)
    recipient = fields.Nested(UserSummarySchema(), required=True)


class ItemConversationContextSchema(ApiSchema):
    """Minimal item context for a conversation."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    image_url = fields.Method("get_image_url", allow_none=True)

    def get_image_url(self, item):
        if not item.images:
            return None
        return item.images[0].url


class ItemRequestConversationContextSchema(ApiSchema):
    """Minimal request context for a conversation."""

    id = fields.UUID(required=True)
    title = fields.String(required=True)
    status = fields.String(required=True)
    visibility = fields.String(required=True)
    expires_at = ApiDateTime(allow_none=True)


class CircleConversationContextSchema(ApiSchema):
    """Minimal circle context for a conversation."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    circle_type = fields.String(required=True)
    image_url = fields.String(allow_none=True)


class ConversationSummarySchema(ApiSchema):
    """Inbox conversation summary for list reads."""

    conversation_id = fields.String(required=True)
    other_user = fields.Nested(UserSummarySchema(), required=True)
    latest_message = fields.Nested(MessageSummarySchema(), required=True)
    unread_count = fields.Integer(required=True)
    is_archived = fields.Boolean(required=True)
    item = fields.Nested(ItemConversationContextSchema(), allow_none=True)
    item_request = fields.Nested(ItemRequestConversationContextSchema(), allow_none=True)
    circle = fields.Nested(CircleConversationContextSchema(), allow_none=True)


class MessageThreadResponseSchema(ApiSchema):
    """Conversation thread payload for a specific message anchor."""

    conversation_id = fields.String(required=True)
    other_user = fields.Nested(UserSummarySchema(), required=True)
    shared_circles = fields.Nested(CircleConversationContextSchema(), many=True, required=True)
    item = fields.Nested(ItemConversationContextSchema(), allow_none=True)
    item_request = fields.Nested(ItemRequestConversationContextSchema(), allow_none=True)
    circle = fields.Nested(CircleConversationContextSchema(), allow_none=True)
    active_loan = fields.Nested(LoanSummarySchema(), allow_none=True)
    has_unread_messages = fields.Boolean(required=True)
    messages = fields.Nested(MessageSummarySchema(), many=True, required=True)


class MessageResponseSchema(ApiSchema):
    """Wrapper for message create and reply responses."""

    message = fields.Nested(MessageSummarySchema(), required=True)


class MessageMarkReadResponseSchema(ApiSchema):
    """Response for explicit message-thread read-state mutations."""

    has_unread_messages = fields.Boolean(required=True)


class MessageStartSchema(ApiSchema):
    """Write payload for starting an item or request conversation."""

    body = fields.String(required=True, validate=validate.Length(min=1, max=1000))
    item_id = fields.UUID(load_default=None, allow_none=True)
    request_id = fields.UUID(load_default=None, allow_none=True)

    @validates_schema
    def validate_target(self, data, **kwargs):
        has_item_id = data.get("item_id") is not None
        has_request_id = data.get("request_id") is not None
        if has_item_id == has_request_id:
            raise ValidationError(
                {
                    "item_id": ["Provide exactly one of item_id or request_id."],
                    "request_id": ["Provide exactly one of item_id or request_id."],
                }
            )


class MessageReplySchema(ApiSchema):
    """Write payload for replying inside an existing conversation."""

    body = fields.String(required=True, validate=validate.Length(min=1, max=1000))
