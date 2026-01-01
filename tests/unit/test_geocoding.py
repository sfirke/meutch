"""Unit tests for geocoding utilities."""
import pytest
from app.utils.geocoding import (
    calculate_distance, sort_by_distance, sort_items_by_owner_distance
)
from tests.factories import UserFactory, ItemFactory, CategoryFactory
from app.models import db

class TestSortByDistance:
    """Test sort_by_distance utility function."""
    
    def test_sort_by_distance_sorts_correctly(self, app):
        """Test that items are sorted by distance correctly."""
        with app.app_context():
            
            # Create a reference user in NYC
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            # Create mock items with different distances
            class MockItem:
                def __init__(self, name, lat, lon):
                    self.name = name
                    self.lat = lat
                    self.lon = lon
            
            # LA is ~2445 miles from NYC
            item_la = MockItem("LA", 34.0522, -118.2437)
            # Chicago is ~713 miles from NYC
            item_chicago = MockItem("Chicago", 41.8781, -87.6298)
            # Boston is ~190 miles from NYC
            item_boston = MockItem("Boston", 42.3601, -71.0589)
            
            items = [item_la, item_chicago, item_boston]
            
            def distance_fn(item, user):
                return calculate_distance(item.lat, item.lon, user.latitude, user.longitude)
            
            sorted_items = sort_by_distance(items, reference_user, distance_fn)
            
            # Should be sorted: Boston (closest), Chicago, LA (farthest)
            assert sorted_items[0].name == "Boston"
            assert sorted_items[1].name == "Chicago"
            assert sorted_items[2].name == "LA"
    
    def test_sort_by_distance_handles_no_location(self, app):
        """Test that items without location are sorted to the end."""
        with app.app_context():
            
            # Create a reference user in NYC
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            class MockItem:
                def __init__(self, name, lat=None, lon=None):
                    self.name = name
                    self.lat = lat
                    self.lon = lon
            
            # Boston has location
            item_boston = MockItem("Boston", 42.3601, -71.0589)
            # No location items
            item_no_loc1 = MockItem("NoLoc1")
            item_no_loc2 = MockItem("NoLoc2")
            
            items = [item_no_loc1, item_boston, item_no_loc2]
            
            def distance_fn(item, user):
                if item.lat is None or item.lon is None:
                    return None
                return calculate_distance(item.lat, item.lon, user.latitude, user.longitude)
            
            sorted_items = sort_by_distance(items, reference_user, distance_fn)
            
            # Boston should be first (has location), no-location items at end
            assert sorted_items[0].name == "Boston"
            assert sorted_items[1].name in ["NoLoc1", "NoLoc2"]
            assert sorted_items[2].name in ["NoLoc1", "NoLoc2"]
    
    def test_sort_by_distance_filters_by_radius(self, app):
        """Test that items beyond radius are filtered out."""
        with app.app_context():
            
            # Create a reference user in NYC
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            class MockItem:
                def __init__(self, name, lat, lon):
                    self.name = name
                    self.lat = lat
                    self.lon = lon
            
            # LA is ~2445 miles from NYC
            item_la = MockItem("LA", 34.0522, -118.2437)
            # Boston is ~190 miles from NYC
            item_boston = MockItem("Boston", 42.3601, -71.0589)
            
            items = [item_la, item_boston]
            
            def distance_fn(item, user):
                return calculate_distance(item.lat, item.lon, user.latitude, user.longitude)
            
            # Filter to 500 mile radius (should exclude LA)
            sorted_items = sort_by_distance(items, reference_user, distance_fn, radius=500)
            
            assert len(sorted_items) == 1
            assert sorted_items[0].name == "Boston"
    
    def test_sort_by_distance_user_not_geocoded(self, app):
        """Test that original list is returned when user is not geocoded."""
        with app.app_context():
            
            # Create a reference user without location
            reference_user = UserFactory(latitude=None, longitude=None)
            
            class MockItem:
                def __init__(self, name, lat, lon):
                    self.name = name
                    self.lat = lat
                    self.lon = lon
            
            item1 = MockItem("Item1", 34.0522, -118.2437)
            item2 = MockItem("Item2", 42.3601, -71.0589)
            
            items = [item1, item2]
            
            def distance_fn(item, user):
                return calculate_distance(item.lat, item.lon, user.latitude, user.longitude)
            
            sorted_items = sort_by_distance(items, reference_user, distance_fn)
            
            # Original order should be preserved
            assert sorted_items[0].name == "Item1"
            assert sorted_items[1].name == "Item2"
    
    def test_sort_by_distance_empty_list(self, app):
        """Test that empty list returns empty list."""
        with app.app_context():
            
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            def distance_fn(item, user):
                return 0
            
            sorted_items = sort_by_distance([], reference_user, distance_fn)
            
            assert sorted_items == []


class TestSortItemsByOwnerDistance:
    """Test sort_items_by_owner_distance convenience function."""
    
    def test_sort_items_by_owner_distance(self, app):
        """Test sorting items by owner distance."""
        with app.app_context():
            
            # Create a reference user in NYC
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            # Create owners at different distances
            owner_la = UserFactory(latitude=34.0522, longitude=-118.2437)  # LA
            owner_boston = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
            owner_chicago = UserFactory(latitude=41.8781, longitude=-87.6298)  # Chicago
            
            category = CategoryFactory()
            db.session.commit()
            
            item_la = ItemFactory(owner=owner_la, category=category, name="LA Item")
            item_boston = ItemFactory(owner=owner_boston, category=category, name="Boston Item")
            item_chicago = ItemFactory(owner=owner_chicago, category=category, name="Chicago Item")
            db.session.commit()
            
            items = [item_la, item_chicago, item_boston]
            
            sorted_items = sort_items_by_owner_distance(items, reference_user)
            
            # Should be sorted by owner distance: Boston, Chicago, LA
            assert sorted_items[0].name == "Boston Item"
            assert sorted_items[1].name == "Chicago Item"
            assert sorted_items[2].name == "LA Item"
    
    def test_sort_items_by_owner_distance_owner_no_location(self, app):
        """Test that items with owners without location are sorted to end."""
        with app.app_context():
            
            reference_user = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            owner_with_loc = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
            owner_no_loc = UserFactory(latitude=None, longitude=None)
            
            category = CategoryFactory()
            db.session.commit()
            
            item_with_loc = ItemFactory(owner=owner_with_loc, category=category, name="Located Item")
            item_no_loc = ItemFactory(owner=owner_no_loc, category=category, name="No Location Item")
            db.session.commit()
            
            items = [item_no_loc, item_with_loc]
            
            sorted_items = sort_items_by_owner_distance(items, reference_user)
            
            # Item with located owner should be first
            assert sorted_items[0].name == "Located Item"
            assert sorted_items[1].name == "No Location Item"
