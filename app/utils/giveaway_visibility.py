from datetime import UTC, datetime, timedelta
from sqlalchemy import or_, and_, select

from app.models import Item, User, circle_members


def _claimed_at_utc(claimed_at):
    if not claimed_at:
        return None
    if claimed_at.tzinfo is None:
        return claimed_at.replace(tzinfo=UTC)
    return claimed_at.astimezone(UTC)


def is_claimed_giveaway_within_visibility_window(item, now=None, days=90):
    if item.claim_status != 'claimed':
        return False

    claimed_at = _claimed_at_utc(item.claimed_at)
    if not claimed_at:
        return False

    current_time = now or datetime.now(UTC)
    return claimed_at >= (current_time - timedelta(days=days))


def is_giveaway_party(item, user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user.id == item.owner_id or user.id == item.claimed_by_id


def can_view_claimed_giveaway(item, user, now=None, days=90):
    return is_giveaway_party(item, user) and is_claimed_giveaway_within_visibility_window(item, now=now, days=days)


def get_unavailable_giveaway_suggestions(user, exclude_item_id=None, limit=4):
    is_authenticated = bool(user and getattr(user, 'is_authenticated', False))

    if is_authenticated:
        has_circles = len(user.circles) > 0
        if not has_circles:
            return []

        shared_circle_user_ids = user.get_shared_circle_user_ids_query()
        all_circle_user_ids = select(circle_members.c.user_id).distinct()

        query = Item.query.join(User, Item.owner_id == User.id).filter(
            Item.is_giveaway == True,
            User.vacation_mode == False,
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None)),
            Item.owner_id != user.id,
            or_(
                and_(
                    or_(Item.giveaway_visibility == 'default', Item.giveaway_visibility.is_(None)),
                    Item.owner_id.in_(shared_circle_user_ids)
                ),
                and_(
                    Item.giveaway_visibility == 'public',
                    Item.owner_id.in_(all_circle_user_ids)
                )
            )
        )
    else:
        showcase_user_ids = select(User.id).where(
            User.is_public_showcase == True,
            User.vacation_mode == False
        )

        query = Item.query.filter(
            Item.owner_id.in_(showcase_user_ids),
            Item.is_giveaway == True,
            Item.giveaway_visibility == 'public',
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None))
        )

    if exclude_item_id:
        query = query.filter(Item.id != exclude_item_id)

    return query.order_by(Item.created_at.desc()).limit(limit).all()