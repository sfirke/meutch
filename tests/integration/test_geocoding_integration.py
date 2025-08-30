"""Integration tests for geocoding and address update functionality."""
import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from flask import url_for
from app import db
from app.models import User
from tests.factories import UserFactory
from app.utils.geocoding import GeocodingError


class TestAddressUpdateIntegration:
    """Integration tests for address update functionality."""

    def test_update_address_success_with_geocoding(self, app, client):
        """Test successful address update with geocoding."""
        with app.app_context():
            user = UserFactory(
                street='Old St',
                city='Old City', 
                state='OS',
                zip_code='00000',
                latitude=None,
                longitude=None,
                geocoded_at=None,
                geocoding_failed=False
            )
            db.session.commit()
            
            # Mock successful geocoding
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
                
                # Check user was updated
                updated_user = User.query.get(user.id)
                assert updated_user.street == '123 Main St'
                assert updated_user.city == 'New York'
                assert updated_user.state == 'NY'
                assert updated_user.zip_code == '10001'
                assert updated_user.latitude == 40.7128
                assert updated_user.longitude == -74.0060
                assert updated_user.geocoded_at is not None
                assert updated_user.geocoding_failed is False
                
                # Verify geocoding was called with correct address
                mock_geocode.assert_called_once_with('123 Main St, New York, NY 10001, USA')

    def test_update_address_success_geocoding_fails(self, app, client):
        """Test address update when geocoding returns None."""
        with app.app_context():
            user = UserFactory(
                latitude=None,
                longitude=None,
                geocoded_at=None,
                geocoding_failed=False
            )
            db.session.commit()
            
            # Mock geocoding returning None (address not found)
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = None
                
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
                
                # Check user address was updated but coordinates are still None
                updated_user = User.query.get(user.id)
                assert updated_user.street == 'Invalid Address'
                assert updated_user.city == 'Nowhere'
                assert updated_user.latitude is None
                assert updated_user.longitude is None
                assert updated_user.geocoding_failed is True

    def test_update_address_geocoding_exception(self, app, client):
        """Test address update when geocoding raises exception."""
        with app.app_context():
            user = UserFactory(
                latitude=None,
                longitude=None,
                geocoded_at=None,
                geocoding_failed=False
            )
            db.session.commit()
            
            # Mock geocoding raising exception
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.side_effect = GeocodingError("API error")
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '123 Test St',
                    'city': 'Test City',
                    'state': 'TC',
                    'zip_code': '12345',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
                
                assert response.status_code == 200
                
                # Check user address was updated but geocoding failed
                updated_user = User.query.get(user.id)
                assert updated_user.street == '123 Test St'
                assert updated_user.geocoding_failed is True

    def test_update_address_unexpected_exception(self, app, client):
        """Test address update when unexpected exception occurs."""
        with app.app_context():
            user = UserFactory(
                latitude=None,
                longitude=None,
                geocoded_at=None,
                geocoding_failed=False
            )
            db.session.commit()
            
            # Mock geocoding raising unexpected exception
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.side_effect = Exception("Unexpected error")
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '123 Test St',
                    'city': 'Test City',
                    'state': 'TC',
                    'zip_code': '12345',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
                
                assert response.status_code == 200
                
                # Check user address was updated but geocoding failed
                updated_user = User.query.get(user.id)
                assert updated_user.street == '123 Test St'
                assert updated_user.geocoding_failed is True

    def test_update_address_daily_limit_respected(self, app, client):
        """Test that daily update limit is enforced."""
        with app.app_context():
            # User updated address 2 hours ago successfully
            recent_time = datetime.utcnow() - timedelta(hours=2)
            user = UserFactory(
                geocoded_at=recent_time,
                geocoding_failed=False
            )
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
            
            # Check user address was NOT updated
            unchanged_user = User.query.get(user.id)
            assert unchanged_user.street != '456 New St'  # Should still be old address

    def test_update_address_allowed_after_failure(self, app, client):
        """Test that address update is allowed after previous failure."""
        with app.app_context():
            # User had failed geocoding yesterday
            yesterday = datetime.utcnow() - timedelta(days=1)
            user = UserFactory(
                geocoded_at=yesterday,
                geocoding_failed=True,
                latitude=None,
                longitude=None
            )
            db.session.commit()
            
            # Mock successful geocoding this time
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '789 Success St',
                    'city': 'Success City',
                    'state': 'SC',
                    'zip_code': '98765',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check user was updated successfully
                updated_user = User.query.get(user.id)
                assert updated_user.street == '789 Success St'
                assert updated_user.latitude == 40.7128
                assert updated_user.longitude == -74.0060
                assert updated_user.geocoding_failed is False

    def test_update_address_allowed_after_old_success(self, app, client):
        """Test that address update is allowed after old successful geocoding."""
        with app.app_context():
            # User updated successfully 2 days ago
            two_days_ago = datetime.utcnow() - timedelta(days=2)
            user = UserFactory(
                geocoded_at=two_days_ago,
                geocoding_failed=False,
                latitude=40.0,
                longitude=-74.0
            )
            db.session.commit()
            
            # Mock successful geocoding
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = (41.0, -75.0)
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '321 Updated St',
                    'city': 'Updated City',
                    'state': 'UC',
                    'zip_code': '13579',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check user was updated with new coordinates
                updated_user = User.query.get(user.id)
                assert updated_user.street == '321 Updated St'
                assert updated_user.latitude == 41.0
                assert updated_user.longitude == -75.0

    def test_update_address_form_validation(self, app, client):
        """Test form validation for address update."""
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            # Test with missing required fields
            response = client.post(url_for('main.update_address'), data={
                'street': '',  # Required field missing
                'city': 'Test City',
                'state': 'TC',
                'zip_code': '12345',
                'country': 'USA',
                'csrf_token': 'test'
            })
            
            assert response.status_code == 200
            # Should stay on form page due to validation error
            assert b'update_address' in response.data or b'Street address is required' in response.data

    def test_update_address_get_request(self, app, client):
        """Test GET request to address update page."""
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
            
            response = client.get(url_for('main.update_address'))
            
            assert response.status_code == 200
            # Should render the form template
            assert b'form' in response.data

    def test_update_address_requires_login(self, app, client):
        """Test that address update requires authentication."""
        with app.app_context():
            response = client.get(url_for('main.update_address'))
            
            # Should redirect to login
            assert response.status_code == 302
            assert 'login' in response.location


