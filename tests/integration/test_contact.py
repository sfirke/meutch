"""Integration tests for contact form routes."""

from unittest.mock import patch

from conftest import login_user
from tests.factories import UserFactory


class TestContactRoutes:
    """Test contact form routes."""

    def test_contact_page_accessible_when_authenticated(self, client, app, auth_user):
        """Test GET /contact returns 200 for logged-in user."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/contact")
            assert response.status_code == 200
            assert b"Contact Us" in response.data
            assert b"Category" in response.data
            assert b"Message" in response.data
            assert b"Send Message" in response.data

    def test_contact_page_redirects_to_login_when_unauthenticated(self, client):
        """Test GET /contact redirects to login for anonymous user."""
        response = client.get("/contact")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_contact_form_submission_sends_email_and_flashes(self, client, app, auth_user):
        """Test POST with valid data sends email and shows success flash."""
        with app.app_context():
            user = auth_user()
            UserFactory(is_admin=True, first_name="Admin", last_name="User")
            login_user(client, user.email)

            with patch("app.main.views.public.send_contact_form_email") as mock_send:
                mock_send.return_value = True

                response = client.post(
                    "/contact",
                    data={
                        "category": "issue",
                        "message": "I found a bug in the search feature.",
                    },
                    follow_redirects=True,
                )

                assert response.status_code == 200
                # Verify the email function was called with correct args
                mock_send.assert_called_once()
                call_args = mock_send.call_args[0]
                # Verify the user object is the current user
                assert call_args[0].email == user.email
                assert call_args[1] == "issue"
                assert call_args[2] == "I found a bug in the search feature."
                # Check for success flash
                assert b"sent to the Meutch team" in response.data

    def test_contact_form_submission_validation_error(self, client, app, auth_user):
        """Test POST with missing message shows validation errors."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/contact",
                data={
                    "category": "issue",
                    "message": "",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Please enter a message." in response.data

    def test_contact_form_submission_message_too_long(self, client, app, auth_user):
        """Test POST with message > 5000 chars shows error."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/contact",
                data={
                    "category": "feedback",
                    "message": "x" * 5001,
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Message must be under 5,000 characters." in response.data

    def test_contact_form_submission_email_failure(self, client, app, auth_user):
        """Test POST when send_email fails shows error flash."""
        with app.app_context():
            user = auth_user()
            UserFactory(is_admin=True, first_name="Admin", last_name="User")
            login_user(client, user.email)

            with patch("app.main.views.public.send_contact_form_email") as mock_send:
                mock_send.return_value = False

                response = client.post(
                    "/contact",
                    data={
                        "category": "issue",
                        "message": "Test message that will fail to send.",
                    },
                    follow_redirects=True,
                )

                assert response.status_code == 200
                assert b"Sorry, we couldn" in response.data

    def test_contact_link_visible_in_footer_when_authenticated(self, client, app, auth_user):
        """Test footer shows 'Contact Us' link for authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Contact Us" in response.data
            assert b"View on GitHub" not in response.data

    def test_contact_link_hidden_in_footer_when_unauthenticated(self, client):
        """Test footer shows 'View on GitHub' for anonymous users."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"View on GitHub" in response.data
        assert b"Contact Us" not in response.data

    def test_contact_link_points_to_contact_page(self, client, app, auth_user):
        """Test the contact link href is /contact."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b'href="/contact"' in response.data
