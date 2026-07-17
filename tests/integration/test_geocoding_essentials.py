"""Essential geocoding tests - optimized for CI runtime.

This file contains the most critical tests for geocoding functionality,
designed to provide maximum coverage with minimal runtime impact.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from flask import url_for

from app import db
from app.models import User
from app.utils.geocoding import GeocodingError, format_distance, geocode_address
from tests.factories import ItemFactory, UserFactory


class TestGeocodingEssentials:
    """Essential geocoding utility tests."""

    @patch("app.utils.geocoding.requests.get")
    def test_geocode_address_success(self, mock_get):
        """Test successful geocoding of an address."""
        mock_response = Mock()
        mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("123 Main St, New York, NY")
        assert result == (40.7128, -74.0060)

    @patch("app.utils.geocoding.requests.get")
    def test_geocode_address_uses_structured_query_when_components_are_available(self, mock_get):
        """Test structured geocoding queries for address components."""
        mock_response = Mock()
        mock_response.json.return_value = [{"lat": "49.2570773", "lon": "-123.0787301"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address(
            street="1255 E 15th Avenue",
            city="Vancouver",
            state="BC",
            zip_code="V5T 2S7",
            country="Canada",
        )

        assert result == (49.2570773, -123.0787301)
        params = mock_get.call_args.kwargs["params"]
        assert params["street"] == "1255 E 15th Avenue"
        assert params["city"] == "Vancouver"
        assert params["state"] == "BC"
        assert params["postalcode"] == "V5T 2S7"
        assert params["country"] == "Canada"
        assert "q" not in params

    @patch("app.utils.geocoding.requests.get")
    def test_geocode_address_retries_without_postal_code_when_needed(self, mock_get):
        """Test structured geocoding falls back without postal code after a miss."""
        first_response = Mock()
        first_response.json.return_value = []
        first_response.raise_for_status.return_value = None

        second_response = Mock()
        second_response.json.return_value = [{"lat": "49.2322956", "lon": "-123.1864962"}]
        second_response.raise_for_status.return_value = None

        mock_get.side_effect = [first_response, second_response]

        result = geocode_address(
            street="5976 Alma St",
            city="Vancouver",
            state="BC",
            zip_code="V6N 1Y",
            country="Canada",
        )

        assert result == (49.2322956, -123.1864962)
        assert mock_get.call_count == 2
        first_params = mock_get.call_args_list[0].kwargs["params"]
        second_params = mock_get.call_args_list[1].kwargs["params"]
        assert first_params["postalcode"] == "V6N 1Y"
        assert second_params["street"] == "5976 Alma St"
        assert second_params["city"] == "Vancouver"
        assert second_params["state"] == "BC"
        assert second_params["country"] == "Canada"
        assert "postalcode" not in second_params

    @patch("app.utils.geocoding.requests.get")
    def test_geocode_address_no_results(self, mock_get):
        """Test geocoding when no results are found."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Invalid Address")
        assert result is None

    @patch("app.utils.geocoding.requests.get")
    def test_geocode_address_exception_handling(self, mock_get):
        """Test geocoding error handling."""
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(GeocodingError):
            geocode_address("123 Main St", max_retries=1)

    def test_format_distance_essential_cases(self):
        """Test key distance formatting scenarios."""
        assert format_distance(0.05) == "< 1 mi"
        assert format_distance(1.23) == "1-2 mi"
        assert format_distance(25.8) == "25+ mi"


class TestDistanceUtilsEssentials:
    """Essential context processor tests."""

    def test_distance_utils_basic_functionality(self, app):
        """Test core distance utility functionality."""
        with app.app_context():
            from app.context_processors import inject_distance_utils

            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory(latitude=34.0522, longitude=-118.2437)
            item = ItemFactory(owner=owner)

            with patch("app.context_processors.current_user", borrower):
                context = inject_distance_utils()
                get_distance = context["get_distance_to_item"]

                result = get_distance(item)
                assert result is not None
                assert "mi" in result

    def test_distance_utils_graceful_degradation(self, app):
        """Test that distance utils fail gracefully."""
        with app.app_context():
            from app.context_processors import inject_distance_utils

            # Test with non-geocoded user
            user = UserFactory(latitude=None, longitude=None)
            item = ItemFactory()

            with patch("app.context_processors.current_user", user):
                context = inject_distance_utils()
                get_distance = context["get_distance_to_item"]

                result = get_distance(item)
                assert result is None


