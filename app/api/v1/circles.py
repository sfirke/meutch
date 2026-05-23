"""Circle read and write endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.circles import (
    CircleAdminToggleResponseSchema,
    CircleCancelJoinRequestResponseSchema,
    CircleDetailResponseSchema,
    CircleJoinRequestActionResponseSchema,
    CircleJoinRequestCreateSchema,
    CircleJoinResponseSchema,
    CircleLeaveResponseSchema,
    CircleMemberRemovalResponseSchema,
    CircleMutationResponseSchema,
    CircleSummarySchema,
    CircleWritePayloadSchema,
)
from app.api.v1.schemas.query import CircleListQuerySchema
from app.models import Circle, CircleJoinRequest, User
from app.services import circle_service
from app.utils.circle_queries import (
    get_admin_circle_pending_counts,
    get_listed_circles,
    get_ordered_circle_members,
    get_sorted_user_circles,
    should_show_circle_members,
)
from app.utils.pagination import ListPagination

CIRCLE_LIST_QUERY_SCHEMA = CircleListQuerySchema()
CIRCLE_SUMMARY_SCHEMA = CircleSummarySchema(many=True)
CIRCLE_DETAIL_RESPONSE_SCHEMA = CircleDetailResponseSchema()
CIRCLE_WRITE_PAYLOAD_SCHEMA = CircleWritePayloadSchema()
CIRCLE_MUTATION_RESPONSE_SCHEMA = CircleMutationResponseSchema()
CIRCLE_JOIN_REQUEST_CREATE_SCHEMA = CircleJoinRequestCreateSchema()
CIRCLE_JOIN_RESPONSE_SCHEMA = CircleJoinResponseSchema()
CIRCLE_JOIN_REQUEST_ACTION_RESPONSE_SCHEMA = CircleJoinRequestActionResponseSchema()
CIRCLE_CANCEL_JOIN_REQUEST_RESPONSE_SCHEMA = CircleCancelJoinRequestResponseSchema()
CIRCLE_LEAVE_RESPONSE_SCHEMA = CircleLeaveResponseSchema()
CIRCLE_MEMBER_REMOVAL_RESPONSE_SCHEMA = CircleMemberRemovalResponseSchema()
CIRCLE_ADMIN_TOGGLE_RESPONSE_SCHEMA = CircleAdminToggleResponseSchema()


def _fetch_pending_requests_by_circle(user_id, circle_ids):
    """Return a dict mapping circle_id -> pending CircleJoinRequest for the user."""
    if not circle_ids:
        return {}
    requests = CircleJoinRequest.query.filter(
        CircleJoinRequest.user_id == user_id,
        CircleJoinRequest.circle_id.in_(circle_ids),
        CircleJoinRequest.status == "pending",
    ).all()
    return {req.circle_id: req for req in requests}


def _annotate_circle(circle, admin_pending_counts, pending_requests_by_circle):
    circle.api_is_member = current_user in circle.members
    circle.api_is_admin = circle.is_admin(current_user) if circle.api_is_member else False
    circle.api_pending_join_request = pending_requests_by_circle.get(circle.id)
    circle.api_pending_join_request_count = admin_pending_counts.get(str(circle.id), 0)
    circle.api_distance_miles = circle.distance_to_user(current_user)
    return circle


def _annotate_circle_detail(circle):
    admin_pending_counts = get_admin_circle_pending_counts(current_user.id)
    pending_requests_by_circle = _fetch_pending_requests_by_circle(current_user.id, [circle.id])
    circle = _annotate_circle(circle, admin_pending_counts, pending_requests_by_circle)
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
    circle_ids = [c.id for c in circles]
    pending_requests_by_circle = _fetch_pending_requests_by_circle(current_user.id, circle_ids)
    annotated_circles = [
        _annotate_circle(circle, admin_pending_counts, pending_requests_by_circle)
        for circle in circles
    ]
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
    if circle.circle_type == "secret" and current_user not in circle.members:
        abort(404)
    return CIRCLE_DETAIL_RESPONSE_SCHEMA.dump({"circle": _annotate_circle_detail(circle)})


@bp.post("/circles")
@jwt_required()
def create_circle():
    """Create a new circle owned by the authenticated user."""
    data = load_request_data(CIRCLE_WRITE_PAYLOAD_SCHEMA)
    result = circle_service.create_circle(
        current_user,
        name=data["name"],
        description=data.get("description"),
        circle_type=data["circle_type"],
        image_file=data.get("image"),
        location_method=data["location_method"],
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        street=data.get("street"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        country=data.get("country"),
    )
    result["circle"] = _annotate_circle_detail(result["circle"])
    return CIRCLE_MUTATION_RESPONSE_SCHEMA.dump(result), 201


@bp.patch("/circles/<uuid:circle_id>")
@jwt_required()
def update_circle(circle_id):
    """Update an existing circle managed by the authenticated user."""
    circle = db.get_or_404(Circle, circle_id)
    data = load_request_data(CIRCLE_WRITE_PAYLOAD_SCHEMA)
    result = circle_service.update_circle(
        circle,
        current_user,
        name=data["name"],
        description=data.get("description"),
        circle_type=data["circle_type"],
        image_file=data.get("image"),
        delete_image=data["delete_image"],
        location_method=data["location_method"],
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        street=data.get("street"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        country=data.get("country"),
    )
    result["circle"] = _annotate_circle_detail(result["circle"])
    return CIRCLE_MUTATION_RESPONSE_SCHEMA.dump(result)


@bp.post("/circles/<uuid:circle_id>/join")
@jwt_required()
def join_circle(circle_id):
    """Join an open circle or submit a join request for a gated circle."""
    circle = db.get_or_404(Circle, circle_id)
    data = load_request_data(CIRCLE_JOIN_REQUEST_CREATE_SCHEMA)
    join_request = circle_service.join_circle(circle, current_user, data.get("message"))
    return CIRCLE_JOIN_RESPONSE_SCHEMA.dump(
        {
            "membership_status": "pending" if join_request else "member",
            "join_request": join_request,
        }
    )


def _handle_join_request_action(circle_id, request_id, action):
    circle = db.get_or_404(Circle, circle_id)
    join_request = db.get_or_404(CircleJoinRequest, request_id)
    handled_action = circle_service.handle_join_request(circle, join_request, current_user, action)
    return CIRCLE_JOIN_REQUEST_ACTION_RESPONSE_SCHEMA.dump(
        {
            "action": handled_action,
            "join_request": {
                "id": join_request.id,
                "status": join_request.status,
            },
        }
    )


@bp.post("/circles/<uuid:circle_id>/cancel-request")
@jwt_required()
def cancel_join_request(circle_id):
    """Cancel the authenticated user's pending join request for a circle."""
    db.get_or_404(Circle, circle_id)
    canceled = circle_service.cancel_join_request(circle_id, current_user.id)
    return CIRCLE_CANCEL_JOIN_REQUEST_RESPONSE_SCHEMA.dump({"canceled": canceled})


