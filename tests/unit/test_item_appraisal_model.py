"""Unit tests for the ItemAppraisal model."""

from datetime import UTC, datetime
from unittest.mock import patch

from item_appraiser import Appraisal, Condition, Confidence, FootprintCategory, Impact, ResaleDemand

from app import db
from app.models import Item, ItemAppraisal
from app.services import item_service
from tests.factories import ItemAppraisalFactory, ItemFactory


def _stub_appraisal(**overrides):
    values = dict(
        new_price_usd=119.99,
        condition=Condition.LIKE_NEW,
        resale_demand=ResaleDemand.WEAK,
        confidence=Confidence.HIGH,
        assumption="Priced as a set of 4 rackets.",
        model_version="stub/p4+img+qty",
        estimated_at=datetime(2026, 11, 1, 12, 30, tzinfo=UTC),
        quantity=4,
        unit_new_price_usd=29.9975,
        footprint_category=FootprintCategory.SMALL_ELECTRONICS,
        impacts=frozenset({Impact.MONEY, Impact.CLIMATE}),
        fingerprint="a" * 64,
        model_fingerprint="fp_123",
        release_year=2019,
    )
    values.update(overrides)
    return Appraisal(**values)


class TestItemAppraisalModel:
    def test_round_trips_appraisal(self, app):
        with app.app_context():
            item = ItemFactory()
            original = _stub_appraisal()
            row = item.appraisal = ItemAppraisal()
            row.update_from_appraisal(original)
            db.session.commit()
            db.session.expire_all()

            rebuilt = db.session.get(ItemAppraisal, row.id).to_appraisal()

            assert rebuilt == original
            assert rebuilt.to_dict() == original.to_dict()
            assert item.appraisal.id == row.id

    def test_round_trips_money_only_appraisal_without_optional_fields(self, app):
        with app.app_context():
            item = ItemFactory()
            original = Appraisal(new_price_usd=40.0, condition=Condition.USED, fingerprint="b" * 64)
            row = item.appraisal = ItemAppraisal()
            row.update_from_appraisal(original)
            db.session.commit()
            db.session.expire_all()

            assert db.session.get(ItemAppraisal, row.id).to_appraisal() == original

    def test_update_overwrites_existing_row(self, app):
        with app.app_context():
            row = ItemAppraisalFactory()
            db.session.commit()
            updated = _stub_appraisal(new_price_usd=50.0, fingerprint="c" * 64)

            row.update_from_appraisal(updated)
            db.session.commit()
            db.session.expire_all()

            assert ItemAppraisal.query.count() == 1
            assert db.session.get(ItemAppraisal, row.id).to_appraisal() == updated

    def test_every_footprint_category_fits(self, app):
        with app.app_context():
            for category in FootprintCategory:
                row = ItemAppraisalFactory(footprint_category=category.value)
                db.session.flush()
                db.session.expire(row)
                assert row.to_appraisal().footprint_category == category

    def test_orm_cascade_removes_loaded_appraisal(self, app):
        with app.app_context():
            row = ItemAppraisalFactory()
            db.session.commit()
            item, row_id = row.item, row.id
            assert item.appraisal is row

            with patch("app.services.item_service.delete_item_images"):
                item_service.delete_item_with_cleanup(item)

            assert db.session.get(ItemAppraisal, row_id) is None

    def test_database_cascade_removes_appraisal_when_not_loaded(self, app):
        with app.app_context():
            row = ItemAppraisalFactory()
            db.session.commit()
            item_id, row_id = row.item_id, row.id
            db.session.expunge_all()

            with patch("app.services.item_service.delete_item_images"):
                item_service.delete_item_with_cleanup(db.session.get(Item, item_id))

            assert db.session.get(ItemAppraisal, row_id) is None
