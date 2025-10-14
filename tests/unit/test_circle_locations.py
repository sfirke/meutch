"""Test circle location functionality."""

import pytest
from tests.factories import UserFactory, CircleFactory
from app.models import db


class TestCircleLocationModel:
    """Test Circle location model methods and properties."""

    def test_is_geocoded_with_coordinates(self, app):
        """Test that is_geocoded returns True when circle has both lat and lon."""
        with app.app_context():
            circle = CircleFactory(latitude=42.3601, longitude=-71.0589)
            assert circle.is_geocoded is True

    def test_is_geocoded_without_coordinates(self, app):
        """Test that is_geocoded returns False when circle has no location."""
        with app.app_context():
            circle = CircleFactory(latitude=None, longitude=None)
            assert circle.is_geocoded is False

    def test_is_geocoded_with_partial_coordinates(self, app):
        """Test that is_geocoded returns False with only lat or only lon."""
        with app.app_context():
            circle_lat_only = CircleFactory(latitude=42.3601, longitude=None)
            circle_lon_only = CircleFactory(latitude=None, longitude=-71.0589)
            
            assert circle_lat_only.is_geocoded is False
            assert circle_lon_only.is_geocoded is False

    def test_distance_to_user_with_valid_locations(self, app):
        """Test distance calculation between circle and user with known coordinates."""
        with app.app_context():
            # Boston: 42.3601° N, 71.0589° W
            circle = CircleFactory(latitude=42.3601, longitude=-71.0589)
            
            # New York: 40.7128° N, 74.0060° W
            user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            distance = circle.distance_to_user(user)
            
            # Distance between Boston and NYC is approximately 190 miles
            # Allow some tolerance for the Haversine calculation
            assert distance is not None
            assert 185 <= distance <= 195

    def test_distance_to_user_same_location(self, app):
        """Test distance calculation when circle and user are at same location."""
        with app.app_context():
            circle = CircleFactory(latitude=42.3601, longitude=-71.0589)
            user = UserFactory(latitude=42.3601, longitude=-71.0589)
            
            distance = circle.distance_to_user(user)
            
            # Distance should be effectively zero (allowing for float precision)
            assert distance is not None
            assert distance < 0.1

    def test_distance_to_user_circle_not_geocoded(self, app):
        """Test that distance returns None when circle has no location."""
        with app.app_context():
            circle = CircleFactory(latitude=None, longitude=None)
            user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            distance = circle.distance_to_user(user)
            
            assert distance is None

    def test_distance_to_user_user_not_geocoded(self, app):
        """Test that distance returns None when user has no location."""
        with app.app_context():
            circle = CircleFactory(latitude=42.3601, longitude=-71.0589)
            user = UserFactory(latitude=None, longitude=None)
            
            distance = circle.distance_to_user(user)
            
            assert distance is None

    def test_distance_to_user_neither_geocoded(self, app):
        """Test that distance returns None when neither has location."""
        with app.app_context():
            circle = CircleFactory(latitude=None, longitude=None)
            user = UserFactory(latitude=None, longitude=None)
            
            distance = circle.distance_to_user(user)
            
            assert distance is None
