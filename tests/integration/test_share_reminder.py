"""Integration tests for the reminder to share public giveaways and requests outside Meutch."""

import uuid
from datetime import UTC, date, datetime, timedelta

from flask import url_for

from app import db
from app.models import Item, ItemRequest
from conftest import login_user
from tests.factories import CategoryFactory, CircleFactory, ItemFactory, ItemRequestFactory

FLASH_MARKER = b'class="share-reminder '
HINT_MARKER = b"share-reminder-hint"


def _external_url(app, endpoint, **values):
    with app.test_request_context():
        return url_for(endpoint, _external=True, **values)


def _giveaway_data(category, name, visibility, **extra):
    data = {
        "name": name,
        "description": "Still works great",
        "category": str(category.id),
        "is_giveaway": True,
        "giveaway_visibility": visibility,
        "tags": "",
    }
    data.update(extra)
    return data


def _request_data(title, visibility):
    return {
        "title": title,
        "description": "Looking for one",
        "expires_at": (date.today() + timedelta(days=30)).isoformat(),
        "seeking": "either",
        "visibility": visibility,
    }


class TestShareReminderAfterCreation:
    """The share reminder flash appears once, right after creating a public activity."""

    def test_reminder_shown_after_public_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data=_giveaway_data(category, "Public Lamp", "public"),
                follow_redirects=True,
            )

            assert response.status_code == 200
            item = Item.query.filter_by(name="Public Lamp").one()
            assert FLASH_MARKER in response.data
            expected_url = _external_url(app, "share.giveaway_preview", item_id=item.id)
            assert f'data-share-url="{expected_url}"'.encode() in response.data
            assert b"Because Meutch is still growing" in response.data

            # Shown only once
            followup = client.get("/")
            assert FLASH_MARKER not in followup.data

    def test_reminder_shown_after_public_giveaway_create_another(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data=_giveaway_data(
                    category,
                    "Public Rake",
                    "public",
                    submit_and_create_another="List Item & Create Another",
                ),
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"List a New Item" in response.data
            item = Item.query.filter_by(name="Public Rake").one()
            expected_url = _external_url(app, "share.giveaway_preview", item_id=item.id)
            assert f'data-share-url="{expected_url}"'.encode() in response.data

    def test_reminder_escapes_item_name(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data=_giveaway_data(category, '<b>"Bold"</b> Chair', "public"),
                follow_redirects=True,
            )

            assert FLASH_MARKER in response.data
            assert b'<b>"Bold"</b>' not in response.data

    def test_no_reminder_after_circle_only_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data=_giveaway_data(category, "Circle Lamp", "default"),
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"has been listed successfully!" in response.data
            assert FLASH_MARKER not in response.data

    def test_no_reminder_after_loan_item(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data={"name": "Drill", "description": "", "category": str(category.id)},
                follow_redirects=True,
            )

            assert b"has been listed successfully!" in response.data
            assert FLASH_MARKER not in response.data

    def test_no_reminder_on_duplicate_submission(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)
            post_data = _giveaway_data(
                category, "Duplicate Lamp", "public", creation_token=str(uuid.uuid4())
            )

            first = client.post("/list-item", data=post_data, follow_redirects=True)
            assert FLASH_MARKER in first.data

            second = client.post("/list-item", data=post_data, follow_redirects=True)
            assert b"We already listed this item from your earlier submission" in second.data
            assert FLASH_MARKER not in second.data

    def test_reminder_shown_after_public_request(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data=_request_data("Need a ladder", "public"),
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Your request has been posted!" in response.data
            req = ItemRequest.query.filter_by(title="Need a ladder").one()
            assert FLASH_MARKER in response.data
            expected_url = _external_url(app, "share.request_preview", request_id=req.id)
            assert f'data-share-url="{expected_url}"'.encode() in response.data

    def test_no_reminder_after_circle_only_request(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data=_request_data("Need a tent", "circles"),
                follow_redirects=True,
            )

            assert b"Your request has been posted!" in response.data
            assert FLASH_MARKER not in response.data


class TestShareReminderDetailHint:
    """The owner-only hint on detail pages for open public listings."""

    def test_hint_shown_to_owner_of_open_public_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            item = ItemFactory(
                owner=user, is_giveaway=True, giveaway_visibility="public", claim_status="unclaimed"
            )
            db.session.commit()
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            assert HINT_MARKER in response.data

    def test_hint_not_shown_to_other_viewer_of_public_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            owner = ItemFactory().owner
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(owner)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            db.session.commit()
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            assert b"share-btn" in response.data
            assert HINT_MARKER not in response.data

    def test_hint_not_shown_for_claimed_or_pending_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            for status in ("pending_pickup", "claimed"):
                item = ItemFactory(
                    owner=user,
                    is_giveaway=True,
                    giveaway_visibility="public",
                    claim_status=status,
                    available=False,
                )
                db.session.commit()
                login_user(client, user.email)

                response = client.get(f"/item/{item.id}")
                assert response.status_code == 200
                assert HINT_MARKER not in response.data

    def test_hint_not_shown_for_circle_only_giveaway(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            item = ItemFactory(
                owner=user,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            assert HINT_MARKER not in response.data

    def test_hint_shown_to_author_of_open_public_request(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, visibility="public")
            db.session.commit()
            login_user(client, user.email)

            response = client.get(f"/requests/{req.id}/detail")
            assert response.status_code == 200
            assert HINT_MARKER in response.data

    def test_hint_not_shown_to_other_viewer_of_public_request(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            other_req = ItemRequestFactory(visibility="public")
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_req.user)
            db.session.commit()
            login_user(client, user.email)

            response = client.get(f"/requests/{other_req.id}/detail")
            assert response.status_code == 200
            assert b"share-btn" in response.data
            assert HINT_MARKER not in response.data

    def test_hint_not_shown_for_fulfilled_expired_or_circle_request(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            requests = [
                ItemRequestFactory(
                    user=user,
                    visibility="public",
                    status="fulfilled",
                    fulfilled_at=datetime.now(UTC),
                ),
                ItemRequestFactory(
                    user=user,
                    visibility="public",
                    expires_at=datetime.now(UTC) - timedelta(days=2),
                ),
                ItemRequestFactory(user=user, visibility="circles"),
            ]
            db.session.commit()
            login_user(client, user.email)

            for req in requests:
                response = client.get(f"/requests/{req.id}/detail")
                assert response.status_code == 200
                assert HINT_MARKER not in response.data


class TestShareFieldsConsistency:
    """The flash reminder and the detail page share the same title and text."""

    def test_giveaway_flash_and_detail_share_fields_match(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            flash_response = client.post(
                "/list-item",
                data=_giveaway_data(category, "Matching Lamp", "public"),
                follow_redirects=True,
            )
            item = Item.query.filter_by(name="Matching Lamp").one()
            detail_response = client.get(f"/item/{item.id}")

            for attr in (
                b'data-share-title="Matching Lamp (Free Giveaway)"',
                b'data-share-text="Free giveaway on Meutch: Matching Lamp"',
            ):
                assert attr in flash_response.data
                assert attr in detail_response.data

    def test_request_flash_and_detail_share_fields_match(self, client, app, auth_user):
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            flash_response = client.post(
                "/requests/new",
                data=_request_data("Matching ladder", "public"),
                follow_redirects=True,
            )
            req = ItemRequest.query.filter_by(title="Matching ladder").one()
            detail_response = client.get(f"/requests/{req.id}/detail")

            for attr in (
                b'data-share-title="Matching ladder (Request)"',
                b'data-share-text="Request on Meutch: Matching ladder"',
            ):
                assert attr in flash_response.data
                assert attr in detail_response.data
