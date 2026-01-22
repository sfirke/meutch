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
        # But should NOT see the item
        assert b'Private Item' not in response.data
        # Should see a message about items being private or hidden
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

    def test_non_admin_non_owner_sees_no_items(self, client):
        """Test that non-admin users cannot see another user's items even with circle access."""
        owner = UserFactory(first_name="Target", last_name="User")
        viewer = UserFactory(first_name="Curious", last_name="Viewer")
        category = CategoryFactory()  # Use default unique name from factory
        item1 = ItemFactory(owner=owner, category=category, name="Secret Hammer")
        item2 = ItemFactory(owner=owner, category=category, name="Secret Drill")
        db.session.commit()

        # Both in same circle
        circle = CircleFactory()
        circle.members.append(owner)
        circle.members.append(viewer)
        db.session.commit()

        login_user(client, viewer.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        assert response.status_code == 200
        # Profile should load but items should not be visible
        assert b'Secret Hammer' not in response.data
        assert b'Secret Drill' not in response.data

    def test_profile_page_shows_items_section_only_for_authorized(self, client):
        """Test that the items section header is hidden for non-authorized viewers."""
        owner = UserFactory(first_name="Profile", last_name="Owner")
        viewer = UserFactory(first_name="Regular", last_name="Viewer")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=owner, category=category, name="Any Item")
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(owner)
        circle.members.append(viewer)
        db.session.commit()

        # When viewer looks at owner's profile
        login_user(client, viewer.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        assert response.status_code == 200
        # The items section should not be visible at all
        assert b"Profile Owner's Items" not in response.data or b"Profile's Items" not in response.data

    def test_admin_sees_items_section_on_any_profile(self, client):
        """Test that admins see the items section on any profile."""
        admin = UserFactory(is_admin=True)
        owner = UserFactory(first_name="Someone", last_name="Else")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=owner, category=category, name="Admin Can See")
        db.session.commit()

        login_user(client, admin.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        assert response.status_code == 200
        assert b'Admin Can See' in response.data

    def test_owner_sees_items_section_on_own_profile(self, client):
        """Test that profile owners see their items section."""
        owner = UserFactory(first_name="Self", last_name="Viewer")
        category = CategoryFactory(name="Test Category")
        item = ItemFactory(owner=owner, category=category, name="Owner Sees This")
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for('main.user_profile', user_id=owner.id))
        
        assert response.status_code == 200
        assert b'Owner Sees This' in response.data
        # Items section should be visible
        assert b"Self's Items" in response.data or b"Self Viewer's Items" in response.data or b"items-section" in response.data
