"""Integration tests for API request reads and writes."""

from datetime import date, timedelta
from unittest.mock import patch

from app import db
from app.models import Conversation, Message
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    ItemRequestFactory,
    MessageFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


class TestApiRequests:
    """Exercise request list, detail, and mutation behavior."""

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
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            MessageFactory(
                sender=helper,
                recipient=owner,
                conversation=conversation,
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

    def test_request_create_returns_request_payload_for_geocoded_user(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True, latitude=40.7128, longitude=-74.0060)
            access_token = login_api_user(client, requester.email)

        response = client.post(
            "/api/v1/requests",
            json={
                "title": "Need a folding table",
                "description": "For a neighborhood swap.",
                "expires_at": (date.today() + timedelta(days=30)).isoformat(),
                "seeking": "either",
                "visibility": "public",
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["request"]["title"] == "Need a folding table"
        assert payload["request"]["visibility"] == "public"
        assert payload["request"]["user"]["id"] == str(requester.id)

    def test_request_detail_returns_404_for_deleted_request(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, status="deleted")
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            request_id = item_request.id

        response = client.get(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404

    def test_request_write_with_invalid_date_returns_422_not_500(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            access_token = login_api_user(client, requester.email)

        response = client.post(
            "/api/v1/requests",
            json={
                "title": "Need a tent",
                "expires_at": "not-a-date",
                "seeking": "either",
                "visibility": "circles",
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_fulfilled_request_cannot_be_updated(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=owner, status="open")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            request_id = item_request.id

        client.post(
            f"/api/v1/requests/{request_id}/fulfill",
            headers=auth_headers(access_token),
        )
        update_response = client.patch(
            f"/api/v1/requests/{request_id}",
            json={
                "title": "Updated after fulfillment",
                "expires_at": (date.today() + timedelta(days=7)).isoformat(),
                "seeking": "loan",
                "visibility": "circles",
            },
            headers=auth_headers(access_token),
        )

        assert update_response.status_code == 409
        assert update_response.get_json()["error"]["code"] == "CONFLICT"

    def test_request_create_rejects_public_visibility_for_non_geocoded_user(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True, latitude=None, longitude=None)
            access_token = login_api_user(client, requester.email)

        response = client.post(
            "/api/v1/requests",
            json={
                "title": "Need moving boxes",
                "description": "Any sizes.",
                "expires_at": (date.today() + timedelta(days=14)).isoformat(),
                "seeking": "either",
                "visibility": "public",
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_only_request_owner_can_update_delete_or_fulfill_request(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            other_user = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=owner, status="open")
            db.session.commit()
            other_access_token = login_api_user(client, other_user.email)
            request_id = item_request.id

        update_response = client.patch(
            f"/api/v1/requests/{request_id}",
            json={
                "title": "Updated title",
                "description": "Updated description",
                "expires_at": (date.today() + timedelta(days=21)).isoformat(),
                "seeking": "loan",
                "visibility": "circles",
            },
            headers=auth_headers(other_access_token),
        )
        delete_response = client.delete(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers(other_access_token),
        )
        fulfill_response = client.post(
            f"/api/v1/requests/{request_id}/fulfill",
            headers=auth_headers(other_access_token),
        )

        assert update_response.status_code == 403
        assert delete_response.status_code == 403
        assert fulfill_response.status_code == 403

    def test_deleted_request_cannot_be_updated_or_fulfilled_again(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=owner, status="open")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            request_id = item_request.id

        delete_response = client.delete(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers(access_token),
        )
        update_response = client.patch(
            f"/api/v1/requests/{request_id}",
            json={
                "title": "Updated after delete",
                "description": "Should fail",
                "expires_at": (date.today() + timedelta(days=21)).isoformat(),
                "seeking": "either",
                "visibility": "circles",
            },
            headers=auth_headers(access_token),
        )
        fulfill_response = client.post(
            f"/api/v1/requests/{request_id}/fulfill",
            headers=auth_headers(access_token),
        )

        assert delete_response.status_code == 200
        assert delete_response.get_json()["request"]["status"] == "deleted"
        assert update_response.status_code == 409
        assert fulfill_response.status_code == 409

    def test_fulfilled_request_cannot_be_fulfilled_again(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item_request = ItemRequestFactory(user=owner, status="open")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            request_id = item_request.id

        first_response = client.post(
            f"/api/v1/requests/{request_id}/fulfill",
            headers=auth_headers(access_token),
        )
        second_response = client.post(
            f"/api/v1/requests/{request_id}/fulfill",
            headers=auth_headers(access_token),
        )

        assert first_response.status_code == 200
        assert first_response.get_json()["request"]["status"] == "fulfilled"
        assert second_response.status_code == 409


class TestApiRespondToRequest:
    """Exercise responding to a request with one of your own items."""

    def _setup(self, **request_kwargs):
        """Create a responder, a requester who shares a circle, and a request."""
        responder = UserFactory(email_confirmed=True)
        requester = UserFactory()
        circle = CircleFactory()
        circle.members.extend([responder, requester])
        item = ItemFactory(owner=responder, name="Extension Ladder")
        item_request = ItemRequestFactory(
            user=requester,
            title="Looking for a ladder",
            visibility="circles",
            **request_kwargs,
        )
        db.session.commit()
        return responder, requester, item, item_request

    def test_respond_creates_message_with_item_link(self, client, app):
        with app.app_context():
            responder, requester, item, item_request = self._setup()
            item_id, request_id, requester_id = item.id, item_request.id, requester.id
            access_token = login_api_user(client, responder.email)

        with patch("app.services.message_service.send_message_notification_email"):
            response = client.post(
                f"/api/v1/requests/{request_id}/respond/{item_id}",
                json={},
                headers=auth_headers(access_token),
            )

        assert response.status_code == 201
        body = response.get_json()["message"]["body"]
        assert "Extension Ladder" in body
        assert f"/item/{item_id}" in body

        with app.app_context():
            message = Message.query.filter_by(recipient_id=requester_id).one()
            conversation = db.session.get(Conversation, message.conversation_id)
            assert conversation.context_type == "request"
            assert conversation.context_id == request_id

    def test_respond_accepts_a_custom_body(self, client, app):
        with app.app_context():
            responder, _requester, item, item_request = self._setup()
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        with patch("app.services.message_service.send_message_notification_email"):
            response = client.post(
                f"/api/v1/requests/{request_id}/respond/{item_id}",
                json={"body": "Happy to lend you mine!"},
                headers=auth_headers(access_token),
            )

        assert response.status_code == 201
        assert response.get_json()["message"]["body"] == "Happy to lend you mine!"

    def test_respond_rejects_an_item_you_do_not_own(self, client, app):
        with app.app_context():
            responder, _requester, _item, item_request = self._setup()
            other_item = ItemFactory(owner=UserFactory(), name="Not Mine")
            db.session.commit()
            other_item_id, request_id = other_item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.post(
            f"/api/v1/requests/{request_id}/respond/{other_item_id}",
            json={},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403

    def test_respond_rejects_a_request_you_cannot_view(self, client, app):
        with app.app_context():
            stranger = UserFactory(email_confirmed=True)
            requester = UserFactory()
            item = ItemFactory(owner=stranger, name="Extension Ladder")
            item_request = ItemRequestFactory(user=requester, visibility="circles")
            db.session.commit()
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, stranger.email)

        response = client.post(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            json={},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403

    def test_respond_rejects_a_closed_request(self, client, app):
        with app.app_context():
            responder, _requester, item, item_request = self._setup(status="fulfilled")
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.post(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            json={},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400

    def test_respond_rejects_an_over_long_body(self, client, app):
        with app.app_context():
            responder, _requester, item, item_request = self._setup()
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.post(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            json={"body": "x" * 1001},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 422

    def test_draft_returns_the_suggested_body(self, client, app):
        with app.app_context():
            responder, _requester, item, item_request = self._setup()
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.get(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert "Extension Ladder" in payload["suggested_body"]
        assert f"/item/{item_id}" in payload["suggested_body"]
        assert payload["seeking_mismatch"] is None

    def test_draft_reports_a_seeking_mismatch(self, client, app):
        """A loan item offered to a giveaway request is flagged, not blocked."""
        with app.app_context():
            responder, _requester, item, item_request = self._setup(seeking="giveaway")
            item_id, request_id = item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.get(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert "asking for a giveaway" in response.get_json()["seeking_mismatch"]

    def test_draft_rejects_an_item_you_do_not_own(self, client, app):
        with app.app_context():
            responder, _requester, _item, item_request = self._setup()
            other_item = ItemFactory(owner=UserFactory(), name="Not Mine")
            db.session.commit()
            other_item_id, request_id = other_item.id, item_request.id
            access_token = login_api_user(client, responder.email)

        response = client.get(
            f"/api/v1/requests/{request_id}/respond/{other_item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403

    def test_draft_does_not_send_anything(self, client, app):
        with app.app_context():
            responder, requester, item, item_request = self._setup()
            item_id, request_id, requester_id = item.id, item_request.id, requester.id
            access_token = login_api_user(client, responder.email)

        client.get(
            f"/api/v1/requests/{request_id}/respond/{item_id}",
            headers=auth_headers(access_token),
        )

        with app.app_context():
            assert Message.query.filter_by(recipient_id=requester_id).count() == 0
