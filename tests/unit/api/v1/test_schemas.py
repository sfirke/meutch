"""Unit tests for API Marshmallow schemas."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from marshmallow import ValidationError

from app import db
from app.api.v1.schemas import ItemSummarySchema, UserSummarySchema
from app.api.v1.schemas.circles import CircleWritePayloadSchema
from app.api.v1.schemas.items import ItemWritePayloadSchema
from app.api.v1.schemas.loans import LoanRequestCreateSchema
from app.api.v1.schemas.messaging import MessageStartSchema
from app.api.v1.schemas.profile import LocationUpdateSchema, ProfileUpdateSchema
from app.api.v1.schemas.requests import RequestWritePayloadSchema
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


class TestApiWriteSchemas:
    """Test request-side API schema validation for PR 8 write payloads."""

    def test_request_write_schema_rejects_expiration_beyond_six_months(self):
        schema = RequestWritePayloadSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "title": "Need a hedge trimmer",
                    "expires_at": date.today() + timedelta(days=190),
                    "seeking": "either",
                    "visibility": "circles",
                }
            )

        assert excinfo.value.messages == {
            "expires_at": ["Expiration date cannot be more than 6 months from today."]
        }

    def test_message_start_schema_requires_exactly_one_target(self):
        schema = MessageStartSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "body": "I can help.",
                    "item_id": str(uuid4()),
                    "request_id": str(uuid4()),
                }
            )

        assert excinfo.value.messages == {
            "item_id": ["Provide exactly one of item_id or request_id."],
            "request_id": ["Provide exactly one of item_id or request_id."],
        }

    def test_item_write_schema_requires_giveaway_visibility_for_giveaways(self):
        schema = ItemWritePayloadSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "name": "Leaf blower",
                    "category_id": str(uuid4()),
                    "is_giveaway": True,
                }
            )

        assert excinfo.value.messages == {
            "giveaway_visibility": ["This field is required when is_giveaway is true."]
        }

    def test_location_update_schema_requires_coordinates_for_coordinate_mode(self):
        schema = LocationUpdateSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load({"location_method": "coordinates"})

        assert excinfo.value.messages == {
            "latitude": ["This field is required when location_method is 'coordinates'."],
            "longitude": ["This field is required when location_method is 'coordinates'."],
        }

    def test_profile_update_schema_requires_custom_name_for_other_links(self):
        schema = ProfileUpdateSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "links": [
                        {
                            "platform": "other",
                            "url": "https://example.com/profile",
                        }
                    ]
                }
            )

        assert excinfo.value.messages["links"][0]["custom_name"] == [
            'This field is required when platform is "other".'
        ]

    def test_circle_write_schema_requires_address_fields_for_address_mode(self):
        schema = CircleWritePayloadSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "name": "Tool Neighbors",
                    "circle_type": "open",
                    "location_method": "address",
                }
            )

        assert excinfo.value.messages == {
            "street": ["This field is required when location_method is 'address'."],
            "city": ["This field is required when location_method is 'address'."],
            "state": ["This field is required when location_method is 'address'."],
            "zip_code": ["This field is required when location_method is 'address'."],
            "country": ["This field is required when location_method is 'address'."],
        }

    def test_loan_request_create_schema_rejects_end_before_start(self):
        schema = LoanRequestCreateSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "start_date": date.today() + timedelta(days=10),
                    "end_date": date.today() + timedelta(days=5),
                    "message": "Could I borrow this next week?",
                }
            )

        assert excinfo.value.messages == {
            "end_date": ["End date must be on or after the start date."]
        }

    def test_item_write_schema_rejects_blank_name(self):
        schema = ItemWritePayloadSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "name": "  ",
                    "category_id": str(uuid4()),
                    "is_giveaway": False,
                }
            )

        assert "name" in excinfo.value.messages

    def test_request_write_schema_rejects_blank_title(self):
        schema = RequestWritePayloadSchema()

        with pytest.raises(ValidationError) as excinfo:
            schema.load(
                {
                    "title": "",
                    "expires_at": date.today() + timedelta(days=30),
                    "seeking": "either",
                    "visibility": "circles",
                }
            )

        assert "title" in excinfo.value.messages
