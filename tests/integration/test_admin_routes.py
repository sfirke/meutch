"""Integration tests for admin panel routes and functionality"""
import pytest
from flask import url_for
from tests.factories import UserFactory, ItemFactory, AdminActionFactory
from app.models import AdminAction


class TestAdminDashboardAccess:
    """Tests for admin dashboard access control"""
    
    def test_admin_dashboard_requires_login(self, client):
        """Test that admin dashboard redirects to login when not authenticated"""
        response = client.get('/admin/')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_admin_dashboard_blocks_non_admin(self, client, db_session):
        """Test that non-admin users get 403 Forbidden"""
        user = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': user.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/admin/')
        assert response.status_code == 403
    
    def test_admin_dashboard_allows_admin(self, client, db_session):
        """Test that admin users can access dashboard"""
        admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Admin Panel' in response.data


class TestAdminDashboardMetrics:
    """Tests for admin dashboard metrics display"""
    
    def test_dashboard_shows_user_count(self, client, db_session):
        """Test dashboard displays correct user count"""
        admin = UserFactory(is_admin=True)
        UserFactory.create_batch(5)  # 5 regular users
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/admin/')
        assert response.status_code == 200
        # Should show 6 total users (5 + 1 admin)
        assert b'6' in response.data
        assert b'Total Users' in response.data
    
    def test_dashboard_shows_item_count(self, client, db_session):
        """Test dashboard displays correct item count"""
        admin = UserFactory(is_admin=True)
        ItemFactory.create_batch(3)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Total Items' in response.data


class TestAdminUserList:
    """Tests for user list display and pagination"""
    
    def test_dashboard_shows_user_list(self, client, db_session):
        """Test that user list is displayed"""
        admin = UserFactory(is_admin=True)
        user = UserFactory()
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/admin/')
        assert response.status_code == 200
        assert user.email.encode() in response.data
        assert user.full_name.encode() in response.data
    
    def test_dashboard_pagination_works(self, client, db_session):
        """Test that pagination works for large user lists"""
        admin = UserFactory(is_admin=True)
        UserFactory.create_batch(25)  # More than one page (20 per page)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        # First page
        response = client.get('/admin/')
        assert response.status_code == 200
        assert b'Next' in response.data or b'next' in response.data
        
        # Second page
        response = client.get('/admin/?page=2')
        assert response.status_code == 200


class TestPromoteUser:
    """Tests for promoting users to admin"""
    
    def test_promote_user_success(self, client, db_session):
        """Test successful user promotion"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{user.id}/promote', follow_redirects=True)
        assert response.status_code == 200
        
        # Check user was promoted
        db_session.refresh(user)
        assert user.is_admin is True
        
        # Check admin action was logged
        action = AdminAction.query.filter_by(
            action_type='promote',
            target_user_id=user.id,
            admin_user_id=admin.id
        ).first()
        assert action is not None
    
    def test_promote_requires_admin(self, client, db_session):
        """Test that only admins can promote users"""
        non_admin = UserFactory(is_admin=False)
        target = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': non_admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{target.id}/promote')
        assert response.status_code == 403
        
        # User should not be promoted
        db_session.refresh(target)
        assert target.is_admin is False
    
    def test_promote_already_admin(self, client, db_session):
        """Test promoting a user who is already admin"""
        admin = UserFactory(is_admin=True)
        already_admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{already_admin.id}/promote', follow_redirects=True)
        assert response.status_code == 200
        assert b'already an admin' in response.data


class TestDemoteUser:
    """Tests for demoting admin users"""
    
    def test_demote_user_success(self, client, db_session):
        """Test successful admin demotion"""
        admin = UserFactory(is_admin=True)
        target_admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{target_admin.id}/demote', follow_redirects=True)
        assert response.status_code == 200
        
        # Check user was demoted
        db_session.refresh(target_admin)
        assert target_admin.is_admin is False
        
        # Check admin action was logged
        action = AdminAction.query.filter_by(
            action_type='demote',
            target_user_id=target_admin.id,
            admin_user_id=admin.id
        ).first()
        assert action is not None
    
    def test_cannot_demote_self(self, client, db_session):
        """Test that admin cannot demote themselves"""
        admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{admin.id}/demote', follow_redirects=True)
        assert response.status_code == 200
        assert b'cannot demote yourself' in response.data
        
        # Admin status should be unchanged
        db_session.refresh(admin)
        assert admin.is_admin is True
    
    def test_demote_non_admin(self, client, db_session):
        """Test demoting a user who is not an admin"""
        admin = UserFactory(is_admin=True)
        regular_user = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{regular_user.id}/demote', follow_redirects=True)
        assert response.status_code == 200
        assert b'not an admin' in response.data


class TestDeleteUser:
    """Tests for deleting user accounts"""
    
    def test_delete_user_success(self, client, db_session):
        """Test successful user deletion"""
        admin = UserFactory(is_admin=True)
        user = UserFactory()
        db_session.commit()
        
        user_id = user.id
        user_email = user.email
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{user_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'has been deleted' in response.data
        
        # Check user was soft-deleted
        db_session.refresh(user)
        assert user.is_deleted is True
        
        # Check admin action was logged
        action = AdminAction.query.filter_by(
            action_type='delete',
            target_user_id=user_id,
            admin_user_id=admin.id
        ).first()
        assert action is not None
    
    def test_cannot_delete_self(self, client, db_session):
        """Test that admin cannot delete their own account"""
        admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{admin.id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'cannot delete your own account' in response.data
        
        # User should not be deleted
        db_session.refresh(admin)
        assert admin.is_deleted is False
    
    def test_delete_requires_admin(self, client, db_session):
        """Test that only admins can delete users"""
        non_admin = UserFactory(is_admin=False)
        target = UserFactory()
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': non_admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{target.id}/delete')
        assert response.status_code == 403
        
        # User should not be deleted
        db_session.refresh(target)
        assert target.is_deleted is False


class TestAdminNavbarLink:
    """Tests for admin navbar link visibility"""
    
    def test_admin_link_visible_to_admin(self, client, db_session):
        """Test that admin link appears for admin users"""
        admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/')
        assert response.status_code == 200
        assert b'Admin Panel' in response.data
    
    def test_admin_link_hidden_from_regular_users(self, client, db_session):
        """Test that admin link does not appear for regular users"""
        user = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': user.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/')
        assert response.status_code == 200
        assert b'Admin Panel' not in response.data


class TestAdminFlashMessages:
    """Tests for admin-specific flash message categories"""
    
    def test_admin_success_flash_message(self, client, db_session):
        """Test admin-success flash message category"""
        admin = UserFactory(is_admin=True)
        user = UserFactory(is_admin=False)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        response = client.post(f'/admin/users/{user.id}/promote', follow_redirects=True)
        assert response.status_code == 200
        # Check for admin flash message styling
        assert b'promoted to admin' in response.data
    
    def test_admin_error_flash_message(self, client, db_session):
        """Test admin-error flash message category"""
        admin = UserFactory(is_admin=True)
        db_session.commit()
        
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'testpassword123'
        })
        
        # Try to demote self
        response = client.post(f'/admin/users/{admin.id}/demote', follow_redirects=True)
        assert response.status_code == 200
        assert b'cannot demote yourself' in response.data