class TestLocationUpdateEssentials:
    """Essential location update integration tests."""

    def test_location_update_with_address_success(self, app, client):
        """Test successful location update using address input with geocoding."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            with patch("app.utils.geocoding.geocode_address") as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)

                with client.session_transaction() as sess:
                    sess["_user_id"] = str(user.id)
                    sess["_fresh"] = True

                response = client.post(
                    url_for("main.update_location"),
                    data={
                        "location_method": "address",
                        "street": "123 Main St",
                        "city": "New York",
                        "state": "NY",
                        "zip_code": "10001",
                        "country": "USA",
                        "csrf_token": "test",
                    },
                    follow_redirects=True,
                )

                assert response.status_code == 200
                mock_geocode.assert_called_once_with(
                    street="123 Main St",
                    city="New York",
                    state="NY",
                    zip_code="10001",
                    country="United States of America",
                )

                updated_user = db.session.get(User, user.id)
                assert updated_user.latitude == 40.7128
                assert updated_user.longitude == -74.0060

    def test_location_update_with_canadian_address_success(self, app, client):
        """Test successful location update using Canadian address components."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            with patch("app.utils.geocoding.geocode_address") as mock_geocode:
                mock_geocode.return_value = (45.4215, -75.6972)

                with client.session_transaction() as sess:
                    sess["_user_id"] = str(user.id)
                    sess["_fresh"] = True

                response = client.post(
                    url_for("main.update_location"),
                    data={
                        "location_method": "address",
                        "street": "111 Wellington St",
                        "city": "Ottawa",
                        "state": "ON",
                        "zip_code": "K1A 0A9",
                        "country": "Canada",
                        "csrf_token": "test",
                    },
                    follow_redirects=True,
                )

                assert response.status_code == 200
                mock_geocode.assert_called_once_with(
                    street="111 Wellington St",
                    city="Ottawa",
                    state="ON",
                    zip_code="K1A 0A9",
                    country="Canada",
                )

                updated_user = db.session.get(User, user.id)
                assert updated_user.latitude == 45.4215
                assert updated_user.longitude == -75.6972

    def test_location_update_with_coordinates_success(self, app, client):
        """Test successful location update using direct coordinate input."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            with client.session_transaction() as sess:
                sess["_user_id"] = str(user.id)
                sess["_fresh"] = True

            response = client.post(
                url_for("main.update_location"),
                data={
                    "location_method": "coordinates",
                    "latitude": "40.7128",
                    "longitude": "-74.0060",
                    "csrf_token": "test",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            updated_user = db.session.get(User, user.id)
            assert updated_user.latitude == 40.7128
            assert updated_user.longitude == -74.0060

    def test_location_update_daily_limit(self, app, client):
        """Test that daily update limit is enforced."""
        with app.app_context():
            from datetime import timedelta

            recent_time = datetime.now(UTC) - timedelta(hours=2)
            user = UserFactory(geocoded_at=recent_time, geocoding_failed=False)
            db.session.commit()

            with client.session_transaction() as sess:
                sess["_user_id"] = str(user.id)
                sess["_fresh"] = True

            response = client.post(
                url_for("main.update_location"),
                data={
                    "location_method": "coordinates",
                    "latitude": "34.0522",
                    "longitude": "-118.2437",
                    "csrf_token": "test",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            # Location should not have been updated due to daily limit
            unchanged_user = db.session.get(User, user.id)
            assert unchanged_user.latitude != 34.0522

    def test_location_update_geocoding_failure(self, app, client):
        """Test location update when geocoding fails."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()

            with patch("app.utils.geocoding.geocode_address") as mock_geocode:
                mock_geocode.return_value = None  # Geocoding fails

                with client.session_transaction() as sess:
                    sess["_user_id"] = str(user.id)
                    sess["_fresh"] = True

                response = client.post(
                    url_for("main.update_location"),
                    data={
                        "location_method": "address",
                        "street": "Invalid Address",
                        "city": "Nowhere",
                        "state": "XX",
                        "zip_code": "99999",
                        "country": "USA",
                        "csrf_token": "test",
                    },
                )

                assert response.status_code == 200

                updated_user = db.session.get(User, user.id)
                assert updated_user.latitude is None  # No coordinates stored
                assert updated_user.geocoding_failed is True


class TestWorkflowEssentials:
    """Essential end-to-end workflow tests."""

    def test_complete_geocoding_workflow_with_address(self, app, client):
        """Test registration -> geocoding -> distance calculation workflow with address input."""
        with app.app_context():
            with patch("app.utils.geocoding.geocode_address") as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)

                # Register user with geocoding via address
                client.post(
                    url_for("auth.register"),
                    data={
                        "email": "test@test.com",
                        "first_name": "Test",
                        "last_name": "User",
                        "password": "testpassword123",
                        "confirm_password": "testpassword123",
                        "location_method": "address",
                        "street": "123 Test St",
                        "city": "New York",
                        "state": "NY",
                        "zip_code": "10001",
                        "country": "United States of America",
                        "age_confirm": True,
                        "csrf_token": "test",
                    },
                )

                user = User.query.filter_by(email="test@test.com").first()
                assert user is not None
                assert user.latitude == 40.7128
                assert user.longitude == -74.0060
                assert user.is_geocoded is True

    def test_complete_geocoding_workflow_with_coordinates(self, app, client):
        """Test registration -> coordinates -> distance calculation workflow with direct coordinates."""
        with app.app_context():
            # Register user with direct coordinates
            client.post(
                url_for("auth.register"),
                data={
                    "email": "test2@test.com",
                    "first_name": "Test",
                    "last_name": "User",
                    "password": "testpassword123",
                    "confirm_password": "testpassword123",
                    "location_method": "coordinates",
                    "latitude": "34.0522",
                    "longitude": "-118.2437",
                    "age_confirm": True,
                    "csrf_token": "test",
                },
            )

            user = User.query.filter_by(email="test2@test.com").first()
            assert user is not None
            assert user.latitude == 34.0522
            assert user.longitude == -118.2437
            assert user.is_geocoded is True

    def test_registration_workflow_skip_location(self, app, client):
        """Test registration workflow when user skips location entry."""
        with app.app_context():
            # Register user without location
            client.post(
                url_for("auth.register"),
                data={
                    "email": "test3@test.com",
                    "first_name": "Test",
                    "last_name": "User",
                    "password": "testpassword123",
                    "confirm_password": "testpassword123",
                    "location_method": "skip",
                    "age_confirm": True,
                    "csrf_token": "test",
                },
            )

            user = User.query.filter_by(email="test3@test.com").first()
            assert user is not None
            assert user.latitude is None
            assert user.longitude is None
            assert user.is_geocoded is False
