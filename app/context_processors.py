# app/context_processors.py

from flask_login import current_user
# Remove model imports from top level

def inject_unread_messages_count():
    # Import models at function level to avoid circular imports
    from app.models import Message, LoanRequest, Item

    if current_user.is_authenticated:
        # Count unread messages that are NOT loan request messages
        unread_messages = Message.query.filter(
            Message.recipient_id == current_user.id,
            Message.is_read == False,
            Message.sender_id != current_user.id,  # Exclude self-sent messages
            Message.loan_request_id.is_(None)  # Only count non-loan-request messages
        ).count()
        
        # Count pending loan requests for items user owns (these will have associated messages)
        pending_requests = LoanRequest.query.join(Item).filter(
            Item.owner_id == current_user.id,
            LoanRequest.status == 'pending'
        ).count()
        
        return dict(unread_messages_count=unread_messages + pending_requests)
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

def inject_has_pending_loans():
    # Import models at function level
    from app.models import LoanRequest, Item

    if current_user.is_authenticated:
        # Check if the user owns any items with pending loan requests
        pending_count = LoanRequest.query.join(Item).filter(
            Item.owner_id == current_user.id,
            LoanRequest.status == 'pending'
        ).count()
        return dict(has_pending_loans=pending_count > 0)
    return dict(has_pending_loans=False)