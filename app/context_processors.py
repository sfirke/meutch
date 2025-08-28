# app/context_processors.py

from flask_login import current_user
# Remove model imports from top level

def inject_unread_messages_count():
    # Import models at function level to avoid circular imports
    from app.models import Message

    if current_user.is_authenticated:
        # Count all unread messages where the current user is the recipient
        # This includes both regular messages and loan request messages (approvals, denials, etc.)
        unread_messages = Message.query.filter(
            Message.recipient_id == current_user.id,
            Message.is_read == False,
            Message.sender_id != current_user.id  # Exclude self-sent messages
        ).count()
        
        return dict(unread_messages_count=unread_messages)
    return dict(unread_messages_count=0)

def inject_total_pending():
    # Import models at function level
    from app.models import Circle, CircleJoinRequest, db, circle_members

    if not current_user.is_authenticated:
        return {'total_pending': 0}
        
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