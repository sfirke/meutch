from sqlalchemy import and_, func, or_

from app import db
from app.models import LoanRequest, Message, User


def get_conversation_other_user_id(message, viewer_id):
    if message.sender_id == viewer_id:
        return message.recipient_id
    if message.recipient_id == viewer_id:
        return message.sender_id
    return None


def build_message_target_filter(message):
    if message.is_request_message:
        return and_(
            Message.request_id == message.request_id,
            Message.item_id.is_(None),
            Message.circle_id.is_(None),
        )
    if message.is_circle_message:
        return and_(
            Message.circle_id == message.circle_id,
            Message.item_id.is_(None),
            Message.request_id.is_(None),
        )
    return and_(
        Message.item_id == message.item_id,
        Message.request_id.is_(None),
        Message.circle_id.is_(None),
    )


def build_message_participant_filter(sender_id, recipient_id):
    return or_(
        and_(
            Message.sender_id == sender_id,
            Message.recipient_id == recipient_id,
        ),
        and_(
            Message.sender_id == recipient_id,
            Message.recipient_id == sender_id,
        ),
    )


def build_inbox_summaries(viewer_id):
    latest_messages_subquery = (
        db.session.query(
            func.least(Message.sender_id, Message.recipient_id).label("user1_id"),
            func.greatest(Message.sender_id, Message.recipient_id).label("user2_id"),
            Message.item_id,
            Message.request_id,
            Message.circle_id,
            func.max(Message.timestamp).label("latest_timestamp"),  # pylint: disable=not-callable
        )
        .filter(or_(Message.sender_id == viewer_id, Message.recipient_id == viewer_id))
        .group_by(
            func.least(Message.sender_id, Message.recipient_id),
            func.greatest(Message.sender_id, Message.recipient_id),
            Message.item_id,
            Message.request_id,
            Message.circle_id,
        )
        .subquery()
    )

    latest_conversations = (
        db.session.query(Message)
        .join(
            latest_messages_subquery,
            and_(
                func.least(Message.sender_id, Message.recipient_id)
                == latest_messages_subquery.c.user1_id,
                func.greatest(Message.sender_id, Message.recipient_id)
                == latest_messages_subquery.c.user2_id,
                or_(
                    and_(Message.item_id.is_(None), latest_messages_subquery.c.item_id.is_(None)),
                    Message.item_id == latest_messages_subquery.c.item_id,
                ),
                or_(
                    and_(
                        Message.request_id.is_(None),
                        latest_messages_subquery.c.request_id.is_(None),
                    ),
                    Message.request_id == latest_messages_subquery.c.request_id,
                ),
                or_(
                    and_(
                        Message.circle_id.is_(None),
                        latest_messages_subquery.c.circle_id.is_(None),
                    ),
                    Message.circle_id == latest_messages_subquery.c.circle_id,
                ),
                Message.timestamp == latest_messages_subquery.c.latest_timestamp,
            ),
        )
        .order_by(Message.timestamp.desc())
        .all()
    )

    conversation_summaries = []
    for conversation in latest_conversations:
        other_user_id = get_conversation_other_user_id(conversation, viewer_id)
        other_user = db.session.get(User, other_user_id)
        target_filter = build_message_target_filter(conversation)

        conversation_summaries.append(
            {
                "conversation_id": (
                    f"{min(conversation.sender_id, conversation.recipient_id)}_"
                    f"{max(conversation.sender_id, conversation.recipient_id)}_"
                    f"{conversation.item_id}_{conversation.request_id}_{conversation.circle_id}"
                ),
                "other_user": other_user,
                "item": conversation.item if not conversation.is_request_message else None,
                "item_request": conversation.request if conversation.is_request_message else None,
                "circle": conversation.circle if conversation.is_circle_message else None,
                "latest_message": conversation,
                "unread_count": Message.query.filter(
                    target_filter,
                    Message.recipient_id == viewer_id,
                    Message.sender_id == other_user.id,
                    Message.is_read.is_(False),
                ).count(),
            }
        )

    return conversation_summaries


def get_conversation_thread_state(message, viewer_id):
    target_filter = build_message_target_filter(message)
    participant_filter = build_message_participant_filter(message.sender_id, message.recipient_id)

    thread_messages = (
        Message.query.filter(target_filter, participant_filter).order_by(Message.timestamp).all()
    )
    for thread_message in thread_messages:
        thread_message.other_user = (
            thread_message.recipient
            if thread_message.sender_id == viewer_id
            else thread_message.sender
        )

    unread_messages = Message.query.filter(
        target_filter,
        participant_filter,
        Message.recipient_id == viewer_id,
        Message.is_read.is_(False),
        or_(
            Message.loan_request_id.is_(None),
            ~Message.loan_request.has(LoanRequest.status == "pending"),
        ),
    ).all()
    has_unread_messages = len(unread_messages) > 0

    for unread_message in unread_messages:
        unread_message.is_read = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return {
        "thread_messages": thread_messages,
        "has_unread_messages": has_unread_messages,
    }


def build_request_conversation_summaries(request_id, viewer_id):
    messages = (
        Message.query.filter(
            Message.request_id == request_id,
            Message.item_id.is_(None),
        )
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
    return (
        Message.query.filter(
            Message.request_id == request_id,
            Message.item_id.is_(None),
            build_message_participant_filter(sender_id, recipient_id),
        )
        .order_by(Message.timestamp.asc())
        .first()
    )
