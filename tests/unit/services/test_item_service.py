import uuid
from unittest.mock import patch

import pytest

from app import db
from app.models import GiveawayInterest, Item, LoanRequest, Message
from app.services import item_service
from app.services.exceptions import ConflictError, InformationalError
from app.utils.storage import MAX_ITEM_IMAGE_COUNT
from tests.factories import (
    CategoryFactory,
    ConversationFactory,
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
                result = item_service.create_item(
                    owner,
                    "Cordless Drill",
                    "Still works great",
                    category.id,
                    False,
                    None,
                    "Drill, Repair",
                    [object(), object()],
                )

            assert result.was_created is True

            db_item = db.session.get(Item, result.item.id)
            assert db_item is not None
            assert [image.url for image in db_item.images] == [
                "https://example.com/1.jpg",
                "https://example.com/2.jpg",
            ]
            assert {tag.name for tag in db_item.tags} == {"drill", "repair"}
            mock_upload.assert_called_once()

    def test_create_item_accepts_api_tag_list_and_optional_description(self, app):
        with app.app_context():
            owner = UserFactory()
            category = CategoryFactory()

            result = item_service.create_item(
                owner,
                "  Cordless Drill  ",
                None,
                category.id,
                False,
                None,
                [" Drill ", "repair", "drill"],
                [],
            )

            db_item = db.session.get(Item, result.item.id)
            assert db_item.name == "Cordless Drill"
            assert db_item.description is None
            assert {tag.name for tag in db_item.tags} == {"drill", "repair"}

    def test_create_item_rejects_when_image_count_exceeds_limit(self, app):
        with app.app_context():
            owner = UserFactory()
            category = CategoryFactory()

            with patch("app.services.item_service.upload_item_images") as mock_upload_images:
                with pytest.raises(InformationalError, match="Maximum 8 images"):
                    item_service.create_item(
                        owner,
                        "Cordless Drill",
                        "Still works great",
                        category.id,
                        False,
                        None,
                        [],
                        [object()] * (MAX_ITEM_IMAGE_COUNT + 1),
                    )

            mock_upload_images.assert_not_called()

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

    def test_create_item_reuses_existing_item_when_creation_token_already_exists(self, app):
        with app.app_context():
            owner = UserFactory()
            category = CategoryFactory()
            creation_token = uuid.uuid4()

            existing_item = ItemFactory(
                owner=owner,
                category=category,
                creation_token=creation_token,
                name="Cordless Drill",
            )
            db.session.commit()

            with patch("app.services.item_service.upload_item_images") as mock_upload_images:
                result = item_service.create_item(
                    owner,
                    "Cordless Drill",
                    "Still works great",
                    category.id,
                    False,
                    None,
                    "Drill, Repair",
                    [object()],
                    creation_token=creation_token,
                )

            assert result.was_created is False
            assert result.item.id == existing_item.id
            assert db.session.get(Item, existing_item.id) is not None
            assert (
                Item.query.filter_by(owner_id=owner.id, creation_token=creation_token).count() == 1
            )
            mock_upload_images.assert_not_called()

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
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            MessageFactory(
                sender=borrower, recipient=item.owner, conversation=conversation, body="Interested"
            )

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

    def test_update_item_rejects_giveaway_conversion_with_pending_loan(self, app):
        with app.app_context():
            owner = UserFactory(latitude=40.7128, longitude=-74.0060)
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)
            borrower = UserFactory()
            LoanRequestFactory(item=item, borrower=borrower, status="pending")

            with pytest.raises(ConflictError, match="pending loan request"):
                item_service.update_item(
                    item,
                    item.name,
                    item.description,
                    item.category_id,
                    True,
                    "public",
                    [],
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

    def test_update_item_rejects_loan_conversion_when_pending_pickup(self, app):
        with app.app_context():
            item = ItemFactory(
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
            )

            with pytest.raises(ConflictError, match="pending pickup"):
                item_service.update_item(
                    item,
                    item.name,
                    item.description,
                    item.category_id,
                    False,
                    None,
                    [],
                    [],
                    [],
                    [],
                )

    def test_update_item_rejects_loan_conversion_when_claimed(self, app):
        with app.app_context():
            item = ItemFactory(
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
            )

            with pytest.raises(ConflictError, match="already been handed off"):
                item_service.update_item(
                    item,
                    item.name,
                    item.description,
                    item.category_id,
                    False,
                    None,
                    [],
                    [],
                    [],
                    [],
                )

    def test_append_item_images_appends_uploaded_images(self, app):
        with app.app_context():
            item = ItemFactory()
            original_image = ItemImageFactory(
                item=item, position=0, url="https://example.com/1.jpg"
            )

            with patch(
                "app.services.item_service.upload_item_images",
                return_value=["https://example.com/2.jpg", "https://example.com/3.jpg"],
            ) as mock_upload:
                item_service.append_item_images(item, item.owner, [object(), object()])

            db_item = db.session.get(Item, item.id)
            assert [image.url for image in db_item.images] == [
                original_image.url,
                "https://example.com/2.jpg",
                "https://example.com/3.jpg",
            ]
            assert [image.position for image in db_item.images] == [0, 1, 2]
            mock_upload.assert_called_once()

    def test_append_item_images_rejects_when_limit_exceeded(self, app):
        with app.app_context():
            item = ItemFactory()
            for position in range(MAX_ITEM_IMAGE_COUNT):
                ItemImageFactory(item=item, position=position)

            with patch("app.services.item_service.upload_item_images") as mock_upload_images:
                with pytest.raises(InformationalError, match="Maximum 8 images"):
                    item_service.append_item_images(item, item.owner, [object()])

            mock_upload_images.assert_not_called()

    def test_append_item_images_does_not_corrupt_existing_images_when_upload_fails(self, app):
        with app.app_context():
            item = ItemFactory()
            existing_image = ItemImageFactory(item=item, position=0)

            with patch(
                "app.services.item_service.upload_item_images",
                side_effect=ValueError("upload failed"),
            ):
                with pytest.raises(ValueError, match="upload failed"):
                    item_service.append_item_images(item, item.owner, [object()])

            db_item = db.session.get(Item, item.id)
            assert [image.id for image in db_item.images] == [existing_image.id]

    def test_reorder_item_images_requires_exact_existing_ids(self, app):
        with app.app_context():
            item = ItemFactory()
            first_image = ItemImageFactory(item=item, position=0)
            ItemImageFactory(item=item, position=1)

            with pytest.raises(InformationalError, match="exactly once"):
                item_service.reorder_item_images(item, item.owner, [first_image.id, first_image.id])

    def test_delete_item_image_reorders_remaining_images_and_cleans_up_storage(self, app):
        with app.app_context():
            item = ItemFactory()
            first_image = ItemImageFactory(item=item, position=0)
            second_image = ItemImageFactory(item=item, position=1)
            third_image = ItemImageFactory(item=item, position=2)

            with patch("app.services.item_service.delete_item_images") as mock_delete_images:
                item_service.delete_item_image(item, second_image, item.owner)

            db_item = db.session.get(Item, item.id)
            assert [image.id for image in db_item.images] == [first_image.id, third_image.id]
            assert [image.position for image in db_item.images] == [0, 1]
            mock_delete_images.assert_called_once_with([second_image.url])

    def test_get_item_delete_blocker_returns_active_loan(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=False, available=False)
            borrower = UserFactory()
            loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")

            blocker_type, blocking_loan = item_service.get_item_delete_blocker(item)

            assert blocker_type == "active_loan"
            assert blocking_loan.id == loan.id

    def test_delete_item_rejects_pending_pickup_giveaway(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=True, claim_status="pending_pickup")

            with pytest.raises(ConflictError, match="pending pickup"):
                item_service.delete_item(item, item.owner)

    def test_delete_item_rejects_claimed_giveaway(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=True, claim_status="claimed")

            with pytest.raises(ConflictError, match="claimed and handed off"):
                item_service.delete_item(item, item.owner)
