"""Messaging read endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.messaging import (
    ConversationSummarySchema,
    MessageMarkReadResponseSchema,
    MessageReplySchema,
    MessageResponseSchema,
    MessageStartSchema,
    MessageThreadResponseSchema,
)
from app.api.v1.schemas.query import ConversationListQuerySchema
from app.models import Item, ItemRequest, Message, User
from app.services import message_service
from app.utils.messaging_queries import build_inbox_summaries, get_conversation_other_user_id
from app.utils.pagination import ListPagination

CONVERSATION_LIST_QUERY_SCHEMA = ConversationListQuerySchema()
CONVERSATION_SUMMARY_SCHEMA = ConversationSummarySchema(many=True)
MESSAGE_THREAD_RESPONSE_SCHEMA = MessageThreadResponseSchema()
MESSAGE_START_REQUEST_SCHEMA = MessageStartSchema()
MESSAGE_REPLY_REQUEST_SCHEMA = MessageReplySchema()
MESSAGE_RESPONSE_SCHEMA = MessageResponseSchema()
MESSAGE_MARK_READ_RESPONSE_SCHEMA = MessageMarkReadResponseSchema()


@bp.get("/messages")
@jwt_required()
def list_conversations():
    """Return paginated inbox summaries for the authenticated user."""
    query_data = load_query_data(CONVERSATION_LIST_QUERY_SCHEMA)
    conversation_summaries = build_inbox_summaries(current_user.id)
    pagination = ListPagination(
        items=conversation_summaries,
        page=query_data["page"],
        per_page=query_data["per_page"],
    )

    return build_collection_response(
        "conversations",
        CONVERSATION_SUMMARY_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )


@bp.get("/messages/<uuid:message_id>")
@jwt_required()
def get_message_thread(message_id):
    """Return a conversation thread without mutating read state."""
    message = db.get_or_404(Message, message_id)
    thread_state = message_service.get_conversation_thread_state(
        message,
        current_user.id,
        mark_read=False,
    )
    other_user_id = get_conversation_other_user_id(message, current_user.id)
    other_user = db.session.get(User, other_user_id)
    if other_user is None:
        abort(404)
    shared_circles = current_user.shared_circles_with(other_user)

    active_loan = None
    if not message.is_request_message:
        for thread_message in thread_state["thread_messages"]:
            loan_request = thread_message.loan_request
            if loan_request and loan_request.status in {"pending", "approved"}:
                active_loan = loan_request
                break

    return MESSAGE_THREAD_RESPONSE_SCHEMA.dump(
        {
            "other_user": other_user,
            "shared_circles": shared_circles,
            "item": message.item if not message.is_request_message else None,
            "item_request": message.request if message.is_request_message else None,
            "circle": message.circle if message.is_circle_message else None,
            "active_loan": active_loan,
            "has_unread_messages": thread_state["has_unread_messages"],
            "messages": thread_state["thread_messages"],
        }
    )


@bp.post("/messages")
@jwt_required()
def start_message_thread():
    """Start a new item or request conversation."""
    data = load_request_data(MESSAGE_START_REQUEST_SCHEMA)

    if data.get("item_id") is not None:
        item = db.get_or_404(Item, data["item_id"])
        message = message_service.start_item_conversation(item, current_user, data["body"])
    else:
        item_request = db.get_or_404(ItemRequest, data["request_id"])
        if item_request.status == "deleted":
            abort(404)
        message = message_service.start_request_conversation(
            item_request, current_user, data["body"]
        )

    return MESSAGE_RESPONSE_SCHEMA.dump({"message": message}), 201


@bp.post("/messages/<uuid:message_id>/reply")
@jwt_required()
def reply_to_message(message_id):
    """Reply within an existing conversation thread."""
    message = db.get_or_404(Message, message_id)
    data = load_request_data(MESSAGE_REPLY_REQUEST_SCHEMA)
    reply = message_service.reply_to_message(message, current_user.id, data["body"])
    return MESSAGE_RESPONSE_SCHEMA.dump({"message": reply}), 201


@bp.post("/messages/<uuid:message_id>/mark-read")
@jwt_required()
def mark_message_thread_read(message_id):
    """Mark unread messages in a thread as read from a message anchor."""
    message = db.get_or_404(Message, message_id)
    read_result = message_service.mark_message_thread_read(message, current_user.id)
    return MESSAGE_MARK_READ_RESPONSE_SCHEMA.dump(read_result)
