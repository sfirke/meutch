"""Integration tests for impact events recorded when loans and giveaways complete."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import item_appraiser
import pytest
from item_appraiser import Appraisal, Condition, Confidence, FootprintCategory, Impact, ResaleDemand
from item_appraiser.climate import appraisal_giveaway_kg_co2e, appraisal_loan_kg_co2e
from item_appraiser.policy import appraisal_buy_value, appraisal_loan_value
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import ImpactEvent, Item, ItemAppraisal, LoanRequest
from app.services import giveaway_service, loan_service
from app.services.exceptions import ConflictError
from conftest import login_user
from tests.factories import ImpactEventFactory, ItemFactory, LoanRequestFactory, UserFactory

from .api_test_helpers import auth_headers, login_api_user


def _stub_appraisal():
    return Appraisal(
        new_price_usd=119.99,
        condition=Condition.LIKE_NEW,
        resale_demand=ResaleDemand.TYPICAL,
        confidence=Confidence.HIGH,
        assumption="Priced as a mid-range cordless drill.",
        model_version="stub/p4",
        estimated_at=datetime(2026, 11, 1, 12, 30, tzinfo=UTC),
        quantity=1,
        footprint_category=FootprintCategory.SMALL_ELECTRONICS,
        impacts=frozenset({Impact.MONEY, Impact.CLIMATE}),
        fingerprint="a" * 64,
    )


def _appraise(item, appraisal):
    row = item.appraisal = ItemAppraisal()
    row.update_from_appraisal(appraisal)
    db.session.flush()


def _events_for(item_id):
    db.session.expire_all()
    return ImpactEvent.query.filter_by(item_id=item_id).all()


def _assert_pending(event):
    assert event.new_price_usd is None
    assert event.condition is None
    assert event.model_version is None
    assert event.usd_saved is None
    assert event.kg_co2e_avoided is None
    assert event.policy_version is None


def _assert_filled(event, appraisal, usd, kg):
    assert event.new_price_usd == Decimal(str(appraisal.new_price_usd))
    assert event.quantity == appraisal.quantity
    assert event.condition == appraisal.condition.value
    assert event.resale_demand == appraisal.resale_demand.value
    assert event.footprint_category == appraisal.footprint_category.value
    assert event.model_version == appraisal.model_version
    assert event.usd_saved == Decimal(str(usd))
    assert event.kg_co2e_avoided == Decimal(str(kg))
    assert event.policy_version == item_appraiser.__version__


def _approved_loan(owner, borrower):
    return LoanRequestFactory(
        item=ItemFactory(owner=owner, available=False), borrower=borrower, status="approved"
    )


def _pending_pickup_giveaway(owner, recipient):
    return ItemFactory(
        owner=owner,
        is_giveaway=True,
        claim_status="pending_pickup",
        claimed_by=recipient,
        available=False,
    )


class TestLoanCompletedEvents:
    def test_web_route_records_pending_event_without_appraisal(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            loan = _approved_loan(owner, borrower)
            db.session.commit()
            login_user(client, owner.email)

            client.post(f"/loan/{loan.id}/complete")

            events = _events_for(loan.item_id)
            assert len(events) == 1
            event = events[0]
            assert event.kind == ImpactEvent.KIND_LOAN
            assert event.loan_request_id == loan.id
            assert event.beneficiary_id == borrower.id
            assert event.provider_id == owner.id
            assert event.item_name == loan.item.name
            assert event.category_name == loan.item.category.name
            assert event.occurred_at.tzinfo is not None
            _assert_pending(event)

    def test_api_route_records_filled_event_with_appraisal(self, client, app):
        appraisal = _stub_appraisal()
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            loan = _approved_loan(owner, borrower)
            _appraise(loan.item, appraisal)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id, item_id = loan.id, loan.item_id
            owner_id, borrower_id = owner.id, borrower.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/complete", headers=auth_headers(access_token)
        )

        assert response.status_code == 200
        with app.app_context():
            events = _events_for(item_id)
            assert len(events) == 1
            event = events[0]
            assert event.kind == ImpactEvent.KIND_LOAN
            assert event.beneficiary_id == borrower_id
            assert event.provider_id == owner_id
            _assert_filled(
                event,
                appraisal,
                appraisal_loan_value(appraisal),
                appraisal_loan_kg_co2e(appraisal),
            )

    def test_completing_twice_does_not_duplicate(self, client, app):
        with app.app_context():
            owner = UserFactory()
            loan = _approved_loan(owner, UserFactory())
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id, item_id = loan.id, loan.item_id

        first = client.post(f"/api/v1/loans/{loan_id}/complete", headers=auth_headers(access_token))
        second = client.post(
            f"/api/v1/loans/{loan_id}/complete", headers=auth_headers(access_token)
        )

        assert first.status_code == 200
        assert second.status_code == 409
        with app.app_context():
            assert len(_events_for(item_id)) == 1

    def test_existing_event_for_loan_does_not_block_completion(self, app):
        with app.app_context():
            owner = UserFactory()
            loan = _approved_loan(owner, UserFactory())
            ImpactEventFactory(item=loan.item, loan_request=loan)
            db.session.commit()
            loan_id, item_id = loan.id, loan.item_id

            loan_service.complete_loan(loan, owner.id)

            db.session.expire_all()
            assert db.session.get(LoanRequest, loan_id).status == "completed"
            assert len(_events_for(item_id)) == 1

    def test_event_insert_failure_does_not_block_completion(self, app):
        with app.app_context():
            owner = UserFactory()
            loan = _approved_loan(owner, UserFactory())
            db.session.commit()
            loan_id, item_id = loan.id, loan.item_id

            with patch.object(
                db.session, "begin_nested", side_effect=SQLAlchemyError("insert failed")
            ):
                loan_service.complete_loan(loan, owner.id)

            db.session.expire_all()
            assert db.session.get(LoanRequest, loan_id).status == "completed"
            assert _events_for(item_id) == []


class TestGiveawayCompletedEvents:
    def test_web_confirm_handoff_records_filled_event_with_appraisal(self, client, app):
        appraisal = _stub_appraisal()
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()
            item = _pending_pickup_giveaway(owner, recipient)
            _appraise(item, appraisal)
            db.session.commit()
            login_user(client, owner.email)

            client.post(f"/item/{item.id}/confirm-handoff")

            events = _events_for(item.id)
            assert len(events) == 1
            event = events[0]
            assert event.kind == ImpactEvent.KIND_GIVEAWAY
            assert event.loan_request_id is None
            assert event.beneficiary_id == recipient.id
            assert event.provider_id == owner.id
            _assert_filled(
                event,
                appraisal,
                appraisal_buy_value(appraisal),
                appraisal_giveaway_kg_co2e(appraisal),
            )

    def test_api_confirm_handoff_records_pending_event_without_appraisal(self, client, app):
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()
            item = _pending_pickup_giveaway(owner, recipient)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id, owner_id, recipient_id = item.id, owner.id, recipient.id

        response = client.post(
            f"/api/v1/items/{item_id}/confirm-handoff", headers=auth_headers(access_token)
        )

        assert response.status_code == 200
        with app.app_context():
            events = _events_for(item_id)
            assert len(events) == 1
            assert events[0].kind == ImpactEvent.KIND_GIVEAWAY
            assert events[0].beneficiary_id == recipient_id
            assert events[0].provider_id == owner_id
            _assert_pending(events[0])

    def test_web_mark_given_away_records_event_without_beneficiary(self, client, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=True, claim_status="unclaimed")
            db.session.commit()
            login_user(client, owner.email)

            client.post(f"/item/{item.id}/mark-given-away")

            events = _events_for(item.id)
            assert len(events) == 1
            assert events[0].kind == ImpactEvent.KIND_GIVEAWAY
            assert events[0].beneficiary_id is None
            assert events[0].provider_id == owner.id
            _assert_pending(events[0])

    def test_api_mark_given_away_records_filled_event(self, client, app):
        appraisal = _stub_appraisal()
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=True, claim_status="unclaimed")
            _appraise(item, appraisal)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id, owner_id = item.id, owner.id

        response = client.post(
            f"/api/v1/items/{item_id}/mark-given-away", headers=auth_headers(access_token)
        )

        assert response.status_code == 200
        with app.app_context():
            events = _events_for(item_id)
            assert len(events) == 1
            assert events[0].beneficiary_id is None
            assert events[0].provider_id == owner_id
            _assert_filled(
                events[0],
                appraisal,
                appraisal_buy_value(appraisal),
                appraisal_giveaway_kg_co2e(appraisal),
            )

    @pytest.mark.parametrize("complete", ["confirm_handoff", "mark_given_away"])
    def test_completing_twice_does_not_duplicate(self, app, complete):
        with app.app_context():
            owner = UserFactory()
            if complete == "confirm_handoff":
                item = _pending_pickup_giveaway(owner, UserFactory())
            else:
                item = ItemFactory(owner=owner, is_giveaway=True, claim_status="unclaimed")
            db.session.commit()
            action = getattr(giveaway_service, complete)

            action(item, owner.id)
            with pytest.raises(ConflictError):
                action(item, owner.id)

            assert len(_events_for(item.id)) == 1

    def test_existing_event_for_giveaway_does_not_block_handoff(self, app):
        with app.app_context():
            owner = UserFactory()
            item = _pending_pickup_giveaway(owner, UserFactory())
            ImpactEventFactory(item=item, kind=ImpactEvent.KIND_GIVEAWAY)
            db.session.commit()
            item_id = item.id

            giveaway_service.confirm_handoff(item, owner.id)

            db.session.expire_all()
            assert db.session.get(Item, item_id).claim_status == "claimed"
            assert len(_events_for(item_id)) == 1
