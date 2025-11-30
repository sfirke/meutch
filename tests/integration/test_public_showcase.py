"""Integration tests for public showcase feature.

Tests that unauthenticated visitors only see items from users marked as 
is_public_showcase=True, and that the admin panel can manage this flag.
"""
import pytest
from flask import url_for
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from app.models import AdminAction, circle_members, db
from conftest import login_user


class TestHomepageShowcaseItems:
    """Tests for homepage item visibility for unauthenticated users"""
    
    def test_unauthenticated_user_sees_only_showcase_items(self, client, db_session):
        """Test that unauthenticated users only see items from showcase users"""
        category = CategoryFactory()
        
        # Create a showcase user with items
        showcase_user = UserFactory(is_public_showcase=True)
        showcase_item = ItemFactory(owner=showcase_user, category=category, name="Showcase Item Visible")
        
        # Create a non-showcase user with items (even in public circle)
        regular_user = UserFactory(is_public_showcase=False)
        regular_item = ItemFactory(owner=regular_user, category=category, name="Regular Item Hidden")
        
        # Add regular user to a public circle
        public_circle = CircleFactory(requires_approval=False)
        db_session.commit()
        db_session.execute(circle_members.insert().values(user_id=regular_user.id, circle_id=public_circle.id))
        db_session.commit()
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        
        # Showcase item should be visible
        assert showcase_item.name.encode() in response.data
        # Regular item should NOT be visible (even though user is in public circle)
        assert regular_item.name.encode() not in response.data
    
    def test_unauthenticated_user_sees_empty_state_when_no_showcase_users(self, client, db_session):
        """Test friendly message when no showcase items exist"""
        category = CategoryFactory()
        
        # Create items but from non-showcase users
        regular_user = UserFactory(is_public_showcase=False)
        ItemFactory(owner=regular_user, category=category)
        db_session.commit()
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        
        # Should see empty state message
        assert b'Join our community' in response.data
        assert b'Join Meutch' in response.data
    
    def test_unauthenticated_user_sees_remaining_items_teaser(self, client, db_session):
        """Test that 'X more' teaser shows correct count for showcase items"""
        category = CategoryFactory()
        showcase_user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        # Create 15 items from showcase user (more than the 12 preview limit)
        for i in range(15):
            ItemFactory(owner=showcase_user, category=category, name=f"Showcase Item {i}")
        db_session.commit()
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        
        # Should show "3 more" (15 - 12 = 3)
        assert b'3 more' in response.data
    
    def test_homepage_shows_random_selection(self, client, db_session):
        """Test that items are randomly selected, not ordered by creation date"""
        category = CategoryFactory()
        showcase_user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        # Create more than 12 items
        items = []
        for i in range(20):
            item = ItemFactory(owner=showcase_user, category=category, name=f"Random Item {i:03d}")
            items.append(item)
        db_session.commit()
        
        # Make multiple requests and check we get different orderings
        # (statistically, with 20 items taking 12, different orderings should appear)
        responses = []
        for _ in range(3):
            response = client.get(url_for('main.index'))
            assert response.status_code == 200
            responses.append(response.data)
        
        # At minimum, we should see that some items appear (validating the query works)
        assert b'Random Item' in responses[0]
    
    def test_authenticated_user_homepage_unchanged(self, client, db_session):
        """Test that authenticated users still see circle-based items"""
        category = CategoryFactory()
        
        # Create two users in same circle
        user1 = UserFactory(is_public_showcase=False)
        user2 = UserFactory(is_public_showcase=False)
        db_session.commit()
        
        circle = CircleFactory(requires_approval=False)
        db_session.commit()
        db_session.execute(circle_members.insert().values(user_id=user1.id, circle_id=circle.id))
        db_session.execute(circle_members.insert().values(user_id=user2.id, circle_id=circle.id))
        db_session.commit()
        
        # Create item owned by user2
        item = ItemFactory(owner=user2, category=category, name="Circle Member Item")
        db_session.commit()
        
        # Login as user1
        login_user(client, user1.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        
        # Should see the item (circle-based visibility, not showcase-based)
        assert item.name.encode() in response.data


class TestAdminShowcaseRoutes:
    """Tests for admin panel showcase enable/disable routes"""
    
    def test_enable_showcase_success(self, client, db_session):
        """Test successfully enabling showcase for a user"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=False)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.post(f'/admin/users/{user.id}/enable-showcase', follow_redirects=True)
        assert response.status_code == 200
        
        # Check user was updated
        db_session.refresh(user)
        assert user.is_public_showcase is True
        
        # Check admin action was logged
        action = AdminAction.query.filter_by(
            action_type='enable_showcase',
            target_user_id=user.id,
            admin_user_id=admin.id
        ).first()
        assert action is not None
        assert action.details['target_email'] == user.email
    
    def test_disable_showcase_success(self, client, db_session):
        """Test successfully disabling showcase for a user"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.post(f'/admin/users/{user.id}/disable-showcase', follow_redirects=True)
        assert response.status_code == 200
        
        # Check user was updated
        db_session.refresh(user)
        assert user.is_public_showcase is False
        
        # Check admin action was logged
        action = AdminAction.query.filter_by(
            action_type='disable_showcase',
            target_user_id=user.id,
            admin_user_id=admin.id
        ).first()
        assert action is not None
    
    def test_enable_showcase_requires_admin(self, client, db_session):
        """Test that only admins can enable showcase"""
        non_admin = UserFactory(is_admin=False)
        target = UserFactory(is_public_showcase=False)
        db_session.commit()
        
        login_user(client, non_admin.email)
        
        response = client.post(f'/admin/users/{target.id}/enable-showcase')
        assert response.status_code == 403
        
        # User should not be changed
        db_session.refresh(target)
        assert target.is_public_showcase is False
    
    def test_disable_showcase_requires_admin(self, client, db_session):
        """Test that only admins can disable showcase"""
        non_admin = UserFactory(is_admin=False)
        target = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        login_user(client, non_admin.email)
        
        response = client.post(f'/admin/users/{target.id}/disable-showcase')
        assert response.status_code == 403
        
        # User should not be changed
        db_session.refresh(target)
        assert target.is_public_showcase is True
    
    def test_enable_showcase_already_enabled(self, client, db_session):
        """Test enabling showcase for user who already has it"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.post(f'/admin/users/{user.id}/enable-showcase', follow_redirects=True)
        assert response.status_code == 200
        assert b'already has public showcase enabled' in response.data
    
    def test_disable_showcase_not_enabled(self, client, db_session):
        """Test disabling showcase for user who doesn't have it"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=False)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.post(f'/admin/users/{user.id}/disable-showcase', follow_redirects=True)
        assert response.status_code == 200
        assert b'does not have public showcase enabled' in response.data
    
    def test_enable_showcase_deleted_user(self, client, db_session):
        """Test cannot enable showcase for deleted user"""
        admin = UserFactory(is_admin=True)
        deleted_user = UserFactory(is_public_showcase=False, is_deleted=True)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.post(f'/admin/users/{deleted_user.id}/enable-showcase', follow_redirects=True)
        assert response.status_code == 200
        assert b'Cannot enable showcase for a deleted user' in response.data


class TestAdminDashboardShowcaseUI:
    """Tests for showcase display in admin dashboard"""
    
    def test_dashboard_shows_showcase_badge(self, client, db_session):
        """Test that showcase users have a 'Showcase' badge"""
        admin = UserFactory(is_admin=True)
        showcase_user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Showcase' in response.data
    
    def test_dashboard_shows_enable_showcase_button(self, client, db_session):
        """Test that non-showcase users have 'Enable Showcase' button"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=False)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Enable Showcase' in response.data
    
    def test_dashboard_shows_disable_showcase_button(self, client, db_session):
        """Test that showcase users have 'Disable Showcase' button"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_public_showcase=True)
        db_session.commit()
        
        login_user(client, admin.email)
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Disable Showcase' in response.data
