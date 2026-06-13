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


class ItemWriteBaseSchema(ApiSchema):
    """Shared fields for item create and update payloads."""

    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    description = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )
    category_id = fields.UUID(required=True)
    tags = fields.List(fields.String(validate=validate.Length(min=1, max=50)), load_default=list)
    is_giveaway = ApiBoolean(required=True)
    giveaway_visibility = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["default", "public"]),
    )

    @validates_schema
    def validate_giveaway_visibility(self, data, **kwargs):
        if data["is_giveaway"] and not data.get("giveaway_visibility"):
            raise ValidationError(
                {"giveaway_visibility": ["This field is required when is_giveaway is true."]}
            )


class ItemWritePayloadSchema(ItemWriteBaseSchema):
    """Write payload for item create endpoints."""

    images = fields.List(ApiUploadedFile(), load_default=list)


class ItemUpdatePayloadSchema(ItemWriteBaseSchema):
    """Write payload for item update endpoints."""


class ItemImagesUploadSchema(ApiSchema):
    """Write payload for appending new item images."""

    images = fields.List(ApiUploadedFile(), required=True, validate=validate.Length(min=1))


class ItemImageOrderSchema(ApiSchema):
    """Write payload for reordering item images."""

    image_ids = fields.List(fields.UUID(), required=True, validate=validate.Length(min=1))


class ItemDeleteResponseSchema(ApiSchema):
    """Response payload for item deletion."""

    deleted = fields.Boolean(required=True)
    item_id = fields.UUID(required=True)


class GiveawayInterestCreateSchema(ApiSchema):
    """Write payload for expressing giveaway interest."""

    message = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )


def _validate_manual_selection_user_id(data):
    if data["selection_method"] == "manual" and data.get("user_id") is None:
        raise ValidationError(
            {"user_id": ["This field is required when selection_method is 'manual'."]}
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
        _validate_manual_selection_user_id(data)


class GiveawayRecipientChangeSchema(ApiSchema):
    """Write payload for changing a giveaway recipient."""

    selection_method = fields.String(
        required=True,
        validate=validate.OneOf(["next", "random", "manual"]),
    )
    user_id = fields.UUID(load_default=None, allow_none=True)

    @validates_schema
    def validate_manual_user_id(self, data, **kwargs):
        _validate_manual_selection_user_id(data)


class GiveawayInterestItemStateSchema(ApiSchema):
    """Minimal giveaway state returned by interest-management endpoints."""

    id = fields.UUID(required=True)
    claim_status = fields.String(allow_none=True)
    claimed_by = fields.Method("get_claimed_by", allow_none=True)
    interested_count = fields.Method("get_interested_count")

    def get_claimed_by(self, item):
        return item.claimed_by_id

    def get_interested_count(self, item):
        return item.api_interest_pool_count


class GiveawayInterestActionsSchema(ApiSchema):
    """Allowed giveaway-recipient actions for the current owner state."""

    select_recipient = fields.Boolean(required=True)
    change_recipient = fields.Boolean(required=True)
    release_to_all = fields.Boolean(required=True)
    confirm_handoff = fields.Boolean(required=True)


class GiveawayInterestSummarySchema(ApiSchema):
    """Owner-facing giveaway interest summary with thread metadata."""

    id = fields.UUID(required=True)
    status = fields.String(required=True)
    created_at = ApiDateTime(required=True)
    message = fields.String(allow_none=True)
    user = fields.Nested(UserSummarySchema(), required=True)
    conversation_message_id = fields.Method("get_conversation_message_id", allow_none=True)
    unread_count = fields.Method("get_unread_count")
    message_count = fields.Method("get_message_count")

    def get_conversation_message_id(self, interest):
        return getattr(interest, "api_conversation_message_id", None)

    def get_unread_count(self, interest):
        return getattr(interest, "api_unread_count", 0)

    def get_message_count(self, interest):
        return getattr(interest, "api_message_count", 0)


class GiveawayInterestCollectionResponseSchema(ApiSchema):
    """Owner-only giveaway interest-management read payload."""

    item = fields.Nested(GiveawayInterestItemStateSchema(), required=True)
    actions = fields.Nested(GiveawayInterestActionsSchema(), required=True)
    interests = fields.Nested(GiveawayInterestSummarySchema(), many=True, required=True)


class GiveawayInterestResponseSchema(ApiSchema):
    """Minimal giveaway-interest payload returned by mutation endpoints."""

    id = fields.UUID(required=True)
    status = fields.String(required=True)
    created_at = ApiDateTime(required=True)
    message = fields.String(allow_none=True)
    user = fields.Nested(UserSummarySchema(), required=True)


class GiveawayInterestMutationResponseSchema(ApiSchema):
    """Response for expressing interest in a giveaway."""

    interest = fields.Nested(GiveawayInterestResponseSchema(), required=True)
    item = fields.Nested(ItemDetailSchema(), required=True)


class GiveawayInterestWithdrawResponseSchema(ApiSchema):
    """Response for withdrawing giveaway interest."""

    withdrawn = fields.Boolean(required=True)
    item = fields.Nested(ItemDetailSchema(), required=True)


class GiveawayRecipientMutationResponseSchema(ApiSchema):
    """Response for owner-side recipient selection mutations."""

    item = fields.Nested(ItemDetailSchema(), required=True)
    selected_interest = fields.Nested(GiveawayInterestResponseSchema(), required=True)


class GiveawayItemResponseSchema(ApiSchema):
    """Response for giveaway item state transitions without interest payloads."""

    item = fields.Nested(ItemDetailSchema(), required=True)
