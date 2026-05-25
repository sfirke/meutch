"""Integration tests for API request reads and writes."""

from datetime import date, timedelta

from app import db
from tests.factories import ItemRequestFactory, MessageFactory, UserFactory

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

    def test_fulfilled_request_can_still_be_updated(self, client, app):
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

        assert update_response.status_code == 200
        assert update_response.get_json()["request"]["title"] == "Updated after fulfillment"

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
