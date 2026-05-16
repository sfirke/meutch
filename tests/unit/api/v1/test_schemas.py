"""Unit tests for API Marshmallow schemas."""

from datetime import UTC, datetime

from app import db
from app.api.v1.schemas import ItemSummarySchema, UserSummarySchema
from tests.factories import CategoryFactory, ItemFactory, ItemImageFactory, TagFactory, UserFactory


class TestApiSchemas:
    """Test shared API schema serialization behavior."""

    def test_user_summary_schema_excludes_private_fields(self, app):
        """Nested user payloads should stay compact and privacy-safe."""
        with app.app_context():
            user = UserFactory(
                first_name="Ada",
                last_name="Lovelace",
                email="ada@example.com",
                profile_image_url="https://example.com/profiles/ada.png",
            )

            payload = UserSummarySchema().dump(user)

        assert payload == {
            "id": str(user.id),
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "profile_image_url": "https://example.com/profiles/ada.png",
        }
        assert "email" not in payload
        assert "password_hash" not in payload

    def test_item_summary_schema_serializes_nested_resources_and_iso_datetimes(self, app):
        """Item schemas should serialize nested resources with stable ordering."""
        created_at = datetime(2026, 5, 15, 12, 30, tzinfo=UTC)

        with app.app_context():
            owner = UserFactory(
                first_name="Grace",
                last_name="Hopper",
                profile_image_url="https://example.com/profiles/grace.png",
            )
            category = CategoryFactory(name="Garden Tools")
            item = ItemFactory(
                owner=owner,
                category=category,
                name="Hedge Trimmer",
                description="Cordless and freshly charged.",
                available=True,
                is_giveaway=False,
                created_at=created_at,
            )
            item.tags.extend(
                [
                    TagFactory(name="zeta"),
                    TagFactory(name="alpha"),
                ]
            )
            ItemImageFactory(
                item=item, position=0, url="https://example.com/items/hedge-trimmer.jpg"
            )
            db.session.flush()

            payload = ItemSummarySchema().dump(item)

        assert payload == {
            "id": str(item.id),
            "name": "Hedge Trimmer",
            "description": "Cordless and freshly charged.",
            "available": True,
            "is_giveaway": False,
            "giveaway_visibility": None,
            "claim_status": None,
            "created_at": "2026-05-15T12:30:00+00:00",
            "image_url": "https://example.com/items/hedge-trimmer.jpg",
            "owner": {
                "id": str(owner.id),
                "first_name": "Grace",
                "last_name": "Hopper",
                "full_name": "Grace Hopper",
                "profile_image_url": "https://example.com/profiles/grace.png",
            },
            "category": {
                "id": str(category.id),
                "name": "Garden Tools",
            },
            "tags": [
                {
                    "id": str(item.tags[1].id),
                    "name": "alpha",
                },
                {
                    "id": str(item.tags[0].id),
                    "name": "zeta",
                },
            ],
        }

    def test_item_summary_schema_allows_missing_image_url(self, app):
        """Items without uploaded images should serialize a null image URL."""
        with app.app_context():
            item = ItemFactory(created_at=datetime(2026, 5, 15, 9, 0, tzinfo=UTC))
            db.session.flush()

            payload = ItemSummarySchema().dump(item)

        assert payload["image_url"] is None
