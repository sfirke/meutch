"""Messaging workflow service helpers."""

import logging

from app import db
from app.models import Message
from app.services.exceptions import AuthorizationError
from app.utils.email import send_message_notification_email
from app.utils.messaging_queries import (
    build_conversation_thread_state,
    mark_conversation_messages_read,
)

logger = logging.getLogger(__name__)


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
    item_id=None,
    request_id=None,
    circle_id=None,
    parent_id=None,
):
    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        item_id=item_id,
        request_id=request_id,
        circle_id=circle_id,
        body=body,
        is_read=False,
        parent_id=parent_id,
    )
    db.session.add(message)
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
        item_id=message.item_id,
        request_id=message.request_id,
        circle_id=message.circle_id,
        parent_id=message.id,
    )


def get_conversation_thread_state(message, viewer_id, *, mark_read=True):
    if viewer_id not in {message.sender_id, message.recipient_id}:
        raise AuthorizationError("You do not have permission to view this message.")

    thread_state = build_conversation_thread_state(message, viewer_id)

    if mark_read:
        mark_conversation_messages_read(thread_state["unread_messages"])

    return {
        "thread_messages": thread_state["thread_messages"],
        "has_unread_messages": thread_state["has_unread_messages"],
    }
