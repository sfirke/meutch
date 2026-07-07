from unittest.mock import patch

import pytest

from app import db
from app.models import ConversationParticipant, Message
from app.services import message_service
from app.services.exceptions import AuthorizationError, InvalidActionError
from app.utils.messaging_queries import get_or_create_conversation
from tests.factories import (
    ConversationFactory,
    ConversationParticipantFactory,
    ItemFactory,
    ItemRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestMessageService:
    def test_create_message_persists_message_and_sends_email(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=recipient)
            conversation = get_or_create_conversation("item", item.id, sender.id, recipient.id)

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                message = message_service.create_message(
                    sender.id,
                    recipient.id,
                    "Interested in borrowing this.",
                    conversation_id=conversation.id,
                )

            db_message = db.session.get(Message, message.id)
            assert db_message is not None
            assert db_message.sender_id == sender.id
            assert db_message.recipient_id == recipient.id
            assert db_message.conversation.context_type == "item"
            assert db_message.conversation.context_id == item.id
            mock_email.assert_called_once_with(message)

    def test_reply_to_message_preserves_request_context(self, app):
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester)
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            message = MessageFactory(
                sender=helper,
                recipient=requester,
                conversation=conversation,
                body="I can help.",
            )

            with patch("app.services.message_service.send_message_notification_email"):
                reply = message_service.reply_to_message(
                    message,
                    requester.id,
                    "Thanks, messaging you now!",
                )

            assert reply.parent_id == message.id
            assert reply.conversation_id == message.conversation_id
            assert reply.conversation.context_type == "request"
            assert reply.conversation.context_id == item_request.id
            assert reply.sender_id == requester.id
            assert reply.recipient_id == helper.id

    def test_start_item_conversation_uses_item_owner_as_recipient(self, app):
        with app.app_context():
            owner = UserFactory()
            sender = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )

            with patch("app.services.message_service.send_message_notification_email"):
                message = message_service.start_item_conversation(
                    item,
                    sender,
                    "Interested in your giveaway.",
                )

            assert message.sender_id == sender.id
            assert message.recipient_id == owner.id
            assert message.conversation.context_type == "item"
            assert message.conversation.context_id == item.id

    def test_start_request_conversation_uses_request_owner_as_recipient(self, app):
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility="public")

            with patch("app.services.message_service.send_message_notification_email"):
                message = message_service.start_request_conversation(
                    item_request,
                    helper,
                    "I have something that could help.",
                )

            assert message.sender_id == helper.id
            assert message.recipient_id == requester.id
            assert message.conversation.context_type == "request"
            assert message.conversation.context_id == item_request.id

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

    def test_start_request_conversation_rejects_self_messaging(self, app):
        with app.app_context():
            requester = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility="public")

            with pytest.raises(InvalidActionError, match="own request"):
                message_service.start_request_conversation(
                    item_request,
                    requester,
                    "I can help myself",
                )

    def test_reply_to_message_rejects_non_participant(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            other_user = UserFactory()
            message = MessageFactory(sender=sender, recipient=recipient)

            with pytest.raises(AuthorizationError, match="reply to this message"):
                message_service.reply_to_message(message, other_user.id, "Hello")

    def test_get_conversation_thread_state_rejects_non_participant(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            other_user = UserFactory()
            item = ItemFactory(owner=recipient)
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(sender=sender, recipient=recipient, conversation=conversation)

            with pytest.raises(AuthorizationError):
                message_service.get_conversation_thread_state(message, other_user.id)

    def test_get_conversation_thread_state_marks_messages_read(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                is_read=False,
            )
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
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                is_read=False,
            )
            db.session.commit()

            thread_state = message_service.get_conversation_thread_state(
                message,
                recipient.id,
                mark_read=False,
            )

            assert thread_state["has_unread_messages"] is True
            db.session.expire_all()
            assert db.session.get(Message, message.id).is_read is False

    def test_mark_message_thread_read_marks_messages(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(owner=sender, is_giveaway=True, claim_status="unclaimed")
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            second_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            read_result = message_service.mark_message_thread_read(first_message, recipient.id)

            assert read_result == {
                "has_unread_messages": False,
            }
            db.session.expire_all()
            assert db.session.get(Message, first_message.id).is_read is True
            assert db.session.get(Message, second_message.id).is_read is True


class TestArchiveService:
    def test_archive_conversation_sets_archive_flag(self, app):
        with app.app_context():
            user = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=user)
            db.session.commit()

            message_service.archive_conversation(user.id, conversation.id)

            participant = ConversationParticipant.query.filter_by(
                conversation_id=conversation.id, user_id=user.id
            ).first()
            assert participant.is_archived is True
            assert participant.archived_at is not None

    def test_unarchive_conversation_clears_archive_flag(self, app):
        with app.app_context():
            user = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=user, is_archived=True)
            db.session.commit()

            message_service.unarchive_conversation(user.id, conversation.id)

            participant = ConversationParticipant.query.filter_by(
                conversation_id=conversation.id, user_id=user.id
            ).first()
            assert participant.is_archived is False
            assert participant.archived_at is None

    def test_bulk_archive_archives_multiple_conversations(self, app):
        with app.app_context():
            user = UserFactory()
            conv1 = ConversationFactory()
            conv2 = ConversationFactory()
            ConversationParticipantFactory(conversation=conv1, user=user)
            ConversationParticipantFactory(conversation=conv2, user=user)
            db.session.commit()

            message_service.bulk_archive(user.id, [conv1.id, conv2.id])

            p1 = ConversationParticipant.query.filter_by(
                conversation_id=conv1.id, user_id=user.id
            ).first()
            p2 = ConversationParticipant.query.filter_by(
                conversation_id=conv2.id, user_id=user.id
            ).first()
            assert p1.is_archived is True
            assert p2.is_archived is True

    def test_bulk_mark_read_marks_unread_messages(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conv1 = ConversationFactory()
            conv2 = ConversationFactory()
            ConversationParticipantFactory(conversation=conv1, user=recipient)
            ConversationParticipantFactory(conversation=conv2, user=recipient)
            msg1 = MessageFactory(
                sender=sender, recipient=recipient, conversation=conv1, is_read=False
            )
            msg2 = MessageFactory(
                sender=sender, recipient=recipient, conversation=conv2, is_read=False
            )
            db.session.commit()

            message_service.bulk_mark_read(recipient.id, [conv1.id, conv2.id])

            db.session.expire_all()
            assert db.session.get(Message, msg1.id).is_read is True
            assert db.session.get(Message, msg2.id).is_read is True

    def test_mark_all_read_in_view_scoped_to_inbox(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            inbox_conv = ConversationFactory()
            archived_conv = ConversationFactory()
            ConversationParticipantFactory(conversation=inbox_conv, user=recipient)
            ConversationParticipantFactory(
                conversation=archived_conv, user=recipient, is_archived=True
            )
            inbox_msg = MessageFactory(
                sender=sender, recipient=recipient, conversation=inbox_conv, is_read=False
            )
            archived_msg = MessageFactory(
                sender=sender, recipient=recipient, conversation=archived_conv, is_read=False
            )
            db.session.commit()

            message_service.mark_all_read_in_view(recipient.id, status="inbox")

            db.session.expire_all()
            assert db.session.get(Message, inbox_msg.id).is_read is True
            # Archived messages should NOT be affected
            assert db.session.get(Message, archived_msg.id).is_read is False

    def test_mark_all_read_in_view_scoped_to_archived(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            inbox_conv = ConversationFactory()
            archived_conv = ConversationFactory()
            ConversationParticipantFactory(conversation=inbox_conv, user=recipient)
            ConversationParticipantFactory(
                conversation=archived_conv, user=recipient, is_archived=True
            )
            inbox_msg = MessageFactory(
                sender=sender, recipient=recipient, conversation=inbox_conv, is_read=False
            )
            archived_msg = MessageFactory(
                sender=sender, recipient=recipient, conversation=archived_conv, is_read=False
            )
            db.session.commit()

            message_service.mark_all_read_in_view(recipient.id, status="archived")

            db.session.expire_all()
            # Inbox messages should NOT be affected
            assert db.session.get(Message, inbox_msg.id).is_read is False
            assert db.session.get(Message, archived_msg.id).is_read is True

    def test_auto_unarchive_on_new_message(self, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(
                conversation=conversation, user=recipient, is_archived=True
            )
            db.session.commit()

            with patch("app.services.message_service.send_message_notification_email"):
                message_service.create_message(
                    sender.id,
                    recipient.id,
                    "Hey, replying to archived thread",
                    conversation_id=conversation.id,
                )

            participant = ConversationParticipant.query.filter_by(
                conversation_id=conversation.id, user_id=recipient.id
            ).first()
            assert participant.is_archived is False
            assert participant.archived_at is None