class TestGeocodingUserRegistration:
    """Test geocoding during user registration."""

    def test_user_registration_with_geocoding_success(self, app, client):
        """Test user registration with successful geocoding."""
        with app.app_context():
            # Mock successful geocoding
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)
                
                response = client.post(url_for('auth.register'), data={
                    'email': 'newuser@test.com',
                    'first_name': 'New',
                    'last_name': 'User',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': '123 Registration St',
                    'city': 'New York',
                    'state': 'NY',
                    'zip_code': '10001',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check user was created with coordinates
                user = User.query.filter_by(email='newuser@test.com').first()
                assert user is not None
                assert user.latitude == 40.7128
                assert user.longitude == -74.0060
                assert user.geocoded_at is not None
                assert user.geocoding_failed is False

    def test_user_registration_with_geocoding_failure(self, app, client):
        """Test user registration when geocoding fails."""
        with app.app_context():
            # Mock failed geocoding
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = None
                
                response = client.post(url_for('auth.register'), data={
                    'email': 'newuser2@test.com',
                    'first_name': 'New',
                    'last_name': 'User',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': 'Invalid Address',
                    'city': 'Nowhere',
                    'state': 'XX',
                    'zip_code': '99999',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check user was created without coordinates
                user = User.query.filter_by(email='newuser2@test.com').first()
                assert user is not None
                assert user.latitude is None
                assert user.longitude is None
                assert user.geocoding_failed is True

    def test_user_registration_with_geocoding_exception(self, app, client):
        """Test user registration when geocoding raises exception."""
        with app.app_context():
            # Mock geocoding exception
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.side_effect = GeocodingError("API error")
                
                response = client.post(url_for('auth.register'), data={
                    'email': 'newuser3@test.com',
                    'first_name': 'New',
                    'last_name': 'User',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': '123 Error St',
                    'city': 'Error City',
                    'state': 'EC',
                    'zip_code': '12345',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check user was created but geocoding failed
                user = User.query.filter_by(email='newuser3@test.com').first()
                assert user is not None
                assert user.latitude is None
                assert user.longitude is None
                assert user.geocoding_failed is True
