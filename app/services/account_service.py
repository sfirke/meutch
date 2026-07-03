import logging
from datetime import UTC, date, datetime

from sqlalchemy import and_, select

from app import db
from app.models import (
    CircleJoinRequest,
    Conversation,
    ConversationParticipant,
    Feedback,
    LoanRequest,
    Message,
    circle_members,
)
from app.utils.email import send_account_deletion_email
from app.utils.storage import delete_file

logger = logging.getLogger(__name__)


def delete_user_account(user):
    user_email = user.email
    user_first_name = user.first_name

    LoanRequest.query.filter_by(borrower_id=user.id, status="pending").update(
        {"status": "canceled"}
    )

    item_ids = [item.id for item in user.items]
    if item_ids:
        LoanRequest.query.filter(
            LoanRequest.item_id.in_(item_ids),
            LoanRequest.status == "pending",
        ).update({"status": "denied"}, synchronize_session=False)

    for circle in user.circles:
        if circle.is_admin(user):
            admin_count = (
                db.session.query(circle_members)
                .filter_by(circle_id=circle.id, is_admin=True)
                .count()
            )

            if admin_count == 1 and len(circle.members) > 1:
                next_admin_assoc = (
                    db.session.query(circle_members)
                    .filter(
                        circle_members.c.circle_id == circle.id,
                        circle_members.c.user_id != user.id,
                        circle_members.c.is_admin.is_(False),
                    )
                    .order_by(circle_members.c.joined_at)
                    .first()
                )

                if next_admin_assoc:
                    stmt = (
                        circle_members.update()
                        .where(
                            and_(
                                circle_members.c.circle_id == circle.id,
                                circle_members.c.user_id == next_admin_assoc.user_id,
                            )
                        )
                        .values(is_admin=True)
                    )
                    db.session.execute(stmt)

    user.circles.clear()
    CircleJoinRequest.query.filter_by(user_id=user.id).delete()
    Feedback.query.filter_by(reviewer_id=user.id).delete()

    for item in user.items[:]:
        has_active_loans = (
            LoanRequest.query.filter_by(item_id=item.id, status="approved")
            .filter(LoanRequest.end_date >= date.today())
            .first()
            is not None
        )

        if has_active_loans:
            item.available = False
        else:
            for image in item.images:
                delete_file(image.url)

            LoanRequest.query.filter_by(item_id=item.id).delete()
            # Delete messages via conversation lookup
            conv_ids = (
                db.session.query(Conversation.id)
                .filter(
                    Conversation.context_type == "item",
                    Conversation.context_id == item.id,
                )
                .subquery()
            )
            Message.query.filter(Message.conversation_id.in_(select(conv_ids))).delete(
                synchronize_session=False
            )
            ConversationParticipant.query.filter(
                ConversationParticipant.conversation_id.in_(select(conv_ids))
            ).delete(synchronize_session=False)
            Conversation.query.filter(
                Conversation.context_type == "item",
                Conversation.context_id == item.id,
            ).delete(synchronize_session=False)
            db.session.delete(item)

    if user.profile_image_url:
        delete_file(user.profile_image_url)

    try:
        send_account_deletion_email(user_email, user_first_name)
    except Exception as exc:  # pragma: no cover - email failure must not block deletion
        logger.error("Failed to send deletion confirmation email: %s", exc)

    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    user.email = f"deleted_{user.id}@deleted.meutch"
    db.session.commit()
