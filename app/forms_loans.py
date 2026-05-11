from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


class LoanRequestForm(FlaskForm):
    start_date = DateField(
        "Start Date",
        validators=[DataRequired(message="Please select a start date.")],
    )
    end_date = DateField(
        "End Date",
        validators=[DataRequired(message="Please select an end date.")],
    )
    message = TextAreaField(
        "Message to Owner",
        validators=[
            DataRequired(message="Please include a message with your request."),
            Length(
                min=10,
                max=1000,
                message="Message must be between 10 and 1000 characters.",
            ),
        ],
    )
    submit = SubmitField("Submit Request")

    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            raise ValidationError("End date must be after start date.")
        if field.data < datetime.now().date():
            raise ValidationError("End date cannot be in the past.")

    def validate_start_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError("Start date cannot be in the past.")


class ExtendLoanForm(FlaskForm):
    new_end_date = DateField(
        "New End Date",
        validators=[DataRequired(message="Please select a new end date.")],
    )
    message = TextAreaField(
        "Include a message to borrower (optional)",
        validators=[
            Optional(),
            Length(max=1000, message="Message must be under 1000 characters."),
        ],
    )
    submit = SubmitField("Extend Loan")

    def __init__(self, current_end_date=None, *args, **kwargs):
        super(ExtendLoanForm, self).__init__(*args, **kwargs)
        self.current_end_date = current_end_date

    def validate_new_end_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError("New end date cannot be in the past.")
