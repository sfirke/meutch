"""Integration tests for API messaging reads and writes."""

from datetime import UTC, datetime, timedelta

import pytest

from app import db
from app.models import ConversationParticipant, Message
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    ItemFactory,
    ItemRequestFactory,
    MessageFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


class TestApiMessaging:
    """Exercise inbox summary and thread read/write behavior."""

    def test_messages_list_returns_unread_count_and_request_context(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, title="Need a melon baller")
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
                body="I have one you can borrow.",
                is_read=False,
            )
            older_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
            newer_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()
            access_token = login_api_user(client, requester.email)

        response = client.get(
            "/api/v1/messages?page=1&per_page=10",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["pagination"]["total"] == 1
        assert payload["conversations"][0]["unread_count"] == 1
        assert payload["conversations"][0]["item_request"]["title"] == "Need a melon baller"

    def test_message_thread_returns_history_without_marking_read(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory(email_confirmed=True)
            shared_circle = CircleFactory()
            shared_circle.members.extend([sender, recipient])
            item = ItemFactory(owner=sender, name="Thread item")
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Checking whether you still need this.",
                is_read=False,
            )
            second_message = MessageFactory(
                sender=recipient,
                recipient=sender,
                conversation=conversation,
                body="Yes, I do.",
                is_read=True,
            )
            first_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
            second_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()
            access_token = login_api_user(client, recipient.email)
            message_id = first_message.id
            shared_circle_id = str(shared_circle.id)

        response = client.get(
            f"/api/v1/messages/{message_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["has_unread_messages"] is True
        assert len(payload["messages"]) == 2
        assert payload["shared_circles"][0]["id"] == shared_circle_id

        with app.app_context():
            db.session.expire_all()
            assert db.session.get(Message, message_id).is_read is False

    def test_message_thread_returns_403_for_non_participant(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            viewer = UserFactory(email_confirmed=True)
            message = MessageFactory(sender=sender, recipient=recipient)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            message_id = message.id

        response = client.get(
            f"/api/v1/messages/{message_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_item_conversation_start_derives_recipient_from_item_owner(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            sender = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, sender.email)
            item_id = item.id
            owner_id = str(owner.id)
            sender_id = str(sender.id)

        response = client.post(
            "/api/v1/messages",
            json={
                "body": "Interested in borrowing this.",
                "item_id": str(item_id),
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["message"]["sender"]["id"] == sender_id
        assert payload["message"]["recipient"]["id"] == owner_id

    def test_request_conversation_start_derives_recipient_from_request_owner(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            helper = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=requester, visibility="public")
            db.session.commit()
            access_token = login_api_user(client, helper.email)
            request_id = item_request.id
            requester_id = str(requester.id)
            helper_id = str(helper.id)

        response = client.post(
            "/api/v1/messages",
            json={
                "body": "I might have one you can use.",
                "request_id": str(request_id),
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["message"]["sender"]["id"] == helper_id
        assert payload["message"]["recipient"]["id"] == requester_id

    def test_item_conversation_start_rejects_self_messaging(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.post(
            "/api/v1/messages",
            json={
                "body": "Checking in on my own item.",
                "item_id": str(item_id),
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_ACTION"

    def test_request_conversation_start_rejects_self_messaging(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=requester, visibility="public")
            db.session.commit()
            access_token = login_api_user(client, requester.email)
            request_id = item_request.id

        response = client.post(
            "/api/v1/messages",
            json={
                "body": "I can solve this myself.",
                "request_id": str(request_id),
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_ACTION"

    def test_request_conversation_start_rejects_viewer_without_visibility(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            viewer = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=requester, visibility="circles")
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            request_id = item_request.id

        response = client.post(
            "/api/v1/messages",
            json={
                "body": "I can help.",
                "request_id": str(request_id),
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_mark_read_endpoint_marks_unread_messages_in_thread(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=sender,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()
            access_token = login_api_user(client, recipient.email)
            message_id = first_message.id

        response = client.post(
            f"/api/v1/messages/{message_id}/mark-read",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "has_unread_messages": False,
        }

        with app.app_context():
            db.session.expire_all()
            assert db.session.get(Message, message_id).is_read is True

    def test_reply_endpoint_rejects_non_participant(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            viewer = UserFactory(email_confirmed=True)
            message = MessageFactory(sender=sender, recipient=recipient)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            message_id = message.id

        response = client.post(
            f"/api/v1/messages/{message_id}/reply",
            json={"body": "Hello"},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_reply_success_returns_new_message(self, client, app):
        with app.app_context():
            sender = UserFactory(email_confirmed=True)
            recipient = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=sender)
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Interested in borrowing this.",
                is_read=True,
            )
            db.session.commit()
            access_token = login_api_user(client, recipient.email)
            message_id = first_message.id
            recipient_id = str(recipient.id)
            sender_id = str(sender.id)
            conv_id = conversation.id
            recipient_pk = recipient.id
            sender_pk = sender.id

        response = client.post(
            f"/api/v1/messages/{message_id}/reply",
            json={"body": "Sure, you can borrow it."},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["message"]["body"] == "Sure, you can borrow it."
        assert payload["message"]["sender"]["id"] == recipient_id
        assert payload["message"]["recipient"]["id"] == sender_id

        with app.app_context():
            db.session.expire_all()
            created_message = Message.query.filter(
                Message.conversation_id == conv_id,
                Message.body == "Sure, you can borrow it.",
            ).first()
            assert created_message is not None
            assert created_message.sender_id == recipient_pk
            assert created_message.recipient_id == sender_pk

    def test_messages_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/messages")

        assert response.status_code == 401


class TestApiConversationArchive:
    """Exercise conversation-level archive / unarchive endpoints."""

    def test_archive_conversation_sets_flag(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=user)
            db.session.commit()
            access_token = login_api_user(client, user.email)
            conv_id = conversation.id

        response = client.post(
            f"/api/v1/conversations/{conv_id}/archive",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}

        with app.app_context():
            participant = ConversationParticipant.query.filter_by(
                conversation_id=conv_id, user_id=user.id
            ).first()
            assert participant.is_archived is True

    def test_unarchive_conversation_clears_flag(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=user, is_archived=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)
            conv_id = conversation.id

        response = client.post(
            f"/api/v1/conversations/{conv_id}/unarchive",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}

        with app.app_context():
            participant = ConversationParticipant.query.filter_by(
                conversation_id=conv_id, user_id=user.id
            ).first()
            assert participant.is_archived is False

    def test_archive_returns_404_for_non_participant(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            conversation = ConversationFactory()
            db.session.commit()
            access_token = login_api_user(client, user.email)
            conv_id = conversation.id

        response = client.post(
            f"/api/v1/conversations/{conv_id}/archive",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404

    def test_bulk_archive_archives_multiple(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            conv1 = ConversationFactory()
            conv2 = ConversationFactory()
            ConversationParticipantFactory(conversation=conv1, user=user)
            ConversationParticipantFactory(conversation=conv2, user=user)
            db.session.commit()
            access_token = login_api_user(client, user.email)
            c1_id = str(conv1.id)
            c2_id = str(conv2.id)

        response = client.post(
            "/api/v1/conversations/bulk-archive",
            json={"conversation_ids": [c1_id, c2_id]},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "archived": 2}

    def test_bulk_mark_read_marks_unread(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory(email_confirmed=True)
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
            access_token = login_api_user(client, recipient.email)
            c1_id = str(conv1.id)
            c2_id = str(conv2.id)
            m1_id = msg1.id
            m2_id = msg2.id

        response = client.post(
            "/api/v1/conversations/bulk-mark-read",
            json={"conversation_ids": [c1_id, c2_id]},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "marked": 2}

        with app.app_context():
            assert db.session.get(Message, m1_id).is_read is True
            assert db.session.get(Message, m2_id).is_read is True

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/conversations/bulk-archive",
            "/api/v1/conversations/bulk-mark-read",
        ],
    )
    def test_bulk_endpoint_requires_conversation_ids(self, client, app, endpoint):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        # Missing conversation_ids
        response = client.post(endpoint, json={}, headers=auth_headers(access_token))
        assert response.status_code == 400
        assert response.get_json()["error"] == "conversation_ids is required"

        # Empty list
        response = client.post(
            endpoint, json={"conversation_ids": []}, headers=auth_headers(access_token)
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "conversation_ids is required"

    def test_mark_all_read_inbox_scoped(self, client, app):
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory(email_confirmed=True)
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
            access_token = login_api_user(client, recipient.email)
            inbox_msg_id = inbox_msg.id
            archived_msg_id = archived_msg.id

        response = client.post(
            "/api/v1/conversations/mark-all-read?status=inbox",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200

        with app.app_context():
            # Inbox message should be marked read
            assert db.session.get(Message, inbox_msg_id).is_read is True
            # Archived message should NOT be affected
            assert db.session.get(Message, archived_msg_id).is_read is False

    def test_messages_list_respects_status_filter(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            other = UserFactory()
            inbox_conv = ConversationFactory()
            archived_conv = ConversationFactory()
            ConversationParticipantFactory(conversation=inbox_conv, user=user)
            ConversationParticipantFactory(conversation=archived_conv, user=user, is_archived=True)
            MessageFactory(sender=other, recipient=user, conversation=inbox_conv)
            MessageFactory(sender=other, recipient=user, conversation=archived_conv)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        # Default inbox view
        resp = client.get("/api/v1/messages", headers=auth_headers(access_token))
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] == 1

        # Archived view
        resp = client.get("/api/v1/messages?status=archived", headers=auth_headers(access_token))
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] == 1
