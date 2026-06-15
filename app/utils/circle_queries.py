from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from app import db
from app.models import Circle, CircleJoinRequest, Item, ItemRequest, User, circle_members


def filter_circles_by_distance(circles, user, radius=None):
    if not circles or not radius or not user.is_geocoded:
        return circles

    radius_miles = float(radius)
    filtered_circles = []
    for circle in circles:
        distance = circle.distance_to_user(user)
        if distance is not None and distance <= radius_miles:
            filtered_circles.append(circle)

    return filtered_circles


def sort_circles_by_membership(circles):
    return sorted(circles, key=lambda circle: len(circle.members), reverse=True)


def _circle_member_user_ids_query(circle_id):
    return (
        select(circle_members.c.user_id).where(circle_members.c.circle_id == circle_id).distinct()
    )


def _distance_tier(distance):
    if distance is None:
        return float("inf")
    if distance < 1:
        return 0
    return int(distance)


def _recommendation_sort_key(circle, user):
    distance = circle.distance_to_user(user)
    distance_tier = _distance_tier(distance)
    return (
        distance_tier,
        -len(circle.members),
        distance if distance is not None else float("inf"),
        circle.circle_type != "open",
        (circle.name or "").casefold(),
    )


def _regional_recommendation_sort_key(circle, user):
    distance = circle.distance_to_user(user)
    return (
        distance if distance is not None else float("inf"),
        -len(circle.members),
        (circle.name or "").casefold(),
    )


def _user_within_regional_circle(circle, user):
    if not circle.is_regional or circle.regional_radius_miles is None:
        return False
    if not (circle.is_geocoded and user.is_geocoded):
        return False

    distance = circle.distance_to_user(user)
    return distance is not None and distance <= circle.regional_radius_miles


def _format_unlock_count_text(value, label):
    suffix = "" if value == 1 else "s"
    return f"{value} {label}{suffix}"


def _build_visible_counts(counts, specs):
    visible_counts = []
    for key, label in specs:
        value = counts[key]
        if value <= 0:
            continue
        visible_counts.append(
            {
                "key": key,
                "value": value,
                "label": label,
                "text": _format_unlock_count_text(value, label),
            }
        )

    return visible_counts


def _build_visible_display_counts(display_counts):
    return _build_visible_counts(
        display_counts,
        (
            ("borrowable_items", "borrowable item"),
            ("giveaways", "giveaway"),
            ("requests", "request"),
        ),
    )


def _join_human_readable(parts):
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def get_circle_unlock_counts(circle):
    member_user_ids = _circle_member_user_ids_query(circle.id)
    now = datetime.now(UTC)
    fulfilled_cutoff = now - timedelta(days=7)

    borrowable_items = (
        db.session.query(db.func.count(Item.id))
        .join(User, Item.owner_id == User.id)
        .filter(
            Item.owner_id.in_(member_user_ids),
            Item.available.is_(True),
            Item.is_giveaway.is_(False),
            User.is_deleted.is_(False),
            User.vacation_mode.is_(False),
        )
        .scalar()
        or 0
    )

    giveaways = (
        db.session.query(db.func.count(Item.id))
        .join(User, Item.owner_id == User.id)
        .filter(
            Item.owner_id.in_(member_user_ids),
            Item.available.is_(True),
            Item.is_giveaway.is_(True),
            Item.giveaway_visibility == "default",
            or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
            User.is_deleted.is_(False),
            User.vacation_mode.is_(False),
        )
        .scalar()
        or 0
    )

    requests = (
        db.session.query(db.func.count(ItemRequest.id))
        .join(User, ItemRequest.user_id == User.id)
        .filter(
            ItemRequest.user_id.in_(member_user_ids),
            ItemRequest.visibility == "circles",
            User.is_deleted.is_(False),
            User.vacation_mode.is_(False),
            or_(
                and_(
                    ItemRequest.status == "open",
                    ItemRequest.expires_at > now,
                ),
                and_(
                    ItemRequest.status == "fulfilled",
                    ItemRequest.fulfilled_at > fulfilled_cutoff,
                ),
            ),
        )
        .scalar()
        or 0
    )

    return {
        "borrowable_items": borrowable_items,
        "giveaways": giveaways,
        "requests": requests,
    }


def get_circle_member_activity_counts(circle):
    member_user_ids = _circle_member_user_ids_query(circle.id)
    now = datetime.now(UTC)
    fulfilled_cutoff = now - timedelta(days=7)

    giveaways = (
        db.session.query(db.func.count(Item.id))
        .join(User, Item.owner_id == User.id)
        .filter(
            Item.owner_id.in_(member_user_ids),
            Item.available.is_(True),
            Item.is_giveaway.is_(True),
            or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
            User.is_deleted.is_(False),
            User.vacation_mode.is_(False),
        )
        .scalar()
        or 0
    )

    requests = (
        db.session.query(db.func.count(ItemRequest.id))
        .join(User, ItemRequest.user_id == User.id)
        .filter(
            ItemRequest.user_id.in_(member_user_ids),
            User.is_deleted.is_(False),
            User.vacation_mode.is_(False),
            or_(
                and_(
                    ItemRequest.status == "open",
                    ItemRequest.expires_at > now,
                ),
                and_(
                    ItemRequest.status == "fulfilled",
                    ItemRequest.fulfilled_at > fulfilled_cutoff,
                ),
            ),
        )
        .scalar()
        or 0
    )

    return {
        "giveaways": giveaways,
        "requests": requests,
    }


