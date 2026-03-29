"""
Test that the conversation page only scrolls to bottom when there are unread messages.
"""
import pytest
from app import db
from app.models import Message
from tests.factories import UserFactory, ItemFactory, MessageFactory
from conftest import login_user


@pytest.mark.usefixtures('clean_db')
class TestConversationScrollBehavior:
    """Test the scroll behavior of the conversation page."""

    def test_has_unread_messages_flag_true_when_unread_messages_exist(self, client, app):
        """When there are unread messages, the has_unread_messages flag should be True."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)

            login_user(client, recipient.email)
            response = client.get(f'/message/{message.id}')

        assert b'scrollIntoView' in response.data
        assert response.data.count(b'scrollIntoView') == 1

    def test_has_unread_messages_flag_false_when_all_messages_read(self, client, app):
        """When all messages are read, the has_unread_messages flag should be False."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=True)

            login_user(client, recipient.email)
            response = client.get(f'/message/{message.id}')

        assert response.status_code == 200
        assert b'scrollIntoView' not in response.data

    def test_message_marked_as_read_after_viewing(self, client, app):
        """Messages should be marked as read after viewing the conversation."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            message_id = message.id

            assert db.session.get(Message, message_id).is_read is False

            login_user(client, recipient.email)
            response = client.get(f'/message/{message_id}')
            assert response.status_code == 200

            db.session.expire_all()
            assert db.session.get(Message, message_id).is_read is True

            # View again — should load without scrolling
            response = client.get(f'/message/{message_id}')
            assert response.status_code == 200
            assert b'scrollIntoView' not in response.data

    def test_sender_viewing_own_message_no_scroll(self, client, app):
        """When sender views their own message, no scroll should happen."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)

            login_user(client, sender.email)
            response = client.get(f'/message/{message.id}')

        assert response.status_code == 200
        assert b'scrollIntoView' not in response.data
