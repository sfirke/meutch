from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FloatField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app.forms_shared import DIGEST_FREQUENCY_CHOICES
from app.models import User


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Invalid email format."),
            Length(max=120, message="Email must be under 120 characters."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=6, message="Password must be at least 6 characters long."),
        ],
    )
    remember_device = BooleanField("Remember this device for 30 days")
    submit = SubmitField("Log In")


class RegistrationForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Invalid email format."),
            Length(max=120, message="Email must be under 120 characters."),
        ],
    )
    first_name = StringField(
        "First Name",
        validators=[
            DataRequired(message="First name is required."),
            Length(max=50, message="First name must be under 50 characters."),
        ],
    )
    last_name = StringField(
        "Last Name",
        validators=[
            DataRequired(message="Last name is required."),
            Length(max=50, message="Last name must be under 50 characters."),
        ],
    )
    digest_frequency = SelectField(
        "Email Digest Frequency",
        choices=DIGEST_FREQUENCY_CHOICES,
        default=User.DIGEST_FREQUENCY_WEEKLY,
        validators=[DataRequired()],
    )

    location_method = RadioField(
        "How would you like to set your location?",
        choices=[
            ("address", "Enter an address (we'll look up coordinates)"),
            ("coordinates", "Enter latitude and longitude directly"),
            ("skip", "Skip for now (you can add this later on your profile)"),
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
        "State",
        validators=[
            Optional(),
            Length(max=100, message="State must be under 100 characters."),
        ],
    )
    zip_code = StringField(
        "ZIP Code",
        validators=[
            Optional(),
            Length(max=20, message="ZIP Code must be under 20 characters."),
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

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=6, message="Password must be at least 6 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Register")

    def validate_email(self, email):
        """Check if email is already registered"""
        from app import db

        user = User.query.filter(db.func.lower(User.email) == db.func.lower(email.data)).first()
        if user:
            raise ValidationError(
                "This email is already registered. Please choose a different one."
            )

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


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Invalid email format."),
            Length(max=120, message="Email must be under 120 characters."),
        ],
    )
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=6, message="Password must be at least 6 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Reset Password")


class ResendConfirmationForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Invalid email format."),
            Length(max=120, message="Email must be under 120 characters."),
        ],
    )
    submit = SubmitField("Send Confirmation Email")
