import logging
from datetime import UTC, datetime

import app.utils.geocoding as geocoding
from app import db

logger = logging.getLogger(__name__)

LOCATION_UPDATE_STATUS_SUCCESS = "success"
LOCATION_UPDATE_STATUS_REMOVED = "removed"
LOCATION_UPDATE_STATUS_RATE_LIMITED = "rate_limited"
LOCATION_UPDATE_STATUS_GEOCODING_FAILED = "geocoding_failed"
LOCATION_UPDATE_STATUS_GEOCODING_ERROR = "geocoding_error"
LOCATION_UPDATE_STATUS_UNEXPECTED_ERROR = "unexpected_error"


def _apply_coordinates(user, latitude, longitude):
    user.latitude = latitude
    user.longitude = longitude
    user.geocoded_at = datetime.now(UTC)
    user.geocoding_failed = False
    return LOCATION_UPDATE_STATUS_SUCCESS


def _apply_address(user, street, city, state, zip_code, country):
    try:
        coordinates = geocoding.geocode_address(
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
        )
        if coordinates:
            user.latitude, user.longitude = coordinates
            user.geocoded_at = datetime.now(UTC)
            user.geocoding_failed = False
            return LOCATION_UPDATE_STATUS_SUCCESS

        user.geocoding_failed = True
        return LOCATION_UPDATE_STATUS_GEOCODING_FAILED
    except geocoding.GeocodingError as exc:
        user.geocoding_failed = True
        logger.error("Geocoding error for user %s: %s", user.email, exc)
        return LOCATION_UPDATE_STATUS_GEOCODING_ERROR
    except Exception as exc:
        user.geocoding_failed = True
        logger.error("Unexpected error during geocoding for user %s: %s", user.email, exc)
        return LOCATION_UPDATE_STATUS_UNEXPECTED_ERROR


def apply_registration_location(
    user,
    *,
    location_method,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
    latitude=None,
    longitude=None,
):
    if location_method == "coordinates":
        return _apply_coordinates(user, latitude, longitude)

    if location_method == "address":
        return _apply_address(user, street, city, state, zip_code, country)

    return LOCATION_UPDATE_STATUS_SUCCESS


def update_user_location(
    user,
    *,
    location_method,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
    latitude=None,
    longitude=None,
):
    if not user.can_update_location():
        return LOCATION_UPDATE_STATUS_RATE_LIMITED

    if location_method == "remove":
        user.latitude = None
        user.longitude = None
        db.session.commit()
        return LOCATION_UPDATE_STATUS_REMOVED

    if location_method == "coordinates":
        status = _apply_coordinates(user, latitude, longitude)
    else:
        status = _apply_address(user, street, city, state, zip_code, country)

    db.session.commit()
    return status
