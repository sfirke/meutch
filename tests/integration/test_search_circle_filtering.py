"""Integration tests for search with circle-based filtering."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import url_for

from app.models import db
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ItemFactory,
    ItemRequestFactory,
    UserFactory,
)


@pytest.mark.usefixtures("app")
class TestSearchCircleFiltering:
    """Test that search only returns items from users in shared circles."""

    def test_search_get_empty(self, client):
        """Test search page with no query loads successfully."""
        user = UserFactory()
        circle = CircleFactory()
        circle.members.append(user)
        db.session.commit()

        login_user(client, user.email)

        response = client.get(url_for("main.find"))
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
        ItemFactory(owner=user2, category=category, name="Shared Circle Hammer")
        ItemFactory(owner=user3, category=category, name="Other Circle Hammer")
        db.session.commit()

        # Login as user1 and search
        login_user(client, user1.email)
        response = client.get(url_for("main.find", q="Hammer"))

        assert response.status_code == 200
        # Should see item from user2 (shared circle)
        assert b"Shared Circle Hammer" in response.data
        # Should NOT see item from user3 (different circle)
        assert b"Other Circle Hammer" not in response.data

    def test_search_does_not_return_own_items(self, client):
        """Test that search excludes user's own items (consistent with browse mode)."""
        category = CategoryFactory()
        user = UserFactory()
        other_user = UserFactory()
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(user)
        circle.members.append(other_user)
        db.session.commit()

        # Create user's own item and another user's item
        ItemFactory(owner=user, category=category, name="My Own Drill")
        ItemFactory(owner=other_user, category=category, name="Shared Drill")
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for("main.find", q="Drill"))

        assert response.status_code == 200
        # Search excludes the user's own items (same as browse mode)
        assert b"My Own Drill" not in response.data
        # Includes items from circle members
        assert b"Shared Drill" in response.data

    def test_search_shows_join_circle_prompt_when_no_circles(self, client):
        """Test that search shows join circle prompt when user has no circles."""
        user = UserFactory()
        db.session.commit()

        login_user(client, user.email)

        # Test both search form page and search results page
        for url_params in [None, {"q": "anything"}]:
            if url_params:
                response = client.get(url_for("main.find", **url_params))
            else:
                response = client.get(url_for("main.find"))

            assert response.status_code == 200
            assert b"Join a circle" in response.data
            assert b"Find Circles to Join" in response.data

    def test_manage_circles_highlights_recommended_circle_when_user_has_no_circles(self, client):
        """The circles page should spotlight a recommended circle for zero-circle users."""
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        category = CategoryFactory()
        owner = UserFactory()
        circle = CircleFactory(name="Neighborhood Helpers", latitude=40.7135, longitude=-74.0050)
        circle.members.extend([owner, UserFactory()])

        ItemFactory(owner=owner, category=category, available=True, is_giveaway=False)
        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )
        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )
        ItemFactory(
            owner=owner,
            category=category,
            available=False,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="claimed",
        )
        ItemRequestFactory(user=owner, visibility="circles", status="open")
        ItemRequestFactory(user=owner, visibility="public", status="open")
        ItemRequestFactory(
            user=owner,
            visibility="public",
            status="fulfilled",
            expires_at=datetime.now(UTC) - timedelta(days=30),
            fulfilled_at=datetime.now(UTC) - timedelta(days=30),
        )
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for("circles.manage_circles"))
        content = response.data.decode("utf-8")

        assert response.status_code == 200
        assert "Join a circle before you browse Meutch" in content
        assert "Neighborhood Helpers" in content
        assert "1 borrowable item" in content
        assert "2 giveaways" in content
        assert "2 requests" in content
        assert "These members also have" not in content
        assert "View Circle" in content
        assert "Join Circle" not in content
        assert "Request to Join" not in content

    def test_manage_circles_pins_regional_circles_first(self, client):
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        CircleFactory(
            name="Ann Arbor Regional",
            circle_type="open",
            latitude=40.7130,
            longitude=-74.0060,
            is_regional=True,
            regional_radius_miles=15,
        )
        CircleFactory(
            name="Washtenaw Regional",
            circle_type="open",
            latitude=40.7200,
            longitude=-74.0060,
            is_regional=True,
            regional_radius_miles=25,
        )
        CircleFactory(
            name="Neighborhood Circle",
            circle_type="open",
            latitude=40.7135,
            longitude=-74.0060,
        )
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for("circles.manage_circles"))
        content = response.data.decode("utf-8")

        assert response.status_code == 200
        assert "Regional circle" in content
        assert content.index("Ann Arbor Regional") < content.index("Washtenaw Regional")
        assert content.index("Washtenaw Regional") < content.index("Neighborhood Circle")

    def test_manage_circles_recommendations_ignore_search_filters(self, client):
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        CircleFactory(
            name="Recommended Circle",
            circle_type="open",
            latitude=40.8628,
            longitude=-74.0060,
        )
        CircleFactory(
            name="Library Exchange",
            circle_type="open",
            latitude=40.7130,
            longitude=-74.0060,
        )
        db.session.commit()

        login_user(client, user.email)
        response = client.post(
            url_for("circles.manage_circles"),
            data={"search_circles": True, "search_query": "Library", "radius": "5"},
        )
        content = response.data.decode("utf-8")
        search_results_section = content.split("Search Results", 1)[1]

        assert response.status_code == 200
        assert "Join a circle before you browse Meutch" in content
        assert "Recommended Circle" in content
        assert "Library Exchange" in search_results_section
        assert "Recommended Circle" not in search_results_section

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
        ItemFactory(owner=user2, category=category, name="Power Saw")
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.find", q="Nonexistent"))

        assert response.status_code == 200
        assert b"No items match your search" in response.data

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

        ItemFactory(owner=user2, category=category, name="Circle A Wrench")
        ItemFactory(owner=user3, category=category, name="Circle B Wrench")
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.find", q="Wrench"))

        assert response.status_code == 200
        # Should see items from both circles
        assert b"Circle A Wrench" in response.data
        assert b"Circle B Wrench" in response.data


@pytest.mark.usefixtures("app")
class TestSearchDistanceSorting:
    """Distance sorting is tested comprehensively in test_geocoding.py unit tests."""

    pass


@pytest.mark.usefixtures("app")
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
            owner = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(owner)
            db.session.commit()

            ItemFactory(owner=owner, category=category, name="Distance Test Item")
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(url_for("main.find", q="Distance"))
            assert response.status_code == 200

            html = response.data.decode("utf-8")
            assert "Distance Test Item" in html

            # Verify distance badge appears with bucketed range
            assert "badge bg-info" in html
            # Distance between Boston and ~190 mi away falls in 25+ mi bucket
            assert "25+ mi" in html
