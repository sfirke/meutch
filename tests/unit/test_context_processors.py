"""Test context processors functionality."""

import pytest
from unittest.mock import patch, MagicMock
from app.context_processors import inject_unread_messages_count, inject_distance_utils
from tests.factories import (
    UserFactory,
    MessageFactory,
    ItemFactory,
    LoanRequestFactory,
    CircleFactory,
    CircleJoinRequestFactory,
)
from app.models import circle_members, db


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

    def test_inject_unread_messages_count_includes_pending_circle_requests_for_admin(self, app):
        """Admins should see pending circle join requests counted."""
        with app.app_context():
            admin = UserFactory()
            requester1 = UserFactory()
            requester2 = UserFactory()
            circle = CircleFactory(requires_approval=True)

            # Make admin an admin member of the circle
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id, circle_id=circle.id, is_admin=True
                )
            )
            db.session.commit()

            # Two pending join requests to that circle
            CircleJoinRequestFactory(circle=circle, user=requester1, status='pending')
            CircleJoinRequestFactory(circle=circle, user=requester2, status='pending')

            # One non-pending should not count
            CircleJoinRequestFactory(circle=circle, user=UserFactory(), status='approved')

            with patch('app.context_processors.current_user', admin):
                result = inject_unread_messages_count()
                assert result == {'unread_messages_count': 2}

    def test_inject_unread_messages_count_excludes_circle_requests_for_non_admin(self, app):
        """Non-admin members should not see pending join requests counted."""
        with app.app_context():
            member = UserFactory()
            requester = UserFactory()
            circle = CircleFactory(requires_approval=True)

            # Add as non-admin member
            db.session.execute(
                circle_members.insert().values(
                    user_id=member.id, circle_id=circle.id, is_admin=False
                )
            )
            db.session.commit()

            CircleJoinRequestFactory(circle=circle, user=requester, status='pending')

            with patch('app.context_processors.current_user', member):
                result = inject_unread_messages_count()
                assert result == {'unread_messages_count': 0}

    def test_inject_unread_messages_count_no_membership(self, app):
        """Users with no admin circle membership should not have pending join count."""
        with app.app_context():
            user = UserFactory()
            circle = CircleFactory(requires_approval=True)
            CircleJoinRequestFactory(circle=circle, user=UserFactory(), status='pending')

            with patch('app.context_processors.current_user', user):
                result = inject_unread_messages_count()
                assert result == {'unread_messages_count': 0}


class TestDistanceUtils:
    """Test distance utilities context processor."""

    def test_inject_distance_utils_returns_function(self, app):
        """Test that inject_distance_utils returns the expected function."""
        with app.app_context():
            result = inject_distance_utils()
            
            assert 'get_distance_to_item' in result
            assert callable(result['get_distance_to_item'])

    def test_get_distance_to_item_success(self, app):
        """Test successful distance calculation between user and item owner."""
        with app.app_context():
            # Create users with known coordinates
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
            borrower = UserFactory(latitude=34.0522, longitude=-118.2437)  # LA
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                
                # Should return formatted distance string
                assert result is not None
                assert 'mi' in result
                # Distance between NYC and LA should be ~2400-2500 miles
                # Extract numeric value to check range
                distance_str = result.replace(' mi', '')
                distance_num = float(distance_str)
                assert 2400 <= distance_num <= 2500

    def test_get_distance_to_item_no_current_user(self, app):
        """Test distance calculation when current_user is not available."""
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner)
            
            # Mock current_user without is_authenticated attribute
            mock_user = MagicMock()
            delattr(mock_user, 'is_authenticated')
            
            with patch('app.context_processors.current_user', mock_user):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_user_not_authenticated(self, app):
        """Test distance calculation when user is not authenticated."""
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner)
            
            mock_user = MagicMock()
            mock_user.is_authenticated = False
            
            with patch('app.context_processors.current_user', mock_user):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_user_not_geocoded(self, app):
        """Test distance calculation when current user is not geocoded."""
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory(latitude=None, longitude=None)
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_no_owner(self, app):
        """Test distance calculation when item has no owner."""
        with app.app_context():
            borrower = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            # Create a mock item without owner to test the context processor logic
            from unittest.mock import MagicMock
            item = MagicMock()
            item.owner = None
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_owner_not_geocoded(self, app):
        """Test distance calculation when item owner is not geocoded."""
        with app.app_context():
            owner = UserFactory(latitude=None, longitude=None)
            borrower = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_same_location(self, app):
        """Test distance calculation when users are at same location."""
        with app.app_context():
            coords = (40.7128, -74.0060)
            owner = UserFactory(latitude=coords[0], longitude=coords[1])
            borrower = UserFactory(latitude=coords[0], longitude=coords[1])
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                
                # Should return very small distance
                assert result is not None
                assert '< 0.1 mi' == result

    def test_get_distance_to_item_nearby_location(self, app):
        """Test distance calculation for nearby locations."""
        with app.app_context():
            # Times Square and Central Park (close locations in NYC)
            owner = UserFactory(latitude=40.7580, longitude=-73.9855)
            borrower = UserFactory(latitude=40.7829, longitude=-73.9654)
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                
                # Should return small distance (under 3 miles)
                assert result is not None
                assert 'mi' in result
                # Extract numeric part and verify it's reasonable
                distance_num = float(result.replace(' mi', ''))
                assert 0.1 <= distance_num <= 3.0

    def test_get_distance_to_item_exception_handling(self, app):
        """Test that exceptions are handled gracefully."""
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner)
            
            # Create a user that will cause an exception in distance_to method
            mock_user = MagicMock()
            mock_user.is_authenticated = True
            mock_user.is_geocoded = True
            mock_user.distance_to.side_effect = Exception("Calculation error")
            
            with patch('app.context_processors.current_user', mock_user):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None

    def test_get_distance_to_item_format_distance_none(self, app):
        """Test when distance_to returns None."""
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory(latitude=34.0522, longitude=-118.2437)
            item = ItemFactory(owner=owner)
            
            with patch('app.context_processors.current_user', borrower):
                with patch.object(borrower, 'distance_to', return_value=None):
                    context = inject_distance_utils()
                    get_distance = context['get_distance_to_item']
                    
                    result = get_distance(item)
                    assert result is None

    def test_get_distance_to_item_missing_attributes(self, app):
        """Test handling of missing attributes on objects."""
        with app.app_context():
            borrower = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            # Create item without proper owner attribute
            item = MagicMock()
            delattr(item, 'owner')
            
            with patch('app.context_processors.current_user', borrower):
                context = inject_distance_utils()
                get_distance = context['get_distance_to_item']
                
                result = get_distance(item)
                assert result is None
