"""Unit tests for the ImpactEvent model."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ImpactEvent, Item
from app.services import account_service, item_service
from tests.factories import ImpactEventFactory, ItemFactory, LoanRequestFactory, UserFactory


def _loan_and_giveaway_events(item, borrower=None):
    loan = LoanRequestFactory(item=item, borrower=borrower or UserFactory(), status="completed")
    loan_event = ImpactEventFactory(item=item, loan_request=loan, beneficiary=loan.borrower)
    giveaway_event = ImpactEventFactory(
        item=item, kind=ImpactEvent.KIND_GIVEAWAY, beneficiary=UserFactory()
    )
    db.session.commit()
    return loan_event, giveaway_event


class TestImpactEventSurvivesDeletion:
    def test_item_delete_keeps_events_with_null_links(self, app):
        with app.app_context():
            item = ItemFactory()
            events = _loan_and_giveaway_events(item)
            snapshot = {e.id: (e.beneficiary_id, e.provider_id, e.item_name) for e in events}

            with patch("app.services.item_service.delete_item_images"):
                item_service.delete_item_with_cleanup(item)

            assert db.session.get(Item, item.id) is None
            for event_id, (beneficiary_id, provider_id, item_name) in snapshot.items():
                event = db.session.get(ImpactEvent, event_id)
                assert event.item_id is None
                assert event.loan_request_id is None
                assert event.beneficiary_id == beneficiary_id
                assert event.provider_id == provider_id
                assert event.item_name == item_name

    def test_item_delete_keeps_events_not_loaded_in_session(self, app):
        with app.app_context():
            item = ItemFactory()
            event_ids = [e.id for e in _loan_and_giveaway_events(item)]
            item_id = item.id
            db.session.expunge_all()

            with patch("app.services.item_service.delete_item_images"):
                item_service.delete_item_with_cleanup(db.session.get(Item, item_id))

            events = [db.session.get(ImpactEvent, event_id) for event_id in event_ids]
            assert [e.item_id for e in events] == [None, None]

    def test_soft_deleted_users_keep_their_events(self, app):
        with app.app_context():
            event = ImpactEventFactory(beneficiary=UserFactory())
            db.session.commit()
            event.beneficiary.is_deleted = True
            event.provider.is_deleted = True
            db.session.commit()
            db.session.expire_all()

            event = db.session.get(ImpactEvent, event.id)
            assert event.beneficiary.is_deleted is True
            assert event.provider.is_deleted is True

    def test_account_deletion_keeps_events(self, app):
        with app.app_context():
            lender = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=lender)
            loan_event, giveaway_event = _loan_and_giveaway_events(item, borrower)
            borrowed_event = ImpactEventFactory(beneficiary=lender)
            db.session.commit()
            event_ids = [loan_event.id, giveaway_event.id, borrowed_event.id]
            borrowed_item_id = borrowed_event.item_id

            with patch("app.services.account_service.send_account_deletion_email"):
                account_service.delete_user_account(lender)
            with patch("app.services.account_service.send_account_deletion_email"):
                account_service.delete_user_account(borrower)

            loan_event, giveaway_event, borrowed_event = (
                db.session.get(ImpactEvent, event_id) for event_id in event_ids
            )
            assert db.session.get(Item, item.id) is None
            assert loan_event.item_id is None
            assert loan_event.loan_request_id is None
            assert giveaway_event.item_id is None
            assert loan_event.beneficiary_id == borrower.id
            assert loan_event.provider_id == lender.id
            assert giveaway_event.provider_id == lender.id
            assert borrowed_event.beneficiary_id == lender.id
            assert borrowed_event.item_id == borrowed_item_id


class TestImpactEventUniqueness:
    def test_second_giveaway_event_for_item_is_rejected(self, app):
        with app.app_context():
            item = ItemFactory(is_giveaway=True)
            ImpactEventFactory(item=item, kind=ImpactEvent.KIND_GIVEAWAY)
            db.session.commit()

            with pytest.raises(IntegrityError):
                ImpactEventFactory(item=item, kind=ImpactEvent.KIND_GIVEAWAY)
            db.session.rollback()

    def test_many_loan_events_for_one_item_are_allowed(self, app):
        with app.app_context():
            item = ItemFactory()
            for _ in range(3):
                loan = LoanRequestFactory(item=item, status="completed")
                ImpactEventFactory(item=item, loan_request=loan)
            db.session.commit()

            assert ImpactEvent.query.filter_by(item_id=item.id).count() == 3

    def test_second_event_for_same_loan_is_rejected(self, app):
        with app.app_context():
            loan = LoanRequestFactory(status="completed")
            ImpactEventFactory(item=loan.item, loan_request=loan)
            db.session.commit()

            with pytest.raises(IntegrityError):
                ImpactEventFactory(item=loan.item, loan_request=loan)
            db.session.rollback()

    def test_giveaway_events_on_deleted_items_do_not_collide(self, app):
        with app.app_context():
            for name in ("a", "b"):
                ImpactEventFactory(
                    kind=ImpactEvent.KIND_GIVEAWAY,
                    item=None,
                    provider=None,
                    item_name=name,
                    category_name="c",
                )
            db.session.commit()

            assert ImpactEvent.query.filter_by(item_id=None).count() == 2
