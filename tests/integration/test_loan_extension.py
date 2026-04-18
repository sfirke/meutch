"""Integration tests for loan extension functionality."""
import pytest
from datetime import date, timedelta
from flask import url_for
from app import db
from app.models import Message, LoanExtensionRequest
from tests.factories import UserFactory, ItemFactory, LoanRequestFactory
from conftest import login_user


class TestLoanExtension:
    """Test loan extension route and message generation."""
    
    def test_extend_loan_with_later_date_says_extended(self, app, client):
        """Test that extending a loan with a later date says 'extended' in message."""
        with app.app_context():
            # Create owner and borrower
            owner = UserFactory()
            borrower = UserFactory()
            
            # Create item and loan
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            db.session.commit()
            
            # Login as owner
            login_user(client, owner.email)
            
            # Extend loan to a later date
            new_end_date = date.today() + timedelta(days=10)
            response = client.post(url_for('main.extend_loan', loan_id=loan.id), data={
                'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                'message': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check that flash message says "extended"
            assert b'extended' in response.data
            
            # Check that the notification message to borrower says "extended"
            message = Message.query.filter_by(
                sender_id=owner.id,
                recipient_id=borrower.id,
                item_id=item.id
            ).order_by(Message.timestamp.desc()).first()
            
            assert message is not None
            assert 'extended' in message.body.lower()
            assert 'good news' in message.body.lower()
    
    def test_extend_loan_with_earlier_date_says_updated(self, app, client):
        """Test that changing a loan to an earlier date says 'updated' not 'extended'."""
        with app.app_context():
            # Create owner and borrower
            owner = UserFactory()
            borrower = UserFactory()
            
            # Create item and loan with due date far in future
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=10)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            db.session.commit()
            
            # Login as owner
            login_user(client, owner.email)
            
            # Change loan to an earlier date
            new_end_date = date.today() + timedelta(days=5)
            response = client.post(url_for('main.extend_loan', loan_id=loan.id), data={
                'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                'message': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check that flash message says "updated" not "extended"
            assert b'Loan due date has been updated to' in response.data
            assert b'Loan has been extended until' not in response.data
            
            # Check that the notification message to borrower says "updated" not "extended"
            message = Message.query.filter_by(
                sender_id=owner.id,
                recipient_id=borrower.id,
                item_id=item.id
            ).order_by(Message.timestamp.desc()).first()
            
            assert message is not None
            assert 'has been updated' in message.body.lower()
            assert 'has been extended' not in message.body.lower()
            # Should not have "good news" for earlier date
            assert 'good news' not in message.body.lower()
    
    def test_extend_loan_with_custom_message_and_later_date(self, app, client):
        """Test loan extension with custom message and later date."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            db.session.commit()
            
            # Login as owner
            login_user(client, owner.email)
            
            # Extend with custom message
            new_end_date = date.today() + timedelta(days=10)
            custom_msg = "You can keep it longer, no rush!"
            response = client.post(url_for('main.extend_loan', loan_id=loan.id), data={
                'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                'message': custom_msg
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check message contains "extended" and custom message
            message = Message.query.filter_by(
                sender_id=owner.id,
                recipient_id=borrower.id,
                item_id=item.id
            ).order_by(Message.timestamp.desc()).first()
            
            assert message is not None
            assert 'extended' in message.body.lower()
            assert custom_msg in message.body
    
    def test_extend_loan_with_custom_message_and_earlier_date(self, app, client):
        """Test loan update with custom message and earlier date."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=10)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status='approved'
            )
            db.session.commit()
            
            # Login as owner
            login_user(client, owner.email)
            
            # Update to earlier date with custom message
            new_end_date = date.today() + timedelta(days=5)
            custom_msg = "Need the item back sooner, sorry!"
            response = client.post(url_for('main.extend_loan', loan_id=loan.id), data={
                'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                'message': custom_msg
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check message contains "updated" (not "extended") and custom message
            message = Message.query.filter_by(
                sender_id=owner.id,
                recipient_id=borrower.id,
                item_id=item.id
            ).order_by(Message.timestamp.desc()).first()
            
            assert message is not None
            assert 'has been updated' in message.body.lower()
            assert 'has been extended' not in message.body.lower()
            assert custom_msg in message.body


class TestLoanExtensionRequests:
    """Test borrower extension request and owner decision workflows."""

    def test_borrower_can_request_extension_for_approved_loan(self, app, client):
        """Borrower can create an extension request with a proposed date and message."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=2),
                status='approved'
            )
            db.session.commit()

            login_user(client, borrower.email)

            proposed_end_date = date.today() + timedelta(days=7)
            response = client.post(
                url_for('main.request_extension', loan_id=loan.id),
                data={
                    'proposed_end_date': proposed_end_date.strftime('%Y-%m-%d'),
                    'message': 'I need extra time to finish my project and can return it next week.'
                },
                follow_redirects=True
            )

            assert response.status_code == 200
            assert b'Extension request sent to the item owner' in response.data

            extension_request = LoanExtensionRequest.query.filter_by(loan_request_id=loan.id).first()
            assert extension_request is not None
            assert extension_request.status == 'pending'
            assert extension_request.proposed_end_date == proposed_end_date

            message = Message.query.filter_by(
                sender_id=borrower.id,
                recipient_id=owner.id,
                loan_request_id=loan.id
            ).order_by(Message.timestamp.desc()).first()
            assert message is not None
            assert 'Extension requested' in message.body

    def test_owner_can_approve_extension_request_and_due_date_updates(self, app, client):
        """Owner approval updates due date and resolves extension request."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            original_due_date = date.today() + timedelta(days=2)
            new_due_date = date.today() + timedelta(days=9)

            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=3),
                end_date=original_due_date,
                status='approved',
                due_soon_reminder_sent=None,
                due_date_reminder_sent=None,
                last_overdue_reminder_sent=None,
                overdue_reminder_count=2
            )
            db.session.commit()

            login_user(client, borrower.email)
            client.post(
                url_for('main.request_extension', loan_id=loan.id),
                data={
                    'proposed_end_date': new_due_date.strftime('%Y-%m-%d'),
                    'message': 'Could I keep this longer while waiting for a replacement?'
                },
                follow_redirects=True
            )

            extension_request = LoanExtensionRequest.query.filter_by(loan_request_id=loan.id, status='pending').first()
            assert extension_request is not None

            login_user(client, owner.email)
            response = client.post(
                url_for('main.process_extension_request', extension_id=extension_request.id, action='approve'),
                data={},
                follow_redirects=True
            )

            assert response.status_code == 200
            assert b'Extension request approved and due date updated' in response.data

            db.session.refresh(loan)
            db.session.refresh(extension_request)
            assert loan.end_date == new_due_date
            assert extension_request.status == 'approved'
            assert extension_request.responded_at is not None
            assert loan.overdue_reminder_count == 0

    def test_owner_can_deny_extension_request(self, app, client):
        """Owner denial keeps existing due date and marks extension request denied."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            due_date = date.today() + timedelta(days=2)

            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today() - timedelta(days=4),
                end_date=due_date,
                status='approved'
            )
            db.session.commit()

            login_user(client, borrower.email)
            client.post(
                url_for('main.request_extension', loan_id=loan.id),
                data={
                    'proposed_end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
                    'message': 'I need a little more time due to travel delays this week.'
                },
                follow_redirects=True
            )

            extension_request = LoanExtensionRequest.query.filter_by(loan_request_id=loan.id, status='pending').first()
            assert extension_request is not None

            login_user(client, owner.email)
            response = client.post(
                url_for('main.process_extension_request', extension_id=extension_request.id, action='deny'),
                data={},
                follow_redirects=True
            )

            assert response.status_code == 200
            assert b'Extension request denied' in response.data

            db.session.refresh(loan)
            db.session.refresh(extension_request)
            assert loan.end_date == due_date
            assert extension_request.status == 'denied'
            assert extension_request.responded_at is not None
