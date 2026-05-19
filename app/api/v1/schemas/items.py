"""Item-focused API schemas."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.reference import CategorySchema, TagSchema
from app.api.v1.schemas.users import UserSummarySchema

_tag_schema = TagSchema(many=True)


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
        return _tag_schema.dump(ordered_tags)


class ItemImageSchema(ApiSchema):
    """Serialized image metadata for item detail reads."""

    id = fields.UUID(required=True)
    url = fields.String(required=True)
    position = fields.Integer(required=True)
    created_at = ApiDateTime(required=True)


class LoanSummarySchema(ApiSchema):
    """Minimal loan representation nested in item detail reads."""

    id = fields.UUID(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    status = fields.String(required=True)
    borrower = fields.Nested(UserSummarySchema(), allow_none=True)


class ItemDetailSchema(ItemSummarySchema):
    """Expanded item representation for detail reads."""

    images = fields.Nested(ItemImageSchema(), many=True, required=True)
    claimed_by = fields.Nested(UserSummarySchema(), allow_none=True)
    current_loan = fields.Nested(LoanSummarySchema(), allow_none=True)
    viewer_interest_status = fields.Method("get_viewer_interest_status", allow_none=True)
    interested_count = fields.Method("get_interested_count", allow_none=True)

    def get_viewer_interest_status(self, item):
        """Return the viewer's current giveaway-interest state when relevant."""
        return getattr(item, "api_viewer_interest_status", None)

    def get_interested_count(self, item):
        """Return the owner's active interest count when relevant."""
        return getattr(item, "api_interested_count", None)


class ItemViewerStateSchema(ApiSchema):
    """Viewer-specific item access metadata."""

    is_owner = fields.Boolean(required=True)
    shares_circle_with_owner = fields.Boolean(required=True)
    is_active_borrower = fields.Boolean(required=True)


class ItemDetailResponseSchema(ApiSchema):
    """Wrapper for item detail reads."""

    item = fields.Nested(ItemDetailSchema(), required=True)
    viewer = fields.Nested(ItemViewerStateSchema(), required=True)
