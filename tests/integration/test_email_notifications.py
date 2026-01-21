import pytest
from unittest.mock import patch
from app import db
from tests.factories import UserFactory, ItemFactory
from conftest import login_user


class TestEmailNotificationIntegration:
    """Integration tests for email notifications during message workflows."""

    def test_message_sends_email_notification(self, client, app):
        """Test that sending a message triggers an email notification."""
        with app.app_context():
            # Create users and item
            sender = UserFactory(email='sender@test.com')
            recipient = UserFactory(email='recipient@test.com')
            item = ItemFactory(owner=recipient, name='Test Item')
            
            db.session.commit()
            
            # Sender logs in
            login_user(client, sender.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                # Send a message via the item detail page
                response = client.post(f'/item/{item.id}', data={
                    'body': 'Hello, I am interested in this item!'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                assert b'message has been sent' in response.data
                
                # Verify email was sent
                mock_send_email.assert_called_once()
                call_args = mock_send_email.call_args
                assert call_args[0][0] == recipient.email  # to_email
                assert 'New Message about Test Item' in call_args[0][1]  # subject
                assert 'Hello, I am interested in this item!' in call_args[0][2]  # message body

    def test_loan_request_sends_email_notification(self, client, app):
        """Test that loan requests trigger email notifications."""
        with app.app_context():
            # Create users and item
            borrower = UserFactory(email='borrower@test.com')
            owner = UserFactory(email='owner@test.com')
            item = ItemFactory(owner=owner, name='Test Item')
            
            db.session.commit()
            
            # Borrower logs in
            login_user(client, borrower.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                # Send a loan request
                from datetime import date, timedelta
                start_date = date.today() + timedelta(days=1)
                end_date = date.today() + timedelta(days=7)
                
                response = client.post(f'/items/{item.id}/request', data={
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'message': 'Can I borrow this item please?'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was sent
                mock_send_email.assert_called_once()
                call_args = mock_send_email.call_args
                assert call_args[0][0] == owner.email  # to_email
                assert 'New Loan Request for Test Item' in call_args[0][1]  # subject
                assert 'Can I borrow this item please?' in call_args[0][2]  # message body


