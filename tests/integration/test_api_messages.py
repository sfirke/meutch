"""Integration tests for API messaging reads and writes."""

from datetime import UTC, datetime, timedelta

from app import db
from app.models import Message
from tests.factories import (
    CircleFactory,
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

            older_message = MessageFactory(
                sender=requester,
                recipient=helper,
                item=None,
                request=item_request,
                is_read=True,
            )
            newer_message = MessageFactory(
                sender=helper,
                recipient=requester,
                item=None,
                request=item_request,
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
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                body="Checking whether you still need this.",
                is_read=False,
            )
            second_message = MessageFactory(
                sender=recipient,
                recipient=sender,
                item=item,
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
            first_message = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                is_read=False,
            )
            MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
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

    def test_messages_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/messages")

        assert response.status_code == 401
