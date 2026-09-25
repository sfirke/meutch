"""Request read and write endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.operational import mutation_limit, read_limit
from app.api.v1.parsing import load_request_data
from app.api.v1.profile_flags import dump_with_viewable_profiles
from app.api.v1.schemas.messaging import MessageResponseSchema
from app.api.v1.schemas.requests import (
    ItemRequestDetailResponseSchema,
    ItemRequestResponseSchema,
    ItemRequestStatusResponseSchema,
    RequestRespondDraftResponseSchema,
    RequestRespondSchema,
    RequestWritePayloadSchema,
)
from app.models import Item, ItemRequest
from app.services import message_service, request_service
from app.services.exceptions import AuthorizationError
from app.utils.messaging_queries import build_request_conversation_summaries
from app.utils.request_queries import can_view_request, describe_seeking_mismatch

ITEM_REQUEST_DETAIL_RESPONSE_SCHEMA = ItemRequestDetailResponseSchema()
ITEM_REQUEST_RESPONSE_SCHEMA = ItemRequestResponseSchema()
ITEM_REQUEST_STATUS_RESPONSE_SCHEMA = ItemRequestStatusResponseSchema()
REQUEST_WRITE_PAYLOAD_SCHEMA = RequestWritePayloadSchema()
REQUEST_RESPOND_SCHEMA = RequestRespondSchema()
REQUEST_RESPOND_DRAFT_RESPONSE_SCHEMA = RequestRespondDraftResponseSchema()
MESSAGE_RESPONSE_SCHEMA = MessageResponseSchema()


def _request_candidate_ids(item_request, conversations=()):
    """User ids nested in a request dump: the requester and conversation partners."""
    ids = [item_request.user_id]
    ids.extend(
        conversation["other_user"].id
        for conversation in conversations
        if conversation.get("other_user")
    )
    return ids


def _get_live_request_or_404(request_id):
    """Load a request, treating a soft-deleted one as missing."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)
    return item_request


@bp.get("/requests/<uuid:request_id>")
@jwt_required()
@read_limit()
def get_request(request_id):
    """Return request details when the authenticated user can view them."""
    item_request = _get_live_request_or_404(request_id)
    if not can_view_request(item_request, current_user):
        raise AuthorizationError("You are not allowed to view this request.")

    conversations = []
    if current_user.id == item_request.user_id:
        conversations = build_request_conversation_summaries(item_request.id, current_user.id)

    return dump_with_viewable_profiles(
        ITEM_REQUEST_DETAIL_RESPONSE_SCHEMA,
        {
            "request": item_request,
            "conversations": conversations,
        },
        _request_candidate_ids(item_request, conversations),
    )


@bp.post("/requests")
@jwt_required()
@mutation_limit()
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
    return (
        dump_with_viewable_profiles(
            ITEM_REQUEST_RESPONSE_SCHEMA,
            {"request": item_request},
            _request_candidate_ids(item_request),
        ),
        201,
    )


@bp.patch("/requests/<uuid:request_id>")
@jwt_required()
@mutation_limit()
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
    return dump_with_viewable_profiles(
        ITEM_REQUEST_RESPONSE_SCHEMA,
        {"request": item_request},
        _request_candidate_ids(item_request),
    )


@bp.delete("/requests/<uuid:request_id>")
@jwt_required()
@mutation_limit()
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
@mutation_limit()
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


@bp.get("/requests/<uuid:request_id>/respond/<uuid:item_id>")
@jwt_required()
@read_limit()
def get_respond_draft(request_id, item_id):
    """Return the suggested message for offering *item_id* against a request.

    Mirrors the web compose screen, which pre-fills the same text.  Clients
    should show this to the sender, let them edit it, and POST the result.
    """
    item_request = _get_live_request_or_404(request_id)
    item = db.get_or_404(Item, item_id)
    suggested_body = message_service.build_respond_draft(item_request, current_user, item)
    return REQUEST_RESPOND_DRAFT_RESPONSE_SCHEMA.dump(
        {
            "suggested_body": suggested_body,
            "seeking_mismatch": describe_seeking_mismatch(item_request, item),
            "visibility_gap": message_service.describe_item_visibility_gap(item_request, item),
        }
    )


@bp.post("/requests/<uuid:request_id>/respond/<uuid:item_id>")
@jwt_required()
@mutation_limit()
def respond_to_request(request_id, item_id):
    """Respond to a request by sharing one of the authenticated user's items."""
    item_request = _get_live_request_or_404(request_id)
    item = db.get_or_404(Item, item_id)
    data = load_request_data(REQUEST_RESPOND_SCHEMA)
    message = message_service.respond_to_request_with_item(
        item_request,
        current_user,
        item,
        body=data["body"],
    )
    return MESSAGE_RESPONSE_SCHEMA.dump({"message": message}), 201
