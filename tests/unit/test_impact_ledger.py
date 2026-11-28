from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import item_appraiser
from item_appraiser import Appraisal, Condition, Confidence, FootprintCategory, Impact, ResaleDemand
from item_appraiser.climate import appraisal_giveaway_kg_co2e, appraisal_loan_kg_co2e
from item_appraiser.policy import buy_value

from app import db
from app.models import ImpactEvent, ItemAppraisal
from app.services import impact_service
from tests.factories import (
    ImpactEventFactory,
    ItemFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)
from tests.helpers_impact import StubAppraiser


def _appraise(
    item,
    new_price_usd=80.0,
    release_year=None,
    footprint_category=FootprintCategory.SMALL_ELECTRONICS,
):
    appraisal = Appraisal(
        new_price_usd=new_price_usd,
        release_year=release_year,
        condition=Condition.USED,
        resale_demand=ResaleDemand.TYPICAL,
        confidence=Confidence.MEDIUM,
        assumption="Stub estimate.",
        model_version="stub/p1",
        estimated_at=datetime.now(UTC),
        quantity=1,
        footprint_category=footprint_category,
        impacts=frozenset({Impact.MONEY, Impact.CLIMATE}),
        fingerprint="b" * 64,
    )
    row = item.appraisal = ItemAppraisal()
    row.update_from_appraisal(appraisal)
    db.session.flush()


def _filled_event(**kwargs):
    item = kwargs.pop("item", None) or ItemFactory()
    _appraise(item)
    event = ImpactEventFactory(item=item, **kwargs)
    impact_service.fill_event(event, item.appraisal)
    db.session.flush()
    return event


def _claimed_giveaway(claimed_by, claimed_at):
    item = ItemFactory(is_giveaway=True, claim_status="claimed")
    item.claimed_by_id = claimed_by.id if claimed_by else None
    item.claimed_at = claimed_at
    db.session.flush()
    return item


def _completed_loan(end_date, item=None):
    return LoanRequestFactory(
        item=item or ItemFactory(),
        status="completed",
        start_date=end_date - timedelta(days=2),
        end_date=end_date,
    )


class TestFillPendingEvents:
    def test_fills_once_item_is_appraised(self, app):
        with app.app_context():
            event = ImpactEventFactory()
            assert impact_service.fill_pending_events() == 0
            db.session.refresh(event)
            assert event.usd_saved is None

            _appraise(event.item)
            assert impact_service.fill_pending_events() == 1
            db.session.refresh(event)
            assert event.usd_saved is not None
            assert event.model_version == "stub/p1"
            assert impact_service.fill_pending_events() == 0

    def test_event_whose_item_was_deleted_stays_pending(self, app):
        with app.app_context():
            event = ImpactEventFactory()
            db.session.delete(event.item)
            db.session.commit()

            assert impact_service.fill_pending_events() == 0
            db.session.refresh(event)
            assert event.item_id is None
            assert event.usd_saved is None

    def test_unusable_appraisal_does_not_stop_other_fills(self, app):
        with app.app_context():
            bad, good = ImpactEventFactory(), ImpactEventFactory()
            _appraise(bad.item)
            _appraise(good.item)
            bad.item.appraisal.condition = "retired"
            db.session.commit()

            assert impact_service.fill_pending_events() == 1
            db.session.refresh(bad)
            db.session.refresh(good)
            assert bad.usd_saved is None
            assert good.usd_saved is not None

    def test_reprices_event_when_model_version_changes(self, app):
        with app.app_context():
            event = _filled_event()
            old_usd = event.usd_saved
            event.item.appraisal.new_price_usd = 200
            event.item.appraisal.model_version = "stub/p2"
            db.session.commit()

            assert impact_service.fill_pending_events() == 1
            db.session.refresh(event)
            assert event.usd_saved > old_usd
            assert event.model_version == "stub/p2"

    def test_item_edit_with_same_model_version_keeps_event_value(self, app):
        with app.app_context():
            event = _filled_event()
            old_usd = event.usd_saved
            event.item.appraisal.new_price_usd = 200
            db.session.commit()

            assert impact_service.fill_pending_events() == 0
            db.session.refresh(event)
            assert event.usd_saved == old_usd


