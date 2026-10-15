"""Which months each user counts as active.

Sam donates $1 to charity per active user per month, so the admin chart and the
profile card must apply exactly the same rules; both go through this module.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import and_, exists, false, func, select, true, union_all

from app import db
from app.models import (
    Conversation,
    GiveawayInterest,
    Item,
    ItemRequest,
    LoanRequest,
    Message,
    User,
    circle_members,
)

ACTIVE_MONTHS_START = datetime(2026, 4, 1, tzinfo=UTC)
MEET_MEUTCH_POST_URL = "https://samfirke.com/2026/05/12/meet-meutch/#charity"


@dataclass
class ActiveMonthsSummary:
    months_counted: int
    active_this_month: bool
    current_month: date
    in_shared_circle: bool


def month_start(when):
    return when.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(start):
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def _shared_circle_ids():
    # pylint: disable=not-callable
    return (
        select(circle_members.c.circle_id.label("circle_id"))
        .group_by(circle_members.c.circle_id)
        .having(func.count(circle_members.c.user_id) >= 2)
        .subquery()
    )


def _active_user_months(first_month, end_month, user_id=None):
    """Select distinct (month_start, user_id) pairs of qualifying activity.

    A user counts once they belong to a circle with at least one other member,
    and only for activity after joining it.
    """
    # pylint: disable=not-callable
    shared_circle_ids = _shared_circle_ids()
    eligible_users = (
        select(
            circle_members.c.user_id.label("user_id"),
            func.min(circle_members.c.joined_at).label("eligible_from"),
        )
        .join(shared_circle_ids, shared_circle_ids.c.circle_id == circle_members.c.circle_id)
        .group_by(circle_members.c.user_id)
        .subquery()
    )

    activity = union_all(
        select(
            ItemRequest.user_id.label("user_id"),
            ItemRequest.created_at.label("event_at"),
        ),
        select(
            Item.owner_id.label("user_id"),
            Item.created_at.label("event_at"),
        ),
        select(
            LoanRequest.borrower_id.label("user_id"),
            LoanRequest.created_at.label("event_at"),
        ),
        select(
            Message.sender_id.label("user_id"),
            Message.timestamp.label("event_at"),
        )
        .join(LoanRequest, Message.loan_request_id == LoanRequest.id)
        .join(Item, LoanRequest.item_id == Item.id)
        .where(Message.sender_id == Item.owner_id),
        select(
            Message.sender_id.label("user_id"),
            Message.timestamp.label("event_at"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(
            ItemRequest,
            and_(
                Conversation.context_type == "request",
                Conversation.context_id == ItemRequest.id,
            ),
        )
        .where(Message.sender_id != ItemRequest.user_id),
        select(
            Message.sender_id.label("user_id"),
            Message.timestamp.label("event_at"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(
            Item,
            and_(
                Conversation.context_type == "item",
                Conversation.context_id == Item.id,
            ),
        )
        .where(
            Item.is_giveaway.is_(true()),
            Message.sender_id != Item.owner_id,
        ),
        select(
            GiveawayInterest.user_id.label("user_id"),
            GiveawayInterest.created_at.label("event_at"),
        )
        .join(Item, GiveawayInterest.item_id == Item.id)
        .where(
            Item.is_giveaway.is_(true()),
            GiveawayInterest.user_id != Item.owner_id,
        ),
    ).subquery()

    event_month = func.date_trunc("month", activity.c.event_at).label("month_start")
    query = (
        select(event_month, activity.c.user_id)
        .join(eligible_users, eligible_users.c.user_id == activity.c.user_id)
        .join(User, User.id == activity.c.user_id)
        .where(
            User.is_deleted.is_(false()),
            activity.c.event_at >= first_month,
            activity.c.event_at < end_month,
            activity.c.event_at >= eligible_users.c.eligible_from,
        )
        .distinct()
    )
    if user_id is not None:
        query = query.where(activity.c.user_id == user_id)
    return query.subquery()


def monthly_active_user_counts(first_month, end_month):
    """Return {(year, month): active user count} for months in [first_month, end_month)."""
    # pylint: disable=not-callable
    user_months = _active_user_months(first_month, end_month)
    rows = db.session.execute(
        select(user_months.c.month_start, func.count(user_months.c.user_id)).group_by(
            user_months.c.month_start
        )
    ).all()
    return {(start.year, start.month): count for start, count in rows}


def user_active_months(user):
    """Summarize which months the user has counted as active since ACTIVE_MONTHS_START."""
    current_month = month_start(datetime.now(UTC))
    user_months = _active_user_months(ACTIVE_MONTHS_START, next_month(current_month), user.id)
    months = {
        (start.year, start.month)
        for start in db.session.execute(select(user_months.c.month_start)).scalars()
    }
    current_key = (current_month.year, current_month.month)

    shared_circle_ids = _shared_circle_ids()
    in_shared_circle = db.session.execute(
        select(
            exists().where(
                circle_members.c.user_id == user.id,
                circle_members.c.circle_id.in_(select(shared_circle_ids.c.circle_id)),
            )
        )
    ).scalar()

    return ActiveMonthsSummary(
        months_counted=len(months),
        active_this_month=current_key in months,
        current_month=current_month.date(),
        in_shared_circle=in_shared_circle,
    )
