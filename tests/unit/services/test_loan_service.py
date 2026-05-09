from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.models import LoanRequest, Message
from app.services import loan_service
from app.services.exceptions import InformationalError
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
