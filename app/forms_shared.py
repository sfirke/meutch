from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms.validators import URL

from app.models import User

DIGEST_FREQUENCY_CHOICES = [
    (User.DIGEST_FREQUENCY_WEEKLY, "Weekly (stay in the loop)"),
    (
        User.DIGEST_FREQUENCY_DAILY,
        "Daily (respond promptly to requests and giveaways)",
    ),
    (User.DIGEST_FREQUENCY_NONE, "Never (must log in to follow activity)"),
]


def OptionalURL(message=None):
    """
    Custom validator for optional URLs - only validates if field has data
    """

    def _validate(form, field):
        if field.data and field.data.strip():
            url_validator = URL(
                message=message or "Please enter a valid URL (starting with http:// or https://)"
            )
            url_validator(form, field)

    return _validate


def OptionalFileAllowed(upload_set, message=None):
    """
    Custom validator that allows empty files and validates non-empty files with FileAllowed
    """

    def _validate(form, field):
        if not field.data:
            return

        if hasattr(field.data, "filename") and field.data.filename and field.data.filename.strip():
            file_allowed = FileAllowed(upload_set, message)
            file_allowed(form, field)

    return _validate


class EmptyForm(FlaskForm):
    pass
