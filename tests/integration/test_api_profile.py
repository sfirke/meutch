"""Integration tests for API current-user profile and settings reads."""

from app import db
from tests.factories import UserFactory, UserWebLinkFactory

from .api_test_helpers import auth_headers, login_api_user


class TestApiProfile:
    """Exercise authenticated profile/settings endpoints."""

    def test_me_profile_returns_profile_details_and_sorted_links(self, client, app):
        with app.app_context():
            user = UserFactory(
                email_confirmed=True,
                about_me="Community builder.",
                geocoding_failed=False,
            )
            UserWebLinkFactory(
                user=user,
                display_order=2,
                platform_type="website",
                url="https://example.com/second",
            )
            UserWebLinkFactory(
                user=user,
                display_order=1,
                platform_type="linkedin",
                url="https://example.com/first",
            )
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.get("/api/v1/me/profile", headers=auth_headers(access_token))

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["user"]["about_me"] == "Community builder."
        assert payload["user"]["has_location"] is False
        assert [link["display_order"] for link in payload["user"]["web_links"]] == [1, 2]

    def test_me_settings_returns_digest_and_vacation_settings(self, client, app):
        with app.app_context():
            user = UserFactory(
                email_confirmed=True,
                vacation_mode=True,
                digest_frequency="daily",
                digest_radius_miles=25,
                digest_include_giveaways=False,
                digest_include_requests=True,
                digest_include_circle_joins=False,
                digest_include_loans=True,
                digest_giveaways_include_public=False,
                digest_requests_include_public=True,
            )
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.get("/api/v1/me/settings", headers=auth_headers(access_token))

        assert response.status_code == 200
        assert response.get_json() == {
            "settings": {
                "vacation_mode": True,
                "digest_frequency": "daily",
                "digest_radius_miles": 25,
                "digest_include_giveaways": False,
                "digest_include_requests": True,
                "digest_include_circle_joins": False,
                "digest_include_loans": True,
                "digest_giveaways_include_public": False,
                "digest_requests_include_public": True,
            }
        }

    def test_me_profile_requires_authentication(self, client, app):
        response = client.get("/api/v1/me/profile")

        assert response.status_code == 401
