"""Integration tests for profile items visibility privacy feature.

Users should only see another user's items on their profile if:
1. They are the profile owner (viewing own profile)
2. They are an admin

Regular users viewing another user's profile (even in same circle) should NOT see items.
"""
import pytest
from app.models import db
from tests.factories import UserFactory, CircleFactory, ItemFactory, CategoryFactory
from flask import url_for
from conftest import login_user


@pytest.mark.usefixtures('app')
class TestProfileItemsVisibility:
    """Test that items on user profiles are only visible to self and admins."""

    def test_user_sees_own_items_on_profile(self, client):
        """Test that users can see their own items when viewing their own profile."""
        user = UserFactory(first_name="Owner", last_name="User")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=user, category=category, name="My Test Item")
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for('main.user_profile', user_id=user.id))
        
        assert response.status_code == 200
        assert b'My Test Item' in response.data

    def test_circle_member_cannot_see_items_on_other_profile(self, client):
        """Test that circle members cannot see items on another user's profile."""
        owner = UserFactory(first_name="Item", last_name="Owner")
        viewer = UserFactory(first_name="Circle", last_name="Member")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=owner, category=category, name="Private Item")
        db.session.commit()

        # Put both users in the same circle
        circle = CircleFactory()
        circle.members.append(owner)
        circle.members.append(viewer)
        db.session.commit()

        login_user(client, viewer.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        # Should be able to view profile (same circle)
        assert response.status_code == 200
        # But should NOT see the item or a header indicating items
        assert b'Private Item' not in response.data
        assert b"Item Owner's Items" not in response.data or b'Items' not in response.data

    def test_admin_can_see_items_on_any_profile(self, client):
        """Test that admin users can see items on any user's profile."""
        admin = UserFactory(is_admin=True, first_name="Admin", last_name="User")
        owner = UserFactory(first_name="Regular", last_name="User")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=owner, category=category, name="Viewable By Admin Item")
        db.session.commit()

        # Admin doesn't need to be in same circle
        circle = CircleFactory()
        circle.members.append(owner)
        db.session.commit()

        login_user(client, admin.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        assert response.status_code == 200
        assert b'Viewable By Admin Item' in response.data

    def test_user_sees_multiple_items_on_own_profile(self, client):
        """Test that users see all their items on their own profile."""
        user = UserFactory(first_name="Multi", last_name="Owner")
        category = CategoryFactory(name="Test Category")
        item1 = ItemFactory(owner=user, category=category, name="First Item")
        item2 = ItemFactory(owner=user, category=category, name="Second Item")
        item3 = ItemFactory(owner=user, category=category, name="Third Item")
        db.session.commit()

        login_user(client, user.email)
        response = client.get(url_for('main.user_profile', user_id=user.id))
        
        assert response.status_code == 200
        assert b'First Item' in response.data
        assert b'Second Item' in response.data
        assert b'Third Item' in response.data
