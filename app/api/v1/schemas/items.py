"""Item-focused API schemas."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.reference import CategorySchema, TagSchema
from app.api.v1.schemas.users import UserSummarySchema


class ItemSummarySchema(ApiSchema):
    """Compact item representation for list and detail reads."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    available = fields.Boolean(required=True)
    is_giveaway = fields.Boolean(required=True)
    giveaway_visibility = fields.String(allow_none=True)
    claim_status = fields.String(allow_none=True)
    created_at = ApiDateTime(required=True)
    image_url = fields.Method("get_image_url", allow_none=True)
    owner = fields.Nested(UserSummarySchema(), required=True)
    category = fields.Nested(CategorySchema(), required=True)
    tags = fields.Method("get_tags")

    def get_image_url(self, item):
        """Return the lead item image URL when one exists."""
        if not item.images:
            return None

        return item.images[0].url

    def get_tags(self, item):
        """Return tags in a stable display order for API consumers."""
        ordered_tags = sorted(item.tags, key=lambda tag: tag.name.casefold())
        return TagSchema(many=True).dump(ordered_tags)
