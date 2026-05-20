"""Feed activity schemas for API v1."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema


class FeedEventSchema(ApiSchema):
    """Serialized activity event for the authenticated home feed."""

    event_type = fields.String(required=True)
    created_at = ApiDateTime(required=True)
    title = fields.String(required=True)
    description = fields.String(allow_none=True)
    action = fields.String(required=True)
    actor_name = fields.String(required=True)
    actor_avatar_url = fields.String(allow_none=True)
    image_url = fields.String(allow_none=True)
    distance = fields.String(allow_none=True)
    item_id = fields.UUID(allow_none=True)
    request_id = fields.UUID(allow_none=True)
    loan_request_id = fields.UUID(allow_none=True)
    circle_id = fields.UUID(allow_none=True)
    user_id = fields.UUID(allow_none=True)
    status = fields.String(allow_none=True)
    claim_status = fields.String(allow_none=True)
    extra_circle_count = fields.Integer(allow_none=True)
