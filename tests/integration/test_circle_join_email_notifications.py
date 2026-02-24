"""Integration tests for circle join request email notifications."""

import pytest
from unittest.mock import patch
from tests.factories import UserFactory, CircleFactory
from app.models import db, circle_members, CircleJoinRequest, Message
from datetime import datetime, UTC
from conftest import login_user


class TestCircleJoinRequestEmailIntegration:
    """Integration tests for email notifications during circle join request workflows."""

    def test_join_circle_request_sends_email_notification(self, client, app):
        """Test that circle join requests trigger email notifications to admins."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin1 = UserFactory()
            admin2 = UserFactory()
            circle = CircleFactory(name='Test Circle', requires_approval=True)
            
            # Add admins to circle
            stmt1 = circle_members.insert().values(
                user_id=admin1.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True
            )
            stmt2 = circle_members.insert().values(
                user_id=admin2.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True
            )
            db.session.execute(stmt1)
            db.session.execute(stmt2)
            db.session.commit()
            
            # User logs in
            login_user(client, requesting_user.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                # Send a circle join request
                response = client.post(f'/circles/join/{circle.id}', data={
                    'message': 'I would like to join this circle please!'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was sent to both admins
                assert mock_send_email.call_count == 2

                # Verify in-app messages were created for both admins
                admin_messages = Message.query.filter_by(
                    sender_id=requesting_user.id,
                    circle_id=circle.id
                ).all()
                assert len(admin_messages) == 2
                admin_recipient_ids = {msg.recipient_id for msg in admin_messages}
                assert admin_recipient_ids == {admin1.id, admin2.id}
                assert all("requested to join the circle" in msg.body for msg in admin_messages)
                
                # Check that both admins received emails
                call_args_list = mock_send_email.call_args_list
                sent_emails = {call[0][0] for call in call_args_list}  # Extract to_email from each call
                assert admin1.email in sent_emails
                assert admin2.email in sent_emails
                
                # Check email content for one of the calls
                call_args = call_args_list[0]
                to_email, subject, text_content, html_content = call_args[0]
                assert 'New Join Request for Test Circle' in subject
                assert 'I would like to join this circle please!' in text_content

                # Verify circle conversations are visible in existing inbox/thread UX
                login_user(client, admin1.email)
                inbox_response = client.get('/messages')
                assert inbox_response.status_code == 200
                assert b'Circle: Test Circle' in inbox_response.data

                thread_message = Message.query.filter_by(
                    sender_id=requesting_user.id,
                    recipient_id=admin1.id,
                    circle_id=circle.id
                ).first()
                thread_response = client.get(f'/message/{thread_message.id}')
                assert thread_response.status_code == 200
                assert b'Circle: Test Circle' in thread_response.data

    def test_approve_join_request_sends_email_notification(self, client, app):
        """Test that approving a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name='Test Circle', requires_approval=True)
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True
            )
            db.session.execute(stmt)
            
            # Create a pending join request
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requesting_user.id,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.add(join_request)
            db.session.commit()
            
            # Admin logs in
            login_user(client, admin.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                # Approve the join request
                response = client.post(f'/circles/{circle.id}/request/{join_request.id}/approve',
                                     follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was sent to requesting user
                mock_send_email.assert_called_once()
                
                call_args = mock_send_email.call_args
                to_email, subject, text_content, html_content = call_args[0]
                
                assert to_email == requesting_user.email
                assert 'Join Request Approved for Test Circle' in subject
                assert 'approved' in text_content.lower()

                # Verify in-app decision message was created
                decision_message = Message.query.filter_by(
                    sender_id=admin.id,
                    recipient_id=requesting_user.id,
                    circle_id=circle.id
                ).order_by(Message.timestamp.desc()).first()
                assert decision_message is not None
                assert 'approved' in decision_message.body.lower()

    def test_reject_join_request_sends_email_notification(self, client, app):
        """Test that rejecting a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name='Test Circle', requires_approval=True)
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True
            )
            db.session.execute(stmt)
            
            # Create a pending join request
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requesting_user.id,
                message='I would like to join this circle please!',
                status='pending'
            )
            db.session.add(join_request)
            db.session.commit()
            
            # Admin logs in
            login_user(client, admin.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                
                # Reject the join request
                response = client.post(f'/circles/{circle.id}/request/{join_request.id}/reject',
                                     follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was sent to requesting user
                mock_send_email.assert_called_once()
                
                call_args = mock_send_email.call_args
                to_email, subject, text_content, html_content = call_args[0]
                
                assert to_email == requesting_user.email
                assert 'Join Request Denied for Test Circle' in subject
                assert 'denied' in text_content.lower()

                # Verify in-app decision message was created
                decision_message = Message.query.filter_by(
                    sender_id=admin.id,
                    recipient_id=requesting_user.id,
                    circle_id=circle.id
                ).order_by(Message.timestamp.desc()).first()
                assert decision_message is not None
                assert 'rejected' in decision_message.body.lower()

    def test_circle_without_approval_no_email(self, client, app):
        """Test that joining a circle without approval requirement doesn't send emails."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name='Test Circle', requires_approval=False)  # No approval required
            
            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True
            )
            db.session.execute(stmt)
            db.session.commit()
            
            # User logs in
            login_user(client, requesting_user.email)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                # Join the circle directly (no approval needed)
                response = client.post(f'/circles/join/{circle.id}', follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify no email was sent since no approval was needed
                mock_send_email.assert_not_called()
