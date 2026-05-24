"""Integration tests for API feed and item endpoints."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from app import db
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    GiveawayInterestFactory,
    ItemFactory,
    ItemImageFactory,
    ItemRequestFactory,
    LoanRequestFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


def _item_payload(category_id, **overrides):
    payload = {
        "name": "Cordless Drill",
        "description": "Still works great",
        "category_id": str(category_id),
        "tags": ["repair", "toolkit"],
        "is_giveaway": False,
        "giveaway_visibility": None,
    }
    payload.update(overrides)
    return payload


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


class TestApiItems:
    """Exercise API item list and detail reads."""

    def test_items_list_returns_paginated_discoverable_items(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            shared_owner = UserFactory()
            public_owner = UserFactory()
            category = CategoryFactory()

            shared_circle = CircleFactory()
            public_owner_circle = CircleFactory()
            shared_circle.members.extend([viewer, shared_owner])
            public_owner_circle.members.append(public_owner)

            older_item = ItemFactory(
                owner=shared_owner,
                category=category,
                name="Older visible item",
                is_giveaway=False,
            )
            newer_item = ItemFactory(
                owner=public_owner,
                category=category,
                name="Newer public giveaway",
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            hidden_claimed_item = ItemFactory(
                owner=shared_owner,
                category=category,
                name="Claimed hidden giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=viewer,
                claimed_at=datetime.now(UTC) - timedelta(days=1),
            )
            older_item.created_at = datetime.now(UTC) - timedelta(days=2)
            newer_item.created_at = datetime.now(UTC) - timedelta(days=1)
            hidden_claimed_item.created_at = datetime.now(UTC)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        response = client.get(
            "/api/v1/items?page=1&per_page=1",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["pagination"] == {
            "page": 1,
            "per_page": 1,
            "total": 2,
            "pages": 2,
            "has_next": True,
            "has_prev": False,
        }
        assert payload["items"][0]["name"] == "Newer public giveaway"

    def test_item_detail_returns_viewer_state_and_images_for_owner(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name="Owner detail item")
            ItemImageFactory(item=item, position=0)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.get(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["item"]["name"] == "Owner detail item"
        assert len(payload["item"]["images"]) == 1
        assert payload["viewer"] == {
            "is_owner": True,
            "shares_circle_with_owner": False,
            "is_active_borrower": False,
        }

    def test_item_detail_forbids_unrelated_user_for_loan_item(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            owner = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name="Private loan item")
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            item_id = item.id

        response = client.get(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_item_detail_allows_active_borrower_without_shared_circle(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            owner = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name="Borrowed item")
            LoanRequestFactory(item=item, borrower=borrower, status="approved")
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id

        response = client.get(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json()["viewer"]["is_active_borrower"] is True

    def test_item_detail_returns_404_for_claimed_giveaway_past_visibility_window(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            claimer = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(
                owner=owner,
                category=category,
                name="Old claimed giveaway",
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=100),
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.get(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404

    def test_items_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/items")

        assert response.status_code == 401


class TestApiItemMutations:
    @patch(
        "app.services.item_service.upload_item_images",
        return_value=[
            "https://example.com/items/one.jpg",
            "https://example.com/items/two.jpg",
        ],
    )
    def test_create_item_succeeds_with_tags_and_initial_images(self, _mock_upload, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            access_token = login_api_user(client, owner.email)
            category_id = str(category.id)

        response = client.post(
            "/api/v1/items",
            headers=auth_headers(access_token),
            data=MultiDict(
                [
                    ("name", "Cordless Drill"),
                    ("description", "Still works great"),
                    ("category_id", category_id),
                    ("tags", "repair"),
                    ("tags", "toolkit"),
                    ("is_giveaway", "false"),
                    ("images", (BytesIO(b"file-one"), "first.jpg")),
                    ("images", (BytesIO(b"file-two"), "second.jpg")),
                ]
            ),
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["viewer"] == {
            "is_owner": True,
            "shares_circle_with_owner": False,
            "is_active_borrower": False,
        }
        assert payload["item"]["name"] == "Cordless Drill"
        assert [tag["name"] for tag in payload["item"]["tags"]] == ["repair", "toolkit"]
        assert [image["url"] for image in payload["item"]["images"]] == [
            "https://example.com/items/one.jpg",
            "https://example.com/items/two.jpg",
        ]

    def test_create_item_rejects_public_giveaway_for_non_geocoded_owner(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True, latitude=None, longitude=None)
            category = CategoryFactory()
            access_token = login_api_user(client, owner.email)
            category_id = category.id

        response = client.post(
            "/api/v1/items",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name="Street Table",
                description="Free to a good home",
                is_giveaway=True,
                giveaway_visibility="public",
            ),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_update_item_changes_scalar_fields_and_tags(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            new_category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name="Old name", description="Old")
            ItemImageFactory(item=item, position=0)
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            new_category_id = new_category.id

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                new_category_id,
                name="Updated name",
                description="Updated description",
                tags=["garden", "tools"],
            ),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["item"]["name"] == "Updated name"
        assert payload["item"]["description"] == "Updated description"
        assert payload["item"]["category"]["id"] == str(new_category_id)
        assert [tag["name"] for tag in payload["item"]["tags"]] == ["garden", "tools"]
        assert len(payload["item"]["images"]) == 1

    def test_update_item_blocks_conversion_to_giveaway_with_active_loan(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True, latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, is_giveaway=False, available=False)
            LoanRequestFactory(item=item, borrower=borrower, status="approved")
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            category_id = category.id
            item_name = item.name
            item_description = item.description

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name=item_name,
                description=item_description,
                is_giveaway=True,
                giveaway_visibility="public",
            ),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_update_item_blocks_conversion_to_giveaway_with_pending_loan_request(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True, latitude=40.7128, longitude=-74.0060)
            borrower = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, is_giveaway=False)
            LoanRequestFactory(item=item, borrower=borrower, status="pending")
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            category_id = category.id
            item_name = item.name
            item_description = item.description

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name=item_name,
                description=item_description,
                is_giveaway=True,
                giveaway_visibility="public",
            ),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_update_item_blocks_conversion_to_loan_with_selected_interest(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            item = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            GiveawayInterestFactory(item=item, status="selected")
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            category_id = category.id
            item_name = item.name
            item_description = item.description

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name=item_name,
                description=item_description,
                is_giveaway=False,
                giveaway_visibility=None,
            ),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_update_item_blocks_conversion_to_loan_when_pending_pickup(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            item = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
            )
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            category_id = category.id
            item_name = item.name
            item_description = item.description

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name=item_name,
                description=item_description,
                is_giveaway=False,
                giveaway_visibility=None,
            ),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_update_item_blocks_conversion_to_loan_when_claimed(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            category = CategoryFactory()
            item = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
            )
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            category_id = category.id
            item_name = item.name
            item_description = item.description

        response = client.patch(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
            json=_item_payload(
                category_id,
                name=item_name,
                description=item_description,
                is_giveaway=False,
                giveaway_visibility=None,
            ),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_delete_item_is_blocked_for_active_loans(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False)
            LoanRequestFactory(item=item, borrower=borrower, status="approved")
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.delete(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_delete_item_is_blocked_for_pending_pickup_giveaways(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner, is_giveaway=True, claim_status="pending_pickup")
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.delete(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_delete_item_is_blocked_for_claimed_giveaways(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner, is_giveaway=True, claim_status="claimed")
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.delete(
            f"/api/v1/items/{item_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    @patch(
        "app.services.item_service.upload_item_images",
        return_value=[
            "https://example.com/items/two.jpg",
            "https://example.com/items/three.jpg",
        ],
    )
    def test_upload_item_images_appends_images(self, _mock_upload, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            ItemImageFactory(item=item, position=0, url="https://example.com/items/one.jpg")
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/images",
            headers=auth_headers(access_token),
            data=MultiDict(
                [
                    ("images", (BytesIO(b"file-two"), "second.jpg")),
                    ("images", (BytesIO(b"file-three"), "third.jpg")),
                ]
            ),
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert [image["url"] for image in payload["item"]["images"]] == [
            "https://example.com/items/one.jpg",
            "https://example.com/items/two.jpg",
            "https://example.com/items/three.jpg",
        ]

    @patch("app.services.item_service.upload_item_images", side_effect=ValueError("upload failed"))
    def test_upload_item_images_failure_preserves_existing_images(self, _mock_upload, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            existing_image = ItemImageFactory(item=item, position=0)
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            existing_image_id = existing_image.id

        response = client.post(
            f"/api/v1/items/{item_id}/images",
            headers=auth_headers(access_token),
            data=MultiDict([("images", (BytesIO(b"file-two"), "second.jpg"))]),
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

        with app.app_context():
            refreshed_item = db.session.get(type(item), item_id)
            assert [image.id for image in refreshed_item.images] == [existing_image_id]

    def test_upload_item_images_rejects_when_limit_would_be_exceeded(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            for position in range(7):
                ItemImageFactory(item=item, position=position)
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/images",
            headers=auth_headers(access_token),
            data=MultiDict(
                [
                    ("images", (BytesIO(b"file-eight"), "eight.jpg")),
                    ("images", (BytesIO(b"file-nine"), "nine.jpg")),
                ]
            ),
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_reorder_item_images_updates_positions_deterministically(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            first_image = ItemImageFactory(item=item, position=0)
            second_image = ItemImageFactory(item=item, position=1)
            third_image = ItemImageFactory(item=item, position=2)
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            first_image_id = first_image.id
            second_image_id = second_image.id
            third_image_id = third_image.id

        response = client.patch(
            f"/api/v1/items/{item_id}/images/order",
            headers=auth_headers(access_token),
            json={
                "image_ids": [
                    str(third_image_id),
                    str(first_image_id),
                    str(second_image_id),
                ]
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert [image["id"] for image in payload["item"]["images"]] == [
            str(third_image_id),
            str(first_image_id),
            str(second_image_id),
        ]

    @patch("app.services.item_service.delete_item_images")
    def test_delete_item_image_removes_image_and_preserves_remaining_order(
        self, mock_delete_images, client, app
    ):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            first_image = ItemImageFactory(item=item, position=0)
            second_image = ItemImageFactory(item=item, position=1)
            third_image = ItemImageFactory(item=item, position=2)
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            first_image_id = first_image.id
            second_image_id = second_image.id
            second_image_url = second_image.url
            third_image_id = third_image.id

        response = client.delete(
            f"/api/v1/items/{item_id}/images/{second_image_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert [image["id"] for image in payload["item"]["images"]] == [
            str(first_image_id),
            str(third_image_id),
        ]
        assert [image["position"] for image in payload["item"]["images"]] == [0, 1]
        mock_delete_images.assert_called_once_with([second_image_url])

    def test_non_owner_cannot_upload_images_to_item(self, client, app):
        with app.app_context():
            owner = UserFactory()
            non_owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            access_token = login_api_user(client, non_owner.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/images",
            headers=auth_headers(access_token),
            data=MultiDict([("images", (BytesIO(b"file"), "photo.jpg"))]),
            content_type="multipart/form-data",
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_non_owner_cannot_reorder_item_images(self, client, app):
        with app.app_context():
            owner = UserFactory()
            non_owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            image = ItemImageFactory(item=item, position=0)
            access_token = login_api_user(client, non_owner.email)
            item_id = item.id
            image_id = image.id

        response = client.patch(
            f"/api/v1/items/{item_id}/images/order",
            headers=auth_headers(access_token),
            json={"image_ids": [str(image_id)]},
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_non_owner_cannot_delete_item_image(self, client, app):
        with app.app_context():
            owner = UserFactory()
            non_owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            image = ItemImageFactory(item=item, position=0)
            access_token = login_api_user(client, non_owner.email)
            item_id = item.id
            image_id = image.id

        response = client.delete(
            f"/api/v1/items/{item_id}/images/{image_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"