class TestFillEventPricesByAge:
    def test_device_is_valued_as_of_when_the_event_happened(self, app):
        with app.app_context():
            past = datetime(2024, 6, 1, 12, tzinfo=UTC)
            then_item, now_item = ItemFactory(), ItemFactory()
            _appraise(then_item, new_price_usd=800.0, release_year=2019)
            _appraise(now_item, new_price_usd=800.0, release_year=2019)
            then_event = ImpactEventFactory(
                item=then_item, kind=ImpactEvent.KIND_GIVEAWAY, occurred_at=past
            )
            now_event = ImpactEventFactory(item=now_item, kind=ImpactEvent.KIND_GIVEAWAY)

            impact_service.fill_event(then_event, then_item.appraisal)
            impact_service.fill_event(now_event, now_item.appraisal)

            expected = buy_value(800.0, Condition.USED, ResaleDemand.TYPICAL, 2019, past.date())
            assert then_event.usd_saved == expected
            assert then_event.release_year == 2019
            assert then_event.usd_saved > now_event.usd_saved

    def test_old_phone_co2_is_reduced_as_of_when_the_event_happened(self, app):
        with app.app_context():
            past = datetime(2024, 6, 1, 12, tzinfo=UTC)

            def filled(kind, **kwargs):
                item = ItemFactory()
                _appraise(
                    item,
                    new_price_usd=399.0,
                    release_year=2019,
                    footprint_category=FootprintCategory.SMARTPHONE,
                )
                event = ImpactEventFactory(item=item, kind=kind, **kwargs)
                impact_service.fill_event(event, item.appraisal)
                return event, item.appraisal.to_appraisal()

            for kind, kg_co2e in (
                (ImpactEvent.KIND_GIVEAWAY, appraisal_giveaway_kg_co2e),
                (ImpactEvent.KIND_LOAN, appraisal_loan_kg_co2e),
            ):
                then_event, appraisal = filled(kind, occurred_at=past)
                now_event, _ = filled(kind)
                unaged = replace(appraisal, release_year=None)

                expected = kg_co2e(appraisal, past.date())
                assert then_event.kg_co2e_avoided == expected
                assert expected < kg_co2e(unaged)
                assert then_event.kg_co2e_avoided > now_event.kg_co2e_avoided


class TestAppraiseCommandFillsEvents:
    def test_reports_filled_count(self, app):
        with app.app_context():
            ImpactEventFactory()
            db.session.commit()
            with patch("app.services.impact_service.build_appraiser", return_value=StubAppraiser()):
                result = app.test_cli_runner().invoke(args=["impact", "appraise"])

            assert result.exit_code == 0, result.output
            assert "Impact events filled or re-priced: 1" in result.output
            assert ImpactEvent.query.filter(ImpactEvent.usd_saved.is_(None)).count() == 0


