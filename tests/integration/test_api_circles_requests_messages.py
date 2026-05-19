"""Integration tests for API circle, request, and messaging reads."""

from datetime import UTC, datetime, timedelta

from app import db
from app.models import Message
from tests.factories import (
    CircleFactory,
    CircleJoinRequestFactory,
    ItemFactory,
    ItemRequestFactory,
    MessageFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


class TestApiCircles:
    """Exercise circle list and detail reads."""

    def test_circles_list_returns_membership_and_pending_request_metadata(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member_circle = CircleFactory(circle_type="open", name="Member Circle")
            pending_circle = CircleFactory(circle_type="closed", name="Pending Circle")
            CircleFactory(circle_type="secret", name="Secret Circle")

            member_circle.members.append(viewer)
            db.session.add(
                CircleJoinRequestFactory(circle=pending_circle, user=viewer, status="pending")
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        response = client.get(
            "/api/v1/circles?membership=discoverable&page=1&per_page=10",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        circles_by_name = {circle["name"]: circle for circle in payload["circles"]}

        assert payload["pagination"] == {
            "page": 1,
            "per_page": 10,
            "total": 2,
            "pages": 1,
            "has_next": False,
            "has_prev": False,
        }
        assert "Secret Circle" not in circles_by_name
        assert circles_by_name["Member Circle"]["is_member"] is True
        assert circles_by_name["Pending Circle"]["has_pending_join_request"] is True

    def test_circle_detail_hides_members_for_closed_circle_non_member(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member = UserFactory()
            circle = CircleFactory(circle_type="closed")
            circle.members.append(member)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            circle_id = circle.id

        response = client.get(
            f"/api/v1/circles/{circle_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json()["circle"]["can_view_members"] is False
        assert response.get_json()["circle"]["members"] == []

    def test_circle_detail_returns_404_for_secret_circle_non_member(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member = UserFactory()
            circle = CircleFactory(circle_type="secret")
            circle.members.append(member)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            circle_id = circle.id

        response = client.get(
            f"/api/v1/circles/{circle_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404

    def test_circles_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/circles")

        assert response.status_code == 401


class TestApiRequests:
    """Exercise request list and detail reads."""

    def test_requests_list_ignores_distance_filter_for_non_geocoded_viewer(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True, latitude=None, longitude=None)
            near_owner = UserFactory(latitude=40.7400, longitude=-74.0100)
            far_owner = UserFactory(latitude=42.3601, longitude=-71.0589)

            ItemRequestFactory(user=near_owner, title="Near request", visibility="public")
            ItemRequestFactory(user=far_owner, title="Far request", visibility="public")
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        response = client.get(
            "/api/v1/requests?distance=5",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        request_titles = {item_request["title"] for item_request in payload["requests"]}

        assert payload["pagination"]["total"] == 2
        assert request_titles == {"Near request", "Far request"}

    def test_request_detail_includes_owner_conversations(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            helper = UserFactory()
            item_request = ItemRequestFactory(user=owner, title="Need a drill", visibility="public")
            MessageFactory(
                sender=helper,
                recipient=owner,
                item=None,
                request=item_request,
                body="I can lend one.",
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            request_id = item_request.id

        response = client.get(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["request"]["title"] == "Need a drill"
        assert len(payload["conversations"]) == 1
        assert payload["conversations"][0]["latest_message"]["body"] == "I can lend one."

    def test_request_detail_forbids_unrelated_viewer_for_circles_only_request(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, visibility="circles")
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            request_id = item_request.id

        response = client.get(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_requests_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/requests")

        assert response.status_code == 401


class TestApiMessaging:
    """Exercise inbox summary and thread reads."""

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

    def test_messages_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/messages")

        assert response.status_code == 401
