"""Integration tests for API feed endpoints."""

from app import db
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ItemFactory,
    ItemRequestFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


class TestApiFeed:
    """Exercise API activity-feed reads."""

    def test_feed_scope_circles_hides_outsider_events_and_paginates(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True, latitude=40.7128, longitude=-74.0060)
            shared_user = UserFactory(latitude=40.7138, longitude=-74.0050)
            outsider = UserFactory(latitude=40.7150, longitude=-74.0020)
            category = CategoryFactory()

            shared_circle = CircleFactory()
            shared_circle.members.extend([viewer, shared_user])

            outsider_circle = CircleFactory()
            outsider_circle.members.append(outsider)

            ItemRequestFactory(
                user=shared_user,
                title="Shared feed request",
                visibility="public",
            )
            ItemRequestFactory(
                user=outsider,
                title="Outsider feed request",
                visibility="public",
            )
            ItemFactory(
                owner=shared_user,
                category=category,
                name="Shared feed giveaway",
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            ItemFactory(
                owner=outsider,
                category=category,
                name="Outsider feed giveaway",
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        response = client.get(
            "/api/v1/feed?scope=circles&page=1&per_page=1",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        event_titles = {event["title"] for event in payload["events"]}

        assert payload["pagination"] == {
            "page": 1,
            "per_page": 1,
            "total": 2,
            "pages": 2,
            "has_next": True,
            "has_prev": False,
        }
        assert event_titles <= {"Shared feed request", "Shared feed giveaway"}

    def test_feed_requires_authentication(self, client, app):
        response = client.get("/api/v1/feed")

        assert response.status_code == 401
