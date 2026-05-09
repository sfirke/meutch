import logging
from datetime import UTC, datetime

from app import db
from app.models import CircleJoinRequest, Message, circle_members
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.email import (
    send_circle_join_request_decision_email,
    send_circle_join_request_notification_email,
)

logger = logging.getLogger(__name__)


def join_circle(circle, user, message_text=None):
    if user in circle.members:
        raise InformationalError("You are already a member of this circle.")

    if circle.requires_join_approval:
        join_request = CircleJoinRequest(
            circle_id=circle.id,
            user_id=user.id,
            message=message_text,
        )
        db.session.add(join_request)
        db.session.commit()

        try:
            send_circle_join_request_notification_email(join_request)
        except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
            logger.error(
                "Failed to send email notification for circle join request %s: %s",
                join_request.id,
                exc,
            )
        return join_request

    stmt = circle_members.insert().values(
        user_id=user.id,
        circle_id=circle.id,
        joined_at=datetime.now(UTC),
        is_admin=False,
    )
    db.session.execute(stmt)
    db.session.commit()
    return None


def handle_join_request(circle, join_request, acting_user, action):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("You must be an admin to perform this action.")

    if join_request.circle_id != circle.id:
        raise InvalidActionError("Invalid join request.")

    if join_request.status != "pending":
        raise InformationalError("This join request has already been handled.")

    if action == "approve":
        stmt = circle_members.insert().values(
            user_id=join_request.user_id,
            circle_id=circle.id,
            joined_at=datetime.now(UTC),
            is_admin=False,
        )
        db.session.execute(stmt)
        join_request.status = "approved"
        decision_message = Message(
            sender_id=acting_user.id,
            recipient_id=join_request.user_id,
            circle_id=circle.id,
            body=f"Your request to join '{circle.name}' has been approved.",
        )
        db.session.add(decision_message)
    elif action == "reject":
        join_request.status = "rejected"
        decision_message = Message(
            sender_id=acting_user.id,
            recipient_id=join_request.user_id,
            circle_id=circle.id,
            body=f"Your request to join '{circle.name}' has been denied.",
        )
        db.session.add(decision_message)
    else:
        raise InvalidActionError("Invalid action.")

    db.session.commit()

    try:
        send_circle_join_request_decision_email(join_request)
    except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
        logger.error(
            "Failed to send email notification for circle join request decision %s: %s",
            join_request.id,
            exc,
        )

    return action


def cancel_join_request(circle_id, user_id):
    pending_request = CircleJoinRequest.query.filter_by(
        circle_id=circle_id,
        user_id=user_id,
        status="pending",
    ).first()
    if not pending_request:
        return False

    db.session.delete(pending_request)
    db.session.commit()
    return True


def toggle_admin(circle, user_id, acting_user, action):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("You must be an admin to perform this action.")

    user_member = (
        db.session.query(circle_members)
        .filter_by(
            circle_id=circle.id,
            user_id=user_id,
        )
        .first()
    )
    if not user_member:
        raise ConflictError("User is not a member of this circle.")

    if action == "add":
        is_admin = True
    elif action == "remove":
        is_admin = False
    else:
        raise InvalidActionError("Invalid action.")

    stmt = (
        circle_members.update()
        .where((circle_members.c.circle_id == circle.id) & (circle_members.c.user_id == user_id))
        .values(is_admin=is_admin)
    )
    db.session.execute(stmt)
    db.session.commit()
    return is_admin
