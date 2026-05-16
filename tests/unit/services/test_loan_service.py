from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.models import LoanRequest, Message
from app.services import loan_service
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError
from tests.factories import ItemFactory, LoanRequestFactory, UserFactory


class TestLoanService:
    def test_create_loan_request_creates_pending_loan_and_message(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)

            with patch("app.services.loan_service.send_message_notification_email") as mock_email:
                message = loan_service.create_loan_request(
                    item,
                    borrower.id,
                    date.today() + timedelta(days=1),
                    date.today() + timedelta(days=3),
                    "Could I borrow this next week?",
                )

            loan = LoanRequest.query.one()
            assert message.loan_request_id == loan.id
            assert loan.borrower_id == borrower.id
            assert loan.status == "pending"
            assert message.recipient_id == owner.id
            mock_email.assert_called_once_with(message)

    def test_create_loan_request_rejects_duplicate_pending_request(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)
            LoanRequestFactory(item=item, borrower=borrower, status="pending")

            with pytest.raises(InformationalError, match="already have a pending request"):
                loan_service.create_loan_request(
                    item,
                    borrower.id,
                    date.today() + timedelta(days=1),
                    date.today() + timedelta(days=2),
                    "Checking again",
                )

    def test_extend_loan_resets_reminders_and_returns_extension_flag(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=2),
                end_date=date.today() + timedelta(days=2),
            )
            loan.due_soon_reminder_sent = date.today()
            loan.due_date_reminder_sent = date.today()
            loan.last_overdue_reminder_sent = date.today()
            loan.overdue_reminder_count = 3

            with patch("app.services.loan_service.send_message_notification_email") as mock_email:
                is_extension = loan_service.extend_loan(
                    loan,
                    owner.id,
                    date.today() + timedelta(days=5),
                    "",
                )

            reminder_message = Message.query.one()
            assert is_extension is True
            assert loan.end_date == date.today() + timedelta(days=5)
            assert loan.due_soon_reminder_sent is None
            assert loan.due_date_reminder_sent is None
            assert loan.last_overdue_reminder_sent is None
            assert loan.overdue_reminder_count == 0
            mock_email.assert_called_once_with(reminder_message)

    def test_extend_loan_shortening_returns_false_and_uses_updated_message(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            original_end = date.today() + timedelta(days=7)
            new_end = date.today() + timedelta(days=3)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=original_end,
            )

            with patch("app.services.loan_service.send_message_notification_email") as mock_email:
                is_extension = loan_service.extend_loan(loan, owner.id, new_end, "")

            message = Message.query.one()
            assert is_extension is False
            assert loan.end_date == new_end
            assert "Good news" not in message.body
            assert "updated" in message.body.lower()
            mock_email.assert_called_once_with(message)

    def test_create_loan_request_rejects_giveaway_items(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=True, available=True)

            with pytest.raises(ConflictError, match="giveaway"):
                loan_service.create_loan_request(
                    item,
                    borrower.id,
                    date.today() + timedelta(days=1),
                    date.today() + timedelta(days=2),
                    "Can I borrow this?",
                )

    def test_create_loan_request_rejects_unavailable_items(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)

            with pytest.raises(ConflictError, match="not currently available"):
                loan_service.create_loan_request(
                    item,
                    borrower.id,
                    date.today() + timedelta(days=1),
                    date.today() + timedelta(days=2),
                    "Can I borrow this?",
                )

    def test_create_loan_request_rejects_owner_requesting_own_item(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)

            with pytest.raises(ConflictError, match="cannot request your own"):
                loan_service.create_loan_request(
                    item,
                    owner.id,
                    date.today() + timedelta(days=1),
                    date.today() + timedelta(days=2),
                    "Requesting my own item",
                )

    def test_process_loan_decision_raises_auth_error_for_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            other = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)
            loan = LoanRequestFactory(item=item, borrower=borrower, status="pending")

            with pytest.raises(AuthorizationError):
                loan_service.process_loan_decision(loan, other.id, "approve")

    def test_process_loan_decision_raises_conflict_for_already_processed(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")

            with patch("app.services.loan_service.send_message_notification_email"):
                with pytest.raises(ConflictError, match="already been processed"):
                    loan_service.process_loan_decision(loan, owner.id, "approve")

    def test_cancel_loan_request_raises_auth_error_for_non_borrower(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            other = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)
            loan = LoanRequestFactory(item=item, borrower=borrower, status="pending")

            with pytest.raises(AuthorizationError):
                loan_service.cancel_loan_request(loan, other.id)

    def test_cancel_loan_request_raises_conflict_for_non_pending(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")

            with pytest.raises(ConflictError, match="cannot be canceled"):
                loan_service.cancel_loan_request(loan, borrower.id)

    def test_complete_loan_raises_auth_error_for_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            other = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")

            with pytest.raises(AuthorizationError):
                loan_service.complete_loan(loan, other.id)

    def test_extend_loan_raises_auth_error_for_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            other = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=3),
            )

            with pytest.raises(AuthorizationError):
                loan_service.extend_loan(loan, other.id, date.today() + timedelta(days=7), "")
