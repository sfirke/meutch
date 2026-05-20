from unittest.mock import patch

import pytest

from app import db
from app.models import GiveawayInterest, Item, LoanRequest, Message
from app.services import item_service
from app.services.exceptions import ConflictError, InformationalError
from tests.factories import (
    CategoryFactory,
    GiveawayInterestFactory,
    ItemFactory,
    ItemImageFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestItemService:
    def test_create_item_creates_images_and_tags(self, app):
        with app.app_context():
            owner = UserFactory()
            category = CategoryFactory()

            with patch(
                "app.services.item_service.upload_item_images",
                return_value=["https://example.com/1.jpg", "https://example.com/2.jpg"],
            ) as mock_upload:
                item = item_service.create_item(
                    owner,
                    "Cordless Drill",
                    "Still works great",
                    category.id,
                    False,
                    None,
                    "Drill, Repair",
                    [object(), object()],
                )

            db_item = db.session.get(Item, item.id)
            assert db_item is not None
            assert [image.url for image in db_item.images] == [
                "https://example.com/1.jpg",
                "https://example.com/2.jpg",
            ]
            assert {tag.name for tag in db_item.tags} == {"drill", "repair"}
            mock_upload.assert_called_once()

    def test_create_item_rejects_public_giveaway_for_non_geocoded_owner(self, app):
        with app.app_context():
            owner = UserFactory(latitude=None, longitude=None)
            category = CategoryFactory()

            with pytest.raises(InformationalError, match="making a giveaway public"):
                item_service.create_item(
                    owner,
                    "Street Table",
                    "Free to a good home",
                    category.id,
                    True,
                    "public",
                    "",
                    [],
                )

    def test_update_item_reorders_images_and_replaces_tags(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=False)
            first_image = ItemImageFactory(item=item, position=0)
            second_image = ItemImageFactory(item=item, position=1)

            item_service.update_item(
                item,
                "Updated name",
                "Updated description",
                item.category_id,
                False,
                None,
                "repair, toolkit",
                [],
                [],
                [str(second_image.id), str(first_image.id)],
            )

            assert item.name == "Updated name"
            assert [image.id for image in item.images] == [second_image.id, first_image.id]
            assert [image.position for image in item.images] == [0, 1]
            assert {tag.name for tag in item.tags} == {"repair", "toolkit"}

    def test_delete_item_with_cleanup_removes_related_records(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=False)
            image = ItemImageFactory(item=item)
            borrower = UserFactory()
            LoanRequestFactory(item=item, borrower=borrower, status="pending")
            GiveawayInterestFactory(item=item, status="active")
            MessageFactory(sender=borrower, recipient=item.owner, item=item, body="Interested")

            with patch("app.services.item_service.delete_item_images") as mock_delete_images:
                item_service.delete_item_with_cleanup(item)

            assert db.session.get(Item, item.id) is None
            assert LoanRequest.query.count() == 0
            assert GiveawayInterest.query.count() == 0
            assert Message.query.count() == 0
            mock_delete_images.assert_called_once_with([image.url])

    def test_update_item_rejects_giveaway_conversion_with_active_loan(self, app):
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            borrower = UserFactory()
            LoanRequestFactory(item=item, borrower=borrower, status="approved")

            with pytest.raises(ConflictError, match="active loan"):
                item_service.update_item(
                    item,
                    item.name,
                    item.description,
                    item.category_id,
                    True,
                    "public",
                    "",
                    [],
                    [],
                    [],
                )

    def test_update_item_rejects_loan_conversion_with_interested_users(self, app):
        with app.app_context():
            item = ItemFactory(
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            GiveawayInterestFactory(item=item, status="active")

            with pytest.raises(ConflictError, match="interested users"):
                item_service.update_item(
                    item,
                    item.name,
                    item.description,
                    item.category_id,
                    False,
                    None,
                    "",
                    [],
                    [],
                    [],
                )

    def test_get_item_delete_blocker_returns_active_loan(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=False, available=False)
            borrower = UserFactory()
            loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")

            blocker_type, blocking_loan = item_service.get_item_delete_blocker(item)

            assert blocker_type == "active_loan"
            assert blocking_loan.id == loan.id
