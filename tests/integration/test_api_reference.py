"""Integration tests for API reference-data endpoints."""

from app import db
from tests.factories import CategoryFactory, TagFactory, UserFactory

from .api_test_helpers import auth_headers, login_api_user


class TestApiReference:
    """Exercise authenticated reference-data reads."""

    def test_categories_require_authentication(self, client):
        response = client.get("/api/v1/categories")

        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_categories_return_sorted_reference_data(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            categories = [CategoryFactory(), CategoryFactory()]
            db.session.commit()
            user_email = user.email
            expected_ids_in_order = [
                str(category.id)
                for category in sorted(categories, key=lambda category: category.name)
            ]

        access_token = login_api_user(client, user_email)

        response = client.get("/api/v1/categories", headers=auth_headers(access_token))

        assert response.status_code == 200
        payload = response.get_json()
        category_entries = [
            entry for entry in payload["categories"] if entry["id"] in set(expected_ids_in_order)
        ]

        assert [entry["id"] for entry in category_entries] == expected_ids_in_order

    def test_tags_return_sorted_reference_data(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            tags = [TagFactory(), TagFactory()]
            db.session.commit()
            user_email = user.email
            expected_ids_in_order = [str(tag.id) for tag in sorted(tags, key=lambda tag: tag.name)]

        access_token = login_api_user(client, user_email)

        response = client.get("/api/v1/tags", headers=auth_headers(access_token))

        assert response.status_code == 200
        payload = response.get_json()
        tag_entries = [
            entry for entry in payload["tags"] if entry["id"] in set(expected_ids_in_order)
        ]

        assert [entry["id"] for entry in tag_entries] == expected_ids_in_order
