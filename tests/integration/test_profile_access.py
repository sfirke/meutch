"""Integration tests for profile access with circle-based restrictions."""
import pytest
from app.models import User, Circle, db
from tests.factories import UserFactory, CircleFactory
from flask import url_for
from conftest import login_user


@pytest.mark.usefixtures('app')
class TestProfileAccessControl:
    """Test that profile access is restricted based on circle membership."""

    def test_profile_requires_login(self, client):
        """Test that profile page redirects to login when not authenticated."""
        user = UserFactory()
        db.session.commit()
        
        response = client.get(url_for('main.user_profile', user_id=user.id))
        assert response.status_code == 302
        assert 'login' in response.location

    def test_profile_accessible_when_shared_circle(self, client):
        """Test that users can view profiles of users in their circles."""
        user1 = UserFactory(first_name="Viewer", last_name="User")
        user2 = UserFactory(first_name="Profile", last_name="Owner")
        db.session.commit()

        circle = CircleFactory()
        
        # Add both users to the same circle
        circle.members.append(user1)
        circle.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.user_profile', user_id=user2.id))
        
        assert response.status_code == 200
        assert b'Profile Owner' in response.data

    def test_profile_not_accessible_when_no_shared_circle(self, client):
        """Test that users cannot view profiles of users not in their circles."""
        user1 = UserFactory()
        user2 = UserFactory()
        db.session.commit()

        # Create separate circles
        circle1 = CircleFactory(name="Circle A")
        circle2 = CircleFactory(name="Circle B")
        
        # Users in different circles
        circle1.members.append(user1)
        circle2.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.user_profile', user_id=user2.id))
        
        # Should redirect with warning
        assert response.status_code == 302
        # Follow redirect to index
        response = client.get(url_for('main.user_profile', user_id=user2.id), follow_redirects=True)
        assert b'You can only view profiles of users in your circles' in response.data

    def test_profile_not_accessible_when_no_circles(self, client):
        """Test that users without circles cannot view other profiles."""
        user1 = UserFactory()  # No circles
        user2 = UserFactory()
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.user_profile', user_id=user2.id))
        
        # Should redirect with warning
        assert response.status_code == 302

    def test_admin_can_view_any_profile(self, client):
        """Test that admin users can view any profile regardless of circles."""
        admin_user = UserFactory(is_admin=True, first_name="Admin", last_name="User")
        regular_user = UserFactory(first_name="Regular", last_name="User")
        db.session.commit()

        # They don't share any circles
        circle = CircleFactory()
        circle.members.append(regular_user)
        db.session.commit()

        login_user(client, admin_user.email)
        response = client.get(url_for('main.user_profile', user_id=regular_user.id))
        
        assert response.status_code == 200
        assert b'Regular User' in response.data

    def test_user_can_view_own_profile(self, client):
        """Test that users can always view their own profile."""
        user = UserFactory(first_name="Self", last_name="Viewer")
        db.session.commit()

        # User has no circles
        login_user(client, user.email)
        response = client.get(url_for('main.user_profile', user_id=user.id))
        
        assert response.status_code == 200
        assert b'Self Viewer' in response.data

    def test_profile_accessible_one_shared_of_many_circles(self, client):
        """Test profile access when users share only one of many circles."""
        user1 = UserFactory()
        user2 = UserFactory(first_name="Partial", last_name="Overlap")
        db.session.commit()

        circle1 = CircleFactory(name="Shared Circle")
        circle2 = CircleFactory(name="User1 Only")
        circle3 = CircleFactory(name="User2 Only")
        
        # user1 in circles 1 and 2
        circle1.members.append(user1)
        circle2.members.append(user1)
        # user2 in circles 1 and 3
        circle1.members.append(user2)
        circle3.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for('main.user_profile', user_id=user2.id))
        
        assert response.status_code == 200
        assert b'Partial Overlap' in response.data

    def test_profile_nonexistent_user_does_not_leak_existence(self, client):
        """Non-admins should not learn if a non-shared user exists (or not)."""
        import uuid

        viewer = UserFactory()
        db.session.commit()

        login_user(client, viewer.email)
        response = client.get(url_for('main.user_profile', user_id=uuid.uuid4()))
        # Redirect to index with generic warning (same behavior as unauthorized access)
        assert response.status_code == 302
