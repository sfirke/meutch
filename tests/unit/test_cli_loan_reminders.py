from datetime import date, datetime, UTC, timedelta
from unittest.mock import patch

from app import db
from app.cli import check_loan_reminders_logic
from tests.factories import LoanRequestFactory


class TestCliLoanReminderOverrides:
    def test_force_loan_reminders_bypasses_due_soon_sent_guard(self, app):
        with app.app_context():
            today = date(2026, 3, 14)
            loan = LoanRequestFactory(
                status='approved',
                end_date=today + timedelta(days=3),
                due_soon_reminder_sent=datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
            )
            db.session.commit()

            with patch('app.utils.email.send_loan_due_soon_email', return_value=True) as due_soon_mock, \
                 patch('app.utils.email.send_loan_due_today_borrower_email', return_value=False), \
                 patch('app.utils.email.send_loan_due_today_owner_email', return_value=False), \
                 patch('app.utils.email.send_loan_overdue_borrower_email', return_value=False), \
                 patch('app.utils.email.send_loan_overdue_owner_email', return_value=False), \
                 patch('app.cli.check_digest_sends_logic', return_value={'total_users': 0, 'sent': 0, 'skipped': 0, 'errors': [], 'by_cadence': {}}):
                stats = check_loan_reminders_logic(today=today, force_loan_reminders=False)

            assert due_soon_mock.call_count == 0
            assert stats['due_soon'] == 0

            with patch('app.utils.email.send_loan_due_soon_email', return_value=True) as due_soon_mock, \
                 patch('app.utils.email.send_loan_due_today_borrower_email', return_value=False), \
                 patch('app.utils.email.send_loan_due_today_owner_email', return_value=False), \
                 patch('app.utils.email.send_loan_overdue_borrower_email', return_value=False), \
                 patch('app.utils.email.send_loan_overdue_owner_email', return_value=False), \
                 patch('app.cli.check_digest_sends_logic', return_value={'total_users': 0, 'sent': 0, 'skipped': 0, 'errors': [], 'by_cadence': {}}):
                stats = check_loan_reminders_logic(today=today, force_loan_reminders=True)

            db.session.refresh(loan)
            assert due_soon_mock.call_count == 1
            assert stats['due_soon'] == 1
            assert loan.due_soon_reminder_sent is not None

    def test_force_digest_passes_through_to_digest_scheduler(self, app):
        with app.app_context():
            now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

            with patch('app.cli.check_digest_sends_logic', return_value={'total_users': 0, 'sent': 0, 'skipped': 0, 'errors': [], 'by_cadence': {}}) as digest_mock:
                check_loan_reminders_logic(force_digest=True, digest_now_utc=now_utc)

            digest_mock.assert_called_once_with(now_utc=now_utc, force_send=True)
