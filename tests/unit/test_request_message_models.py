"""Unit tests for request-linked message model behavior."""
import pytest
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Message
from tests.factories import UserFactory, ItemFactory, ItemRequestFactory


class TestRequestMessageModel:
    """Validate Message targeting constraints for items vs requests."""

    def test_message_can_target_item_request(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item_request = ItemRequestFactory(user=recipient)

            message = Message(
                sender_id=sender.id,
                recipient_id=recipient.id,
                item_id=None,
                request_id=item_request.id,
                body='I can help with this request.'
            )
            db.session.add(message)
            db.session.commit()

            assert message.id is not None
            assert message.request_id == item_request.id
            assert message.item_id is None
            assert message.is_request_message is True

    def test_message_can_target_item(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)

            message = Message(
                sender_id=sender.id,
                recipient_id=recipient.id,
                item_id=item.id,
                request_id=None,
                body='Is this item still available?'
            )
            db.session.add(message)
            db.session.commit()

            assert message.id is not None
            assert message.item_id == item.id
            assert message.request_id is None
            assert message.is_request_message is False

    def test_message_requires_exactly_one_target(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            item_request = ItemRequestFactory(user=recipient)

            invalid_both_null = Message(
                sender_id=sender.id,
                recipient_id=recipient.id,
                item_id=None,
                request_id=None,
                body='Invalid: no target.'
            )
            db.session.add(invalid_both_null)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            invalid_both_set = Message(
                sender_id=sender.id,
                recipient_id=recipient.id,
                item_id=item.id,
                request_id=item_request.id,
                body='Invalid: both targets.'
            )
            db.session.add(invalid_both_set)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
