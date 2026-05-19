"""Messaging read endpoints for API v1."""

from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.messaging import ConversationSummarySchema, MessageThreadResponseSchema
from app.api.v1.schemas.query import ConversationListQuerySchema
from app.models import Message, User
from app.services import message_service
from app.utils.messaging_queries import build_inbox_summaries, get_conversation_other_user_id
from app.utils.pagination import ListPagination

CONVERSATION_LIST_QUERY_SCHEMA = ConversationListQuerySchema()
CONVERSATION_SUMMARY_SCHEMA = ConversationSummarySchema(many=True)
MESSAGE_THREAD_RESPONSE_SCHEMA = MessageThreadResponseSchema()


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
