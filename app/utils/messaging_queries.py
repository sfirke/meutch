# pylint: disable=not-callable

from sqlalchemy import and_, func, or_, select
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


def find_context_conversation(context_type, context_id, user1_id, user2_id):
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


def get_or_create_conversation(context_type, context_id, user1_id, user2_id):
    """Find an existing conversation or create one with two participants.

    Normalizes user order for deterministic lookup.  Handles the race
    where two simultaneous requests both try to create the same
    conversation by catching IntegrityError and re-querying.
    """
    u1, u2 = sorted([user1_id, user2_id])
    existing = find_context_conversation(context_type, context_id, u1, u2)
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
        return find_context_conversation(context_type, context_id, u1, u2)


def build_inbox_summaries(viewer_id, *, include_archived=False):
    """Return inbox summaries for the viewer, keyed by conversation.

    Uses batch queries to avoid N+1 problems — a fixed number of queries
    regardless of inbox size.
    """
    # ── 1. All participant rows for the viewer ─────────────────────────
    participants = ConversationParticipant.query.filter(
        ConversationParticipant.user_id == viewer_id
    ).all()
    conv_ids = [p.conversation_id for p in participants]
    participant_by_conv = {p.conversation_id: p for p in participants}

    if not conv_ids:
        return []

    # ── 2. Other participants (batch-loaded users) ─────────────────────
    other_participants = ConversationParticipant.query.filter(
        ConversationParticipant.conversation_id.in_(conv_ids),
        ConversationParticipant.user_id != viewer_id,
    ).all()
    other_user_ids = {op.user_id for op in other_participants}
    other_participant_by_conv = {op.conversation_id: op for op in other_participants}

    users_by_id = {}
    if other_user_ids:
        users_by_id = {
            u.id: u for u in db.session.query(User).filter(User.id.in_(other_user_ids)).all()
        }

    # ── 3. Latest message per conversation ─────────────────────────────
    latest_msg_subq = (
        db.session.query(
            Message.conversation_id,
            func.max(Message.timestamp).label("latest_timestamp"),
        )
        .filter(Message.conversation_id.in_(conv_ids))
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
    messages_by_conv = {m.conversation_id: m for m in latest_messages}

    # ── 4. Context entities (batch-loaded by type) ─────────────────────
    conversation_map = {
        c.id: c for c in db.session.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()
    }

    context_ids_by_type = {}
    for conv in conversation_map.values():
        context_ids_by_type.setdefault(conv.context_type, set()).add(conv.context_id)

    # Lazy-load context objects so the identity map handles dedup
    for ctype, cids in context_ids_by_type.items():
        if ctype == "item":
            from app.models import Item

            db.session.query(Item).filter(Item.id.in_(cids)).all()
        elif ctype == "request":
            from app.models import ItemRequest

            db.session.query(ItemRequest).filter(ItemRequest.id.in_(cids)).all()
        elif ctype == "circle":
            from app.models import Circle

            db.session.query(Circle).filter(Circle.id.in_(cids)).all()

    # ── 5. Unread counts (single GROUP BY query) ───────────────────────
    unread_counts = dict(
        db.session.query(
            Message.conversation_id,
            func.count(Message.id),
        )
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.recipient_id == viewer_id,
            Message.is_read.is_(False),
        )
        .group_by(Message.conversation_id)
        .all()
    )

    # ── 6. Assemble summaries ──────────────────────────────────────────
    summaries = []
    for conv_id in conv_ids:
        conversation = conversation_map.get(conv_id)
        if conversation is None:
            continue
        msg = messages_by_conv.get(conv_id)
        if msg is None:
            continue
        participant = participant_by_conv.get(conv_id)
        op = other_participant_by_conv.get(conv_id)
        other_user = users_by_id.get(op.user_id) if op else None

        summaries.append(
            {
                "conversation_id": str(conversation.id),
                "other_user": other_user,
                "item": conversation.item if conversation.context_type == "item" else None,
                "item_request": (
                    conversation.request if conversation.context_type == "request" else None
                ),
                "circle": (conversation.circle if conversation.context_type == "circle" else None),
                "latest_message": msg,
                "unread_count": unread_counts.get(conv_id, 0),
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
        Message.query.filter(Message.conversation_id.in_(select(conv_ids)))
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


# ── Sort & filter helpers ──────────────────────────────────────────────


def sort_conversation_summaries(summaries, sort_by="newest"):
    """Sort conversation summaries in Python.

    ``sort_by`` is one of ``"newest"``, ``"oldest"``, ``"unread"``,
    or ``"name_asc"``.
    """
    if sort_by == "oldest":
        return sorted(summaries, key=lambda s: s["latest_message"].timestamp)
    if sort_by == "unread":
        return sorted(summaries, key=lambda s: s["unread_count"], reverse=True)
    if sort_by == "name_asc":
        return sorted(
            summaries,
            key=lambda s: (
                s["other_user"].first_name if s["other_user"] else "",
                s["other_user"].last_name if s["other_user"] else "",
            ),
        )
    # newest (default) — already sorted by timestamp DESC from query
    return summaries


def filter_by_archive_status(summaries, status):
    """Filter summaries by archive status.

    ``status`` is ``"inbox"`` (default, non-archived) or ``"archived"``.
    """
    if status == "archived":
        return [s for s in summaries if s.get("is_archived")]
    # inbox (default)
    return [s for s in summaries if not s.get("is_archived")]
