from sqlalchemy import and_

from app import db
from app.models import Circle, CircleJoinRequest, User, circle_members


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
