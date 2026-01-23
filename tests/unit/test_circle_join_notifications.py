"""Tests for circle join request email notifications."""

import pytest
from unittest.mock import patch
from tests.factories import UserFactory, CircleFactory, CircleJoinRequestFactory
from app.utils.email import send_circle_join_request_notification_email, send_circle_join_request_decision_email
from app.models import db, circle_members
from sqlalchemy import and_
from datetime import datetime, UTC


class TestCircleJoinRequestNotifications:
    """Test circle join request email notification functionality."""

    def test_send_circle_join_request_notification_email_no_message(self, app):
        """Test sending email notification when join request has no message."""
        with app.app_context():
            # Create test users and circle - use factory-generated unique emails
            admin = UserFactory(first_name='John', last_name='Admin')
            requesting_user = UserFactory(first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
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
                
                assert to_email == admin.email  # Use the actual admin email
                assert 'New Join Request for Test Circle' in subject
                assert 'Bob User' in text_content
                # Should not contain message section when no message
                assert 'Request Message:' not in text_content

    def test_send_circle_join_request_notification_email_no_admins(self, app):
        """Test handling when circle has no admins."""
        with app.app_context():
            # Create test users and circle - use factory-generated unique emails
            requesting_user = UserFactory(first_name='Bob', last_name='User')
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
            # Create test users and circle - use factory-generated unique emails
            admin = UserFactory(first_name='John', last_name='Admin')
            requesting_user = UserFactory(first_name='Bob', last_name='User')
            circle = CircleFactory(name='Test Circle')
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
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


    def test_send_circle_join_request_decision_email_invalid_status(self, app):
        """Test handling of invalid join request status."""
        with app.app_context():
            # Create test users and circle - use factory-generated unique emails
            requesting_user = UserFactory(first_name='Bob', last_name='User')
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
            # Create test users and circle - use factory-generated unique emails
            requesting_user = UserFactory(first_name='Bob', last_name='User')
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
