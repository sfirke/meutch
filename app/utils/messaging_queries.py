# pylint: disable=not-callable

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Conversation,
    ConversationParticipant,
    LoanRequest,
    Message,
    User,
)


def get_conversation_other_user_id(message, viewer_id):
    if message.sender_id == viewer_id:
        return message.recipient_id
    if message.recipient_id == viewer_id:
        return message.sender_id
    return None


def _find_conversation(context_type, context_id, user1_id, user2_id):
    """Look up an existing conversation between two users in a given context."""
    conv_subq = (
        db.session.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.user_id.in_([user1_id, user2_id]),
        )
        .group_by(ConversationParticipant.conversation_id)
        .having(func.count(ConversationParticipant.user_id) == 2)
        .subquery()
    )
    return (
        db.session.query(Conversation)
        .join(conv_subq, Conversation.id == conv_subq.c.conversation_id)
        .filter(
            Conversation.context_type == context_type,
            Conversation.context_id == context_id,
        )
        .first()
    )


def resolve_conversation(context_type, context_id, user1_id, user2_id):
    """Find or create a conversation WITHOUT committing.

    Returns (conversation, is_new) where is_new is True if the conversation
    was freshly created.
    """
    u1, u2 = sorted([user1_id, user2_id])
    existing = _find_conversation(context_type, context_id, u1, u2)
    if existing:
        return existing, False

    conv = Conversation(context_type=context_type, context_id=context_id)
    db.session.add(conv)
    db.session.flush()  # get the ID
    for uid in {u1, u2}:
        db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
    db.session.flush()  # ensure participants are visible to later queries
    return conv, True


def get_or_create_conversation(context_type, context_id, user1_id, user2_id):
    """Find an existing conversation or create one with two participants.

    Normalizes user order for deterministic lookup.  Handles the race
    where two simultaneous requests both try to create the same
    conversation by catching IntegrityError and re-querying.
    """
    u1, u2 = sorted([user1_id, user2_id])
    existing = _find_conversation(context_type, context_id, u1, u2)
    if existing:
        return existing

    try:
        conv = Conversation(context_type=context_type, context_id=context_id)
        db.session.add(conv)
        db.session.flush()  # get the ID
        for uid in (u1, u2):
            db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
        db.session.commit()
        return conv
    except IntegrityError:
        db.session.rollback()
        return _find_conversation(context_type, context_id, u1, u2)


def build_inbox_summaries(viewer_id, *, include_archived=False):
    """Return inbox summaries for the viewer, keyed by conversation."""
    participant_conversations = (
        db.session.query(ConversationParticipant.conversation_id)
        .filter(ConversationParticipant.user_id == viewer_id)
        .subquery()
    )

    latest_msg_subq = (
        db.session.query(
            Message.conversation_id,
            func.max(Message.timestamp).label("latest_timestamp"),
        )
        .filter(Message.conversation_id.in_(participant_conversations))
        .group_by(Message.conversation_id)
        .subquery()
    )

    latest_messages = (
        db.session.query(Message)
        .join(
            latest_msg_subq,
            and_(
                Message.conversation_id == latest_msg_subq.c.conversation_id,
                Message.timestamp == latest_msg_subq.c.latest_timestamp,
            ),
        )
        .order_by(Message.timestamp.desc())
        .all()
    )

    summaries = []
    for msg in latest_messages:
        conversation = msg.conversation
        participant = ConversationParticipant.query.filter_by(
            conversation_id=conversation.id, user_id=viewer_id
        ).first()
        other_participant = ConversationParticipant.query.filter(
            ConversationParticipant.conversation_id == conversation.id,
            ConversationParticipant.user_id != viewer_id,
        ).first()

        summaries.append(
            {
                "conversation_id": str(conversation.id),
                "other_user": other_participant.user if other_participant else None,
                "item": conversation.item if conversation.context_type == "item" else None,
                "item_request": (
                    conversation.request if conversation.context_type == "request" else None
                ),
                "circle": conversation.circle if conversation.context_type == "circle" else None,
                "latest_message": msg,
                "unread_count": Message.query.filter_by(
                    conversation_id=conversation.id,
                    recipient_id=viewer_id,
                    is_read=False,
                ).count(),
                "is_archived": participant.is_archived if participant else False,
            }
        )

    if not include_archived:
        summaries = [s for s in summaries if not s.get("is_archived")]

    return summaries


def build_conversation_thread_state(message, viewer_id):
    """Return thread messages and unread state for a conversation."""

    thread_messages = (
        Message.query.filter_by(conversation_id=message.conversation_id)
        .order_by(Message.timestamp)
        .all()
    )
    for thread_message in thread_messages:
        thread_message.other_user = (
            thread_message.recipient
            if thread_message.sender_id == viewer_id
            else thread_message.sender
        )

    unread_messages = Message.query.filter(
        Message.conversation_id == message.conversation_id,
        Message.recipient_id == viewer_id,
        Message.is_read.is_(False),
        or_(
            Message.loan_request_id.is_(None),
            ~Message.loan_request.has(LoanRequest.status == "pending"),
        ),
    ).all()
    has_unread_messages = len(unread_messages) > 0

    return {
        "thread_messages": thread_messages,
        "has_unread_messages": has_unread_messages,
        "unread_messages": unread_messages,
    }


def mark_conversation_messages_read(unread_messages):
    for unread_message in unread_messages:
        unread_message.is_read = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_conversation_thread_state(message, viewer_id):
    thread_state = build_conversation_thread_state(message, viewer_id)

    mark_conversation_messages_read(thread_state["unread_messages"])

    return {
        "thread_messages": thread_state["thread_messages"],
        "has_unread_messages": thread_state["has_unread_messages"],
    }


def build_request_conversation_summaries(request_id, viewer_id):
    """Return conversation summaries for an item request."""
    conv_ids = (
        db.session.query(Conversation.id)
        .filter(
            Conversation.context_type == "request",
            Conversation.context_id == request_id,
        )
        .subquery()
    )

    messages = (
        Message.query.filter(Message.conversation_id.in_(conv_ids))
        .order_by(Message.timestamp.desc())
        .all()
    )

    conversation_map = {}
    for message in messages:
        pair = tuple(sorted([message.sender_id, message.recipient_id]))
        if pair not in conversation_map:
            conversation_map[pair] = message

    conversations = []
    for latest_message in conversation_map.values():
        other_user_id = get_conversation_other_user_id(latest_message, viewer_id)
        conversations.append(
            {
                "other_user": db.session.get(User, other_user_id),
                "latest_message": latest_message,
            }
        )

    return conversations


def find_request_conversation_message(request_id, sender_id, recipient_id):
    """Find the first message in a request conversation between two users."""
    conv = _find_conversation("request", request_id, sender_id, recipient_id)
    if conv is None:
        return None
    return (
        Message.query.filter_by(conversation_id=conv.id).order_by(Message.timestamp.asc()).first()
    )
