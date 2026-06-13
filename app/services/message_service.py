"""Messaging workflow service helpers."""

import logging

from flask import url_for

from app import db
from app.models import Message
from app.services.exceptions import AuthorizationError, InvalidActionError
from app.utils.email import send_message_notification_email
from app.utils.item_share import generate_item_share_token
from app.utils.item_visibility import build_item_access_state
from app.utils.messaging_queries import (
    build_conversation_thread_state,
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
    return create_message(sender.id, recipient_id, body, item_id=item.id)


def start_request_conversation(item_request, sender, body):
    recipient_id = get_request_conversation_recipient_id(item_request, sender)
    return create_message(sender.id, recipient_id, body, request_id=item_request.id)


def _build_item_url_for_requester(item, item_owner, requester):
    """Return the best URL so *requester* can view *item*.

    - Public giveaways → public preview URL.
    - Regular items where owner and requester share a circle → direct URL.
    - Regular items without shared circles → tokenized share-preview URL.
    - Default-visibility giveaways are visible to everyone → direct URL.
    """
    if item.is_giveaway and item.giveaway_visibility == "public":
        return url_for("share.giveaway_preview", item_id=item.id, _external=True)

    if item.is_giveaway or item_owner.shares_circle_with(requester):
        return url_for("main.item_detail", item_id=item.id, _external=True)

    token = generate_item_share_token(item)
    return url_for("share.item_preview", token=token, _external=True)


_RESPOND_BODY_TEMPLATE = (
    "Hi {requester_name}! I have a {item_name} that might help with "
    "your request for '{request_title}'. You can see it here: {item_url}"
)


def respond_to_request_with_item(item_request, sender, item, body=None):
    """Respond to *item_request* by sharing *item* with the requester.

    Creates a message in the request conversation that includes an
    item link.  When the requester cannot see the item directly a share
    token is generated automatically.

    Args:
        item_request: The :class:`ItemRequest` being responded to.
        sender: The :class:`User` responding (must own *item*).
        item: The :class:`Item` being offered in response.
        body: Optional custom message body.  When ``None`` a
            pre-formatted message is generated.

    Returns:
        The newly created :class:`Message`.
    """
    if item_request.status != "open" or item_request.is_expired:
        raise InvalidActionError("This request is no longer open.")

    if item.owner_id != sender.id:
        raise AuthorizationError("You can only respond with your own items.")

    recipient_id = get_request_conversation_recipient_id(item_request, sender)

    item_url = _build_item_url_for_requester(item, sender, item_request.user)

    if body is None:
        body = _RESPOND_BODY_TEMPLATE.format(
            requester_name=item_request.user.full_name,
            item_name=item.name,
            request_title=item_request.title,
            item_url=item_url,
        )

    return create_message(sender.id, recipient_id, body, request_id=item_request.id)


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
    if sender_id == recipient_id:
        raise InvalidActionError("You cannot message yourself.")

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
