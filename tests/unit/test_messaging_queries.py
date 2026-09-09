from datetime import UTC, datetime, timedelta

from app import db
from app.utils.messaging_queries import (
    build_conversation_thread_state,
    build_inbox_summaries,
    build_request_conversation_summaries,
    filter_by_archive_status,
    find_context_conversation,
    get_conversation_thread_state,
    sort_conversation_summaries,
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


# ── Sort & filter helpers ──────────────────────────────────────────────


def _make_summary(conversation_id, other_user, timestamp, unread_count=0, is_archived=False):
    """Build a minimal summary dict for sort/filter tests."""
    return {
        "conversation_id": conversation_id,
        "other_user": other_user,
        "latest_message": type("FakeMsg", (), {"timestamp": timestamp})(),
        "unread_count": unread_count,
        "is_archived": is_archived,
        "item": None,
        "item_request": None,
        "circle": None,
    }


class TestSortConversationSummaries:
    def test_default_is_newest_order(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            summaries = [
                _make_summary("c1", None, now - timedelta(minutes=1)),
                _make_summary("c2", None, now - timedelta(minutes=2)),
                _make_summary("c3", None, now - timedelta(minutes=3)),
            ]
            sorted_summaries = sort_conversation_summaries(summaries, "newest")
            # Preserves input order (already DESC from query)
            assert [s["conversation_id"] for s in sorted_summaries] == ["c1", "c2", "c3"]

    def test_oldest_order(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            summaries = [
                _make_summary("c1", None, now - timedelta(minutes=1)),
                _make_summary("c2", None, now - timedelta(minutes=2)),
                _make_summary("c3", None, now - timedelta(minutes=3)),
            ]
            sorted_summaries = sort_conversation_summaries(summaries, "oldest")
            assert [s["conversation_id"] for s in sorted_summaries] == ["c3", "c2", "c1"]

    def test_unread_first_order(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            summaries = [
                _make_summary("c1", None, now, unread_count=2),
                _make_summary("c2", None, now - timedelta(minutes=1), unread_count=5),
                _make_summary("c3", None, now, unread_count=0),
            ]
            sorted_summaries = sort_conversation_summaries(summaries, "unread")
            # Unread first (c1, c2), then read (c3).
            # Within unread group: newest first (c1 > c2).
            assert [s["conversation_id"] for s in sorted_summaries] == ["c1", "c2", "c3"]

    def test_name_asc_order(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            alice = type("FakeUser", (), {"first_name": "Alice", "last_name": "Zeta"})()
            bob = type("FakeUser", (), {"first_name": "Bob", "last_name": "Alpha"})()
            carol = type("FakeUser", (), {"first_name": "Carol", "last_name": "Beta"})()
            summaries = [
                _make_summary("c1", alice, now),
                _make_summary("c2", bob, now),
                _make_summary("c3", carol, now),
            ]
            sorted_summaries = sort_conversation_summaries(summaries, "name_asc")
            assert [s["conversation_id"] for s in sorted_summaries] == ["c1", "c2", "c3"]


class TestFilterByArchiveStatus:
    def test_inbox_excludes_archived(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            summaries = [
                _make_summary("c1", None, now, is_archived=False),
                _make_summary("c2", None, now, is_archived=True),
                _make_summary("c3", None, now, is_archived=False),
            ]
            filtered = filter_by_archive_status(summaries, "inbox")
            assert [s["conversation_id"] for s in filtered] == ["c1", "c3"]

    def test_archived_only_shows_archived(self, app):
        with app.app_context():
            now = datetime.now(UTC)
            summaries = [
                _make_summary("c1", None, now, is_archived=False),
                _make_summary("c2", None, now, is_archived=True),
                _make_summary("c3", None, now, is_archived=False),
            ]
            filtered = filter_by_archive_status(summaries, "archived")
            assert [s["conversation_id"] for s in filtered] == ["c2"]
