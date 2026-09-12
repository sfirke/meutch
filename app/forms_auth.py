import time

from flask import current_app
from flask_wtf import FlaskForm
from itsdangerous import BadSignature, URLSafeSerializer
from wtforms import (
    BooleanField,
    FloatField,
    HiddenField,
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

from app.forms_shared import (
    COUNTRY_CHOICES,
    COUNTRY_DEFAULT,
    DIGEST_FREQUENCY_CHOICES,
    CountryChoice,
)
from app.models import User
from app.services.auth_service import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

REGISTRATION_STARTED_SALT = "registration-form-started"


def _registration_started_serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=REGISTRATION_STARTED_SALT)


def issue_registration_started_token(now=None):
    """Sign the time the sign-up form was served, for the minimum fill time check."""
    started_at = time.time() if now is None else now
    return _registration_started_serializer().dumps(int(started_at))


def _seconds_since_registration_started(token):
    """Seconds since the form behind *token* was served, or None if it is missing or forged."""
    if not token:
        return None
    try:
        started_at = _registration_started_serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(started_at, int):
        return None
    return time.time() - started_at


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
            # No minimum here: accounts created before the minimum was raised must
            # still be able to log in.
            Length(max=PASSWORD_MAX_LENGTH),
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

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(
                min=PASSWORD_MIN_LENGTH,
                max=PASSWORD_MAX_LENGTH,
                message=f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    age_confirm = BooleanField(
        "I confirm I am at least 13 years old",
        validators=[
            DataRequired(message="You must be at least 13 years old to use Meutch."),
        ],
    )
    submit = SubmitField("Register")

    # Bot traps, checked by bot_trap_reason() before the rest of validation. People
    # never see `website`, so anything in it was filled in by a script. `started`
    # carries the signed time the form was served.
    website = StringField("Website")
    started = HiddenField()

    def bot_trap_reason(self):
        """Return why this submission looks automated, or None if it passes."""
        if self.website.data:
            return "honeypot"

        min_seconds = current_app.config["REGISTRATION_MIN_FILL_SECONDS"]
        if min_seconds <= 0:
            return None

        elapsed = _seconds_since_registration_started(self.started.data)
        if elapsed is None:
            return "missing_start_time"
        if elapsed < min_seconds:
            return "too_fast"
        return None

    def validate_email(self, email):
        """Reject an address that already belongs to a confirmed account.

        An address on an unconfirmed account is left alone: nobody has proved they
        control it, so this sign-up is allowed to claim it.
        """
        from app.services.auth_service import check_existing_email

        result = check_existing_email(email.data)
        if result.exists and result.is_confirmed:
            self.email_status = "confirmed"
            raise ValidationError(
                "This email is already registered. Use the forgot-password link below to regain access."
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
            Length(
                min=PASSWORD_MIN_LENGTH,
                max=PASSWORD_MAX_LENGTH,
                message=f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.",
            ),
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
    submit = SubmitField("Resend Confirmation Email")
