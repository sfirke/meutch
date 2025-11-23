"""Authorization decorators for the application"""
from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def admin_required(f):
    """
    Decorator that requires the current user to be an admin.
    Includes login_required functionality.
    Returns 403 Forbidden if user is not an admin.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
