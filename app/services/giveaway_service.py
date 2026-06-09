import logging
import random
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import GiveawayInterest, Message, User
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.email import send_message_notification_email

logger = logging.getLogger(__name__)


def _send_notification_email(message, error_prefix):
    try:
        send_message_notification_email(message)
    except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
        logger.error("%s: %s", error_prefix, exc)


def _commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def get_giveaway_interest_annotations(item_id, owner_id):
    """Return per-user conversation metadata for each active or selected interest.

    Returns a dict keyed by user_id (UUID) with:
        conversation_message_id: UUID or None
        unread_count: int
        message_count: int
        has_conversation: bool
        latest_message: Message or None

    Uses a single batched Message query so callers never need N+1 per-user queries.
    """
    from sqlalchemy import and_, or_

    interests = (
        GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item_id,
            GiveawayInterest.status.in_(["active", "selected"]),
        )
        .order_by(GiveawayInterest.created_at)
        .all()
    )

    interest_user_ids = {interest.user_id for interest in interests}
    if not interest_user_ids:
        return {}

    all_messages = (
        Message.query.filter(
            Message.item_id == item_id,
            or_(
                and_(
                    Message.sender_id == owner_id,
                    Message.recipient_id.in_(interest_user_ids),
                ),
                and_(
                    Message.sender_id.in_(interest_user_ids),
                    Message.recipient_id == owner_id,
                ),
            ),
        )
        .order_by(Message.timestamp)
        .all()
    )

    messages_by_user = {}
    for message in all_messages:
        counterpart_id = (
            message.recipient_id if message.sender_id == owner_id else message.sender_id
        )
        messages_by_user.setdefault(counterpart_id, []).append(message)

    annotations = {}
    for interest in interests:
        conversation_messages = messages_by_user.get(interest.user_id, [])
        latest_message = conversation_messages[-1] if conversation_messages else None
        annotations[interest.user_id] = {
            "conversation_message_id": latest_message.id if latest_message else None,
            "unread_count": sum(
                1
                for message in conversation_messages
                if message.recipient_id == owner_id and not message.is_read
            ),
            "message_count": len(conversation_messages),
            "has_conversation": len(conversation_messages) > 0,
            "latest_message": latest_message,
        }

    return annotations


def get_giveaway_interest_state(item, user_id):
    """Return the authenticated user's giveaway-interest context for one item.

    Returns a dict with:
        viewer_interest_status: None, "active", or "selected"
        interested_count: int (owner only) or None
    """
    viewer_interest_status = None
    interested_count = None

    if not item.is_giveaway:
        return {
            "viewer_interest_status": viewer_interest_status,
            "interested_count": interested_count,
        }

    viewer_interest = GiveawayInterest.query.filter_by(
        item_id=item.id,
        user_id=user_id,
    ).first()
    if viewer_interest:
        viewer_interest_status = viewer_interest.status

    if item.owner_id == user_id:
        interested_count = GiveawayInterest.query.filter_by(
            item_id=item.id,
            status="active",
        ).count()

    return {
        "viewer_interest_status": viewer_interest_status,
        "interested_count": interested_count,
    }


def _build_selection_message(item, sender_id, recipient_id):
    notification_message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        item_id=item.id,
        body=(
            f"Good news! You've been selected for the giveaway '{item.name}'! "
            "Please coordinate pickup with the owner."
        ),
    )
    db.session.add(notification_message)
    return notification_message


def _finalize_recipient_selection(item, selected_interest, sender_id):
    item.claim_status = "pending_pickup"
    item.claimed_by_id = selected_interest.user_id
    item.claimed_at = None
    item.available = False
    selected_interest.status = "selected"

    notification_message = _build_selection_message(item, sender_id, selected_interest.user_id)
    _commit()
    _send_notification_email(
        notification_message,
        f"Failed to send email notification for giveaway selection message {notification_message.id}",
    )
    return selected_interest


def express_interest(item, user_id, message_text):
    if not item.is_giveaway:
        raise InvalidActionError("This item is not a giveaway.")

    if item.claim_status not in [None, "unclaimed"]:
        raise ConflictError("This giveaway is no longer available.")

    if item.owner_id == user_id:
        raise ConflictError("You cannot express interest in your own giveaway.")

    cleaned_message = message_text.strip() if message_text else None
    notification_body = cleaned_message or f"Hi! I'm interested in your giveaway '{item.name}'."

    interest = GiveawayInterest(
        item_id=item.id,
        user_id=user_id,
        message=cleaned_message,
        status="active",
    )
    message = Message(
        sender_id=user_id,
        recipient_id=item.owner_id,
        item_id=item.id,
        body=notification_body,
    )
    db.session.add(interest)
    db.session.add(message)

    try:
        _commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise InformationalError("You have already expressed interest in this giveaway.") from exc

    _send_notification_email(
        message,
        f"Failed to send email notification for giveaway interest message {message.id}",
    )
    return interest


def withdraw_interest(item, user_id):
    interest = GiveawayInterest.query.filter_by(item_id=item.id, user_id=user_id).first()
    if not interest:
        raise ConflictError("You have not expressed interest in this giveaway.")

    db.session.delete(interest)
    _commit()


