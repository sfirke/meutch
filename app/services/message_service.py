"""Messaging workflow service helpers."""

import logging

from app import db
from app.models import ConversationParticipant, Message
from app.services.exceptions import AuthorizationError, InvalidActionError
from app.utils.email import send_message_notification_email
from app.utils.item_visibility import build_item_access_state
from app.utils.messaging_queries import (
    build_conversation_thread_state,
    get_or_create_conversation,
    mark_conversation_messages_read,
)
from app.utils.request_queries import can_view_request

logger = logging.getLogger(__name__)


def get_item_conversation_recipient_id(item, sender, *, share_token=None):
    if item.owner_id == sender.id:
        raise InvalidActionError("You cannot message yourself about your own item.")

    access_state = build_item_access_state(item, sender, share_token=share_token)
    if not access_state["can_view"]:
        raise AuthorizationError("You do not have permission to message the owner about this item.")

    return item.owner_id


def get_request_conversation_recipient_id(item_request, sender):
    if item_request.user_id == sender.id:
        raise InvalidActionError("You cannot message yourself about your own request.")

    if not can_view_request(item_request, sender):
        raise AuthorizationError("You do not have permission to message this request owner.")

    return item_request.user_id


def start_item_conversation(item, sender, body, *, share_token=None):
    recipient_id = get_item_conversation_recipient_id(item, sender, share_token=share_token)
    conversation = get_or_create_conversation("item", item.id, sender.id, recipient_id)
    return create_message(sender.id, recipient_id, body, conversation_id=conversation.id)


def start_request_conversation(item_request, sender, body):
    recipient_id = get_request_conversation_recipient_id(item_request, sender)
    conversation = get_or_create_conversation("request", item_request.id, sender.id, recipient_id)
    return create_message(sender.id, recipient_id, body, conversation_id=conversation.id)


def _commit_and_notify(message, error_prefix):
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    try:
        send_message_notification_email(message)
    except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
        logger.error("%s: %s", error_prefix, exc)

    return message


def create_message(
    sender_id,
    recipient_id,
    body,
    *,
    conversation_id=None,
    parent_id=None,
    loan_request_id=None,
):
    if sender_id == recipient_id:
        raise InvalidActionError("You cannot message yourself.")

    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        conversation_id=conversation_id,
        body=body,
        is_read=False,
        parent_id=parent_id,
        loan_request_id=loan_request_id,
    )
    db.session.add(message)

    # Auto-unarchive for the recipient when a new message arrives
    ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=recipient_id, is_archived=True
    ).update({"is_archived": False, "archived_at": None}, synchronize_session=False)

    return _commit_and_notify(
        message,
        f"Failed to send email notification for message {message.id}",
    )


def reply_to_message(message, sender_id, body):
    if sender_id not in {message.sender_id, message.recipient_id}:
        raise AuthorizationError("You do not have permission to reply to this message.")

    recipient_id = message.recipient_id if message.sender_id == sender_id else message.sender_id
    return create_message(
        sender_id,
        recipient_id,
        body,
        conversation_id=message.conversation_id,
        parent_id=message.id,
    )


def _build_authorized_conversation_thread_state(message, viewer_id):
    if viewer_id not in {message.sender_id, message.recipient_id}:
        raise AuthorizationError("You do not have permission to view this message.")

    return build_conversation_thread_state(message, viewer_id)


def get_conversation_thread_state(message, viewer_id, *, mark_read=True):
    thread_state = _build_authorized_conversation_thread_state(message, viewer_id)

    if mark_read:
        mark_conversation_messages_read(thread_state["unread_messages"])

    return {
        "thread_messages": thread_state["thread_messages"],
        "has_unread_messages": thread_state["has_unread_messages"],
    }


def mark_message_thread_read(message, viewer_id):
    thread_state = _build_authorized_conversation_thread_state(message, viewer_id)
    unread_messages = thread_state["unread_messages"]

    if unread_messages:
        mark_conversation_messages_read(unread_messages)

    return {
        "has_unread_messages": False,
    }
