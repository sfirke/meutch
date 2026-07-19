"""Contact form for submitting messages to the Meutch team."""

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class ContactForm(FlaskForm):
    """Form for authenticated users to contact the Meutch team."""

    category = SelectField(
        "Category",
        choices=[
            ("bug_report", "Bug Report"),
            ("feature_suggestion", "Feature Suggestion"),
            ("question", "Question"),
        ],
        validators=[DataRequired()],
        validate_choice=True,
    )
    message = TextAreaField(
        "Message",
        validators=[DataRequired(), Length(min=10, max=2000)],
        render_kw={"rows": 6},
    )
    submit = SubmitField("Send")
