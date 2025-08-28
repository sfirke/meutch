"""Test context processors functionality."""

import pytest
from unittest.mock import patch, MagicMock
from app.context_processors import inject_unread_messages_count
from tests.factories import UserFactory, MessageFactory, ItemFactory, LoanRequestFactory


class TestUnreadMessagesCount:
    """Test unread messages count context processor."""

    def test_inject_unread_messages_count_anonymous(self, app):
        """Test that anonymous users get zero unread messages."""
        with app.app_context():
            with patch('app.context_processors.current_user') as mock_user:
                mock_user.is_authenticated = False
                
                result = inject_unread_messages_count()
                
                assert result == {'unread_messages_count': 0}

    def test_inject_unread_messages_count_no_messages(self, app):
        """Test authenticated user with no messages."""
        with app.app_context():
            user = UserFactory()
            
            with patch('app.context_processors.current_user', user):
                result = inject_unread_messages_count()
                
                assert result == {'unread_messages_count': 0}

    def test_inject_unread_messages_count_regular_messages(self, app):
        """Test counting regular unread messages."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            
            # Create regular unread messages
            MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            
            # Create read message (should not be counted)
            MessageFactory(sender=sender, recipient=recipient, item=item, is_read=True)
            
            with patch('app.context_processors.current_user', recipient):
                result = inject_unread_messages_count()
                
                assert result == {'unread_messages_count': 2}

    def test_inject_unread_messages_count_loan_request_messages(self, app):
        """Test counting loan request related messages."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            
            # Create loan request
            loan_request = LoanRequestFactory(item=item, borrower=sender, status='pending')
            
            # Create loan request message (initial request)
            MessageFactory(
                sender=sender, 
                recipient=recipient, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            # Create loan approval message
            loan_request.status = 'approved'
            MessageFactory(
                sender=recipient, 
                recipient=sender, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            # Test recipient sees the initial request
            with patch('app.context_processors.current_user', recipient):
                result = inject_unread_messages_count()
                assert result == {'unread_messages_count': 1}
            
            # Test sender sees the approval
            with patch('app.context_processors.current_user', sender):
                result = inject_unread_messages_count()
                assert result == {'unread_messages_count': 1}

    def test_inject_unread_messages_count_mixed_messages(self, app):
        """Test counting mixed regular and loan request messages."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            
            # Create regular message
            MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            
            # Create loan request
            loan_request = LoanRequestFactory(item=item, borrower=sender, status='pending')
            
            # Create loan request message
            MessageFactory(
                sender=sender, 
                recipient=recipient, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            # Create loan approval message  
            loan_request.status = 'approved'
            MessageFactory(
                sender=recipient, 
                recipient=sender, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            with patch('app.context_processors.current_user', recipient):
                result = inject_unread_messages_count()
                # Should count both regular message and loan request message
                assert result == {'unread_messages_count': 2}

    def test_inject_unread_messages_count_excludes_self_sent(self, app):
        """Test that self-sent messages are excluded from count."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            
            # Create self-sent message (should not be counted)
            MessageFactory(sender=user, recipient=user, item=item, is_read=False)
            
            with patch('app.context_processors.current_user', user):
                result = inject_unread_messages_count()
                
                assert result == {'unread_messages_count': 0}

    def test_unread_count_consistency_with_conversation_view(self, app):
        """Test that context processor count matches conversation view logic."""
        with app.app_context():
            from app.models import Message
            
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            
            # Create various types of messages
            # Regular message
            MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            
            # Loan request
            loan_request = LoanRequestFactory(item=item, borrower=sender, status='pending')
            MessageFactory(
                sender=sender, 
                recipient=recipient, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            # Loan approval
            loan_request.status = 'approved'
            MessageFactory(
                sender=recipient, 
                recipient=sender, 
                item=item, 
                is_read=False,
                loan_request=loan_request
            )
            
            # Test context processor count
            with patch('app.context_processors.current_user', recipient):
                context_result = inject_unread_messages_count()
                context_count = context_result['unread_messages_count']
            
            # Test conversation view logic (from main/routes.py)
            conversation_count = Message.query.filter(
                Message.recipient_id == recipient.id,
                Message.is_read == False,
                Message.sender_id != recipient.id
            ).count()
            
            # Both counts should be identical
            assert context_count == conversation_count == 2
