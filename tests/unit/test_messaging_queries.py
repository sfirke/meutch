from datetime import UTC, datetime, timedelta

from app import db
from app.utils.messaging_queries import (
    build_conversation_thread_state,
    build_inbox_summaries,
    build_request_conversation_summaries,
    find_context_conversation,
    get_conversation_thread_state,
)
from tests.factories import (
    ConversationFactory,
    ItemFactory,
    ItemRequestFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)


def test_build_inbox_summaries_groups_request_thread_and_counts_unread(app):
    with app.app_context():
        requester = UserFactory()
        helper = UserFactory()
        item_request = ItemRequestFactory(user=requester)
        conversation = ConversationFactory(context_type="request", context_id=item_request.id)
        older_message = MessageFactory(
            sender=requester,
            recipient=helper,
            conversation=conversation,
            is_read=True,
        )
        newer_message = MessageFactory(
            sender=helper,
            recipient=requester,
            conversation=conversation,
            is_read=False,
        )
        older_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
        newer_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
        db.session.commit()

        summaries = build_inbox_summaries(requester.id)

        assert len(summaries) == 1
        assert summaries[0]["latest_message"].id == newer_message.id
        assert summaries[0]["item_request"].id == item_request.id
        assert summaries[0]["unread_count"] == 1


def test_get_conversation_thread_state_marks_non_pending_messages_read(app):
    with app.app_context():
        sender = UserFactory()
        recipient = UserFactory()
        item = ItemFactory(owner=sender)
        conversation = ConversationFactory(context_type="item", context_id=item.id)
        first_message = MessageFactory(
            sender=sender, recipient=recipient, conversation=conversation, is_read=False
        )
        second_message = MessageFactory(
            sender=recipient, recipient=sender, conversation=conversation, is_read=True
        )
        db.session.commit()

        thread_state = get_conversation_thread_state(first_message, recipient.id)

        assert thread_state["has_unread_messages"] is True
        assert [message.id for message in thread_state["thread_messages"]] == [
            first_message.id,
            second_message.id,
        ]

        db.session.expire_all()
        assert db.session.get(type(first_message), first_message.id).is_read is True


def test_build_conversation_thread_state_does_not_mark_messages_read(app):
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

        thread_state = build_conversation_thread_state(message, recipient.id)

        assert thread_state["has_unread_messages"] is True

        db.session.expire_all()
        assert db.session.get(type(message), message.id).is_read is False


def test_get_conversation_thread_state_skips_pending_loan_messages(app):
    with app.app_context():
        owner = UserFactory()
        borrower = UserFactory()
        item = ItemFactory(owner=owner)
        loan_request = LoanRequestFactory(item=item, borrower=borrower, status="pending")
        conversation = ConversationFactory(context_type="item", context_id=item.id)
        message = MessageFactory(
            sender=owner,
            recipient=borrower,
            conversation=conversation,
            loan_request=loan_request,
            is_read=False,
        )
        db.session.commit()

        thread_state = get_conversation_thread_state(message, borrower.id)

        assert thread_state["has_unread_messages"] is False

        db.session.expire_all()
        assert db.session.get(type(message), message.id).is_read is False


def test_request_conversation_helpers_group_and_find_existing_thread(app):
    with app.app_context():
        requester = UserFactory()
        helper = UserFactory()
        item_request = ItemRequestFactory(user=requester)
        conversation = ConversationFactory(context_type="request", context_id=item_request.id)
        first_message = MessageFactory(
            sender=helper,
            recipient=requester,
            conversation=conversation,
        )
        reply_message = MessageFactory(
            sender=requester,
            recipient=helper,
            conversation=conversation,
        )
        first_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
        reply_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
        db.session.commit()

        conversations = build_request_conversation_summaries(item_request.id, requester.id)
        existing_conv = find_context_conversation(
            "request",
            item_request.id,
            helper.id,
            requester.id,
        )

        assert len(conversations) == 1
        assert conversations[0]["latest_message"].id == reply_message.id
        assert existing_conv is not None
        assert existing_conv.id == first_message.conversation_id
