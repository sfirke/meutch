"""Tests for circle leave functionality."""
import pytest
from flask import url_for
from app.models import db, Circle
from tests.factories import UserFactory, CircleFactory
from conftest import login_user


class TestCircleLeave:
    """Test circle leave behavior."""
    
    def test_last_member_leaving_deletes_circle(self, client, app):
        """Test that when the last member leaves a circle, the circle is deleted."""
        with app.app_context():
            # Create a user and a circle with just that user
            user = UserFactory()
            circle = CircleFactory(name='Test Circle to Delete')
            circle.members.append(user)
            db.session.commit()
            
            circle_id = circle.id
            
            # Verify circle exists and has 1 member
            assert len(circle.members) == 1
            assert user in circle.members
            
            # Login and leave the circle
            login_user(client, user.email)
            response = client.post(
                f'/circles/leave/{circle_id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            # Check for the flash message indicating deletion
            assert b'Circle has been deleted as it has no remaining members' in response.data
            
            # Verify circle was deleted from database
            deleted_circle = db.session.get(Circle, circle_id)
            assert deleted_circle is None
    
    def test_warning_displayed_for_last_member(self, client, app):
        """Test that a warning is displayed when the last member views the circle."""
        with app.app_context():
            # Create a user and a circle with just that user
            user = UserFactory()
            circle = CircleFactory(name='Test Circle Warning')
            circle.members.append(user)
            db.session.commit()
            
            # Login and view the circle details
            login_user(client, user.email)
            response = client.get(f'/circles/{circle.id}')
            
            assert response.status_code == 200
            # Check that the warning script is present in the page
            assert b'You are the last member of this circle' in response.data
            assert b'the circle will be permanently deleted' in response.data
    
    def test_no_warning_for_non_last_member(self, client, app):
        """Test that no warning is displayed when there are multiple members."""
        with app.app_context():
            # Create two users and a circle
            user1 = UserFactory()
            user2 = UserFactory()
            circle = CircleFactory(name='Test Circle No Warning')
            circle.members.extend([user1, user2])
            db.session.commit()
            
            # Login as user1 and view the circle details
            login_user(client, user1.email)
            response = client.get(f'/circles/{circle.id}')
            
            assert response.status_code == 200
            # Check that the warning script is NOT present
            assert b'You are the last member of this circle' not in response.data
    
    def test_non_last_member_leaving_keeps_circle(self, client, app):
        """Test that when a non-last member leaves, the circle remains."""
        with app.app_context():
            # Create two users and a circle
            user1 = UserFactory()
            user2 = UserFactory()
            circle = CircleFactory(name='Test Circle to Keep')
            circle.members.extend([user1, user2])
            db.session.commit()
            
            circle_id = circle.id
            
            # Verify circle has 2 members
            assert len(circle.members) == 2
            
            # User1 leaves the circle
            login_user(client, user1.email)
            response = client.post(
                f'/circles/leave/{circle_id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'You have left the circle' in response.data
            
            # Verify circle still exists
            remaining_circle = db.session.get(Circle, circle_id)
            assert remaining_circle is not None
            
            # Verify user1 is no longer a member
            assert user1 not in remaining_circle.members
            
            # Verify user2 is still a member
            assert user2 in remaining_circle.members
            assert len(remaining_circle.members) == 1
    
    def test_admin_leaving_promotes_next_member(self, client, app):
        """Test that when the only admin leaves, the next member becomes admin."""
        with app.app_context():
            # Create admin and regular member
            admin = UserFactory()
            member = UserFactory()
            circle = CircleFactory(name='Test Admin Transfer')
            circle.members.extend([admin, member])
            db.session.commit()
            
            # Make admin the circle admin
            from app.models import circle_members
            from sqlalchemy import and_
            stmt = circle_members.update().where(
                and_(
                    circle_members.c.circle_id == circle.id,
                    circle_members.c.user_id == admin.id
                )
            ).values(is_admin=True)
            db.session.execute(stmt)
            db.session.commit()
            
            # Verify admin status
            assert circle.is_admin(admin)
            assert not circle.is_admin(member)
            
            # Admin leaves the circle
            login_user(client, admin.email)
            response = client.post(
                f'/circles/leave/{circle.id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Refresh circle from database
            db.session.expire_all()
            remaining_circle = db.session.get(Circle, circle.id)
            
            # Verify admin left
            assert admin not in remaining_circle.members
            
            # Verify member is now an admin
            assert remaining_circle.is_admin(member)
