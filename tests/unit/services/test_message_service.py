from unittest.mock import patch

import pytest

from app import db
from app.models import Message
from app.services import message_service
from app.services.exceptions import AuthorizationError, InvalidActionError
from tests.factories import ItemFactory, ItemRequestFactory, MessageFactory, UserFactory


class TestMessageService:
    def test_create_message_persists_message_and_sends_email(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                message = message_service.create_message(
                    sender.id,
                    recipient.id,
                    "Interested in borrowing this.",
                    item_id=item.id,
                )

            db_message = db.session.get(Message, message.id)
            assert db_message is not None
            assert db_message.sender_id == sender.id
            assert db_message.recipient_id == recipient.id
            assert db_message.item_id == item.id
            assert db_message.request_id is None
            mock_email.assert_called_once_with(message)

    def test_reply_to_message_preserves_request_context(self, app):
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester)
            message = MessageFactory(
                sender=helper,
                recipient=requester,
                item=None,
                request=item_request,
                body="I can help.",
            )

            with patch("app.services.message_service.send_message_notification_email"):
                reply = message_service.reply_to_message(
                    message,
                    requester.id,
                    "Thanks, messaging you now!",
                )

            assert reply.parent_id == message.id
            assert reply.request_id == item_request.id
            assert reply.item_id is None
            assert reply.circle_id is None
            assert reply.sender_id == requester.id
            assert reply.recipient_id == helper.id

    def test_start_item_conversation_rejects_self_messaging(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(owner=owner)

            with pytest.raises(InvalidActionError, match="own item"):
                message_service.start_item_conversation(item, owner, "Checking in")

    def test_start_item_conversation_rejects_invisible_item(self, app):
        with app.app_context():
            owner = UserFactory()
            viewer = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False)

            with pytest.raises(AuthorizationError, match="message the owner about this item"):
                message_service.start_item_conversation(item, viewer, "I can pick this up")

    def test_start_request_conversation_rejects_invisible_request(self, app):
        with app.app_context():
            owner = UserFactory()
            viewer = UserFactory()
            item_request = ItemRequestFactory(user=owner, visibility="circles")

            with pytest.raises(AuthorizationError, match="message this request owner"):
                message_service.start_request_conversation(
                    item_request,
                    viewer,
                    "I can help",
                )

    def test_get_conversation_thread_state_rejects_non_participant(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            other_user = UserFactory()
            item = ItemFactory(owner=recipient)
            message = MessageFactory(sender=sender, recipient=recipient, item=item)

            with pytest.raises(AuthorizationError):
                message_service.get_conversation_thread_state(message, other_user.id)

    def test_get_conversation_thread_state_marks_messages_read(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            db.session.commit()

            thread_state = message_service.get_conversation_thread_state(message, recipient.id)

            assert thread_state["has_unread_messages"] is True
            db.session.expire_all()
            assert db.session.get(Message, message.id).is_read is True

    def test_get_conversation_thread_state_can_skip_mark_read(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(sender=sender, recipient=recipient, item=item, is_read=False)
            db.session.commit()

            thread_state = message_service.get_conversation_thread_state(
                message,
                recipient.id,
                mark_read=False,
            )

            assert thread_state["has_unread_messages"] is True
            db.session.expire_all()
            assert db.session.get(Message, message.id).is_read is False
