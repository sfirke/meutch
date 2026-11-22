from datetime import datetime, timedelta

import pytest

from app import db
from app.models import ItemAppraisal
from app.services import impact_service
from tests.factories import ItemAppraisalFactory, ItemFactory, ItemImageFactory
from tests.helpers_impact import StubAppraiser


def _items(count):
    base = datetime(2026, 1, 1)
    items = [
        ItemFactory(name=f"Item {i}", created_at=base + timedelta(days=i)) for i in range(count)
    ]
    db.session.commit()
    return items


class TestListingFor:
    def test_builds_listing_from_item(self, app):
        with app.app_context():
            item = ItemFactory(name="Drill", description="18V")
            ItemImageFactory(item=item, url="https://img/2", position=1)
            ItemImageFactory(item=item, url="https://img/1", position=0)
            db.session.commit()

            listing = impact_service.listing_for(item)

            assert listing.name == "Drill"
            assert listing.description == f"18V\n\nCategory: {item.category.name}"
            assert listing.image_urls == ("https://img/1", "https://img/2")
            assert listing.item_id == str(item.id)


class TestAppraisePending:
    def test_new_item_is_appraised(self, app):
        with app.app_context():
            (item,) = _items(1)
            stub = StubAppraiser()

            summary = impact_service.appraise_pending(10, stub)

            assert summary.appraised == 1
            row = ItemAppraisal.query.filter_by(item_id=item.id).one()
            assert row.fingerprint == stub.fingerprint(impact_service.listing_for(item))

    def test_unchanged_item_is_skipped(self, app):
        with app.app_context():
            (item,) = _items(1)
            stub = StubAppraiser()
            impact_service.appraise_pending(10, stub)
            stub.appraised_names.clear()

            summary = impact_service.appraise_pending(10, stub)

            assert (summary.appraised, summary.skipped) == (0, 1)
            assert stub.appraised_names == []

    def test_edited_item_is_reappraised(self, app):
        with app.app_context():
            (item,) = _items(1)
            stub = StubAppraiser()
            impact_service.appraise_pending(10, stub)
            item.description = "Now with a case"
            db.session.commit()

            summary = impact_service.appraise_pending(10, stub)

            assert summary.appraised == 1
            assert ItemAppraisal.query.filter_by(item_id=item.id).count() == 1
            assert not impact_service.needs_appraisal(item, stub)

    def test_error_on_one_item_does_not_stop_others(self, app):
        with app.app_context():
            _items(3)
            stub = StubAppraiser(fail_for={"Item 1"})

            summary = impact_service.appraise_pending(10, stub)

            assert (summary.appraised, summary.failed) == (2, 1)
            assert ItemAppraisal.query.count() == 2

    def test_limit_is_respected_oldest_first(self, app):
        with app.app_context():
            _items(3)
            stub = StubAppraiser()

            summary = impact_service.appraise_pending(2, stub)

            assert summary.appraised == 2
            assert stub.appraised_names == ["Item 0", "Item 1"]

    def test_dry_run_estimates_without_appraising(self, app):
        with app.app_context():
            _items(3)
            ItemAppraisalFactory(item=ItemFactory(name="Done"))
            db.session.commit()
            stub = StubAppraiser()

            summary = impact_service.appraise_pending(2, stub, dry_run=True)

            assert summary.pending == 2
            assert summary.estimated_cost_usd == pytest.approx(0.006)
            assert stub.appraised_names == []


class TestBuildAppraiser:
    def test_unknown_provider_raises(self, app):
        with app.app_context():
            app.config["IMPACT_APPRAISER_PROVIDER"] = "nope"
            with pytest.raises(ValueError):
                impact_service.build_appraiser()

    @pytest.mark.parametrize("provider", ["claude", "deepseek"])
    def test_builds_provider_appraiser(self, app, provider):
        with app.app_context():
            app.config.update(
                IMPACT_APPRAISER_PROVIDER=provider,
                ANTHROPIC_API_KEY="test-key",
                DEEPSEEK_API_KEY="test-key",
            )
            assert impact_service.build_appraiser().fingerprint
