"""Request read schemas for API v1."""

from datetime import date

from dateutil.relativedelta import relativedelta
from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.users import UserSummarySchema
from app.models import ItemRequest


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


class RequestWritePayloadSchema(ApiSchema):
    """Write payload for request create and update endpoints."""

    title = fields.String(required=True, validate=validate.Length(max=100))
    description = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=1000),
    )
    expires_at = fields.Date(required=True)
    seeking = fields.String(
        required=True,
        validate=validate.OneOf([choice[0] for choice in ItemRequest.SEEKING_CHOICES]),
    )
    visibility = fields.String(
        required=True,
        validate=validate.OneOf([choice[0] for choice in ItemRequest.VISIBILITY_CHOICES]),
    )

    @validates_schema
    def validate_expires_at(self, data, **kwargs):
        expires_at = data["expires_at"]
        today = date.today()
        max_date = today + relativedelta(months=6)

        if expires_at < today:
            raise ValidationError({"expires_at": ["Expiration date cannot be in the past."]})
        if expires_at > max_date:
            raise ValidationError(
                {"expires_at": ["Expiration date cannot be more than 6 months from today."]}
            )
