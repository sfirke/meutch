"""Integration tests for profile routes."""

from app import db
from app.models import User
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    ItemImageFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
    UserWebLinkFactory,
)


class TestProfileRoutes:
    """Test profile-related routes."""

    def test_profile_requires_login(self, client):
        """Test that profile requires login."""
        response = client.get("/profile")
        assert response.status_code == 302  # Redirect to login

    def test_profile_authenticated(self, client, app, auth_user):
        """Test profile page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get("/profile")
            assert response.status_code == 200
            assert b"About Me" in response.data

    def test_profile_has_tabs(self, client, app, auth_user):
        """Test profile page has tab navigation."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/profile")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "my-items-tab" in content
            assert "my-activity-tab" in content
            assert "about-me-tab" in content
            assert "settings-tab" in content

    def test_profile_about_me_read_only_by_default(self, client, app, auth_user):
        """Test that the About Me section shows read-only view by default."""
        with app.app_context():
            user = auth_user()
            user.about_me = "Test bio content"
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/profile")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            # Edit button should be present
            assert "Edit Profile" in content
            # Read-only view is visible (not hidden)
            assert 'id="profile-view"' in content
            assert 'id="profile-view" class="d-none"' not in content
            # Edit form exists but is hidden
            assert 'id="profile-edit"' in content
            assert 'id="profile-edit" class="d-none"' in content

    def test_profile_edit_form_shown_on_validation_error(self, client, app, auth_user):
        """Test that edit form is shown when form validation fails."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            # Submit invalid data (URL without platform)
            response = client.post(
                "/profile",
                data={
                    "about_me": "Test bio",
                    "link_1_url": "https://example.com",
                    "link_1_platform": "",
                },
            )
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            # About Me tab should be active when form has errors
            assert "about-me-tab" in content
            # Edit view should be visible and read-only view hidden on validation errors
            assert 'id="profile-view" class="d-none"' in content
            assert 'id="profile-edit" class="d-none"' not in content

    def test_profile_active_loans_have_clickable_user_and_item_links(self, client, app, auth_user):
        """Test active loans tab: item name/thumbnail link to item, View Loan button links to conversation."""
        with app.app_context():
            user = auth_user()
            lender = UserFactory()
            borrower = UserFactory()
            category = CategoryFactory()

            # Shared circle ensures profile links are accessible
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(lender)
            circle.members.append(borrower)

            borrowed_item = ItemFactory(owner=lender, category=category, name="Borrowed Item")
            ItemImageFactory(item=borrowed_item, url="https://example.com/borrowed.jpg", position=0)
            lent_item = ItemFactory(owner=user, category=category, name="Lent Item")
            ItemImageFactory(item=lent_item, url="https://example.com/lent.jpg", position=0)

            borrowed_loan = LoanRequestFactory(item=borrowed_item, borrower=user, status="approved")
            lent_loan = LoanRequestFactory(item=lent_item, borrower=borrower, status="approved")

            # Create messages so View Loan buttons appear
            borrowed_conv = ConversationFactory(context_type="item", context_id=borrowed_item.id)
            borrowed_msg = MessageFactory(
                sender=user,
                recipient=lender,
                conversation=borrowed_conv,
                loan_request=borrowed_loan,
                body="Can I borrow this?",
            )
            lent_conv = ConversationFactory(context_type="item", context_id=lent_item.id)
            lent_msg = MessageFactory(
                sender=borrower,
                recipient=user,
                conversation=lent_conv,
                loan_request=lent_loan,
                body="Can I borrow this?",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/profile?tab=my-activity")
            assert response.status_code == 200
            content = response.data.decode("utf-8")

            # Borrowing section: lender profile + item links (name + thumbnail) + View Loan button
            assert f'href="/user/{lender.id}"' in content
            assert f'href="/item/{borrowed_item.id}"' in content
            assert f'href="/conversation/{borrowed_msg.conversation_id}"' in content

            # Lending section: borrower profile + item links (name + thumbnail) + View Loan button
            assert f'href="/user/{borrower.id}"' in content
            assert f'href="/item/{lent_item.id}"' in content
            assert f'href="/conversation/{lent_msg.conversation_id}"' in content

    def test_profile_displays_custom_other_site_name(self, client, app, auth_user):
        """Test that custom name for 'Other' web links is shown in read-only profile view."""
        with app.app_context():
            user = auth_user()
            UserWebLinkFactory(
                user=user,
                platform_type="other",
                platform_name="GitHub",
                url="https://github.com/example_user",
                display_order=1,
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/profile")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "GitHub" in content
            assert "https://github.com/example_user" in content

    def test_update_profile(self, client, app, auth_user):
        """Test updating profile."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)

            response = client.post(
                "/profile", data={"about_me": "Updated bio information"}, follow_redirects=True
            )

            assert response.status_code == 200
            assert b"Your profile has been updated." in response.data

            # Verify profile was updated
            updated_user = db.session.get(User, user.id)
            assert updated_user.about_me == "Updated bio information"

    def test_profile_digest_settings_load_current_values(self, client, app, auth_user):
        """Test profile settings shows current digest values."""
        with app.app_context():
            user = auth_user()
            user.digest_frequency = "daily"
            user.digest_radius_miles = 25
            user.digest_include_requests = False
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/profile?tab=settings")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "Email Digest Settings" in content
            assert 'value="daily"' in content
            assert "selected" in content
            assert 'name="digest_radius_miles"' in content
            assert 'value="25"' in content

    def test_profile_digest_settings_save(self, client, app, auth_user):
        """Test saving digest settings from profile page."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/profile/digest-settings",
                data={
                    "digest_frequency": "daily",
                    "digest_radius_miles": "30",
                    "digest_include_giveaways": "y",
                    "digest_include_requests": "y",
                    "digest_include_circle_joins": "y",
                    "digest_giveaways_include_public": "y",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Digest settings updated." in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == "daily"
            assert updated_user.digest_radius_miles == 30
            assert updated_user.digest_include_giveaways is True
            assert updated_user.digest_include_requests is True
            assert updated_user.digest_include_circle_joins is True
            assert updated_user.digest_include_loans is False
            assert updated_user.digest_giveaways_include_public is True
            assert updated_user.digest_requests_include_public is False

    def test_profile_digest_settings_opt_out_warning(self, client, app, auth_user):
        """Test warning flash when user opts out of digest emails."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/profile/digest-settings",
                data={
                    "digest_frequency": "none",
                    "digest_radius_miles": "10",
                    "digest_include_giveaways": "y",
                    "digest_include_requests": "y",
                    "digest_include_circle_joins": "y",
                    "digest_include_loans": "y",
                    "digest_giveaways_include_public": "y",
                    "digest_requests_include_public": "y",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"You turned off digest emails" in response.data
