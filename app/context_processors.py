# app/context_processors.py

from flask_login import current_user
from sqlalchemy import select
from app.utils.geocoding import format_distance
# Remove model imports from top level

def inject_unread_messages_count():
    # Import models at function level to avoid circular imports
    from app import db
    from app.models import Message, CircleJoinRequest, circle_members

    if current_user.is_authenticated:
        # Count all unread messages where the current user is the recipient
        # This includes both regular messages and loan request messages (approvals, denials, etc.)
        unread_messages = Message.query.filter(
            Message.recipient_id == current_user.id,
            Message.is_read == False,
            Message.sender_id != current_user.id  # Exclude self-sent messages
        ).count()

        # Also include pending circle join requests for circles where the user is an admin
        # Find circles current_user administers
        admin_circle_ids_sq = select(circle_members.c.circle_id).where(
            circle_members.c.user_id == current_user.id,
            circle_members.c.is_admin == True,
        )

        pending_join_requests = (
            db.session.query(CircleJoinRequest)
            .filter(
                CircleJoinRequest.circle_id.in_(admin_circle_ids_sq),
                CircleJoinRequest.status == 'pending',
            )
            .count()
        )

        return dict(unread_messages_count=unread_messages + pending_join_requests)
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

def inject_distance_utils():
    """Make distance calculation utilities available in templates"""
    def get_distance_to_item(item):
        """Calculate distance from current user to item owner"""
        try:
            # Check if current_user is available and properly initialized
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return None
            if not hasattr(current_user, 'is_geocoded') or not current_user.is_geocoded:
                return None
            if not hasattr(item, 'owner') or not item.owner:
                return None
            if not hasattr(item.owner, 'is_geocoded') or not item.owner.is_geocoded:
                return None
            
            distance = current_user.distance_to(item.owner)
            return format_distance(distance) if distance is not None else None
        except Exception:
            # In case of any error (e.g., in test environment), return None
            return None
    
    def get_distance_to_circle(circle):
        """Calculate distance from current user to circle center"""
        try:
            # Check if current_user is available and properly initialized
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return None
            if not hasattr(current_user, 'is_geocoded') or not current_user.is_geocoded:
                return None
            if not hasattr(circle, 'is_geocoded') or not circle.is_geocoded:
                return None
            
            distance = circle.distance_to_user(current_user)
            return format_distance(distance) if distance is not None else None
        except Exception:
            # In case of any error (e.g., in test environment), return None
            return None
    
    def get_distance_to_user(user):
        """Calculate distance from current user to another user"""
        try:
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return None
            if not hasattr(current_user, 'is_geocoded') or not current_user.is_geocoded:
                return None
            if not hasattr(user, 'is_geocoded') or not user.is_geocoded:
                return None
            
            distance = current_user.distance_to(user)
            return format_distance(distance) if distance is not None else None
        except Exception:
            return None
    
    return {
        'get_distance_to_item': get_distance_to_item,
        'get_distance_to_circle': get_distance_to_circle,
        'get_distance_to_user': get_distance_to_user
    }