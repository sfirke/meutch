from unittest.mock import patch

from app import db
from app.models import GiveawayInterest, Item, LoanRequest, Message
from app.services import item_service
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
