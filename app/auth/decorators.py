"""Authorization decorators for the application"""

from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user, login_required

from app import db


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


def login_required_or_public_preview(model, is_public, preview_endpoint):
    """
    Like login_required, but a logged-out visitor is sent to the public
    /share preview instead of the login page when the record is public.
    The view must take the record's id as its only URL argument, named the
    same as in the preview route.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(**kwargs):
            if not current_user.is_authenticated:
                (record_id,) = kwargs.values()
                record = db.session.get(model, record_id)
                if record and is_public(record):
                    return redirect(url_for(preview_endpoint, **kwargs))
            return login_required(f)(**kwargs)

        return decorated_function

    return decorator