def select_recipient(item, owner_id, selection_method, selected_user_id=None):
    if item.owner_id != owner_id:
        raise AuthorizationError("You do not have permission to manage this giveaway.")

    if not item.is_giveaway:
        raise InvalidActionError("This item is not a giveaway.")

    if item.claim_status not in [None, "unclaimed", "pending_pickup"]:
        raise ConflictError("This giveaway has already been claimed.")

    active_interests = (
        GiveawayInterest.query.filter_by(item_id=item.id, status="active")
        .order_by(GiveawayInterest.created_at)
        .all()
    )
    if not active_interests:
        raise ConflictError("No interested users found.")

    if selection_method == "first":
        selected_interest = active_interests[0]
    elif selection_method == "random":
        selected_interest = random.choice(active_interests)
    elif selection_method == "manual":
        selected_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=selected_user_id,
            status="active",
        ).first()
    else:
        raise InvalidActionError("Invalid selection. Please try again.")

    if not selected_interest:
        raise InvalidActionError("Invalid selection. Please try again.")

    return _finalize_recipient_selection(item, selected_interest, owner_id)


def change_recipient(item, owner_id, selection_method, selected_user_id=None):
    if item.owner_id != owner_id:
        raise AuthorizationError("You do not have permission to manage this giveaway.")

    if not item.is_giveaway:
        raise InvalidActionError("This item is not a giveaway.")

    if item.claim_status != "pending_pickup":
        raise ConflictError("This giveaway is not pending pickup.")

    previous_claimed_by_id = item.claimed_by_id
    active_interests = (
        GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.status == "active",
            GiveawayInterest.user_id != previous_claimed_by_id,
        )
        .order_by(GiveawayInterest.created_at)
        .all()
    )
    if not active_interests:
        raise ConflictError("No other interested users available to select.")

    if selection_method == "next":
        selected_interest = active_interests[0]
    elif selection_method == "random":
        selected_interest = random.choice(active_interests)
    elif selection_method == "manual":
        if str(selected_user_id) == str(previous_claimed_by_id):
            raise ConflictError("That recipient is currently selected.")
        selected_interest = GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.user_id == selected_user_id,
            GiveawayInterest.status == "active",
            GiveawayInterest.user_id != previous_claimed_by_id,
        ).first()
    else:
        raise InvalidActionError("Invalid selection. Please try again.")

    if not selected_interest:
        raise InvalidActionError("Invalid selection. Please try again.")

    previous_interest = GiveawayInterest.query.filter_by(
        item_id=item.id,
        user_id=previous_claimed_by_id,
    ).first()
    if previous_interest:
        previous_interest.status = "active"

    previous_notification = None
    previous_recipient = (
        db.session.get(User, previous_claimed_by_id) if previous_claimed_by_id else None
    )
    if previous_recipient:
        previous_notification = Message(
            sender_id=owner_id,
            recipient_id=previous_recipient.id,
            item_id=item.id,
            body=(
                f"The owner has selected a different recipient for the giveaway '{item.name}'. "
                "Your interest remains active and you may still be selected in the future."
            ),
        )
        db.session.add(previous_notification)

    item.claimed_by_id = selected_interest.user_id
    selected_interest.status = "selected"
    notification_message = _build_selection_message(item, owner_id, selected_interest.user_id)

    _commit()
    _send_notification_email(
        notification_message,
        f"Failed to send email notification for giveaway reassignment message {notification_message.id}",
    )
    if previous_notification:
        _send_notification_email(
            previous_notification,
            f"Failed to send email notification to previous recipient for giveaway {item.id}",
        )
    return selected_interest


def release_to_all(item, owner_id):
    if item.owner_id != owner_id:
        raise AuthorizationError("You do not have permission to manage this giveaway.")

    if not item.is_giveaway:
        raise InvalidActionError("This item is not a giveaway.")

    if item.claim_status != "pending_pickup":
        raise ConflictError("This giveaway is not pending pickup.")

    release_notification = None
    previous_recipient_id = item.claimed_by_id
    if previous_recipient_id:
        previous_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=previous_recipient_id,
        ).first()
        if previous_interest:
            previous_interest.status = "active"

        release_notification = Message(
            sender_id=owner_id,
            recipient_id=previous_recipient_id,
            item_id=item.id,
            body=(
                f"The owner has released the giveaway '{item.name}' back to everyone. "
                "Your interest remains active and you may still be selected."
            ),
        )
        db.session.add(release_notification)

    item.claim_status = "unclaimed"
    item.claimed_by_id = None
    item.available = True

    _commit()
    if release_notification:
        _send_notification_email(
            release_notification,
            f"Failed to send email notification for giveaway release message {release_notification.id}",
        )


def confirm_handoff(item, owner_id):
    if item.owner_id != owner_id:
        raise AuthorizationError("You do not have permission to manage this giveaway.")

    if not item.is_giveaway:
        raise InvalidActionError("This item is not a giveaway.")

    if item.claim_status != "pending_pickup":
        raise ConflictError("This giveaway is not pending pickup.")

    item.claim_status = "claimed"
    item.claimed_at = datetime.now(UTC)
    item.available = False
    _commit()
