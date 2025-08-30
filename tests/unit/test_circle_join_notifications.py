"""Tests for circle join request email notifications."""

import pytest
from unittest.mock import patch
from tests.factories import UserFactory, CircleFactory, CircleJoinRequestFactory
from app.utils.email import send_circle_join_request_notification_email, send_circle_join_request_decision_email
from app.models import db, circle_members
from sqlalchemy import and_
from datetime import datetime


class TestCircleJoinRequestNotifications:
    """Test circle join request email notification functionality."""

    def test_send_circle_join_request_notification_email_success(self, app):
        """Test sending email notification to circle admins for a new join request."""
        with app.app_context():
            # Create test users and circle
            admin1 = UserFactory(email='admin1@test.com', first_name='John', last_name='Admin')
            admin2 = UserFactory(email='admin2@test.com', first_name='Jane', last_name='Admin')
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admins to circle
            stmt1 = circle_members.insert().values(
                user_id=admin1.id,
                circle_id=circle.id,
                joined_at=datetime.utcnow(),
                is_admin=True
            )
            stmt2 = circle_members.insert().values(
                user_id=admin2.id,
                circle_id=circle.id,
                joined_at=datetime.utcnow(),
                is_admin=True
            )
            db.session.execute(stmt1)
            db.session.execute(stmt2)
            
            # Create a join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_circle_join_request_notification_email(join_request)
                
                assert result is True
                # Should be called twice (once for each admin)
                assert mock_send_email.call_count == 2
                
                # Check that both admins received emails
                call_args_list = mock_send_email.call_args_list
                sent_emails = {call[0][0] for call in call_args_list}  # Extract to_email from each call
                assert 'admin1@test.com' in sent_emails
                assert 'admin2@test.com' in sent_emails
                
                # Check email content for one of the calls
                call_args = call_args_list[0]
                to_email, subject, text_content, html_content = call_args[0]
                
                assert 'New Join Request for Test Circle' in subject
                assert 'Bob User' in text_content
                assert 'Test Circle' in text_content
                assert 'I would like to join this circle please!' in text_content
                assert html_content is not None

    def test_send_circle_join_request_notification_email_no_message(self, app):
        """Test sending email notification when join request has no message."""
        with app.app_context():
            # Create test users and circle
            admin = UserFactory(email='admin@test.com', first_name='John', last_name='Admin')
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.utcnow(),
                is_admin=True
            )
            db.session.execute(stmt)
            
            # Create a join request without message
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message=None,
                status='pending'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_circle_join_request_notification_email(join_request)
                
                assert result is True
                mock_send_email.assert_called_once()
                
                # Check email content
                call_args = mock_send_email.call_args
                to_email, subject, text_content, html_content = call_args[0]
                
                assert to_email == 'admin@test.com'
                assert 'New Join Request for Test Circle' in subject
                assert 'Bob User' in text_content
                # Should not contain message section when no message
                assert 'Request Message:' not in text_content

    def test_send_circle_join_request_notification_email_disabled_preference(self, app):
        """Test that email notification is skipped when admin has disabled preferences."""
        with app.app_context():
            # Create test users and circle
            admin = UserFactory(email='admin@test.com', first_name='John', last_name='Admin',
                              email_notifications_enabled=False)
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.utcnow(),
                is_admin=True
            )
            db.session.execute(stmt)
            
            # Create a join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_circle_join_request_notification_email(join_request)
                
                assert result is True  # Should return True even when skipped
                mock_send_email.assert_not_called()

    def test_send_circle_join_request_notification_email_no_admins(self, app):
        """Test handling when circle has no admins."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Create a join request but don't add any admins to circle
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_circle_join_request_notification_email(join_request)
                
                assert result is False
                mock_send_email.assert_not_called()

    def test_send_circle_join_request_notification_email_send_failure(self, app):
        """Test handling of email sending failure."""
        with app.app_context():
            # Create test users and circle
            admin = UserFactory(email='admin@test.com', first_name='John', last_name='Admin')
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.utcnow(),
                is_admin=True
            )
            db.session.execute(stmt)
            
            # Create a join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = False  # Simulate email sending failure
                
                result = send_circle_join_request_notification_email(join_request)
                
                assert result is False
                mock_send_email.assert_called_once()

    def test_send_circle_join_request_decision_email_approved(self, app):
        """Test sending email notification when join request is approved."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Create an approved join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='approved'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_circle_join_request_decision_email(join_request)
                
                assert result is True
                mock_send_email.assert_called_once()
                
                # Check email content
                call_args = mock_send_email.call_args
                to_email, subject, text_content, html_content = call_args[0]
                
                assert to_email == 'user@test.com'
                assert 'Join Request Approved for Test Circle' in subject
                assert 'approved' in text_content.lower()
                assert 'Test Circle' in text_content
                assert 'View Circle' in html_content

    def test_send_circle_join_request_decision_email_rejected(self, app):
        """Test sending email notification when join request is rejected."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Create a rejected join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='rejected'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_circle_join_request_decision_email(join_request)
                
                assert result is True
                mock_send_email.assert_called_once()
                
                # Check email content
                call_args = mock_send_email.call_args
                to_email, subject, text_content, html_content = call_args[0]
                
                assert to_email == 'user@test.com'
                assert 'Join Request Denied for Test Circle' in subject
                assert 'denied' in text_content.lower()
                assert 'Test Circle' in text_content
                assert 'search for other circles' in html_content.lower()

    def test_send_circle_join_request_decision_email_disabled_preference(self, app):
        """Test that email notification is skipped when user has disabled preferences."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User',
                                        email_notifications_enabled=False)
            circle = CircleFactory(name='Test Circle')
            
            # Create an approved join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='approved'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_circle_join_request_decision_email(join_request)
                
                assert result is True  # Should return True even when skipped
                mock_send_email.assert_not_called()

    def test_send_circle_join_request_decision_email_invalid_status(self, app):
        """Test handling of invalid join request status."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Create a join request with invalid status
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='invalid_status'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_circle_join_request_decision_email(join_request)
                
                assert result is False
                mock_send_email.assert_not_called()

    def test_send_circle_join_request_decision_email_send_failure(self, app):
        """Test handling of email sending failure during decision notification."""
        with app.app_context():
            # Create test users and circle
            requesting_user = UserFactory(email='user@test.com', first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Create an approved join request
            join_request = CircleJoinRequestFactory(
                circle=circle,
                user=requesting_user,
                message='I would like to join this circle please!',
                status='approved'
            )
            db.session.commit()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = False  # Simulate email sending failure
                
                result = send_circle_join_request_decision_email(join_request)
                
                assert result is False
                mock_send_email.assert_called_once()
