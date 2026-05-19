"""Circle read endpoints for API v1."""

from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.circles import CircleDetailResponseSchema, CircleSummarySchema
from app.api.v1.schemas.query import CircleListQuerySchema
from app.models import Circle
from app.utils.circle_queries import (
    get_admin_circle_pending_counts,
    get_listed_circles,
    get_ordered_circle_members,
    get_pending_circle_join_request,
    get_sorted_user_circles,
    should_show_circle_members,
)
from app.utils.pagination import ListPagination

CIRCLE_LIST_QUERY_SCHEMA = CircleListQuerySchema()
CIRCLE_SUMMARY_SCHEMA = CircleSummarySchema(many=True)
CIRCLE_DETAIL_RESPONSE_SCHEMA = CircleDetailResponseSchema()


def _annotate_circle(circle, admin_pending_counts):
    circle.api_is_member = current_user in circle.members
    circle.api_is_admin = circle.is_admin(current_user) if circle.api_is_member else False
    circle.api_pending_join_request = get_pending_circle_join_request(circle.id, current_user.id)
    circle.api_pending_join_request_count = admin_pending_counts.get(str(circle.id), 0)
    circle.api_distance_miles = circle.distance_to_user(current_user)
    return circle


@bp.get("/circles")
@jwt_required()
def list_circles():
    """Return paginated circle summaries for the authenticated user."""
    query_data = load_query_data(CIRCLE_LIST_QUERY_SCHEMA)
    if query_data["membership"] == "mine":
        circles = list(get_sorted_user_circles(current_user))
    else:
        circles = list(
            get_listed_circles(
                current_user,
                search_query=query_data["q"],
                radius=query_data["radius"],
            )
        )

    admin_pending_counts = get_admin_circle_pending_counts(current_user.id)
    annotated_circles = [_annotate_circle(circle, admin_pending_counts) for circle in circles]
    pagination = ListPagination(
        items=annotated_circles,
        page=query_data["page"],
        per_page=query_data["per_page"],
    )

    return build_collection_response(
        "circles",
        CIRCLE_SUMMARY_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )


@bp.get("/circles/<uuid:circle_id>")
@jwt_required()
def get_circle(circle_id):
    """Return circle details for the authenticated user."""
    circle = db.get_or_404(Circle, circle_id)
    admin_pending_counts = get_admin_circle_pending_counts(current_user.id)
    circle = _annotate_circle(circle, admin_pending_counts)
    circle.api_can_view_members = should_show_circle_members(circle, current_user)
    circle.api_is_last_member = circle.api_is_member and len(circle.members) == 1
    circle.api_members = []
    if circle.api_can_view_members:
        circle.api_members = [
            {
                "user": member.User,
                "joined_at": member.joined_at,
                "is_admin": member.is_admin,
            }
            for member in get_ordered_circle_members(circle.id)
        ]

    return CIRCLE_DETAIL_RESPONSE_SCHEMA.dump({"circle": circle})
