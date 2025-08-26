import pytest
from unittest.mock import patch, MagicMock
from flask import url_for

from app.models import User, Item, Message
from app.utils.email import send_message_notification_email
from tests.factories import UserFactory, ItemFactory, MessageFactory


class TestMessageNotifications:
    """Test message email notification functionality."""

    def test_send_message_notification_email_regular_message(self, app):
        """Test sending email notification for a regular message."""
        with app.app_context():
            # Create test users and item
            sender = UserFactory(email='sender@test.com', first_name='John', last_name='Doe')
            recipient = UserFactory(email='recipient@test.com', first_name='Jane', last_name='Smith')
            item = ItemFactory(name='Test Item', owner=recipient)
            
            # Create a regular message
            message = MessageFactory(
                sender=sender,
                recipient=recipient, 
                item=item,
                body='Hi, I am interested in this item!'
            )
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_message_notification_email(message)
                
                assert result is True
                mock_send_email.assert_called_once()
                
                # Check the call arguments
                call_args = mock_send_email.call_args
                assert call_args[0][0] == 'recipient@test.com'  # to_email
                assert 'New Message about Test Item' in call_args[0][1]  # subject
                assert 'John Doe' in call_args[0][2]  # text content includes sender name
                assert 'Hi, I am interested in this item!' in call_args[0][2]  # text content includes message body
                assert call_args[0][3] is not None  # HTML content provided as 4th positional argument

    def test_send_message_notification_email_disabled_preference(self, app):
        """Test that email notification is skipped when user has disabled preferences."""
        with app.app_context():
            # Create test users and item
            sender = UserFactory(email='sender@test.com')
            recipient = UserFactory(email='recipient@test.com', email_notifications_enabled=False)
            item = ItemFactory(name='Test Item', owner=recipient)
            
            # Create a regular message
            message = MessageFactory(
                sender=sender,
                recipient=recipient, 
                item=item,
                body='Hi, I am interested in this item!'
            )
            
            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_message_notification_email(message)
                
                assert result is True  # Should return True (not an error)
                mock_send_email.assert_not_called()  # Email should not be sent

    def test_send_message_notification_email_loan_request(self, app):
        """Test sending email notification for a loan request message."""
        with app.app_context():
            from tests.factories import LoanRequestFactory
            
            # Create test users and item
            sender = UserFactory(email='borrower@test.com', first_name='John', last_name='Doe')
            recipient = UserFactory(email='owner@test.com', first_name='Jane', last_name='Smith')
            item = ItemFactory(name='Test Item', owner=recipient)
            
            # Create a loan request
            loan_request = LoanRequestFactory(
                item=item,
                borrower=sender,
                status='pending'
            )
            
            # Create a loan request message
            message = MessageFactory(
                sender=sender,
                recipient=recipient, 
                item=item,
                body='Can I borrow this item please?',
                loan_request=loan_request
            )
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                result = send_message_notification_email(message)
                
                assert result is True
                mock_send_email.assert_called_once()
                
                # Check the call arguments
                call_args = mock_send_email.call_args
                assert call_args[0][0] == 'owner@test.com'  # to_email
                assert 'New Loan Request for Test Item' in call_args[0][1]  # subject for pending loan request
                assert 'loan request' in call_args[0][2]  # text content indicates loan request

    def test_send_message_notification_email_missing_users(self, app):
        """Test handling of missing users."""
        with app.app_context():
            # Create a message with non-existent user IDs
            import uuid
            fake_message = MagicMock()
            fake_message.sender_id = uuid.uuid4()
            fake_message.recipient_id = uuid.uuid4()
            
            with patch('app.utils.email.send_email') as mock_send_email:
                with patch('app.models.User.query') as mock_query:
                    mock_query.get.return_value = None  # Simulate users not found
                    
                    result = send_message_notification_email(fake_message)
                    
                    assert result is False
                    mock_send_email.assert_not_called()

    def test_send_message_notification_email_failure(self, app):
        """Test handling of email sending failure."""
        with app.app_context():
            # Create test users and item
            sender = UserFactory(email='sender@test.com')
            recipient = UserFactory(email='recipient@test.com')
            item = ItemFactory(name='Test Item', owner=recipient)
            
            # Create a regular message
            message = MessageFactory(
                sender=sender,
                recipient=recipient, 
                item=item,
                body='Test message'
            )
            
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = False  # Simulate email failure
                
                result = send_message_notification_email(message)
                
                assert result is False
                mock_send_email.assert_called_once()
