# app/context_processors.py

from flask_login import current_user

def inject_unread_messages_count():
    if current_user.is_authenticated:
        from app.models import Message  # Local import to avoid circular dependency
        unread_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return dict(unread_messages_count=unread_count)
    return dict(unread_messages_count=0)