"""Item-focused API schemas."""

from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import ApiBoolean, ApiDateTime, ApiSchema, ApiUploadedFile
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


class ItemWritePayloadSchema(ApiSchema):
    """Write payload for item create and update endpoints."""

    name = fields.String(required=True, validate=validate.Length(max=100))
    description = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )
    category_id = fields.UUID(required=True)
    tags = fields.List(fields.String(validate=validate.Length(max=50)), load_default=list)
    is_giveaway = ApiBoolean(required=True)
    giveaway_visibility = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["default", "public"]),
    )
    images = fields.List(ApiUploadedFile(), load_default=list)

    @validates_schema
    def validate_giveaway_visibility(self, data, **kwargs):
        if data["is_giveaway"] and not data.get("giveaway_visibility"):
            raise ValidationError(
                {"giveaway_visibility": ["This field is required when is_giveaway is true."]}
            )


class ItemImagesUploadSchema(ApiSchema):
    """Write payload for appending new item images."""

    images = fields.List(ApiUploadedFile(), required=True, validate=validate.Length(min=1))


class ItemImageOrderSchema(ApiSchema):
    """Write payload for reordering item images."""

    image_ids = fields.List(fields.UUID(), required=True, validate=validate.Length(min=1))


class GiveawayInterestCreateSchema(ApiSchema):
    """Write payload for expressing giveaway interest."""

    message = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )


class GiveawayRecipientSelectionSchema(ApiSchema):
    """Write payload for selecting a giveaway recipient."""

    selection_method = fields.String(
        required=True,
        validate=validate.OneOf(["first", "random", "manual"]),
    )
    user_id = fields.UUID(load_default=None, allow_none=True)

    @validates_schema
    def validate_manual_user_id(self, data, **kwargs):
        if data["selection_method"] == "manual" and data.get("user_id") is None:
            raise ValidationError(
                {"user_id": ["This field is required when selection_method is 'manual'."]}
            )


class GiveawayRecipientChangeSchema(ApiSchema):
    """Write payload for changing a giveaway recipient."""

    selection_method = fields.String(
        required=True,
        validate=validate.OneOf(["next", "random", "manual"]),
    )
    user_id = fields.UUID(load_default=None, allow_none=True)

    @validates_schema
    def validate_manual_user_id(self, data, **kwargs):
        if data["selection_method"] == "manual" and data.get("user_id") is None:
            raise ValidationError(
                {"user_id": ["This field is required when selection_method is 'manual'."]}
            )
