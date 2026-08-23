"""Integration tests for API feed endpoints."""

from datetime import UTC, datetime, timedelta

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

    def test_feed_show_own_activity_toggle(self, client, app):
        """API feed respects show_own_activity — default includes own, false hides it."""
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([viewer, other_user])

            ItemRequestFactory(
                user=viewer,
                title="My own API request",
                visibility="circles",
            )
            ItemRequestFactory(
                user=other_user,
                title="Other API request",
                visibility="circles",
            )
            ItemFactory(
                owner=viewer,
                name="My own API giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            ItemFactory(
                owner=other_user,
                name="Other API giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        # Default: own activity is included
        default_response = client.get(
            "/api/v1/feed",
            headers=auth_headers(access_token),
        )
        assert default_response.status_code == 200
        default_titles = {e["title"] for e in default_response.get_json()["events"]}
        assert "My own API request" in default_titles
        assert "My own API giveaway" in default_titles

        # Explicit false: own activity is hidden, others' still visible
        hidden_response = client.get(
            "/api/v1/feed?show_own_activity=false",
            headers=auth_headers(access_token),
        )
        assert hidden_response.status_code == 200
        hidden_titles = {e["title"] for e in hidden_response.get_json()["events"]}
        assert "My own API request" not in hidden_titles
        assert "My own API giveaway" not in hidden_titles
        assert "Other API request" in hidden_titles
        assert "Other API giveaway" in hidden_titles

    def test_feed_show_claimed_giveaways_toggle(self, client, app):
        """API feed hides claimed giveaways by default and can include them."""
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            owner = UserFactory()
            claimer = UserFactory()
            circle = CircleFactory()
            circle.members.extend([viewer, owner, claimer])

            ItemFactory(
                owner=owner,
                name="API unclaimed giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            ItemFactory(
                owner=owner,
                name="API claimed giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=2),
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        default_response = client.get(
            "/api/v1/feed?types=giveaways",
            headers=auth_headers(access_token),
        )
        assert default_response.status_code == 200
        default_titles = {e["title"] for e in default_response.get_json()["events"]}
        assert "API unclaimed giveaway" in default_titles
        assert "API claimed giveaway" not in default_titles

        shown_response = client.get(
            "/api/v1/feed?types=giveaways&show_claimed_giveaways=true",
            headers=auth_headers(access_token),
        )
        assert shown_response.status_code == 200
        shown_titles = {e["title"] for e in shown_response.get_json()["events"]}
        assert "API unclaimed giveaway" in shown_titles
        assert "API claimed giveaway" in shown_titles