class TestBackfillEvents:
    def test_creates_loan_event(self, app):
        with app.app_context():
            loan = _completed_loan(date(2026, 3, 5))
            db.session.commit()

            summary = impact_service.backfill_events()

            assert (summary.loans, summary.giveaways) == (1, 0)
            event = ImpactEvent.query.one()
            assert event.kind == ImpactEvent.KIND_LOAN
            assert event.loan_request_id == loan.id
            assert event.item_id == loan.item_id
            assert event.beneficiary_id == loan.borrower_id
            assert event.provider_id == loan.item.owner_id
            assert event.occurred_at == datetime(2026, 3, 5, 12, tzinfo=UTC)
            assert event.usd_saved is None

    def test_loan_event_dated_by_when_it_was_marked_returned(self, app):
        with app.app_context():
            loan = _completed_loan(date(2026, 3, 5))
            MessageFactory(loan_request_id=loan.id, timestamp=datetime(2026, 3, 1, 8))
            MessageFactory(loan_request_id=loan.id, timestamp=datetime(2026, 3, 20, 10, 30))
            db.session.commit()

            impact_service.backfill_events()

            assert ImpactEvent.query.one().occurred_at == datetime(2026, 3, 20, 10, 30, tzinfo=UTC)

    def test_loan_event_is_never_dated_in_the_future(self, app):
        with app.app_context():
            _completed_loan(date.today() + timedelta(days=30))
            db.session.commit()

            impact_service.backfill_events()

            assert ImpactEvent.query.one().occurred_at <= datetime.now(UTC)

    def test_creates_giveaway_events(self, app):
        with app.app_context():
            recipient = UserFactory()
            claimed_at = datetime(2026, 2, 3, 9, 15)
            with_recipient = _claimed_giveaway(recipient, claimed_at)
            no_recipient = _claimed_giveaway(None, claimed_at)
            no_claimed_at = _claimed_giveaway(recipient, None)
            db.session.commit()

            summary = impact_service.backfill_events()

            assert summary.giveaways == 3
            by_item = {e.item_id: e for e in ImpactEvent.query.all()}
            first = by_item[with_recipient.id]
            assert first.kind == ImpactEvent.KIND_GIVEAWAY
            assert first.beneficiary_id == recipient.id
            assert first.provider_id == with_recipient.owner_id
            assert first.occurred_at == claimed_at.replace(tzinfo=UTC)
            assert by_item[no_recipient.id].beneficiary_id is None
            assert by_item[no_claimed_at.id].occurred_at == (
                no_claimed_at.created_at.replace(tzinfo=UTC)
            )

    def test_fills_events_for_appraised_items(self, app):
        with app.app_context():
            item = ItemFactory()
            _appraise(item)
            _completed_loan(date(2026, 3, 5), item=item)
            db.session.commit()

            summary = impact_service.backfill_events()

            assert summary.filled == 1
            assert ImpactEvent.query.one().usd_saved is not None

    def test_skips_ineligible_and_existing(self, app):
        with app.app_context():
            done = _completed_loan(date(2026, 3, 5))
            ImpactEventFactory(item=done.item, loan_request_id=done.id)
            LoanRequestFactory(status="approved")
            ItemFactory(is_giveaway=True)
            claimed = _claimed_giveaway(UserFactory(), datetime(2026, 2, 3))
            ImpactEventFactory(item=claimed, kind=ImpactEvent.KIND_GIVEAWAY)
            db.session.commit()
            before = ImpactEvent.query.count()

            summary = impact_service.backfill_events()

            assert (summary.loans, summary.giveaways) == (0, 0)
            assert ImpactEvent.query.count() == before

    def test_dry_run_writes_nothing(self, app):
        with app.app_context():
            _completed_loan(date(2026, 3, 5))
            _claimed_giveaway(UserFactory(), datetime(2026, 2, 3))
            db.session.commit()

            result = app.test_cli_runner().invoke(args=["impact", "backfill-events", "--dry-run"])

            assert result.exit_code == 0, result.output
            assert "1 loan event(s), 1 giveaway event(s)" in result.output
            assert ImpactEvent.query.count() == 0

    def test_command_creates_events(self, app):
        with app.app_context():
            _completed_loan(date(2026, 3, 5))
            db.session.commit()

            result = app.test_cli_runner().invoke(args=["impact", "backfill-events"])

            assert result.exit_code == 0, result.output
            assert "Created 1 loan event(s)" in result.output
            assert ImpactEvent.query.count() == 1


class TestRepriceEvents:
    def _stale_old_phone_event(self, kind, occurred_at):
        """An old phone's event valued under 0.2.0, which ignored age for CO2."""
        item = ItemFactory()
        _appraise(
            item,
            new_price_usd=399.0,
            release_year=2019,
            footprint_category=FootprintCategory.SMARTPHONE,
        )
        appraisal = item.appraisal.to_appraisal()
        event = ImpactEventFactory(item=item, kind=kind, occurred_at=occurred_at)
        impact_service.fill_event(event, item.appraisal)
        unaged = replace(appraisal, release_year=None)
        stale = (
            appraisal_loan_kg_co2e if kind == ImpactEvent.KIND_LOAN else appraisal_giveaway_kg_co2e
        )
        event.kg_co2e_avoided = stale(unaged)
        event.policy_version = "0.2.0"
        db.session.flush()
        return event, appraisal

    def test_reprices_old_phone_co2_as_of_event_date_even_after_item_deleted(self, app):
        with app.app_context():
            past = datetime(2024, 6, 1, 12, tzinfo=UTC)
            giveaway, appraisal = self._stale_old_phone_event(ImpactEvent.KIND_GIVEAWAY, past)
            loan, _ = self._stale_old_phone_event(ImpactEvent.KIND_LOAN, past)
            usd_before = giveaway.usd_saved
            db.session.delete(giveaway.item)
            db.session.commit()

            summary = impact_service.reprice_events()

            assert (summary.repriced, summary.changed) == (2, 2)
            db.session.expire_all()
            assert giveaway.item_id is None
            assert giveaway.kg_co2e_avoided == Decimal(
                str(appraisal_giveaway_kg_co2e(appraisal, past.date()))
            )
            assert loan.kg_co2e_avoided == Decimal(
                str(appraisal_loan_kg_co2e(appraisal, past.date()))
            )
            assert giveaway.usd_saved == Decimal(str(usd_before))
            assert {giveaway.policy_version, loan.policy_version} == {item_appraiser.__version__}

    def test_leaves_current_and_pending_events_alone(self, app):
        with app.app_context():
            current = _filled_event()
            ImpactEventFactory()
            db.session.commit()
            kg_before = current.kg_co2e_avoided

            summary = impact_service.reprice_events()

            assert summary.repriced == 0
            db.session.refresh(current)
            assert current.kg_co2e_avoided == Decimal(str(kg_before))

    def test_unchanged_value_is_repriced_but_not_counted_as_changed(self, app):
        with app.app_context():
            event = _filled_event()
            event.policy_version = "0.1.1"
            db.session.commit()

            summary = impact_service.reprice_events()

            assert (summary.repriced, summary.changed) == (1, 0)
            db.session.refresh(event)
            assert event.policy_version == item_appraiser.__version__

    def test_dry_run_command_writes_nothing(self, app):
        with app.app_context():
            event, _ = self._stale_old_phone_event(
                ImpactEvent.KIND_GIVEAWAY, datetime(2024, 6, 1, 12, tzinfo=UTC)
            )
            db.session.commit()
            kg_before = event.kg_co2e_avoided

            result = app.test_cli_runner().invoke(args=["impact", "reprice-events", "--dry-run"])

            assert result.exit_code == 0, result.output
            assert "would re-price 1 event(s); 1 with a new value" in result.output
            db.session.expire_all()
            assert event.kg_co2e_avoided == Decimal(str(kg_before))
            assert event.policy_version == "0.2.0"


