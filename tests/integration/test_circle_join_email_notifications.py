"""Integration tests for circle join request email notifications."""

from datetime import UTC, datetime
from unittest.mock import patch

from app.models import CircleJoinRequest, Conversation, Message, circle_members, db
from conftest import login_user
from tests.factories import CircleFactory, UserFactory


def get_single_email_by_subject(mock, subject_substring):
    """Return the (to, subject, text, html) args tuple of the one email whose
    subject contains *subject_substring*. Asserts exactly one match."""
    matches = [call.args for call in mock.call_args_list if subject_substring in call.args[1]]
    assert len(matches) == 1, (
        f"Expected 1 email with subject containing {subject_substring!r}, " f"got {len(matches)}"
    )
    return matches[0]


class TestCircleJoinRequestEmailIntegration:
    """Integration tests for email notifications during circle join request workflows."""

    def test_join_circle_request_sends_email_notification(self, client, app):
        """Test that circle join requests trigger email notifications to admins."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin1 = UserFactory()
            admin2 = UserFactory()
            circle = CircleFactory(name="Test Circle", circle_type="closed")

            # Add admins to circle
            stmt1 = circle_members.insert().values(
                user_id=admin1.id, circle_id=circle.id, joined_at=datetime.now(UTC), is_admin=True
            )
            stmt2 = circle_members.insert().values(
                user_id=admin2.id, circle_id=circle.id, joined_at=datetime.now(UTC), is_admin=True
            )
            db.session.execute(stmt1)
            db.session.execute(stmt2)
            db.session.commit()

            # User logs in
            login_user(client, requesting_user.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                # Send a circle join request
                response = client.post(
                    f"/circles/join/{circle.id}",
                    data={"message": "I would like to join this circle please!"},
                    follow_redirects=True,
                )

                assert response.status_code == 200

                # Verify email was sent to both admins
                assert mock_send_email.call_count == 2

                # Verify no in-app messages were created for admins
                admin_messages = (
                    Message.query.join(Conversation)
                    .filter(
                        Conversation.context_type == "circle",
                        Conversation.context_id == circle.id,
                        Message.sender_id == requesting_user.id,
                    )
                    .all()
                )
                assert len(admin_messages) == 0

                # Check that both admins received emails
                call_args_list = mock_send_email.call_args_list
                sent_emails = {
                    call[0][0] for call in call_args_list
                }  # Extract to_email from each call
                assert admin1.email in sent_emails
                assert admin2.email in sent_emails

                # Check email content for one of the calls
                call_args = call_args_list[0]
                to_email, subject, text_content, html_content = call_args[0]
                assert "New Join Request for Test Circle" in subject
                assert "I would like to join this circle please!" in text_content

    def test_second_admin_action_on_handled_request_is_ignored(self, client, app):
        """A handled join request should not be handled again by another admin."""
        with app.app_context():
            requesting_user = UserFactory()
            admin1 = UserFactory()
            admin2 = UserFactory()
            circle = CircleFactory(name="Test Circle", circle_type="closed")

            db.session.execute(
                circle_members.insert().values(
                    user_id=admin1.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin2.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )

            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requesting_user.id,
                message="Please let me join",
                status="pending",
            )
            db.session.add(join_request)
            db.session.commit()

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                login_user(client, admin1.email)
                first_response = client.post(
                    f"/circles/{circle.id}/request/{join_request.id}/approve", follow_redirects=True
                )
                assert first_response.status_code == 200

                join_request = db.session.get(CircleJoinRequest, join_request.id)
                assert join_request.status == "approved"
                # 1 email: circle-join approval notification only
                # (message-notification email suppressed via notify=False in handle_join_request)
                assert mock_send_email.call_count == 1

                first_decision_count = (
                    Message.query.join(Conversation)
                    .filter(
                        Conversation.context_type == "circle",
                        Conversation.context_id == circle.id,
                        Message.recipient_id == requesting_user.id,
                    )
                    .count()
                )
                assert first_decision_count == 1

                login_user(client, admin2.email)
                second_response = client.post(
                    f"/circles/{circle.id}/request/{join_request.id}/reject", follow_redirects=True
                )
                assert second_response.status_code == 200
                assert b"already been handled" in second_response.data

                join_request = db.session.get(CircleJoinRequest, join_request.id)
                assert join_request.status == "approved"
                # No new emails sent for the ignored second action
                assert mock_send_email.call_count == 1

                second_decision_count = (
                    Message.query.join(Conversation)
                    .filter(
                        Conversation.context_type == "circle",
                        Conversation.context_id == circle.id,
                        Message.recipient_id == requesting_user.id,
                    )
                    .count()
                )
                assert second_decision_count == 1

    def test_approve_join_request_sends_email_notification(self, client, app):
        """Test that approving a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name="Test Circle", circle_type="closed")

            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id, circle_id=circle.id, joined_at=datetime.now(UTC), is_admin=True
            )
            db.session.execute(stmt)

            # Create a pending join request
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requesting_user.id,
                message="I would like to join this circle please!",
                status="pending",
            )
            db.session.add(join_request)
            db.session.commit()

            # Admin logs in
            login_user(client, admin.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                # Approve the join request
                response = client.post(
                    f"/circles/{circle.id}/request/{join_request.id}/approve", follow_redirects=True
                )

                assert response.status_code == 200

                # 1 email: circle-join approval notification only
                # (message-notification email suppressed via notify=False in handle_join_request)
                assert mock_send_email.call_count == 1
                # Verify the circle-join approval email was sent
                to_email, subject, text_content, html_content = get_single_email_by_subject(
                    mock_send_email, "Join Request Approved for Test Circle"
                )

                assert to_email == requesting_user.email
                assert "approved" in text_content.lower()

                # Verify in-app decision message was created
                decision_message = (
                    Message.query.join(Conversation)
                    .filter(
                        Conversation.context_type == "circle",
                        Conversation.context_id == circle.id,
                        Message.sender_id == admin.id,
                        Message.recipient_id == requesting_user.id,
                    )
                    .order_by(Message.timestamp.desc())
                    .first()
                )
                assert decision_message is not None
                assert "approved" in decision_message.body.lower()

    def test_reject_join_request_sends_email_notification(self, client, app):
        """Test that rejecting a join request sends email notification to the requesting user."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name="Test Circle", circle_type="closed")

            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id, circle_id=circle.id, joined_at=datetime.now(UTC), is_admin=True
            )
            db.session.execute(stmt)

            # Create a pending join request
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requesting_user.id,
                message="I would like to join this circle please!",
                status="pending",
            )
            db.session.add(join_request)
            db.session.commit()

            # Admin logs in
            login_user(client, admin.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                # Reject the join request
                response = client.post(
                    f"/circles/{circle.id}/request/{join_request.id}/reject", follow_redirects=True
                )

                assert response.status_code == 200

                # 1 email: circle-join rejection notification only
                # (message-notification email suppressed via notify=False in handle_join_request)
                assert mock_send_email.call_count == 1
                # Verify the circle-join rejection email was sent
                to_email, subject, text_content, html_content = get_single_email_by_subject(
                    mock_send_email, "Join Request Denied for Test Circle"
                )

                assert to_email == requesting_user.email
                assert "denied" in text_content.lower()

                # Verify in-app decision message was created
                decision_message = (
                    Message.query.join(Conversation)
                    .filter(
                        Conversation.context_type == "circle",
                        Conversation.context_id == circle.id,
                        Message.sender_id == admin.id,
                        Message.recipient_id == requesting_user.id,
                    )
                    .order_by(Message.timestamp.desc())
                    .first()
                )
                assert decision_message is not None
                assert "denied" in decision_message.body.lower()

    def test_circle_without_approval_no_email(self, client, app):
        """Test that joining a circle without approval requirement doesn't send emails."""
        with app.app_context():
            # Create users and circle - use factory-generated unique emails
            requesting_user = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(name="Test Circle", circle_type="open")  # No approval required

            # Add admin to circle
            stmt = circle_members.insert().values(
                user_id=admin.id, circle_id=circle.id, joined_at=datetime.now(UTC), is_admin=True
            )
            db.session.execute(stmt)
            db.session.commit()

            # User logs in
            login_user(client, requesting_user.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                # Join the circle directly (no approval needed)
                response = client.post(f"/circles/join/{circle.id}", follow_redirects=True)

                assert response.status_code == 200

                # Verify no email was sent since no approval was needed
                mock_send_email.assert_not_called()
