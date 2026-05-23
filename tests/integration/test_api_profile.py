"""Integration tests for API current-user profile and settings reads and writes."""

from io import BytesIO
from unittest.mock import patch

from app import db
from tests.factories import (
    CircleFactory,
    ItemFactory,
    LoanRequestFactory,
    UserFactory,
    UserWebLinkFactory,
)

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

    def test_patch_me_profile_returns_updated_profile_payload(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True, about_me="Old bio")
            user_id = user.id
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            json={"about_me": "Updated bio", "links": []},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["image_upload_failed"] is False
        assert payload["user"]["about_me"] == "Updated bio"

        with app.app_context():
            updated_user = db.session.get(type(user), user_id)
            assert updated_user.about_me == "Updated bio"

    def test_patch_me_profile_saves_links_in_array_order(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            json={
                "about_me": user.about_me,
                "links": [
                    {
                        "platform": "website",
                        "url": "https://example.com/first",
                    },
                    {
                        "platform": "other",
                        "custom_name": "Community Wiki",
                        "url": "https://example.com/wiki",
                    },
                ],
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert [link["display_order"] for link in payload["user"]["web_links"]] == [1, 2]
        assert [link["platform_type"] for link in payload["user"]["web_links"]] == [
            "website",
            "other",
        ]

    @patch(
        "app.services.profile_service.upload_profile_image",
        return_value="https://example.com/profiles/new.jpg",
    )
    def test_patch_me_profile_uploads_profile_image(self, _mock_upload, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True, profile_image_url=None)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            data={
                "about_me": "With image",
                "links": "[]",
                "profile_image": (BytesIO(b"fake image data"), "avatar.jpg"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["image_upload_failed"] is False
        assert payload["user"]["profile_image_url"] == "https://example.com/profiles/new.jpg"

    @patch("app.services.profile_service.delete_file")
    def test_patch_me_profile_deletes_profile_image(self, mock_delete, client, app):
        with app.app_context():
            user = UserFactory(
                email_confirmed=True,
                about_me="Keep this bio",
                profile_image_url="https://example.com/profiles/old.jpg",
            )
            UserWebLinkFactory(
                user=user,
                display_order=1,
                platform_type="website",
                url="https://example.com/keep",
            )
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            json={"delete_image": True},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["user"]["profile_image_url"] is None
        assert payload["user"]["about_me"] == "Keep this bio"
        assert len(payload["user"]["web_links"]) == 1
        mock_delete.assert_called_once_with("https://example.com/profiles/old.jpg")

    @patch("app.services.profile_service.upload_profile_image", return_value=None)
    def test_patch_me_profile_reports_image_upload_failure_without_losing_text_changes(
        self, _mock_upload, client, app
    ):
        with app.app_context():
            user = UserFactory(email_confirmed=True, about_me="Old bio", profile_image_url=None)
            user_id = user.id
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            data={
                "about_me": "Saved anyway",
                "links": "[]",
                "profile_image": (BytesIO(b"fake image data"), "avatar.jpg"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["image_upload_failed"] is True
        assert payload["user"]["about_me"] == "Saved anyway"
        assert payload["user"]["profile_image_url"] is None

        with app.app_context():
            updated_user = db.session.get(type(user), user_id)
            assert updated_user.about_me == "Saved anyway"

    def test_patch_me_settings_persists_digest_and_vacation_fields(self, client, app):
        with app.app_context():
            user = UserFactory(
                email_confirmed=True,
                vacation_mode=False,
                digest_frequency="weekly",
                digest_radius_miles=10,
                digest_include_giveaways=True,
                digest_include_requests=False,
                digest_include_circle_joins=True,
                digest_include_loans=False,
                digest_giveaways_include_public=True,
                digest_requests_include_public=False,
            )
            user_id = user.id
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/settings",
            headers=auth_headers(access_token),
            json={
                "vacation_mode": True,
                "digest_frequency": "daily",
                "digest_radius_miles": 25,
                "digest_include_giveaways": False,
                "digest_include_requests": True,
                "digest_include_circle_joins": False,
                "digest_include_loans": True,
                "digest_giveaways_include_public": False,
                "digest_requests_include_public": True,
            },
        )

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

        with app.app_context():
            updated_user = db.session.get(type(user), user_id)
            assert updated_user.vacation_mode is True
            assert updated_user.digest_frequency == "daily"
            assert updated_user.digest_radius_miles == 25

    def test_patch_me_location_updates_coordinates(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True, latitude=None, longitude=None)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/location",
            headers=auth_headers(access_token),
            json={
                "location_method": "coordinates",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "success",
            "user": {
                "has_location": True,
                "geocoding_failed": False,
            },
        }

    @patch("app.utils.geocoding.geocode_address", return_value=None)
    def test_patch_me_location_reports_geocoding_failure(self, _mock_geocode, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True, latitude=None, longitude=None)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/location",
            headers=auth_headers(access_token),
            json={
                "location_method": "address",
                "street": "123 Unknown",
                "city": "Nowhere",
                "state": "NC",
                "zip_code": "12345",
                "country": "USA",
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "geocoding_failed",
            "user": {
                "has_location": False,
                "geocoding_failed": True,
            },
        }

    def test_patch_me_location_returns_rate_limited_status(self, client, app):
        with app.app_context():
            user = UserFactory(
                email_confirmed=True,
                latitude=40.0,
                longitude=-70.0,
                geocoding_failed=False,
            )
            user.geocoded_at = db.func.now()
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.patch(
            "/api/v1/me/location",
            headers=auth_headers(access_token),
            json={
                "location_method": "coordinates",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        )

        assert response.status_code == 200
        assert response.get_json()["status"] == "rate_limited"

    def test_delete_me_requires_exact_confirmation_phrase(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        response = client.delete(
            "/api/v1/me",
            headers=auth_headers(access_token),
            json={"confirmation": "delete my account"},
        )

        assert response.status_code == 422
        assert response.get_json() == {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": {
                    "confirmation": [
                        'You must type "DELETE MY ACCOUNT" exactly to confirm deletion.'
                    ]
                },
            }
        }

    @patch("app.services.account_service.send_account_deletion_email")
    def test_delete_me_soft_deletes_user_and_revokes_tokens(self, _mock_email, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True, profile_image_url=None)
            user_id = user.id
            user_email = user.email
            circle = CircleFactory()
            active_item = ItemFactory(owner=user, is_giveaway=False, available=True)
            borrower = UserFactory(email_confirmed=True)
            LoanRequestFactory(item=active_item, borrower=borrower, status="approved")
            db.session.execute(
                db.text(
                    """
                    INSERT INTO circle_members (user_id, circle_id, joined_at, is_admin)
                    VALUES (:user_id, :circle_id, NOW(), TRUE)
                    """
                ),
                {"user_id": str(user.id), "circle_id": str(circle.id)},
            )
            db.session.commit()

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "testpassword123"},
        )
        payload = login_response.get_json()

        response = client.delete(
            "/api/v1/me",
            headers=auth_headers(payload["access_token"]),
            json={"confirmation": "DELETE MY ACCOUNT"},
        )

        assert response.status_code == 200
        assert response.get_json() == {"deleted": True}

        me_response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers(payload["access_token"]),
        )
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers(payload["refresh_token"]),
        )

        assert me_response.status_code == 401
        assert me_response.get_json()["error"]["code"] == "TOKEN_REVOKED"
        assert refresh_response.status_code == 401
        assert refresh_response.get_json()["error"]["code"] == "TOKEN_REVOKED"

        with app.app_context():
            deleted_user = db.session.get(type(user), user_id)
            assert deleted_user.is_deleted is True
            assert deleted_user.email.startswith("deleted_")
            assert deleted_user.circles == []

    def test_patch_me_profile_rejects_more_than_five_links(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)

        six_links = [{"platform": "website", "url": f"https://example.com/{i}"} for i in range(6)]
        response = client.patch(
            "/api/v1/me/profile",
            headers=auth_headers(access_token),
            json={"links": six_links},
        )

        assert response.status_code == 422

    def test_me_profile_requires_authentication(self, client, app):
        response = client.get("/api/v1/me/profile")

        assert response.status_code == 401
