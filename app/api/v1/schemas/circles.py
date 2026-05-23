"""Circle read and write schemas for API v1."""

from marshmallow import fields, validate, validates_schema

from app.api.v1.schemas.base import (
    ApiBoolean,
    ApiDateTime,
    ApiSchema,
    ApiUploadedFile,
    LocationFieldsMixin,
    validate_location_method_fields,
)
from app.api.v1.schemas.users import UserSummarySchema


class PendingJoinRequestSchema(ApiSchema):
    """Current-user pending join request for a circle."""

    id = fields.UUID(required=True)
    message = fields.String(allow_none=True)
    status = fields.String(required=True)
    created_at = ApiDateTime(required=True)


class CircleMemberSummarySchema(ApiSchema):
    """Circle membership metadata for detail reads."""

    user = fields.Nested(UserSummarySchema(), required=True)
    joined_at = ApiDateTime(required=True)
    is_admin = fields.Boolean(required=True)


_PENDING_JOIN_REQUEST_SCHEMA = PendingJoinRequestSchema()
_CIRCLE_MEMBER_SUMMARY_SCHEMA = CircleMemberSummarySchema(many=True)


class CircleSummarySchema(ApiSchema):
    """Serialized circle summary for list and detail reads."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    circle_type = fields.String(required=True)
    created_at = ApiDateTime(required=True)
    image_url = fields.String(allow_none=True)
    requires_join_approval = fields.Boolean(required=True)
    member_count = fields.Method("get_member_count")
    is_member = fields.Method("get_is_member")
    is_admin = fields.Method("get_is_admin")
    has_pending_join_request = fields.Method("get_has_pending_join_request")
    pending_join_request_count = fields.Method("get_pending_join_request_count")
    distance_miles = fields.Method("get_distance_miles", allow_none=True)

    def get_member_count(self, circle):
        return len(circle.members)

    def get_is_member(self, circle):
        return getattr(circle, "api_is_member", False)

    def get_is_admin(self, circle):
        return getattr(circle, "api_is_admin", False)

    def get_has_pending_join_request(self, circle):
        return getattr(circle, "api_pending_join_request", None) is not None

    def get_pending_join_request_count(self, circle):
        return getattr(circle, "api_pending_join_request_count", 0)

    def get_distance_miles(self, circle):
        distance = getattr(circle, "api_distance_miles", None)
        if distance is None:
            return None
        return round(distance, 2)


class CircleDetailSchema(CircleSummarySchema):
    """Expanded circle representation for detail reads."""

    can_view_members = fields.Method("get_can_view_members")
    is_last_member = fields.Method("get_is_last_member")
    pending_join_request = fields.Method("get_pending_join_request", allow_none=True)
    members = fields.Method("get_members")

    def get_can_view_members(self, circle):
        return getattr(circle, "api_can_view_members", False)

    def get_is_last_member(self, circle):
        return getattr(circle, "api_is_last_member", False)

    def get_pending_join_request(self, circle):
        pending_request = getattr(circle, "api_pending_join_request", None)
        if pending_request is None:
            return None
        return _PENDING_JOIN_REQUEST_SCHEMA.dump(pending_request)

    def get_members(self, circle):
        return _CIRCLE_MEMBER_SUMMARY_SCHEMA.dump(getattr(circle, "api_members", []))


class CircleDetailResponseSchema(ApiSchema):
    """Wrapper for circle detail responses."""

    circle = fields.Nested(CircleDetailSchema(), required=True)


class CircleMutationResponseSchema(ApiSchema):
    """Response for circle create and update mutations."""

    circle = fields.Nested(CircleDetailSchema(), required=True)
    geocoding_failed = fields.Boolean(required=True)
    image_removed = fields.Boolean(required=True)
    image_updated = fields.Boolean(required=True)


class CircleWritePayloadSchema(LocationFieldsMixin, ApiSchema):
    """Write payload for circle create and update endpoints."""

    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    description = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )
    circle_type = fields.String(
        required=True,
        validate=validate.OneOf(["open", "closed", "secret"]),
    )
    delete_image = ApiBoolean(load_default=False)
    image = ApiUploadedFile(load_default=None, allow_none=True)
    location_method = fields.String(
        required=True,
        validate=validate.OneOf(["address", "coordinates", "skip"]),
    )

    @validates_schema
    def validate_location_fields(self, data, **kwargs):
        validate_location_method_fields(data)


class CircleJoinRequestCreateSchema(ApiSchema):
    """Write payload for submitting a circle join request."""

    message = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=500),
    )


class CircleJoinResponseSchema(ApiSchema):
    """Response after a join or join-request mutation."""

    membership_status = fields.String(
        required=True,
        validate=validate.OneOf(["member", "pending"]),
    )
    join_request = fields.Nested(PendingJoinRequestSchema(), allow_none=True, required=True)


class CircleJoinRequestStatusSchema(ApiSchema):
    """Minimal join-request status payload for admin actions."""

    id = fields.UUID(required=True)
    status = fields.String(required=True)


class CircleJoinRequestActionResponseSchema(ApiSchema):
    """Response after approving or rejecting a join request."""

    action = fields.String(required=True, validate=validate.OneOf(["approve", "reject"]))
    join_request = fields.Nested(CircleJoinRequestStatusSchema(), required=True)


class CircleCancelJoinRequestResponseSchema(ApiSchema):
    """Response after canceling a pending join request."""

    canceled = fields.Boolean(required=True)


class CircleLeaveResponseSchema(ApiSchema):
    """Response after leaving a circle."""

    circle_deleted = fields.Boolean(required=True)


class CircleMemberRemovalResponseSchema(ApiSchema):
    """Response after removing a member from a circle."""

    removed_user_id = fields.UUID(required=True)


class CircleAdminToggleResponseSchema(ApiSchema):
    """Response after promoting or demoting a circle admin."""

    user_id = fields.UUID(required=True)
    is_admin = fields.Boolean(required=True)
