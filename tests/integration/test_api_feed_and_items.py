"""Integration tests for API feed and item read endpoints."""

from datetime import UTC, datetime, timedelta

from app import db
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ItemFactory,
    ItemImageFactory,
    ItemRequestFactory,
    LoanRequestFactory,
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
