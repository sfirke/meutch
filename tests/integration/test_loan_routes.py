"""Integration tests for loan-related routes."""
import pytest
from datetime import date, timedelta, datetime, UTC
from app import db
from app.models import LoanRequest, Message
from tests.factories import UserFactory, ItemFactory, LoanRequestFactory, CategoryFactory
from conftest import login_user


class TestExtendLoanRoute:
    """Test the extend_loan route and notification flag resets."""
    
    def test_extend_loan_resets_notification_flags(self, client, app):
        """Test that extending a loan resets all notification reminder flags."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category)
            
            # Create an approved loan with notification flags set
            current_end_date = date.today() + timedelta(days=2)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=5),
                end_date=current_end_date,
                status='approved'
            )
            
            # Simulate that reminders have already been sent
            loan.due_soon_reminder_sent = datetime.now(UTC)
            loan.due_date_reminder_sent = datetime.now(UTC)
            loan.last_overdue_reminder_sent = datetime.now(UTC)
            loan.overdue_reminder_count = 2
            
            db.session.commit()
            loan_id = loan.id
            
            # Login as owner
            login_user(client, owner.email)
            
            # Extend the loan
            new_end_date = current_end_date + timedelta(days=7)
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': 'Here is some extra time!'
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'Loan has been extended' in response.data
            
            # Verify notification flags were reset
            loan = db.session.get(LoanRequest, loan_id)
            assert loan.due_soon_reminder_sent is None
            assert loan.due_date_reminder_sent is None
            assert loan.last_overdue_reminder_sent is None
            assert loan.overdue_reminder_count == 0
            assert loan.end_date == new_end_date
    
    def test_extend_loan_creates_notification_message(self, client, app):
        """Test that extending a loan creates a notification message to the borrower."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name='Test Ladder')
            
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            
            db.session.commit()
            loan_id = loan.id
            item_id = item.id
            
            # Login as owner
            login_user(client, owner.email)
            
            # Extend the loan with a custom message
            new_end_date = current_end_date + timedelta(days=10)
            custom_message = 'Take your time, no rush!'
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': custom_message
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify a message was created
            message = Message.query.filter_by(
                item_id=item_id,
                loan_request_id=loan_id,
                sender_id=owner.id,
                recipient_id=borrower.id
            ).first()
            
            assert message is not None
            assert 'extended' in message.body.lower()
            assert custom_message in message.body
            assert loan.item.name in message.body
    
    def test_extend_loan_requires_owner_authorization(self, client, app):
        """Test that only the item owner can extend a loan."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            other_user = UserFactory(email='other@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category)
            
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=5),
                status='approved'
            )
            
            db.session.commit()
            loan_id = loan.id
            
            # Try to extend as a different user (not the owner)
            login_user(client, other_user.email)
            
            new_end_date = date.today() + timedelta(days=10)
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': ''
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not authorized' in response.data
    
    def test_extend_loan_only_for_pending_or_approved(self, client, app):
        """Test that only pending or approved loans can be extended."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category)
            
            # Create a completed loan (cannot be extended)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status='completed'
            )
            
            db.session.commit()
            loan_id = loan.id
            
            # Login as owner
            login_user(client, owner.email)
            
            # Try to extend the completed loan
            new_end_date = date.today() + timedelta(days=5)
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': ''
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'Only pending or approved loans can be extended' in response.data
    
    def test_extend_loan_without_custom_message(self, client, app):
        """Test that extending a loan without a custom message uses default message."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, name='Power Drill')
            
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            
            db.session.commit()
            loan_id = loan.id
            item_id = item.id
            
            # Login as owner
            login_user(client, owner.email)
            
            # Extend the loan without a custom message
            new_end_date = current_end_date + timedelta(days=7)
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': ''  # No custom message
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify a message was created with default text
            message = Message.query.filter_by(
                item_id=item_id,
                loan_request_id=loan_id,
                sender_id=owner.id,
                recipient_id=borrower.id
            ).first()
            
            assert message is not None
            assert 'Good news!' in message.body
            assert 'extended' in message.body.lower()
            assert loan.item.name in message.body
            assert current_end_date.strftime('%B %d, %Y') in message.body
            assert new_end_date.strftime('%B %d, %Y') in message.body
    
    def test_extend_loan_with_notification_flags_prevents_duplicate_reminders(self, client, app):
        """Test that after extending a loan with reset flags, reminders can be sent again."""
        with app.app_context():
            # Create test data
            owner = UserFactory(email='owner@example.com')
            borrower = UserFactory(email='borrower@example.com')
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category)
            
            # Create a loan due in 3 days (would trigger due-soon reminder)
            current_end_date = date.today() + timedelta(days=3)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=5),
                end_date=current_end_date,
                status='approved'
            )
            
            # Simulate that the due-soon reminder was already sent
            loan.due_soon_reminder_sent = datetime.now(UTC)
            db.session.commit()
            loan_id = loan.id
            
            # Verify the flag is set
            assert loan.due_soon_reminder_sent is not None
            
            # Login as owner and extend the loan
            login_user(client, owner.email)
            
            # Extend the loan so it's due in 10 days from now
            new_end_date = date.today() + timedelta(days=10)
            response = client.post(
                f'/loan/{loan_id}/extend',
                data={
                    'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                    'message': 'Extended for more time'
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify the reminder flag is now cleared
            loan = db.session.get(LoanRequest, loan_id)
            assert loan.due_soon_reminder_sent is None
            
            # This means when the loan becomes due in 3 days again (7 days from now),
            # the reminder can be sent again because the flag is cleared
