# app/context_processors.py

from flask_login import current_user

def inject_unread_messages_count():
    if current_user.is_authenticated:
        from app.models import Message  # Local import to avoid circular dependency
        unread_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return dict(unread_messages_count=unread_count)
    return dict(unread_messages_count=0)

def inject_total_pending():
    if not current_user.is_authenticated:
        return {'total_pending': 0}
    from app.models import Circle, CircleJoinRequest, db, circle_members
    # Get user's admin circles with pending request counts
    user_admin_circles = db.session.query(
        Circle,
        db.func.count(CircleJoinRequest.id).label('pending_count')
    ).join(
        circle_members,
        Circle.id == circle_members.c.circle_id
    ).outerjoin(
        CircleJoinRequest,
        db.and_(
            Circle.id == CircleJoinRequest.circle_id,
            CircleJoinRequest.status == 'pending'
        )
    ).filter(
        circle_members.c.user_id == current_user.id,
        circle_members.c.is_admin == True
    ).group_by(Circle.id).all()

    total_pending = sum(circle[1] for circle in user_admin_circles) if user_admin_circles else 0
    
    return {'total_pending': total_pending}