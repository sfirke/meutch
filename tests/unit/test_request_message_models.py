"""Unit tests for conversation-linked message model behavior."""

import pytest

from app import db
from app.models import Message
from tests.factories import (
    ConversationFactory,
    ItemFactory,
    ItemRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestConversationMessageModel:
    """Validate Message context is determined by its Conversation."""

    def test_message_context_is_request(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item_request = ItemRequestFactory(user=recipient)
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)

            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="I can help with this request.",
            )

            assert message.id is not None
            assert message.conversation.context_type == "request"
            assert message.conversation.context_id == item_request.id
            assert message.is_request_message is True

    def test_message_context_is_item(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            conversation = ConversationFactory(context_type="item", context_id=item.id)

            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Is this item still available?",
            )

            assert message.id is not None
            assert message.conversation.context_type == "item"
            assert message.conversation.context_id == item.id
            assert message.is_request_message is False

    def test_message_conversation_is_required(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()

            from sqlalchemy.exc import IntegrityError

            with pytest.raises(IntegrityError):
                message = Message(
                    sender_id=sender.id,
                    recipient_id=recipient.id,
                    body="Missing conversation.",
                )
                db.session.add(message)
                db.session.commit()
