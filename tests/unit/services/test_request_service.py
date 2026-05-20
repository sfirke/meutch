from datetime import UTC, date, datetime, timedelta

import pytest

from app import db
from app.models import ItemRequest
from app.services import request_service
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError
from tests.factories import ItemRequestFactory, UserFactory


class TestRequestService:
    def test_create_request_persists_item_request(self, app):
        with app.app_context():
            owner = UserFactory()
            expires_on = date.today() + timedelta(days=30)

            item_request = request_service.create_request(
                owner,
                "Need a ladder",
                "  For painting  ",
                expires_on,
                "loan",
                "circles",
            )

            db_item_request = db.session.get(ItemRequest, item_request.id)
            assert db_item_request is not None
            assert db_item_request.user_id == owner.id
            assert db_item_request.title == "Need a ladder"
            assert db_item_request.description == "For painting"
            assert db_item_request.expires_at.date() == expires_on
            assert db_item_request.seeking == "loan"
            assert db_item_request.visibility == "circles"
            assert db_item_request.status == "open"

    def test_create_request_rejects_public_request_for_non_geocoded_owner(self, app):
        with app.app_context():
            owner = UserFactory(latitude=None, longitude=None)
            expires_on = date.today() + timedelta(days=30)

            with pytest.raises(InformationalError, match="making a request public"):
                request_service.create_request(
                    owner,
                    "Need a shovel",
                    "Soon",
                    expires_on,
                    "either",
                    "public",
                )

    def test_update_request_updates_request_for_owner(self, app):
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item_request = ItemRequestFactory(user=owner, title="Old title")
            expires_on = date.today() + timedelta(days=45)

            request_service.update_request(
                item_request,
                owner,
                "Updated title",
                "Updated description",
                expires_on,
                "giveaway",
                "public",
            )

            assert item_request.title == "Updated title"
            assert item_request.description == "Updated description"
            assert item_request.expires_at.date() == expires_on
            assert item_request.seeking == "giveaway"
            assert item_request.visibility == "public"

    def test_update_request_rejects_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            other_user = UserFactory()
            item_request = ItemRequestFactory(user=owner)

            with pytest.raises(AuthorizationError):
                request_service.update_request(
                    item_request,
                    other_user,
                    item_request.title,
                    item_request.description,
                    item_request.expires_at.date(),
                    item_request.seeking,
                    item_request.visibility,
                )

    def test_delete_request_marks_request_deleted(self, app):
        with app.app_context():
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, status="open")

            request_service.delete_request(item_request, owner)

            assert item_request.status == "deleted"

    def test_delete_request_rejects_deleted_request(self, app):
        with app.app_context():
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, status="deleted")

            with pytest.raises(ConflictError):
                request_service.delete_request(item_request, owner)

    def test_fulfill_request_marks_request_fulfilled(self, app):
        with app.app_context():
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, status="open", fulfilled_at=None)
            fulfilled_at = datetime.now(UTC)

            request_service.fulfill_request(item_request, owner, fulfilled_at=fulfilled_at)

            assert item_request.status == "fulfilled"
            assert item_request.fulfilled_at == fulfilled_at.replace(tzinfo=None)

    def test_fulfill_request_rejects_already_fulfilled(self, app):
        with app.app_context():
            owner = UserFactory()
            item_request = ItemRequestFactory(user=owner, status="fulfilled")

            with pytest.raises(ConflictError, match="already been fulfilled"):
                request_service.fulfill_request(item_request, owner)
