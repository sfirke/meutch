from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app import db
from app.services import location_service
from app.utils.geocoding import GeocodingError
from tests.factories import UserFactory


class TestLocationService:
    def test_update_user_location_returns_rate_limited_for_recent_success(self, app):
        with app.app_context():
            user = UserFactory(
                geocoded_at=datetime.now(UTC) - timedelta(hours=2),
                geocoding_failed=False,
            )
            db.session.commit()

            result = location_service.update_user_location(
                user,
                location_method="coordinates",
                latitude=40.7128,
                longitude=-74.0060,
            )

            db.session.refresh(user)
            assert result == location_service.LOCATION_UPDATE_STATUS_RATE_LIMITED
            assert user.latitude != 40.7128

    def test_update_user_location_removes_coordinates(self, app):
        with app.app_context():
            user = UserFactory(latitude=40.7128, longitude=-74.0060)
            db.session.commit()

            result = location_service.update_user_location(user, location_method="remove")

            db.session.refresh(user)
            assert result == location_service.LOCATION_UPDATE_STATUS_REMOVED
            assert user.latitude is None
            assert user.longitude is None

    def test_update_user_location_with_coordinates_sets_location(self, app):
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            result = location_service.update_user_location(
                user,
                location_method="coordinates",
                latitude=40.7128,
                longitude=-74.0060,
            )

            db.session.refresh(user)
            assert result == location_service.LOCATION_UPDATE_STATUS_SUCCESS
            assert user.latitude == 40.7128
            assert user.longitude == -74.0060

    def test_update_user_location_with_address_marks_geocoding_failed(self, app):
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            with patch("app.utils.geocoding.geocode_address", return_value=None):
                result = location_service.update_user_location(
                    user,
                    location_method="address",
                    street="123 Unknown",
                    city="Nowhere",
                    state="NC",
                    zip_code="12345",
                    country="USA",
                )

            db.session.refresh(user)
            assert result == location_service.LOCATION_UPDATE_STATUS_GEOCODING_FAILED
            assert user.geocoding_failed is True

    def test_apply_registration_location_returns_geocoding_error_status(self, app):
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)

            with patch(
                "app.utils.geocoding.geocode_address",
                side_effect=GeocodingError("geocoder down"),
            ):
                result = location_service.apply_registration_location(
                    user,
                    location_method="address",
                    street="123 Error",
                    city="Nowhere",
                    state="NC",
                    zip_code="12345",
                    country="USA",
                )

            assert result == location_service.LOCATION_UPDATE_STATUS_GEOCODING_ERROR
            assert user.geocoding_failed is True
