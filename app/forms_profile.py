from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    FloatField,
    IntegerField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.forms_shared import DIGEST_FREQUENCY_CHOICES, OptionalFileAllowed, OptionalURL


class UpdateLocationForm(FlaskForm):
    location_method = RadioField(
        "How would you like to set your location?",
        choices=[
            ("address", "Enter an address (we'll look up coordinates)"),
            ("coordinates", "Enter latitude and longitude directly"),
            ("remove", "Remove my location"),
        ],
        default="address",
        validators=[DataRequired()],
    )

    street = StringField(
        "Street Address",
        validators=[
            Optional(),
            Length(max=200, message="Street address must be under 200 characters."),
        ],
    )
    city = StringField(
        "City",
        validators=[
            Optional(),
            Length(max=100, message="City must be under 100 characters."),
        ],
    )
    state = StringField(
        "State/Province",
        validators=[
            Optional(),
            Length(max=100, message="State/Province must be under 100 characters."),
        ],
    )
    zip_code = StringField(
        "Postal Code",
        validators=[
            Optional(),
            Length(max=20, message="Postal Code must be under 20 characters."),
        ],
    )
    country = StringField(
        "Country",
        validators=[
            Optional(),
            Length(max=100, message="Country must be under 100 characters."),
        ],
        default="USA",
    )

    latitude = FloatField(
        "Latitude",
        validators=[
            Optional(),
            NumberRange(min=-90, max=90, message="Latitude must be between -90 and 90 degrees."),
        ],
    )
    longitude = FloatField(
        "Longitude",
        validators=[
            Optional(),
            NumberRange(
                min=-180, max=180, message="Longitude must be between -180 and 180 degrees."
            ),
        ],
    )

    submit = SubmitField("Update Location")

    def validate(self, extra_validators=None):
        """Custom validation to ensure required fields are filled based on location method"""
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.location_method.data == "address":
            required_fields = [self.street, self.city, self.state, self.zip_code, self.country]
            for field in required_fields:
                if not field.data or not field.data.strip():
                    field.errors.append(f"{field.label.text} is required when entering an address.")
                    rv = False
        elif self.location_method.data == "coordinates":
            if self.latitude.data is None:
                self.latitude.errors.append(
                    "Latitude is required when entering coordinates directly."
                )
                rv = False
            if self.longitude.data is None:
                self.longitude.errors.append(
                    "Longitude is required when entering coordinates directly."
                )
                rv = False

        return rv


class EditProfileForm(FlaskForm):
    about_me = TextAreaField("About Me", validators=[Length(max=500)])
    profile_image = FileField(
        "Profile Picture",
        validators=[
            OptionalFileAllowed(
                ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
                "Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP",
            )
        ],
    )
    delete_image = BooleanField("Delete current profile picture")

    link_1_platform = SelectField("Platform 1", choices=[], validators=[Optional()])
    link_1_custom_name = StringField(
        "Custom Name 1",
        validators=[Optional(), Length(max=50)],
    )
    link_1_url = StringField("URL 1", validators=[OptionalURL()])

    link_2_platform = SelectField("Platform 2", choices=[], validators=[Optional()])
    link_2_custom_name = StringField(
        "Custom Name 2",
        validators=[Optional(), Length(max=50)],
    )
    link_2_url = StringField("URL 2", validators=[OptionalURL()])

    link_3_platform = SelectField("Platform 3", choices=[], validators=[Optional()])
    link_3_custom_name = StringField(
        "Custom Name 3",
        validators=[Optional(), Length(max=50)],
    )
    link_3_url = StringField("URL 3", validators=[OptionalURL()])

    link_4_platform = SelectField("Platform 4", choices=[], validators=[Optional()])
    link_4_custom_name = StringField(
        "Custom Name 4",
        validators=[Optional(), Length(max=50)],
    )
    link_4_url = StringField("URL 4", validators=[OptionalURL()])

    link_5_platform = SelectField("Platform 5", choices=[], validators=[Optional()])
    link_5_custom_name = StringField(
        "Custom Name 5",
        validators=[Optional(), Length(max=50)],
    )
    link_5_url = StringField("URL 5", validators=[OptionalURL()])

    submit = SubmitField("Update Profile")

    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        from app.models import UserWebLink

        platform_choices = [("", "Select a platform...")] + UserWebLink.PLATFORM_CHOICES
        self.link_1_platform.choices = platform_choices
        self.link_2_platform.choices = platform_choices
        self.link_3_platform.choices = platform_choices
        self.link_4_platform.choices = platform_choices
        self.link_5_platform.choices = platform_choices

    def validate(self, **kwargs):
        rv = FlaskForm.validate(self, **kwargs)
        if not rv:
            return False

        for index in range(1, 6):
            platform_field = getattr(self, f"link_{index}_platform")
            custom_name_field = getattr(self, f"link_{index}_custom_name")
            url_field = getattr(self, f"link_{index}_url")

            if url_field.data and url_field.data.strip() and not platform_field.data:
                platform_field.errors.append("Please select a platform when providing a URL.")
                rv = False

            if platform_field.data == "other":
                if not custom_name_field.data or not custom_name_field.data.strip():
                    custom_name_field.errors.append(
                        'Please provide a custom name when selecting "Other".'
                    )
                    rv = False
                if not url_field.data or not url_field.data.strip():
                    url_field.errors.append('Please provide a URL when selecting "Other".')
                    rv = False

        return rv


class DeleteAccountForm(FlaskForm):
    confirmation = StringField(
        'Type "DELETE MY ACCOUNT" to confirm',
        validators=[
            DataRequired(message="Please type the confirmation phrase."),
            Length(max=50, message="Confirmation phrase is too long."),
        ],
    )
    submit = SubmitField("Delete My Account")

    def validate_confirmation(self, field):
        if field.data != "DELETE MY ACCOUNT":
            raise ValidationError('You must type "DELETE MY ACCOUNT" exactly to confirm deletion.')


class VacationModeForm(FlaskForm):
    vacation_mode = BooleanField("Vacation Mode")
    submit = SubmitField("Update")


class DigestSettingsForm(FlaskForm):
    digest_frequency = SelectField(
        "Digest Frequency",
        choices=DIGEST_FREQUENCY_CHOICES,
        validators=[DataRequired()],
    )
    digest_radius_miles = IntegerField(
        "Digest Radius (miles)",
        validators=[
            DataRequired(),
            NumberRange(min=1, max=50, message="Radius must be between 1 and 50 miles."),
        ],
        default=10,
    )
    digest_include_giveaways = BooleanField("Giveaways")
    digest_include_requests = BooleanField("Requests")
    digest_include_circle_joins = BooleanField("People joining my closed circles")
    digest_include_loans = BooleanField("Loans in my circles")
    digest_giveaways_include_public = BooleanField("Include public giveaways within radius")
    digest_requests_include_public = BooleanField("Include public requests within radius")
    submit = SubmitField("Save Digest Settings")
