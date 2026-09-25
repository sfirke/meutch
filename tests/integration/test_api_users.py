"""Integration tests for the API member profile endpoint."""

import uuid
from datetime import UTC, datetime

from app import db
from app.models import circle_members
from tests.factories import (
    CircleFactory,
    CircleJoinRequestFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    ItemFactory,
    UserFactory,
    UserWebLinkFactory,
)

from .api_test_helpers import auth_headers, login_api_user

USER_KEYS = {
    "id",
    "first_name",
    "last_name",
    "full_name",
    "profile_image_url",
    "about_me",
    "web_links",
}


def _get_profile(client, token, user_id):
    return client.get(f"/api/v1/users/{user_id}", headers=auth_headers(token))


def _assert_not_found(response):
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def _collect_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys |= _collect_keys(child)
        return keys
    if isinstance(value, list):
        keys = set()
        for child in value:
            keys |= _collect_keys(child)
        return keys
    return set()


def _add_admin(circle, user):
    db.session.execute(
        circle_members.insert().values(
            user_id=user.id,
            circle_id=circle.id,
            joined_at=datetime.now(UTC),
            is_admin=True,
        )
    )


class TestApiUserProfile:
    """Exercise GET /api/v1/users/<id>."""

    def test_requires_authentication(self, client, app):
        with app.app_context():
            user = UserFactory()
            db.session.commit()
            user_id = user.id

        response = client.get(f"/api/v1/users/{user_id}")

        assert response.status_code == 401

    def test_self_returns_profile_without_shared_circles(self, client, app):
        with app.app_context():
            user = UserFactory(about_me="Hello there.")
            circle = CircleFactory()
            circle.members.append(user)
            db.session.commit()
            user_id = str(user.id)
            token = login_api_user(client, user.email)

        response = _get_profile(client, token, user_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_reason"] == "self"
        assert payload["shared_circles"] == []
        assert payload["user"]["id"] == user_id
        assert payload["user"]["about_me"] == "Hello there."
        assert set(payload["user"]) == USER_KEYS

    def test_circle_member_sees_profile_and_shared_circles(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            target = UserFactory(first_name="Pat", last_name="Neighbor")
            beta = CircleFactory(name="Beta Circle", circle_type="closed")
            alpha = CircleFactory(name="alpha circle")
            other = CircleFactory(name="Target Only")
            for circle in (alpha, beta):
                circle.members.append(viewer)
                circle.members.append(target)
            other.members.append(target)
            db.session.commit()
            target_id = str(target.id)
            alpha_id, beta_id = str(alpha.id), str(beta.id)
            token = login_api_user(client, viewer.email)

        response = _get_profile(client, token, target_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_reason"] == "circle"
        assert payload["user"]["full_name"] == "Pat Neighbor"
        assert [circle["id"] for circle in payload["shared_circles"]] == [alpha_id, beta_id]
        assert set(payload["shared_circles"][0]) == {"id", "name", "circle_type", "image_url"}
        assert payload["shared_circles"][1]["circle_type"] == "closed"

    def test_admin_can_view_stranger(self, client, app):
        with app.app_context():
            admin = UserFactory(is_admin=True)
            target = UserFactory()
            db.session.commit()
            target_id = target.id
            token = login_api_user(client, admin.email)

        response = _get_profile(client, token, target_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_reason"] == "admin"
        assert payload["shared_circles"] == []

    def test_conversation_partner_can_view(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            target = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=viewer)
            ConversationParticipantFactory(conversation=conversation, user=target)
            db.session.commit()
            target_id = target.id
            token = login_api_user(client, viewer.email)

        response = _get_profile(client, token, target_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_reason"] == "conversation"
        assert payload["shared_circles"] == []

    def test_circle_admin_can_view_pending_join_requester(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            requester = UserFactory()
            circle = CircleFactory(circle_type="closed")
            _add_admin(circle, viewer)
            CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
            db.session.commit()
            requester_id = requester.id
            token = login_api_user(client, viewer.email)

        response = _get_profile(client, token, requester_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["access_reason"] == "join_request"
        assert payload["shared_circles"] == []

    def test_stranger_returns_not_found(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            target = UserFactory()
            db.session.commit()
            target_id = target.id
            token = login_api_user(client, viewer.email)

        _assert_not_found(_get_profile(client, token, target_id))

    def test_unknown_id_returns_not_found(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            db.session.commit()
            token = login_api_user(client, viewer.email)

        _assert_not_found(_get_profile(client, token, uuid.uuid4()))

    def test_deleted_user_hidden_from_circle_mate_but_visible_to_admin(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            admin = UserFactory(is_admin=True)
            departed = UserFactory()
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(departed)
            departed.is_deleted = True
            db.session.commit()
            departed_id = departed.id
            viewer_token = login_api_user(client, viewer.email)
            admin_token = login_api_user(client, admin.email)

        _assert_not_found(_get_profile(client, viewer_token, departed_id))

        admin_response = _get_profile(client, admin_token, departed_id)
        assert admin_response.status_code == 200
        assert admin_response.get_json()["access_reason"] == "admin"

    def test_response_omits_email_and_items(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            target = UserFactory()
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(target)
            ItemFactory(owner=target)
            db.session.commit()
            target_id = target.id
            token = login_api_user(client, viewer.email)

        response = _get_profile(client, token, target_id)

        assert response.status_code == 200
        payload = response.get_json()
        assert set(payload) == {"user", "shared_circles", "access_reason"}
        keys = _collect_keys(payload)
        assert "email" not in keys
        assert "items" not in keys

    def test_web_links_sorted_by_display_order(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            target = UserFactory()
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(target)
            UserWebLinkFactory(
                user=target,
                display_order=3,
                platform_type="website",
                url="https://example.com/third",
            )
            UserWebLinkFactory(
                user=target,
                display_order=1,
                platform_type="linkedin",
                url="https://example.com/first",
            )
            UserWebLinkFactory(
                user=target,
                display_order=2,
                platform_type="instagram",
                url="https://example.com/second",
            )
            db.session.commit()
            target_id = target.id
            token = login_api_user(client, viewer.email)

        response = _get_profile(client, token, target_id)

        assert response.status_code == 200
        links = response.get_json()["user"]["web_links"]
        assert [link["display_order"] for link in links] == [1, 2, 3]
        assert [link["url"] for link in links] == [
            "https://example.com/first",
            "https://example.com/second",
            "https://example.com/third",
        ]