def _build_display_counts(unlock_counts, member_activity_counts):
    return {
        "borrowable_items": unlock_counts["borrowable_items"],
        "giveaways": member_activity_counts["giveaways"],
        "requests": member_activity_counts["requests"],
    }


def _build_circle_recommendation(circle):
    unlock_counts = get_circle_unlock_counts(circle)
    visible_unlock_counts = _build_visible_display_counts(unlock_counts)
    member_activity_counts = get_circle_member_activity_counts(circle)
    display_counts = _build_display_counts(unlock_counts, member_activity_counts)
    visible_display_counts = _build_visible_display_counts(display_counts)
    return {
        "circle": circle,
        "is_open": circle.circle_type == "open",
        "is_regional": circle.is_regional,
        "regional_radius_miles": circle.regional_radius_miles,
        "join_label": "Join Circle" if circle.circle_type == "open" else "Request to Join",
        "unlock_counts": unlock_counts,
        "unlock_total": sum(unlock_counts.values()),
        "visible_unlock_counts": visible_unlock_counts,
        "visible_unlock_text": _join_human_readable(
            [count["text"] for count in visible_unlock_counts]
        ),
        "member_activity_counts": member_activity_counts,
        "display_counts": display_counts,
        "visible_display_counts": visible_display_counts,
        "visible_display_text": _join_human_readable(
            [count["text"] for count in visible_display_counts]
        ),
    }


def _get_pinned_regional_circles(user, user_circle_ids, limit, radius=None):
    if limit <= 0 or not user.is_geocoded:
        return []

    regional_candidates = [
        circle
        for circle in get_listed_circles(user, radius=radius)
        if circle.id not in user_circle_ids and _user_within_regional_circle(circle, user)
    ]
    return sorted(
        regional_candidates,
        key=lambda circle: _regional_recommendation_sort_key(circle, user),
    )[: min(limit, 2)]


def build_circle_recommendations(user, *, circles=None, limit=3, radius=None):
    user_circle_ids = {circle.id for circle in user.circles}
    candidate_circles = circles if circles is not None else get_listed_circles(user, radius=radius)
    candidate_circles = [circle for circle in candidate_circles if circle.id not in user_circle_ids]
    ranked_circles = sorted(
        candidate_circles, key=lambda circle: _recommendation_sort_key(circle, user)
    )

    selected_circles = []
    selected_circle_ids = set()

    for circle in _get_pinned_regional_circles(user, user_circle_ids, limit, radius=radius):
        selected_circles.append(circle)
        selected_circle_ids.add(circle.id)

    for circle in ranked_circles:
        if circle.id in selected_circle_ids:
            continue
        selected_circles.append(circle)
        selected_circle_ids.add(circle.id)
        if len(selected_circles) >= limit:
            break

    recommendations = []
    for circle in selected_circles[:limit]:
        recommendations.append(_build_circle_recommendation(circle))

    return recommendations


def get_admin_circle_pending_counts(user_id):
    admin_circle_counts = (
        db.session.query(
            Circle.id.cast(db.String).label("circle_id"),
            db.func.count(CircleJoinRequest.id).label("pending_count"),
        )
        .join(circle_members, Circle.id == circle_members.c.circle_id)
        .outerjoin(
            CircleJoinRequest,
            and_(
                Circle.id == CircleJoinRequest.circle_id,
                CircleJoinRequest.status == "pending",
            ),
        )
        .filter(circle_members.c.user_id == user_id, circle_members.c.is_admin)
        .group_by(Circle.id)
        .all()
    )
    return {circle_id: count for circle_id, count in admin_circle_counts}


def get_listed_circles(user, search_query="", radius=None):
    if search_query:
        circles_query = Circle.query.filter(
            and_(
                Circle.name.ilike(f"%{search_query}%"),
                Circle.circle_type != "secret",
            )
        )
    else:
        circles_query = Circle.query.filter(Circle.circle_type != "secret")

    circles = circles_query.all()
    circles = filter_circles_by_distance(circles, user, radius)
    return sort_circles_by_membership(circles)


def get_sorted_user_circles(user):
    return sorted(user.circles, key=lambda circle: len(circle.members), reverse=True)


def get_pending_circle_join_request(circle_id, user_id):
    return CircleJoinRequest.query.filter_by(
        circle_id=circle_id,
        user_id=user_id,
        status="pending",
    ).first()


def should_show_circle_members(circle, viewer):
    return not circle.requires_join_approval or viewer in circle.members


def get_ordered_circle_members(circle_id):
    members_info = (
        db.session.query(User, circle_members.c.joined_at, circle_members.c.is_admin)
        .join(
            circle_members,
            and_(User.id == circle_members.c.user_id, circle_members.c.circle_id == circle_id),
        )
        .all()
    )
    return sorted(members_info, key=lambda member: (not member.is_admin, member.joined_at))