@bp.post("/circles/<uuid:circle_id>/join-requests/<uuid:request_id>/approve")
@jwt_required()
def approve_join_request(circle_id, request_id):
    """Approve a pending circle join request."""
    return _handle_join_request_action(circle_id, request_id, "approve")


@bp.post("/circles/<uuid:circle_id>/join-requests/<uuid:request_id>/reject")
@jwt_required()
def reject_join_request(circle_id, request_id):
    """Reject a pending circle join request."""
    return _handle_join_request_action(circle_id, request_id, "reject")


@bp.post("/circles/<uuid:circle_id>/leave")
@jwt_required()
def leave_circle(circle_id):
    """Leave a circle, deleting it when the last member exits."""
    circle = db.get_or_404(Circle, circle_id)
    result = circle_service.leave_circle(circle, current_user)
    return CIRCLE_LEAVE_RESPONSE_SCHEMA.dump(result)


@bp.delete("/circles/<uuid:circle_id>/members/<uuid:user_id>")
@jwt_required()
def remove_member(circle_id, user_id):
    """Remove another member from a circle as an admin."""
    circle = db.get_or_404(Circle, circle_id)
    member_user = db.get_or_404(User, user_id)
    removed_user = circle_service.remove_member(circle, member_user, current_user)
    return CIRCLE_MEMBER_REMOVAL_RESPONSE_SCHEMA.dump({"removed_user_id": removed_user.id})


def _toggle_circle_admin(circle_id, user_id, action):
    circle = db.get_or_404(Circle, circle_id)
    is_admin = circle_service.toggle_admin(circle, user_id, current_user, action)
    return CIRCLE_ADMIN_TOGGLE_RESPONSE_SCHEMA.dump(
        {
            "user_id": user_id,
            "is_admin": is_admin,
        }
    )


@bp.post("/circles/<uuid:circle_id>/admins/<uuid:user_id>")
@jwt_required()
def add_circle_admin(circle_id, user_id):
    """Promote a circle member to admin."""
    return _toggle_circle_admin(circle_id, user_id, "add")


@bp.delete("/circles/<uuid:circle_id>/admins/<uuid:user_id>")
@jwt_required()
def remove_circle_admin(circle_id, user_id):
    """Demote a circle admin back to a regular member."""
    return _toggle_circle_admin(circle_id, user_id, "remove")
