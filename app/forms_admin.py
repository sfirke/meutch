from datetime import UTC, datetime

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import URL, DataRequired, Length, Optional, ValidationError

from app.models import Announcement


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class AnnouncementForm(FlaskForm):
    message = TextAreaField(
        "Message",
        filters=[_strip],
        validators=[DataRequired(), Length(max=280)],
    )
    link_url = StringField(
        "Link URL (optional)",
        filters=[_strip],
        validators=[Optional(), Length(max=500), URL(message="Please enter a valid URL.")],
    )
    link_text = StringField(
        "Link text (optional)",
        filters=[_strip],
        validators=[Optional(), Length(max=60)],
    )
    level = SelectField(
        "Style", choices=Announcement.LEVEL_CHOICES, default=Announcement.LEVEL_INFO
    )
    starts_at = DateField("Starts on (blank = now)", validators=[Optional()])
    ends_at = DateField("Ends after (blank = until ended)", validators=[Optional()])
    dismissible = BooleanField("Members can dismiss it", default=True)
    submit = SubmitField("Post announcement")

    def validate_link_url(self, field):
        if field.data and not field.data.lower().startswith("https://"):
            raise ValidationError("Links must start with https://.")

    def validate_link_text(self, field):
        if field.data and not self.link_url.data:
            raise ValidationError("Link text needs a link URL.")

    def validate_ends_at(self, field):
        if field.data is None:
            return
        start_date = self.starts_at.data or datetime.now(UTC).date()
        if field.data < start_date:
            raise ValidationError("The end date can't be before the start date.")
