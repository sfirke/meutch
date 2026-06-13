"""Query-parameter schemas for API v1 read endpoints."""

from marshmallow import fields, pre_load, validate

from app.api.v1.schemas.base import ApiSchema

DEFAULT_COLLECTION_PER_PAGE = 12
DEFAULT_FEED_PER_PAGE = 20
MAX_COLLECTION_PER_PAGE = 50
FEED_TYPE_CHOICES = ["requests", "giveaways", "circle_joins", "loans"]
FEED_DISTANCE_CHOICES = [5, 10, 20, 25, 50]


class PaginationQuerySchema(ApiSchema):
    """Shared page/per-page query parameters."""

    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(
        load_default=DEFAULT_COLLECTION_PER_PAGE,
        validate=validate.Range(min=1, max=MAX_COLLECTION_PER_PAGE),
    )


class FeedQuerySchema(PaginationQuerySchema):
    """Query parameters for the authenticated activity feed."""

    scope = fields.String(load_default="all", validate=validate.OneOf(["all", "circles"]))
    circles = fields.List(fields.UUID(), load_default=list)
    types = fields.List(
        fields.String(validate=validate.OneOf(FEED_TYPE_CHOICES)),
        load_default=lambda: FEED_TYPE_CHOICES[:],
    )
    distance = fields.Integer(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(FEED_DISTANCE_CHOICES),
    )
    per_page = fields.Integer(
        load_default=DEFAULT_FEED_PER_PAGE,
        validate=validate.Range(min=1, max=MAX_COLLECTION_PER_PAGE),
    )

    @pre_load
    def normalize_distance(self, data, **kwargs):
        if hasattr(data, "copy"):
            mutable_data = data.copy()
        else:
            mutable_data = dict(data)

        if mutable_data.get("distance") == "none":
            mutable_data["distance"] = None

        return mutable_data


class ItemListQuerySchema(PaginationQuerySchema):
    """Query parameters for discoverable item reads."""

    q = fields.String(load_default="")
    categories = fields.List(fields.UUID(), load_default=list)
    circles = fields.List(fields.UUID(), load_default=list)
    item_type = fields.String(
        load_default="both",
        validate=validate.OneOf(["loans", "giveaways", "both"]),
    )
    sort = fields.String(
        load_default="date",
        validate=validate.OneOf(["date", "distance"]),
    )


class CircleListQuerySchema(PaginationQuerySchema):
    """Query parameters for circle list reads."""

    membership = fields.String(
        load_default="discoverable",
        validate=validate.OneOf(["discoverable", "mine"]),
    )
    q = fields.String(load_default="")
    radius = fields.Integer(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=1),
    )


class RequestListQuerySchema(PaginationQuerySchema):
    """Query parameters for visible request reads."""

    scope = fields.String(load_default="all", validate=validate.OneOf(["all", "circles"]))
    circles = fields.List(fields.UUID(), load_default=list)
    distance = fields.Integer(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(FEED_DISTANCE_CHOICES),
    )

    @pre_load
    def normalize_distance(self, data, **kwargs):
        if hasattr(data, "copy"):
            mutable_data = data.copy()
        else:
            mutable_data = dict(data)

        if mutable_data.get("distance") == "none":
            mutable_data["distance"] = None

        return mutable_data


class ConversationListQuerySchema(PaginationQuerySchema):
    """Query parameters for paginated inbox summaries."""

    per_page = fields.Integer(
        load_default=DEFAULT_FEED_PER_PAGE,
        validate=validate.Range(min=1, max=MAX_COLLECTION_PER_PAGE),
    )


class LoanListQuerySchema(PaginationQuerySchema):
    """Query parameters for authenticated loan-activity reads."""

    role = fields.String(
        required=True,
        validate=validate.OneOf(["borrowing", "lending"]),
    )
    status = fields.String(
        load_default="active",
        validate=validate.OneOf(["active", "pending", "all"]),
    )
