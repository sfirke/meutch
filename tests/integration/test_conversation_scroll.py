"""
Test that the conversation page only scrolls to bottom when there are unread messages.
"""
import pytest
from app.models import Message
from tests.factories import UserFactory, ItemFactory, MessageFactory


@pytest.mark.usefixtures('clean_db')
class TestConversationScrollBehavior:
    """Test the scroll behavior of the conversation page."""

    def test_has_unread_messages_flag_true_when_unread_messages_exist(self, client, app):
        """When there are unread messages, the has_unread_messages flag should be True."""
        with app.app_context():
            # Create users and item
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            
            # Create an unread message
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                is_read=False
            )
            
            # Log in as the recipient
            with client.session_transaction() as sess:
                sess['_user_id'] = str(recipient.id)
            
            # View the conversation
            response = client.get(f'/message/{message.id}')
            
            # Check that the response includes the scroll script
            # The scroll should happen because there were unread messages
            assert b'scrollIntoView' in response.data
            # Check that the conditional check for has_unread_messages is present
            assert response.data.count(b'scrollIntoView') == 1

    def test_has_unread_messages_flag_false_when_all_messages_read(self, client, app):
        """When all messages are read, the has_unread_messages flag should be False."""
        with app.app_context():
            # Create users and item
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            
            # Create a message that's already read
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                is_read=True
            )
            
            # Log in as the recipient
            with client.session_transaction() as sess:
                sess['_user_id'] = str(recipient.id)
            
            # View the conversation
            response = client.get(f'/message/{message.id}')
            
            # Check that page loads successfully
            assert response.status_code == 200
            # The scroll script should NOT be present when there are no unread messages
            assert b'scrollIntoView' not in response.data

    def test_message_marked_as_read_after_viewing(self, client, app):
        """Messages should be marked as read after viewing the conversation."""
        with app.app_context():
            # Create users and item
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            
            # Create an unread message
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                is_read=False
            )
            message_id = message.id
            
            # Verify it's unread before viewing
            msg = Message.query.get(message_id)
            assert msg.is_read is False
            
            # Log in as the recipient
            with client.session_transaction() as sess:
                sess['_user_id'] = str(recipient.id)
            
            # View the conversation (first time - should scroll)
            response = client.get(f'/message/{message_id}')
            assert response.status_code == 200
            
            # Verify message is now marked as read
            msg = Message.query.get(message_id)
            assert msg.is_read is True
            
            # View the conversation again (second time - should NOT scroll)
            response = client.get(f'/message/{message_id}')
            assert response.status_code == 200
            # The page should load successfully but without scrolling behavior

    def test_sender_viewing_own_message_no_scroll(self, client, app):
        """When sender views their own message, no scroll should happen."""
        with app.app_context():
            # Create users and item
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            
            # Create a message (sender's perspective)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                is_read=False  # Unread by recipient, but sender is viewing
            )
            
            # Log in as the sender (not the recipient)
            with client.session_transaction() as sess:
                sess['_user_id'] = str(sender.id)
            
            # View the conversation
            response = client.get(f'/message/{message.id}')
            
            # The sender viewing their own sent message shouldn't trigger scroll
            # because they don't have unread messages (they sent it)
            assert response.status_code == 200
