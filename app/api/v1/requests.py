"""Request read and write endpoints for API v1."""

from flask import abort, request
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.query import RequestListQuerySchema
from app.api.v1.schemas.requests import (
    ItemRequestDetailResponseSchema,
    ItemRequestResponseSchema,
    ItemRequestStatusResponseSchema,
    ItemRequestSummarySchema,
    RequestWritePayloadSchema,
)
from app.models import ItemRequest
from app.services import request_service
from app.services.exceptions import AuthorizationError
from app.utils.messaging_queries import build_request_conversation_summaries
from app.utils.request_queries import build_visible_requests_pagination, can_view_request

REQUEST_LIST_QUERY_SCHEMA = RequestListQuerySchema()
ITEM_REQUEST_SUMMARY_SCHEMA = ItemRequestSummarySchema(many=True)
ITEM_REQUEST_DETAIL_RESPONSE_SCHEMA = ItemRequestDetailResponseSchema()
ITEM_REQUEST_RESPONSE_SCHEMA = ItemRequestResponseSchema()
ITEM_REQUEST_STATUS_RESPONSE_SCHEMA = ItemRequestStatusResponseSchema()
REQUEST_WRITE_PAYLOAD_SCHEMA = RequestWritePayloadSchema()
DEFAULT_GEOLOCATED_REQUEST_DISTANCE = 20


@bp.get("/requests")
@jwt_required()
def list_requests():
    """Return paginated visible requests for the authenticated user."""
    query_data = load_query_data(REQUEST_LIST_QUERY_SCHEMA)
    distance_explicit = "distance" in request.args
    selected_distance = query_data["distance"]
    if not distance_explicit and current_user.is_geocoded:
        selected_distance = DEFAULT_GEOLOCATED_REQUEST_DISTANCE

    pagination = build_visible_requests_pagination(
        current_user,
        selected_circle_ids=query_data["circles"],
        scope=query_data["scope"],
        distance=selected_distance,
        distance_explicit=distance_explicit,
        page=query_data["page"],
        per_page=query_data["per_page"],
    )

    return build_collection_response(
        "requests",
        ITEM_REQUEST_SUMMARY_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )


@bp.get("/requests/<uuid:request_id>")
@jwt_required()
def get_request(request_id):
    """Return request details when the authenticated user can view them."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)
    if not can_view_request(item_request, current_user):
        raise AuthorizationError("You are not allowed to view this request.")

    conversations = []
    if current_user.id == item_request.user_id:
        conversations = build_request_conversation_summaries(item_request.id, current_user.id)

    return ITEM_REQUEST_DETAIL_RESPONSE_SCHEMA.dump(
        {
            "request": item_request,
            "conversations": conversations,
        }
    )


@bp.post("/requests")
@jwt_required()
def create_request():
    """Create a new request owned by the authenticated user."""
    data = load_request_data(REQUEST_WRITE_PAYLOAD_SCHEMA)
    item_request = request_service.create_request(
        current_user,
        data["title"],
        data.get("description"),
        data["expires_at"],
        data["seeking"],
        data["visibility"],
    )
    return ITEM_REQUEST_RESPONSE_SCHEMA.dump({"request": item_request}), 201


@bp.patch("/requests/<uuid:request_id>")
@jwt_required()
def update_request(request_id):
    """Update an existing request owned by the authenticated user."""
    item_request = db.get_or_404(ItemRequest, request_id)
    data = load_request_data(REQUEST_WRITE_PAYLOAD_SCHEMA)
    request_service.update_request(
        item_request,
        current_user,
        data["title"],
        data.get("description"),
        data["expires_at"],
        data["seeking"],
        data["visibility"],
    )
    return ITEM_REQUEST_RESPONSE_SCHEMA.dump({"request": item_request})


@bp.delete("/requests/<uuid:request_id>")
@jwt_required()
def delete_request(request_id):
    """Soft-delete a request owned by the authenticated user."""
    item_request = db.get_or_404(ItemRequest, request_id)
    deleted_request = request_service.delete_request(item_request, current_user)
    return ITEM_REQUEST_STATUS_RESPONSE_SCHEMA.dump(
        {
            "request": {
                "id": deleted_request.id,
                "status": deleted_request.status,
            }
        }
    )


@bp.post("/requests/<uuid:request_id>/fulfill")
@jwt_required()
def fulfill_request(request_id):
    """Mark a request owned by the authenticated user as fulfilled."""
    item_request = db.get_or_404(ItemRequest, request_id)
    fulfilled_request = request_service.fulfill_request(item_request, current_user)
    return ITEM_REQUEST_STATUS_RESPONSE_SCHEMA.dump(
        {
            "request": {
                "id": fulfilled_request.id,
                "status": fulfilled_request.status,
            }
        }
    )
