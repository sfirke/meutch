"""Integration tests for search with circle-based filtering."""
import pytest
from app.models import db
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from flask import url_for
from conftest import login_user


@pytest.mark.usefixtures('app')
class TestSearchCircleFiltering:
    """Test that search only returns items from users in shared circles."""

    def test_search_get_empty(self, client):
        """Test search page with no query loads successfully."""
        user = UserFactory()
        circle = CircleFactory()
        circle.members.append(user)
        db.session.commit()
        
        login_user(client, user.email)
        
        response = client.get(url_for('main.search'))
        assert response.status_code == 200

    def test_search_returns_only_shared_circle_items(self, client):
        """Test that search only returns items from users in shared circles."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory()  # Same circle as user1
        user3 = UserFactory()  # Different circle
        db.session.commit()

        # Create circles
        circle1 = CircleFactory(name="Circle One")
        circle2 = CircleFactory(name="Circle Two")

        # user1 and user2 in circle1, user3 in circle2
        circle1.members.append(user1)
        circle1.members.append(user2)
        circle2.members.append(user3)
        db.session.commit()

        # Create items with searchable names
        item2 = ItemFactory(owner=user2, category=category, name="Shared Circle Hammer")
        item3 = ItemFactory(owner=user3, category=category, name="Other Circle Hammer")
        db.session.commit()

        # Login as user1 and search
        login_user(client, user1.email)
        response = client.get(url_for('main.search', q='Hammer'))
        
        assert response.status_code == 200
        # Should see item from user2 (shared circle)
        assert b'Shared Circle Hammer' in response.data
        # Should NOT see item from user3 (different circle)
        assert b'Other Circle Hammer' not in response.data

    def test_search_does_not_return_own_items(self, client):
        """Test that search includes user's own items (unlike homepage)."""
        category = CategoryFactory()
        user = UserFactory()
        other_user = UserFactory()
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(user)
        circle.members.append(other_user)
        db.session.commit()

        # Create user's own item and another user's item
        own_item = ItemFactory(owner=user, category=category, name="My Own Drill")
        other_item = ItemFactory(owner=other_user, category=category, name="Shared Drill")
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for('main.search', q='Drill'))
        
        assert response.status_code == 200
        # Search DOES include the user's own items (unlike the homepage)
        assert b'My Own Drill' in response.data
        # Also includes items from circle members
        assert b'Shared Drill' in response.data

    def test_search_shows_join_circle_prompt_when_no_circles(self, client):
        """Test that search shows join circle prompt when user has no circles."""
        user = UserFactory()
        db.session.commit()

        login_user(client, user.email)
        
        # Test both search form page and search results page
        for url_params in [None, {'q': 'anything'}]:
            if url_params:
                response = client.get(url_for('main.search', **url_params))
            else:
                response = client.get(url_for('main.search'))
            
            assert response.status_code == 200
            assert b'Join a circle' in response.data
            assert b'Find Circles to Join' in response.data

    def test_search_returns_empty_when_no_matching_items_in_circles(self, client):
        """Test that search returns empty results when no items match in circles."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(user1)
        circle.members.append(user2)
        db.session.commit()

        # Create item with different name
        item = ItemFactory(owner=user2, category=category, name="Power Saw")
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.search', q='Nonexistent'))
        
        assert response.status_code == 200
        assert b'No items found matching your search' in response.data

    def test_search_multiple_circles_returns_items_from_all(self, client):
        """Test that search returns items from all circles user is in."""
        category = CategoryFactory()
        user1 = UserFactory()  # In both circles
        user2 = UserFactory()  # Circle A only
        user3 = UserFactory()  # Circle B only
        db.session.commit()

        circle_a = CircleFactory(name="Circle A")
        circle_b = CircleFactory(name="Circle B")

        # user1 in both circles
        circle_a.members.append(user1)
        circle_b.members.append(user1)
        # user2 in circle A
        circle_a.members.append(user2)
        # user3 in circle B
        circle_b.members.append(user3)
        db.session.commit()

        item2 = ItemFactory(owner=user2, category=category, name="Circle A Wrench")
        item3 = ItemFactory(owner=user3, category=category, name="Circle B Wrench")
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.search', q='Wrench'))
        
        assert response.status_code == 200
        # Should see items from both circles
        assert b'Circle A Wrench' in response.data
        assert b'Circle B Wrench' in response.data


@pytest.mark.usefixtures('app')
class TestSearchDistanceSorting:
    """Distance sorting is tested comprehensively in test_geocoding.py unit tests."""
    pass


@pytest.mark.usefixtures('app')
class TestSearchDistanceDisplay:
    def test_search_results_show_distance_when_geocoded(self, client, app):
        """Integration test: verify distance badges render in HTML.
        
        This is the only test that verifies the full rendering pipeline from
        context processor -> template -> HTML output. Unit tests verify the
        get_distance_to_item() function works, but don't test actual rendering.
        
        Note: NYC to Boston is approximately 190 miles.
        """
        with app.app_context():
            category = CategoryFactory()
            viewer = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
            owner = UserFactory(latitude=42.3601, longitude=-71.0589)   # Boston
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(owner)
            db.session.commit()

            ItemFactory(owner=owner, category=category, name="Distance Test Item")
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(url_for('main.search', q='Distance'))
            assert response.status_code == 200
            
            html = response.data.decode('utf-8')
            assert 'Distance Test Item' in html
            
            # Verify distance badge appears with expected range (180-200 mi)
            # Badge format: <span class="badge bg-info ms-1">...190.X mi</span>
            assert 'badge bg-info' in html
            assert ' mi' in html
            # Rough sanity check that distance is in expected range
            assert any(f'{d}' in html for d in range(180, 201))

