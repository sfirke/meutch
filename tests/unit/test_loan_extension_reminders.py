"""Unit tests for loan extension notification reset behavior."""
import pytest
from datetime import date, timedelta, datetime, UTC
from app import db
from app.models import LoanRequest
from tests.factories import UserFactory, ItemFactory, LoanRequestFactory
from app.cli import check_loan_reminders_logic
from unittest.mock import patch


class TestLoanExtensionReminderReset:
    """Test that loan extension resets notification flags and allows reminders to be sent again."""
    
    def test_reminder_not_sent_if_flag_is_set(self, app):
        """Test that reminders are not sent if the flag indicates they were already sent."""
        with app.app_context():
            # Create a loan due in 3 days
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=3),
                status='approved'
            )
            
            # Set the flag to indicate reminder was already sent
            loan.due_soon_reminder_sent = datetime.now(UTC)
            db.session.commit()
            
            # Mock the email sending function
            with patch('app.utils.email.send_loan_due_soon_email', return_value=True) as mock_send:
                stats = check_loan_reminders_logic()
                
                # Verify no email was sent because flag was already set
                assert mock_send.call_count == 0
                assert stats['due_soon'] == 0
    
    def test_reminder_sent_after_flag_reset(self, app):
        """Test that reminders can be sent again after extending a loan clears the flag."""
        with app.app_context():
            # Create a loan due in 3 days
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=3),
                status='approved'
            )
            
            # Simulate that reminder was sent
            loan.due_soon_reminder_sent = datetime.now(UTC)
            db.session.commit()
            
            # Now simulate loan extension by resetting the flag (as done in extend_loan route)
            loan.due_soon_reminder_sent = None
            loan.due_date_reminder_sent = None
            loan.last_overdue_reminder_sent = None
            loan.overdue_reminder_count = 0
            db.session.commit()
            
            # Mock the email sending function
            with patch('app.utils.email.send_loan_due_soon_email', return_value=True) as mock_send:
                stats = check_loan_reminders_logic()
                
                # Verify email WAS sent because flag was reset
                assert mock_send.call_count == 1
                assert stats['due_soon'] == 1
    
    def test_overdue_reminder_count_reset_allows_more_reminders(self, app):
        """Test that resetting overdue_reminder_count allows more overdue reminders to be sent."""
        with app.app_context():
            # Create an overdue loan (1 day overdue)
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status='approved'
            )
            
            # Simulate that 4 overdue reminders were already sent (max limit)
            loan.overdue_reminder_count = 4
            loan.last_overdue_reminder_sent = datetime.now(UTC) - timedelta(days=2)
            db.session.commit()
            
            # Mock the email sending functions
            with patch('app.utils.email.send_loan_overdue_borrower_email', return_value=True) as mock_borrower, \
                 patch('app.utils.email.send_loan_overdue_owner_email', return_value=True) as mock_owner:
                stats = check_loan_reminders_logic()
                
                # Verify no emails sent because count limit reached
                assert mock_borrower.call_count == 0
                assert mock_owner.call_count == 0
                assert stats['overdue'] == 0
            
            # Now simulate loan extension by resetting the counters
            loan.due_soon_reminder_sent = None
            loan.due_date_reminder_sent = None
            loan.last_overdue_reminder_sent = None
            loan.overdue_reminder_count = 0
            db.session.commit()
            
            # Mock the email sending functions again
            with patch('app.utils.email.send_loan_overdue_borrower_email', return_value=True) as mock_borrower, \
                 patch('app.utils.email.send_loan_overdue_owner_email', return_value=True) as mock_owner:
                stats = check_loan_reminders_logic()
                
                # Verify emails CAN be sent again because counter was reset
                assert mock_borrower.call_count == 1
                assert mock_owner.call_count == 1
                assert stats['overdue'] == 1
    
    def test_due_date_reminder_reset_allows_resending(self, app):
        """Test that resetting due_date_reminder_sent allows the reminder to be sent again."""
        with app.app_context():
            # Create a loan due today
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                status='approved'
            )
            
            # Set the flag to indicate reminder was already sent
            loan.due_date_reminder_sent = datetime.now(UTC)
            db.session.commit()
            
            # Mock the email sending functions
            with patch('app.utils.email.send_loan_due_today_borrower_email', return_value=True) as mock_borrower, \
                 patch('app.utils.email.send_loan_due_today_owner_email', return_value=True) as mock_owner:
                stats = check_loan_reminders_logic()
                
                # Verify no emails sent because flag was set
                assert mock_borrower.call_count == 0
                assert mock_owner.call_count == 0
                assert stats['due_today'] == 0
            
            # Reset the flag (simulating loan extension)
            loan.due_date_reminder_sent = None
            db.session.commit()
            
            # Mock the email sending functions again
            with patch('app.utils.email.send_loan_due_today_borrower_email', return_value=True) as mock_borrower, \
                 patch('app.utils.email.send_loan_due_today_owner_email', return_value=True) as mock_owner:
                stats = check_loan_reminders_logic()
                
                # Verify emails CAN be sent again
                assert mock_borrower.call_count == 1
                assert mock_owner.call_count == 1
                assert stats['due_today'] == 1
