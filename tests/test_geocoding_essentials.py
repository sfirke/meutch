"""Essential geocoding tests - optimized for CI runtime.

This file contains the most critical tests for geocoding functionality,
designed to provide maximum coverage with minimal runtime impact.
"""
import pytest
from unittest.mock import patch, Mock
from app.utils.geocoding import geocode_address, GeocodingError, format_distance
from tests.factories import UserFactory, ItemFactory
from app import db
from app.models import User
from flask import url_for


class TestGeocodingEssentials:
    """Essential geocoding utility tests."""

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_success(self, mock_get):
        """Test successful geocoding of an address."""
        mock_response = Mock()
        mock_response.json.return_value = [{'lat': '40.7128', 'lon': '-74.0060'}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("123 Main St, New York, NY")
        assert result == (40.7128, -74.0060)

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_no_results(self, mock_get):
        """Test geocoding when no results are found."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Invalid Address")
        assert result is None

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_exception_handling(self, mock_get):
        """Test geocoding error handling."""
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(GeocodingError):
            geocode_address("123 Main St", max_retries=1)

    def test_format_distance_essential_cases(self):
        """Test key distance formatting scenarios."""
        assert format_distance(0.05) == "< 0.1 mi"
        assert format_distance(1.23) == "1.2 mi"
        assert format_distance(25.8) == "25.8 mi"


class TestUserGeocodingEssentials:
    """Essential User model geocoding tests."""

    def test_user_is_geocoded_property(self, app):
        """Test is_geocoded property."""
        with app.app_context():
            user_with_coords = UserFactory(latitude=40.7128, longitude=-74.0060)
            user_without_coords = UserFactory(latitude=None, longitude=None)
            
            assert user_with_coords.is_geocoded is True
            assert user_without_coords.is_geocoded is False

    def test_user_distance_calculation(self, app):
        """Test distance calculation between users."""
        with app.app_context():
            # NYC and LA coordinates
            user1 = UserFactory(latitude=40.7128, longitude=-74.0060)
            user2 = UserFactory(latitude=34.0522, longitude=-118.2437)
            
            distance = user1.distance_to(user2)
            assert distance is not None
            assert 2400 < distance < 2500

    def test_user_distance_to_non_geocoded(self, app):
        """Test distance calculation when users aren't geocoded."""
        with app.app_context():
            user1 = UserFactory(latitude=None, longitude=None)
            user2 = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            assert user1.distance_to(user2) is None

    def test_can_update_address_logic(self, app):
        """Test address update permission logic."""
        with app.app_context():
            from datetime import datetime, timedelta
            
            # User with no previous geocoding
            user1 = UserFactory(geocoded_at=None)
            assert user1.can_update_address() is True
            
            # User with recent successful geocoding
            recent_time = datetime.utcnow() - timedelta(hours=2)
            user2 = UserFactory(geocoded_at=recent_time, geocoding_failed=False)
            assert user2.can_update_address() is False


class TestDistanceUtilsEssentials:
    """Essential context processor tests."""

    def test_distance_utils_basic_functionality(self, app):
        """Test core distance utility functionality."""
        with app.app_context():
            from app.context_processors import inject_distance_utils
            
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory(latitude=34.0522, longitude=-118.2437)
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is not None
                assert 'mi' in result

    def test_distance_utils_graceful_degradation(self, app):
        """Test that distance utils fail gracefully."""
        with app.app_context():
            from app.context_processors import inject_distance_utils
            from unittest.mock import MagicMock
            
            # Test with non-geocoded user
            user = UserFactory(latitude=None, longitude=None)
            item = ItemFactory()
            
            with patch('app.context_processors.current_user', user):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None


class TestAddressUpdateEssentials:
    """Essential address update integration tests."""

    def test_address_update_success(self, app, client):
        """Test successful address update with geocoding."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()
            
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '123 Main St',
                    'city': 'New York',
                    'state': 'NY',
                    'zip_code': '10001',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                updated_user = User.query.get(user.id)
                assert updated_user.latitude == 40.7128
                assert updated_user.longitude == -74.0060

    def test_address_update_daily_limit(self, app, client):
        """Test that daily update limit is enforced."""
        with app.app_context():
            from datetime import datetime, timedelta
            
            recent_time = datetime.utcnow() - timedelta(hours=2)
            user = UserFactory(geocoded_at=recent_time, geocoding_failed=False)
            db.session.commit()
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            response = client.post(url_for('main.update_address'), data={
                'street': '456 New St',
                'city': 'New City',
                'state': 'NC',
                'zip_code': '54321',
                'country': 'USA',
                'csrf_token': 'test'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Address should not have been updated due to daily limit
            unchanged_user = User.query.get(user.id)
            assert unchanged_user.street != '456 New St'

    def test_address_update_geocoding_failure(self, app, client):
        """Test address update when geocoding fails."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()
            
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = None  # Geocoding fails
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': 'Invalid Address',
                    'city': 'Nowhere',
                    'state': 'XX',
                    'zip_code': '99999',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
                
                assert response.status_code == 200
                
                updated_user = User.query.get(user.id)
                assert updated_user.street == 'Invalid Address'  # Address updated
                assert updated_user.latitude is None  # But no coordinates
                assert updated_user.geocoding_failed is True


class TestWorkflowEssentials:
    """Essential end-to-end workflow tests."""

    def test_complete_geocoding_workflow(self, app, client):
        """Test registration -> geocoding -> distance calculation workflow."""
        with app.app_context():
            with patch('app.auth.routes.geocode_address') as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)
                
                # Register user with geocoding
                client.post(url_for('auth.register'), data={
                    'email': 'test@test.com',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': '123 Test St',
                    'city': 'New York',
                    'state': 'NY',
                    'zip_code': '10001',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
                
                user = User.query.filter_by(email='test@test.com').first()
                assert user is not None
                assert user.latitude == 40.7128
                assert user.longitude == -74.0060
                assert user.is_geocoded is True
