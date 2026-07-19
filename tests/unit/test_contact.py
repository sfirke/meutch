"""Unit tests for contact form and email functions."""

from unittest.mock import patch

from app.forms import ContactForm
from app.utils.email import send_contact_form_email
from tests.factories import UserFactory


class TestContactForm:
    """Test ContactForm."""

    def test_valid_contact_form(self, app):
        """Test valid contact form accepts category + message."""
        with app.app_context():
            form_data = {"category": "issue", "message": "I found a bug in the search feature."}
            form = ContactForm(data=form_data)
            assert form.validate() is True

    def test_empty_message_rejected(self, app):
        """Test that empty message is rejected."""
        with app.app_context():
            form_data = {"category": "feature", "message": ""}
            form = ContactForm(data=form_data)
            assert form.validate() is False
            assert any("Please enter a message." in error for error in form.message.errors)

    def test_message_too_long(self, app):
        """Test that message over 5000 characters is rejected."""
        with app.app_context():
            form_data = {"category": "feedback", "message": "x" * 5001}
            form = ContactForm(data=form_data)
            assert form.validate() is False
            assert any(
                "Message must be under 5,000 characters." in error for error in form.message.errors
            )

    def test_invalid_category_rejected(self, app):
        """Test that an invalid category choice is rejected."""
        with app.app_context():
            form_data = {"category": "invalid_category", "message": "Test message"}
            form = ContactForm(data=form_data)
            assert form.validate() is False
            assert "Not a valid choice" in str(form.category.errors)

    def test_valid_categories_accepted(self, app):
        """Test all valid category choices are accepted."""
        with app.app_context():
            for cat in ("issue", "feature", "feedback", "other"):
                form_data = {"category": cat, "message": "Test message"}
                form = ContactForm(data=form_data)
                assert form.validate() is True, f"Category '{cat}' should be valid"

    def test_message_at_max_length(self, app):
        """Test message at exactly 5000 characters is accepted."""
        with app.app_context():
            form_data = {"category": "issue", "message": "x" * 5000}
            form = ContactForm(data=form_data)
            assert form.validate() is True


class TestContactEmail:
    """Test send_contact_form_email function."""

    def test_send_contact_form_email_to_admins(self, app):
        """Test email is sent to all admin users with correct subject/body."""
        with app.app_context():
            user = UserFactory(first_name="Alice", last_name="Smith", email="alice@example.com")
            admin1 = UserFactory(is_admin=True, first_name="Admin", last_name="One")
            admin2 = UserFactory(is_admin=True, first_name="Admin", last_name="Two")

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_contact_form_email(user, "issue", "Test bug report")

                assert result is True
                assert mock_send_email.call_count == 2

                # Check first call
                call1_args = mock_send_email.call_args_list[0][0]
                assert call1_args[0] == admin1.email
                assert "[Issue Report] Message from Alice Smith" in call1_args[1]
                assert "Test bug report" in call1_args[2]
                assert "alice@example.com" in call1_args[2]

                # Check second call
                call2_args = mock_send_email.call_args_list[1][0]
                assert call2_args[0] == admin2.email
                assert "[Issue Report] Message from Alice Smith" in call2_args[1]
                assert "Test bug report" in call2_args[2]

    def test_send_contact_form_email_no_admins(self, app):
        """Test returns False when no admin users exist."""
        with app.app_context():
            user = UserFactory(first_name="Bob", last_name="Jones")

            result = send_contact_form_email(user, "feature", "New feature idea")

            assert result is False

    def test_send_contact_form_email_skips_deleted_admins(self, app):
        """Test admin with is_deleted=True is not included."""
        with app.app_context():
            user = UserFactory(first_name="Carol", last_name="Davis")
            admin = UserFactory(is_admin=True, first_name="Real", last_name="Admin")
            UserFactory(is_admin=True, is_deleted=True, first_name="Deleted", last_name="Admin")

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                result = send_contact_form_email(user, "feedback", "Great app!")

                assert result is True
                # Only the non-deleted admin should receive the email
                assert mock_send_email.call_count == 1
                call_args = mock_send_email.call_args_list[0][0]
                assert call_args[0] == admin.email

    def test_send_contact_form_email_send_failure(self, app):
        """Test returns False when send_email fails for all recipients."""
        with app.app_context():
            user = UserFactory(first_name="David", last_name="Lee")
            UserFactory(is_admin=True, first_name="Admin", last_name="Only")

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = False

                result = send_contact_form_email(user, "issue", "Test")

                assert result is False

    def test_send_contact_form_email_partial_failure(self, app):
        """Test returns True when at least one admin receives email."""
        with app.app_context():
            user = UserFactory(first_name="Eve", last_name="Wilson")
            UserFactory(is_admin=True, first_name="Admin1", last_name="Success")
            UserFactory(is_admin=True, first_name="Admin2", last_name="Failure")

            with patch("app.utils.email.send_email") as mock_send_email:
                # First call succeeds, second fails
                mock_send_email.side_effect = [True, False]

                result = send_contact_form_email(user, "other", "Test message")

                assert result is True
                assert mock_send_email.call_count == 2

    def test_subject_line_formatting(self, app):
        """Test subject format is [Category] Message from First Last."""
        with app.app_context():
            user = UserFactory(first_name="Frank", last_name="Miller")
            UserFactory(is_admin=True, first_name="Admin", last_name="User")

            test_cases = [
                ("issue", "[Issue Report] Message from Frank Miller"),
                ("feature", "[Feature Suggestion] Message from Frank Miller"),
                ("feedback", "[General Feedback] Message from Frank Miller"),
                ("other", "[Other Feedback] Message from Frank Miller"),
            ]

            for category, expected_subject in test_cases:
                with patch("app.utils.email.send_email") as mock_send_email:
                    mock_send_email.return_value = True

                    send_contact_form_email(user, category, "Test")

                    call_args = mock_send_email.call_args_list[0][0]
                    assert call_args[1] == expected_subject, (
                        f"Failed for category '{category}': "
                        f"expected '{expected_subject}', got '{call_args[1]}'"
                    )
