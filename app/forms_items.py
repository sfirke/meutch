from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    HiddenField,
    MultipleFileField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional

from app.models import Category


class ListItemForm(FlaskForm):
    name = StringField("Item Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Length(max=500)])
    category = SelectField("Category", coerce=str, validators=[DataRequired()])
    tags = StringField("Tags (comma-separated)", validators=[Length(max=200)])
    image = MultipleFileField("Images", validators=[])
    creation_token = HiddenField("Creation Token", validators=[Optional()])
    delete_images = HiddenField("Delete Images")
    image_order = HiddenField("Image Order")
    is_giveaway = BooleanField("This is a giveaway (free item)")
    giveaway_visibility = RadioField(
        "Giveaway Visibility",
        choices=[
            ("default", "Circles only - Only visible to users in my circles"),
            ("public", "Public - Visible to all users on the platform"),
        ],
        default="default",
        validators=[Optional()],
    )
    submit = SubmitField("List Item")
    submit_and_create_another = SubmitField("List Item & Create Another")

    def __init__(self, *args, **kwargs):
        super(ListItemForm, self).__init__(*args, **kwargs)
        self.category.choices = [("", "Select a category...")] + [
            (str(category.id), category.name) for category in Category.query.order_by("name")
        ]

    def validate(self, extra_validators=None):
        """Custom validation to ensure giveaway_visibility is set when is_giveaway is checked"""
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.is_giveaway.data and not self.giveaway_visibility.data:
            self.giveaway_visibility.errors.append(
                "Please select a visibility option for this giveaway."
            )
            rv = False

        if self.is_giveaway.data and self.giveaway_visibility.data == "public":
            if current_user.is_authenticated and not current_user.is_geocoded:
                self.giveaway_visibility.errors.append(
                    "You must set your location before making a giveaway public. "
                    "Public giveaways are visible to everyone on Meutch and users "
                    "will have no idea where the item is located. "
                    "Please update your location in your profile settings."
                )
                rv = False

        return rv


class DeleteItemForm(FlaskForm):
    submit = SubmitField("Delete")


class ExpressInterestForm(FlaskForm):
    message = TextAreaField(
        "Optional message to the owner",
        validators=[Optional(), Length(max=500, message="Message must be under 500 characters.")],
    )
    submit = SubmitField("Submit Interest")


class WithdrawInterestForm(FlaskForm):
    submit = SubmitField("Withdraw Interest")


class SelectRecipientForm(FlaskForm):
    selection_method = RadioField(
        "Selection Method",
        choices=[
            ("first", "First Requester"),
            ("random", "Random Selection"),
            ("manual", "Manual Selection"),
        ],
        validators=[DataRequired(message="Please select a method.")],
    )
    user_id = StringField("Selected User ID")
    submit = SubmitField("Select Recipient")


class ChangeRecipientForm(FlaskForm):
    """Form for changing the recipient of a giveaway that's pending pickup."""

    selection_method = RadioField(
        "Selection Method",
        choices=[
            ("next", "Next in Line"),
            ("random", "Random from Remaining"),
            ("manual", "Manual Selection"),
        ],
        validators=[DataRequired(message="Please select a method.")],
    )
    user_id = StringField("Selected User ID")
    submit = SubmitField("Change Recipient")


class ReleaseToAllForm(FlaskForm):
    """Form for releasing a giveaway back to unclaimed status."""

    submit = SubmitField("Release to Everyone")


class ConfirmHandoffForm(FlaskForm):
    """Form for confirming the handoff of a giveaway."""

    submit = SubmitField("Confirm Handoff Complete")
