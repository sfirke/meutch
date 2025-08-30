"""Functional tests for geocoding and distance features."""
import pytest
from unittest.mock import patch
from flask import url_for
from app import db
from tests.factories import UserFactory, ItemFactory
from app.models import User


class TestGeocodingWorkflow:
    """Test complete geocoding workflow from user perspective."""

    def test_complete_distance_calculation_workflow(self, app, client):
        """Test complete workflow: user registration -> address update -> distance calculation."""
        with app.app_context():
            # Step 1: Register two users with different locations
            with patch('app.auth.routes.geocode_address') as mock_geocode_register:
                mock_geocode_register.return_value = (40.7128, -74.0060)  # NYC
                
                # Register first user (item owner)
                client.post(url_for('auth.register'), data={
                    'email': 'owner@test.com',
                    'first_name': 'Item',
                    'last_name': 'Owner',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': '123 NYC St',
                    'city': 'New York',
                    'state': 'NY',
                    'zip_code': '10001',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
                
                # Register second user (potential borrower)
                mock_geocode_register.return_value = (34.0522, -118.2437)  # LA
                
                client.post(url_for('auth.register'), data={
                    'email': 'borrower@test.com',
                    'first_name': 'Item',
                    'last_name': 'Borrower',
                    'password': 'testpassword123',
                    'confirm_password': 'testpassword123',
                    'street': '456 LA Ave',
                    'city': 'Los Angeles',
                    'state': 'CA',
                    'zip_code': '90210',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
            
            # Verify users were created with correct coordinates
            owner = User.query.filter_by(email='owner@test.com').first()
            borrower = User.query.filter_by(email='borrower@test.com').first()
            
            assert owner.latitude == 40.7128
            assert owner.longitude == -74.0060
            assert borrower.latitude == 34.0522
            assert borrower.longitude == -118.2437
            
            # Step 2: Create an item for the owner
            item = ItemFactory(owner=owner)
            db.session.commit()
            
            # Step 3: Test distance calculation
            distance = borrower.distance_to(owner)
            assert distance is not None
            assert 2400 < distance < 2500  # Distance between NYC and LA
            
            # Step 4: Test context processor distance utility
            from app.context_processors import inject_distance_utils
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                formatted_distance = get_distance(item)
                assert formatted_distance is not None
                assert 'mi' in formatted_distance
                # Extract distance value and check range
                distance_str = formatted_distance.replace(' mi', '')
                distance_num = float(distance_str)
                assert 2400 <= distance_num <= 2500

    def test_user_address_update_and_distance_recalculation(self, app, client):
        """Test that updating address recalculates distances correctly."""
        with app.app_context():
            # Create users at known locations
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
            borrower = UserFactory(latitude=34.0522, longitude=-118.2437)  # LA
            db.session.commit()
            
            # Calculate initial distance
            initial_distance = borrower.distance_to(owner)
            assert 2400 < initial_distance < 2500
            
            # Update borrower's address to be closer (Chicago)
            with patch('app.main.routes.geocode_address') as mock_geocode:
                mock_geocode.return_value = (41.8781, -87.6298)  # Chicago
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(borrower.id)
                    sess['_fresh'] = True
                
                client.post(url_for('main.update_address'), data={
                    'street': '789 Chicago Ave',
                    'city': 'Chicago',
                    'state': 'IL',
                    'zip_code': '60601',
                    'country': 'USA',
                    'csrf_token': 'test'
                })
            
            # Refresh user from database
            db.session.refresh(borrower)
            
            # Calculate new distance
            new_distance = borrower.distance_to(owner)
            assert new_distance is not None
            assert 700 < new_distance < 900  # Distance between Chicago and NYC
            assert new_distance < initial_distance  # Should be closer now

    def test_geocoding_failure_retry_workflow(self, app, client):
        """Test workflow when initial geocoding fails but retry succeeds."""
        with app.app_context():
            # Create user with failed geocoding
            user = UserFactory(
                latitude=None,
                longitude=None,
                geocoding_failed=True
            )
            db.session.commit()
            
            # Verify user is not geocoded
            assert not user.is_geocoded
            assert user.can_update_address()  # Should be able to retry
            
            # Update address with successful geocoding
            with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                mock_geocode.return_value = (40.7128, -74.0060)
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                
                response = client.post(url_for('main.update_address'), data={
                    'street': '123 Success St',
                    'city': 'New York',
                    'state': 'NY',
                    'zip_code': '10001',
                    'country': 'USA',
                    'csrf_token': 'test'
                }, follow_redirects=True)
                
                assert response.status_code == 200
            
            # Refresh user from database
            db.session.refresh(user)
            
            # Verify user is now geocoded
            assert user.is_geocoded
            assert user.geocoding_failed is False
            assert user.latitude == 40.7128
            assert user.longitude == -74.0060

    def test_distance_display_in_item_context(self, app, client):
        """Test that distances are properly formatted for display."""
        with app.app_context():
            # Create users at different known distances
            owner = UserFactory(latitude=40.7580, longitude=-73.9855)  # Times Square
            borrower = UserFactory(latitude=40.7829, longitude=-73.9654)  # Central Park
            db.session.commit()
            
            item = ItemFactory(owner=owner)
            db.session.commit()
            
            # Test context processor formatting
            from app.context_processors import inject_distance_utils
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                formatted_distance = get_distance(item)
                
                # Should be a small distance in Manhattan
                assert formatted_distance is not None
                assert 'mi' in formatted_distance
                # Distance should be less than 3 miles
                distance_value = float(formatted_distance.replace(' mi', ''))
                assert distance_value < 3.0

    def test_multiple_users_distance_calculation(self, app):
        """Test distance calculations between multiple users."""
        with app.app_context():
            # Create users in different cities
            users = {
                'nyc': UserFactory(latitude=40.7128, longitude=-74.0060),      # NYC
                'la': UserFactory(latitude=34.0522, longitude=-118.2437),      # LA  
                'chicago': UserFactory(latitude=41.8781, longitude=-87.6298),  # Chicago
                'miami': UserFactory(latitude=25.7617, longitude=-80.1918),    # Miami
            }
            db.session.commit()
            
            # Expected approximate distances (in miles)
            expected_distances = {
                ('nyc', 'la'): (2400, 2500),
                ('nyc', 'chicago'): (700, 900),
                ('nyc', 'miami'): (1000, 1300),
                ('la', 'chicago'): (1700, 2000),
                ('la', 'miami'): (2300, 2700),
                ('chicago', 'miami'): (1100, 1400),
            }
            
            # Test all combinations
            for (city1, city2), (min_dist, max_dist) in expected_distances.items():
                distance = users[city1].distance_to(users[city2])
                assert distance is not None
                assert min_dist <= distance <= max_dist, f"Distance between {city1} and {city2} was {distance}, expected {min_dist}-{max_dist}"
                
                # Test reverse direction (should be the same)
                reverse_distance = users[city2].distance_to(users[city1])
                assert abs(distance - reverse_distance) < 0.01  # Should be essentially identical

    def test_edge_case_coordinates(self, app):
        """Test distance calculation with edge case coordinates."""
        with app.app_context():
            # Test with coordinates at extreme locations
            north_pole = UserFactory(latitude=90.0, longitude=0.0)
            south_pole = UserFactory(latitude=-90.0, longitude=0.0)
            equator_prime = UserFactory(latitude=0.0, longitude=0.0)
            equator_opposite = UserFactory(latitude=0.0, longitude=180.0)
            db.session.commit()
            
            # Distance from North to South Pole should be about half Earth's circumference
            pole_distance = north_pole.distance_to(south_pole)
            assert pole_distance is not None
            assert 12000 < pole_distance < 13000  # Roughly half of Earth's circumference
            
            # Distance across equator should be about half Earth's circumference
            equator_distance = equator_prime.distance_to(equator_opposite)
            assert equator_distance is not None
            assert 12000 < equator_distance < 13000

    def test_geocoding_error_handling_workflow(self, app, client):
        """Test complete error handling workflow for geocoding failures."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            db.session.commit()
            
            # Test different types of geocoding failures
            failure_scenarios = [
                None,  # No results found
                Exception("Network error"),  # Generic exception
                ValueError("Invalid JSON"),  # Parsing error
            ]
            
            for i, failure in enumerate(failure_scenarios):
                with patch('app.utils.geocoding.geocode_address') as mock_geocode:
                    if isinstance(failure, Exception):
                        mock_geocode.side_effect = failure
                    else:
                        mock_geocode.return_value = failure
                    
                    with client.session_transaction() as sess:
                        sess['_user_id'] = str(user.id)
                        sess['_fresh'] = True
                    
                    response = client.post(url_for('main.update_address'), data={
                        'street': f'Test St {i}',
                        'city': f'Test City {i}',
                        'state': 'TC',
                        'zip_code': f'1234{i}',
                        'country': 'USA',
                        'csrf_token': 'test'
                    })
                    
                    assert response.status_code == 200
                    
                    # Refresh user from database
                    db.session.refresh(user)
                    
                    # Address should be updated but geocoding should have failed
                    assert user.street == f'Test St {i}'
                    assert user.geocoding_failed is True
                    assert user.latitude is None
                    assert user.longitude is None
                    
                    # Should still be able to retry after failure
                    assert user.can_update_address() is True
