from datetime import datetime

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.models import ItemRequest


class ItemRequestForm(FlaskForm):
    """Form for creating or editing a community item request."""

    title = StringField(
        "What are you looking for?",
        validators=[
            DataRequired(message="A short title is required."),
            Length(max=100, message="Title must be under 100 characters."),
        ],
    )
    description = TextAreaField(
        "More details (optional)",
        validators=[
            Optional(),
            Length(max=1000, message="Description must be under 1000 characters."),
        ],
    )
    expires_at = DateField(
        "Request expires on",
        validators=[DataRequired(message="Please select an expiration date.")],
    )
    seeking = SelectField(
        "What are you looking for?",
        choices=ItemRequest.SEEKING_CHOICES,
        default="either",
        validators=[DataRequired()],
    )
    visibility = SelectField(
        "Who can see this?",
        choices=ItemRequest.VISIBILITY_CHOICES,
        default="public",
        validators=[DataRequired()],
    )
    submit = SubmitField("Post Request")

    def validate_expires_at(self, field):
        """Expiration must be between today and 6 months from today."""
        from dateutil.relativedelta import relativedelta

        today = datetime.now().date()
        max_date = today + relativedelta(months=6)
        if field.data < today:
            raise ValidationError("Expiration date cannot be in the past.")
        if field.data > max_date:
            raise ValidationError("Expiration date cannot be more than 6 months from today.")

    def validate_visibility(self, field):
        """Public visibility requires user to have a location set."""
        if field.data == "public":
            if current_user.is_authenticated and not current_user.is_geocoded:
                raise ValidationError(
                    "You must set your location before making a request public. "
                    "Public requests are visible to everyone on Meutch and users "
                    "will have no idea where you are located. "
                    "Please update your location in your profile settings."
                )
