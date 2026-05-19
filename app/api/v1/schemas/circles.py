"""Circle read schemas for API v1."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
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