class TestTotals:
    def test_empty_totals_are_zero(self, app):
        with app.app_context():
            assert impact_service.site_totals() == (0, 0, 0)
            assert impact_service.user_totals(UserFactory().id) == (0, 0, 0, 0)

    def test_site_totals_count_only_filled_events(self, app):
        with app.app_context():
            events = [_filled_event(), _filled_event(beneficiary=UserFactory())]
            ImpactEventFactory()
            db.session.commit()

            totals = impact_service.site_totals()

            assert totals.event_count == 2
            assert totals.usd == sum(e.usd_saved for e in events)
            assert totals.kg == sum(e.kg_co2e_avoided for e in events)
            assert totals.usd > 0

    def test_user_totals_split_saved_and_helped(self, app):
        with app.app_context():
            me, other = UserFactory(), UserFactory()
            saved = [_filled_event(beneficiary=me) for _ in range(2)]
            helped = _filled_event(item=ItemFactory(owner=me), beneficiary=other)
            orphan = _filled_event(item=ItemFactory(owner=me), beneficiary=None)
            ImpactEventFactory(beneficiary=me)
            db.session.commit()

            mine = impact_service.user_totals(me.id)

            assert mine.saved_usd == sum(e.usd_saved for e in saved)
            assert mine.saved_kg == sum(e.kg_co2e_avoided for e in saved)
            assert mine.helped_usd == helped.usd_saved + orphan.usd_saved
            assert mine.helped_kg == helped.kg_co2e_avoided + orphan.kg_co2e_avoided
            assert impact_service.user_totals(other.id).saved_usd == helped.usd_saved

    def test_date_range_start_inclusive_end_exclusive(self, app):
        with app.app_context():
            me = UserFactory()
            start = datetime(2026, 1, 1, tzinfo=UTC)
            end = datetime(2027, 1, 1, tzinfo=UTC)
            before = _filled_event(beneficiary=me, occurred_at=start - timedelta(seconds=1))
            at_start = _filled_event(beneficiary=me, occurred_at=start)
            inside = _filled_event(beneficiary=me, occurred_at=start + timedelta(days=100))
            at_end = _filled_event(beneficiary=me, occurred_at=end)
            db.session.commit()

            windowed = impact_service.user_totals(me.id, start=start, end=end)
            assert windowed.saved_usd == at_start.usd_saved + inside.usd_saved
            assert windowed.saved_kg == at_start.kg_co2e_avoided + inside.kg_co2e_avoided
            everything = impact_service.user_totals(me.id)
            assert everything.saved_usd == sum(
                e.usd_saved for e in (before, at_start, inside, at_end)
            )
            assert impact_service.user_totals(me.id, start=end).saved_usd == at_end.usd_saved
