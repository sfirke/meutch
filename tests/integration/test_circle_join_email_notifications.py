"""Integration tests for circle join request email notifications."""

import pytest
from unittest.mock import patch
from tests.factories import UserFactory, CircleFactory
from app.models import db, circle_members, CircleJoinRequest
from datetime import datetime, UTC


class TestCircleJoinRequestEmailIntegration:
    """Integration tests for email notifications during circle join request workflows."""

    def test_join_circle_request_sends_email_notification(self, client, app):
        """Test that circle join requests trigger email notifications to admins."""
        with app.app_context():
            # Create users and circle
            requesting_user = UserFactory(email='user@test.com')
            requesting_user.set_password('testpassword123')
            
            admin1 = UserFactory(email='admin1@test.com')
            admin2 = UserFactory(email='admin2@test.com')
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
            client.post('/auth/login', data={
                'email': requesting_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
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
                
                # Check that both admins received emails
                call_args_list = mock_send_email.call_args_list
                sent_emails = {call[0][0] for call in call_args_list}  # Extract to_email from each call
                assert 'admin1@test.com' in sent_emails
                assert 'admin2@test.com' in sent_emails
                
                # Check email content for one of the calls
                call_args = call_args_list[0]
                to_email, subject, text_content, html_content = call_args[0]
                assert 'New Join Request for Test Circle' in subject
                assert 'I would like to join this circle please!' in text_content

    def test_approve_join_request_sends_email_notification(self, client, app):
        """Test that approving a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle
            requesting_user = UserFactory(email='user@test.com')
            admin = UserFactory(email='admin@test.com')
            admin.set_password('testpassword123')
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
            client.post('/auth/login', data={
                'email': admin.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
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

    def test_reject_join_request_sends_email_notification(self, client, app):
        """Test that rejecting a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle
            requesting_user = UserFactory(email='user@test.com')
            admin = UserFactory(email='admin@test.com')
            admin.set_password('testpassword123')
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
            client.post('/auth/login', data={
                'email': admin.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
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

    def test_circle_without_approval_no_email(self, client, app):
        """Test that joining a circle without approval requirement doesn't send emails."""
        with app.app_context():
            # Create users and circle
            requesting_user = UserFactory(email='user@test.com')
            requesting_user.set_password('testpassword123')
            
            admin = UserFactory(email='admin@test.com')
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
            client.post('/auth/login', data={
                'email': requesting_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            # Patch the email sending function
            with patch('app.utils.email.send_email') as mock_send_email:
                # Join the circle directly (no approval needed)
                response = client.post(f'/circles/join/{circle.id}', follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify no email was sent since no approval was needed
                mock_send_email.assert_not_called()
