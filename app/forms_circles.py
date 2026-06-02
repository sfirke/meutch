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
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms_shared import COUNTRY_CHOICES, COUNTRY_DEFAULT, CountryChoice, OptionalFileAllowed


class CircleCreateForm(FlaskForm):
    name = StringField(
        "Circle Name",
        validators=[
            DataRequired(message="Circle name is required."),
            Length(max=100, message="Circle name must be under 100 characters."),
        ],
    )
    description = TextAreaField(
        "Description",
        validators=[Length(max=500, message="Description must be under 500 characters.")],
    )
    circle_type = SelectField(
        "Circle Type",
        choices=[
            ("open", "Open - Anyone can find and join"),
            ("closed", "Closed - Anyone can find it, but requires approval to join."),
            ("secret", "Secret - Cannot be found by search, requires UUID and approval to join."),
        ],
        default="open",
        validators=[DataRequired()],
    )
    image = FileField(
        "Circle Image",
        validators=[
            OptionalFileAllowed(
                ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
                "Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP",
            )
        ],
    )
    delete_image = BooleanField("Delete current image")

    location_method = RadioField(
        "How would you like to set the circle location?",
        choices=[
            ("address", "Enter an address (we'll look up coordinates)"),
            ("coordinates", "Enter latitude and longitude directly"),
            ("skip", "Skip for now (admins can add this later)"),
        ],
        default="skip",
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
    country = SelectField(
        "Country",
        validators=[
            Optional(),
            CountryChoice(),
        ],
        choices=COUNTRY_CHOICES,
        default=COUNTRY_DEFAULT,
        validate_choice=False,
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

    submit = SubmitField("Create Circle")

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


class CircleSearchForm(FlaskForm):
    search_query = StringField(
        "Search Circles",
        validators=[
            Optional(),
            Length(max=100, message="Search term must be under 100 characters."),
        ],
    )
    radius = SelectField(
        "Within",
        choices=[
            ("", "Any distance"),
            ("5", "Within 5 miles"),
            ("10", "Within 10 miles"),
            ("25", "Within 25 miles"),
            ("50", "Within 50 miles"),
            ("100", "Within 100 miles"),
        ],
        default="25",
        validators=[Optional()],
    )
    submit = SubmitField("Search")


class CircleUuidSearchForm(FlaskForm):
    circle_uuid = StringField(
        "Circle UUID",
        validators=[
            DataRequired(message="Please enter a circle UUID."),
            Length(min=36, max=36, message="UUID must be exactly 36 characters."),
        ],
    )
    submit = SubmitField("Find Circle")


class CircleJoinRequestForm(FlaskForm):
    message = TextAreaField(
        "Message to Circle Admins",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Request to Join")


class CircleRegionalSettingsForm(FlaskForm):
    is_regional = BooleanField("This is a regional circle")
    regional_radius_miles = IntegerField("Circle's radius in miles", validators=[Optional()])
    submit = SubmitField("Save Regional Settings")

    def validate(self, extra_validators=None):
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.is_regional.data and self.regional_radius_miles.data is None:
            self.regional_radius_miles.errors.append(
                "Circle radius is required when regional status is enabled."
            )
            return False
        if (
            self.regional_radius_miles.data is not None
            and not 1 <= self.regional_radius_miles.data <= 100
        ):
            self.regional_radius_miles.errors.append(
                "Circle radius must be between 1 and 100 miles."
            )
            return False

        return True
