from unittest.mock import MagicMock, patch

import pytest

from app.utils.email import build_message_reply_address, send_message_notification_email
from tests.factories import ConversationFactory, ItemFactory, MessageFactory, UserFactory


class TestMessageNotifications:
    """Test message email notification functionality."""

    def test_send_message_notification_email_regular_message(self, app):
        """Test sending email notification for a regular message."""
        with app.app_context():
            # Create test users and item
            sender = UserFactory(email="sender@test.com", first_name="John", last_name="Doe")
            recipient = UserFactory(
                email="recipient@test.com", first_name="Jane", last_name="Smith"
            )
            item = ItemFactory(name="Test Item", owner=recipient)

            # Create a regular message
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Hi, I am interested in this item!",
            )

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_message_notification_email(message)

                assert result is True
                mock_send_email.assert_called_once()

                # Check the call arguments
                call_args = mock_send_email.call_args
                assert call_args[0][0] == "recipient@test.com"  # to_email
                assert "New Message about Test Item" in call_args[0][1]  # subject
                assert "John Doe" in call_args[0][2]  # text content includes sender name
                assert (
                    "Hi, I am interested in this item!" in call_args[0][2]
                )  # text content includes message body
                assert (
                    call_args[0][3] is not None
                )  # HTML content provided as 4th positional argument
                assert "Reply to this email directly" in call_args[0][2]
                assert "reply to this email directly" in call_args[0][3]

    def test_send_message_notification_email_sets_reply_to(self, app):
        """Test message notifications include a reply-to address for email replies."""
        with app.app_context():
            app.config["MAILGUN_DOMAIN"] = "meutch.com"
            sender = UserFactory(email="sender@test.com")
            recipient = UserFactory(email="recipient@test.com")
            item = ItemFactory(name="Test Item", owner=recipient)
            message = MessageFactory(sender=sender, recipient=recipient, item=item)

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_message_notification_email(message)

                assert result is True
                assert mock_send_email.call_args.kwargs["reply_to"] == (
                    f"Meutch Replies <reply+{message.id}@meutch.com>"
                )

    def test_build_message_reply_address_returns_none_without_domain(self, app):
        with app.app_context():
            app.config["MAILGUN_DOMAIN"] = None
            message = MessageFactory()

            assert build_message_reply_address(message) is None

    def test_build_message_reply_address_with_prefix(self, app):
        """Reply address includes MAILGUN_REPLY_PREFIX when configured."""
        with app.app_context():
            app.config["MAILGUN_DOMAIN"] = "meutch.com"
            app.config["MAILGUN_REPLY_PREFIX"] = "staging-"
            message = MessageFactory()

            address = build_message_reply_address(message)
            assert address == f"Meutch Replies <reply+staging-{message.id}@meutch.com>"

    def test_build_message_reply_address_without_prefix(self, app):
        """Reply address omits prefix when MAILGUN_REPLY_PREFIX is empty."""
        with app.app_context():
            app.config["MAILGUN_DOMAIN"] = "meutch.com"
            app.config["MAILGUN_REPLY_PREFIX"] = ""
            message = MessageFactory()

            address = build_message_reply_address(message)
            assert address == f"Meutch Replies <reply+{message.id}@meutch.com>"

    def test_send_message_notification_email_loan_request(self, app):
        """Test sending email notification for a loan request message."""
        with app.app_context():
            from tests.factories import LoanRequestFactory

            # Create test users and item
            sender = UserFactory(email="borrower@test.com", first_name="John", last_name="Doe")
            recipient = UserFactory(email="owner@test.com", first_name="Jane", last_name="Smith")
            item = ItemFactory(name="Test Item", owner=recipient)

            # Create a loan request
            loan_request = LoanRequestFactory(item=item, borrower=sender, status="pending")

            # Create a loan request message
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Can I borrow this item please?",
                loan_request=loan_request,
            )

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_message_notification_email(message)

                assert result is True
                mock_send_email.assert_called_once()

                # Check the call arguments
                call_args = mock_send_email.call_args
                assert call_args[0][0] == "owner@test.com"  # to_email
                assert (
                    "New Loan Request for Test Item" in call_args[0][1]
                )  # subject for pending loan request
                assert "loan request" in call_args[0][2]  # text content indicates loan request
                assert "Reply to this email directly" not in call_args[0][2]
                assert "reply to this email directly" not in call_args[0][3]
                assert "and respond" not in call_args[0][2]
                assert "& Respond" not in call_args[0][3]
                assert mock_send_email.call_args.kwargs["reply_to"] is None

    def test_send_message_notification_email_missing_users(self, app):
        """Test handling of missing users."""
        with app.app_context():
            # Create a message with non-existent user IDs
            import uuid

            fake_message = MagicMock()
            fake_message.sender_id = uuid.uuid4()
            fake_message.recipient_id = uuid.uuid4()

            with patch("app.utils.email.send_email") as mock_send_email:
                with patch("app.models.User.query") as mock_query:
                    mock_query.get.return_value = None  # Simulate users not found

                    result = send_message_notification_email(fake_message)

                    assert result is False
                    mock_send_email.assert_not_called()

    def test_send_message_notification_email_failure(self, app):
        """Test handling of email sending failure."""
        with app.app_context():
            # Create test users and item
            sender = UserFactory(email="sender@test.com")
            recipient = UserFactory(email="recipient@test.com")
            item = ItemFactory(name="Test Item", owner=recipient)

            # Create a regular message
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, body="Test message"
            )

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = False  # Simulate email failure

                result = send_message_notification_email(message)

                assert result is False
                mock_send_email.assert_called_once()

    def test_send_message_notification_email_canceled_loan(self, app):
        """Test sending email notification for a canceled loan request."""
        with app.app_context():
            from tests.factories import LoanRequestFactory

            # Create test users and item
            sender = UserFactory(email="borrower@test.com", first_name="John", last_name="Doe")
            recipient = UserFactory(email="owner@test.com", first_name="Jane", last_name="Smith")
            item = ItemFactory(name="Test Item", owner=recipient)

            # Create a canceled loan request
            loan_request = LoanRequestFactory(item=item, borrower=sender, status="canceled")

            # Create a loan cancellation message
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Loan request has been canceled by the borrower.",
                loan_request=loan_request,
            )

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_message_notification_email(message)

                assert result is True
                mock_send_email.assert_called_once()

                # Verify the email content
                args, kwargs = mock_send_email.call_args
                to_email, subject, text_content, html_content = args

                assert to_email == "owner@test.com"
                assert "Loan Request Canceled" in subject
                assert "Test Item" in subject
                assert "loan cancellation" in text_content.lower()
                assert "canceled by the borrower" in text_content
                assert "loan cancellation" in html_content.lower()
                assert "Reply to this email directly" not in text_content
                assert "reply to this email directly" not in html_content
                assert kwargs["reply_to"] is None

    def test_send_message_notification_email_invalid_status(self, app):
        """Test that invalid loan request status raises ValueError."""
        with app.app_context():
            from tests.factories import LoanRequestFactory

            # Create test users and item
            sender = UserFactory(email="borrower@test.com", first_name="John", last_name="Doe")
            recipient = UserFactory(email="owner@test.com", first_name="Jane", last_name="Smith")
            item = ItemFactory(name="Test Item", owner=recipient)

            # Create a loan request with invalid status
            loan_request = LoanRequestFactory(
                item=item,
                borrower=sender,
                status="invalid_status",  # This should trigger the ValueError
            )

            # Create a loan request message
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                body="Test message with invalid status.",
                loan_request=loan_request,
            )

            # Should raise ValueError for unknown status
            with pytest.raises(ValueError) as exc_info:
                send_message_notification_email(message)

            assert "Unknown loan request status 'invalid_status'" in str(exc_info.value)
            assert "Valid statuses are: pending, approved, denied, completed, canceled" in str(
                exc_info.value
            )
