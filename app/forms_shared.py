import pycountry
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms.validators import URL, ValidationError

from app.models import User

DIGEST_FREQUENCY_CHOICES = [
    (User.DIGEST_FREQUENCY_WEEKLY, "Weekly (stay in the loop)"),
    (
        User.DIGEST_FREQUENCY_DAILY,
        "Daily (respond promptly to requests and giveaways)",
    ),
    (User.DIGEST_FREQUENCY_NONE, "Never (must log in to follow activity)"),
]

COUNTRY_DEFAULT = "United States of America"
COUNTRY_PRIORITY_ORDER = (COUNTRY_DEFAULT, "Canada")


def _country_display_name(country):
    if country.alpha_2 == "US":
        return COUNTRY_DEFAULT
    return getattr(country, "common_name", country.name)


def _build_country_choices():
    remaining_countries = sorted(
        {
            _country_display_name(country)
            for country in pycountry.countries
            if _country_display_name(country) not in COUNTRY_PRIORITY_ORDER
        }
    )
    return tuple((country_name, country_name) for country_name in COUNTRY_PRIORITY_ORDER) + tuple(
        (country_name, country_name) for country_name in remaining_countries
    )


COUNTRY_CHOICES = _build_country_choices()
_COUNTRY_LOOKUP = {value.casefold(): value for value, _ in COUNTRY_CHOICES}
_COUNTRY_LOOKUP.update(
    {
        "us": COUNTRY_DEFAULT,
        "usa": COUNTRY_DEFAULT,
        "u.s.": COUNTRY_DEFAULT,
        "u.s.a.": COUNTRY_DEFAULT,
        "united states": COUNTRY_DEFAULT,
    }
)


def normalize_country_choice(value):
    """Normalize user-provided country values to the canonical dropdown value."""
    if not value or not value.strip():
        return value
    stripped_value = value.strip()
    return _COUNTRY_LOOKUP.get(stripped_value.casefold(), stripped_value)


def CountryChoice(message=None):
    """Validator that restricts countries to the supported dropdown values."""

    def _validate(form, field):
        if not field.data:
            return

        normalized_country = normalize_country_choice(field.data)
        if normalized_country not in _COUNTRY_LOOKUP.values():
            raise ValidationError(message or "Please choose a country from the list.")
        field.data = normalized_country

    return _validate


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
