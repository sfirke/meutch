"""Messaging workflow service helpers."""

import logging
from datetime import UTC, datetime

from flask import url_for

from app import db
from app.models import ConversationParticipant, Message
from app.services.exceptions import AuthorizationError, InvalidActionError
from app.utils.email import send_message_notification_email
from app.utils.item_share import generate_item_share_token
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

    return create_message(sender.id, recipient_id, body, loan_request_id=item_request.id)


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


def _commit_only(message):
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return message


def create_message(
    sender_id,
    recipient_id,
    body,
    *,
    # `notify=False` lets callers suppress the message-notification email.
    # Use this when a dedicated, context-specific email is already being sent
    # for the same event (e.g. circle join-request decisions already send a
    # separate approval/rejection email via send_circle_join_request_decision_email).
    notify=True,
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

    if notify:
        return _commit_and_notify(
            message,
            f"Failed to send email notification for message {message.id}",
        )

    return _commit_only(message)


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


# ── Archive & bulk-action helpers ──────────────────────────────────────────


def archive_conversation(user_id, conversation_id):
    """Archive a conversation for a user. Each user's archive state is independent."""
    ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=user_id
    ).update({"is_archived": True, "archived_at": datetime.now(UTC)}, synchronize_session=False)
    db.session.commit()


def unarchive_conversation(user_id, conversation_id):
    """Unarchive a conversation for a user."""
    ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=user_id
    ).update({"is_archived": False, "archived_at": None}, synchronize_session=False)
    db.session.commit()


def bulk_archive(user_id, conversation_ids):
    """Archive multiple conversations in a single UPDATE."""
    if not conversation_ids:
        return
    ConversationParticipant.query.filter(
        ConversationParticipant.conversation_id.in_(conversation_ids),
        ConversationParticipant.user_id == user_id,
    ).update({"is_archived": True, "archived_at": datetime.now(UTC)}, synchronize_session=False)
    db.session.commit()


def bulk_unarchive(user_id, conversation_ids):
    """Unarchive multiple conversations in a single UPDATE."""
    if not conversation_ids:
        return
    ConversationParticipant.query.filter(
        ConversationParticipant.conversation_id.in_(conversation_ids),
        ConversationParticipant.user_id == user_id,
    ).update({"is_archived": False, "archived_at": None}, synchronize_session=False)
    db.session.commit()


def bulk_mark_read(user_id, conversation_ids):
    """Mark all unread messages as read in the given conversations."""
    if not conversation_ids:
        return
    Message.query.filter(
        Message.conversation_id.in_(conversation_ids),
        Message.recipient_id == user_id,
        Message.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.session.commit()


def bulk_mark_unread(user_id, conversation_ids):
    """Mark the latest message in each conversation as unread for the user.

    Only the single most-recent message (by timestamp) per conversation is
    flipped back to unread.  That is enough to surface the conversation in
    the inbox while avoiding an explosion of unread counts.
    """
    if not conversation_ids:
        return

    # Window-function subquery: row_number = 1 picks the latest message
    # per conversation where the user is the recipient.

    ranked = (
        db.session.query(
            Message.id,
            db.func.row_number()
            .over(
                partition_by=Message.conversation_id,
                order_by=Message.timestamp.desc(),
            )
            .label("rn"),
        )
        .filter(
            Message.conversation_id.in_(conversation_ids),
            Message.recipient_id == user_id,
        )
        .subquery()
    )

    latest_ids = db.session.query(ranked.c.id).filter(ranked.c.rn == 1).scalar_subquery()

    Message.query.filter(Message.id.in_(latest_ids)).update(
        {"is_read": False}, synchronize_session=False
    )
    db.session.commit()


def mark_all_read_in_view(user_id, status="inbox"):
    """Mark all unread messages as read for conversations in the active view.

    ``status`` is ``"inbox"`` (non-archived conversations) or ``"archived"``.
    """
    is_archived_flag = status == "archived"
    if is_archived_flag:
        archive_filter = ConversationParticipant.is_archived.is_(True)
    else:
        # Use isnot(True) rather than is_(False) so that NULL rows
        # (where is_archived was never set) are also treated as "not archived".
        archive_filter = ConversationParticipant.is_archived.isnot(True)

    view_conversation_ids = (
        db.session.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.user_id == user_id,
            archive_filter,
        )
        .scalar_subquery()
    )

    Message.query.filter(
        Message.conversation_id.in_(view_conversation_ids),
        Message.recipient_id == user_id,
        Message.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.session.commit()
