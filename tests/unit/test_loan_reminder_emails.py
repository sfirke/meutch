"""Unit tests for borrower loan reminder emails."""
from datetime import date, timedelta
from unittest.mock import patch

from app.utils.email import (
    send_loan_due_soon_email,
    send_loan_due_today_borrower_email,
    send_loan_overdue_borrower_email,
)
from tests.factories import UserFactory, ItemFactory, LoanRequestFactory


class TestLoanReminderEmails:
    """Verify borrower reminder emails include extension links."""

    def test_due_soon_email_includes_request_extension_link(self, app):
        with app.app_context():
            owner = UserFactory(first_name='Owner', last_name='Person')
            borrower = UserFactory(email='borrower_due_soon@example.com')
            item = ItemFactory(owner=owner, name='Projector')
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=4),
                end_date=date.today() + timedelta(days=3),
                status='approved'
            )

            with patch('app.utils.email.send_email', return_value=True) as mock_send_email:
                result = send_loan_due_soon_email(loan)
                assert result is True

                args, _ = mock_send_email.call_args
                text_content = args[2]
                html_content = args[3]
                assert '/loan/' in text_content
                assert '/request-extension' in text_content
                assert '/request-extension' in html_content
                assert 'Request Extension' in html_content

    def test_due_today_email_includes_request_extension_link(self, app):
        with app.app_context():
            owner = UserFactory(first_name='Owner', last_name='Person')
            borrower = UserFactory(email='borrower_due_today@example.com')
            item = ItemFactory(owner=owner, name='Bike Pump')
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                status='approved'
            )

            with patch('app.utils.email.send_email', return_value=True) as mock_send_email:
                result = send_loan_due_today_borrower_email(loan)
                assert result is True

                args, _ = mock_send_email.call_args
                text_content = args[2]
                html_content = args[3]
                assert '/loan/' in text_content
                assert '/request-extension' in text_content
                assert '/request-extension' in html_content
                assert 'Request Extension' in html_content

    def test_overdue_email_includes_request_extension_link(self, app):
        with app.app_context():
            owner = UserFactory(first_name='Owner', last_name='Person')
            borrower = UserFactory(email='borrower_overdue@example.com')
            item = ItemFactory(owner=owner, name='Extension Cord')
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status='approved'
            )

            with patch('app.utils.email.send_email', return_value=True) as mock_send_email:
                result = send_loan_overdue_borrower_email(loan, days_overdue=1)
                assert result is True

                args, _ = mock_send_email.call_args
                text_content = args[2]
                html_content = args[3]
                assert '/loan/' in text_content
                assert '/request-extension' in text_content
                assert '/request-extension' in html_content
                assert 'Request Extension' in html_content
