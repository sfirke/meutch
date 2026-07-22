"""Integration tests for main routes."""

from app import db
from app.models import Circle
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    CircleJoinRequestFactory,
    ItemFactory,
    ItemRequestFactory,
    LoanRequestFactory,
    UserFactory,
)


class TestMainRoutes:
    """Test main application routes."""

    def test_index_page(self, client, app):
        """Test index page loads correctly for anonymous users (landing page)."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"What if borrowing from a neighbor" in response.data

    def test_index_with_authenticated_user(self, client, app, auth_user):
        """Test index page with authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Community Activity" in response.data
            assert b"Create Request" in response.data
            assert b"List Item" in response.data

    def test_index_with_authenticated_user_renders_feed_filter_controls(
        self, client, app, auth_user
    ):
        """Test authenticated homepage renders feed filter controls with smart defaults."""
        with app.app_context():
            user = auth_user()
            user.latitude = 0.0
            user.longitude = 0.0
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")

            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert 'name="scope"' in content
            assert "All Activity" in content
            assert "My Circles" in content
            assert 'name="distance"' in content
            assert 'value="requests"' in content
            assert 'value="giveaways"' in content
            assert 'value="circle_joins"' in content
            assert 'value="loans"' in content
            assert 'option value="20" selected' in content

    def test_home_feed_scope_circles_hides_non_shared_public_request_and_giveaway(
        self, client, app, auth_user
    ):
        """Test scope=circles hides public request and giveaway from users without a shared circle."""
        with app.app_context():
            viewer = auth_user()
            shared_user = UserFactory()
            outsider = UserFactory()
            category = CategoryFactory()

            shared_circle = CircleFactory()
            shared_circle.members.extend([viewer, shared_user])

            outsider_circle = CircleFactory()
            outsider_circle.members.append(outsider)

            ItemRequestFactory(user=shared_user, title="Shared Scope Request", visibility="public")
            ItemRequestFactory(user=outsider, title="Outsider Scope Request", visibility="public")

            ItemFactory(
                owner=shared_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
                name="Shared Scope Giveaway",
            )
            ItemFactory(
                owner=outsider,
                category=category,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
                name="Outsider Scope Giveaway",
            )
            db.session.commit()

            login_user(client, viewer.email)

            all_scope_response = client.get("/")
            all_scope_content = all_scope_response.data.decode("utf-8")
            assert "Shared Scope Request" in all_scope_content
            assert "Outsider Scope Request" in all_scope_content
            assert "Shared Scope Giveaway" in all_scope_content
            assert "Outsider Scope Giveaway" in all_scope_content

            circles_scope_response = client.get("/?scope=circles")
            circles_scope_content = circles_scope_response.data.decode("utf-8")
            assert "Shared Scope Request" in circles_scope_content
            assert "Outsider Scope Request" not in circles_scope_content
            assert "Shared Scope Giveaway" in circles_scope_content
            assert "Outsider Scope Giveaway" not in circles_scope_content

    def test_home_feed_no_circle_viewer_sees_public_request_and_giveaway_with_join_prompt(
        self, client, app, auth_user
    ):
        """No-circle viewers should still see public activity while being nudged to join a circle."""
        with app.app_context():
            viewer = auth_user()
            requester = UserFactory()
            giveaway_owner = UserFactory()
            category = CategoryFactory()

            ItemRequestFactory(
                user=requester,
                title="No Circle Public Request",
                visibility="public",
            )
            ItemFactory(
                owner=giveaway_owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
                name="No Circle Public Giveaway",
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "No Circle Public Request" in content
            assert "No Circle Public Giveaway" in content
            assert "Join a circle to get started" in content
            assert "Find Circles to Join" in content

    def test_home_feed_no_circle_viewer_links_recommended_circle_and_hides_zero_counts(
        self, client, app, auth_user
    ):
        """Homepage prompt should link the recommended circle and omit zero-value activity counts."""
        with app.app_context():
            viewer = auth_user()
            category = CategoryFactory()
            owner = UserFactory()
            circle = CircleFactory(name="Helpful Neighbors")
            circle.members.extend([owner, UserFactory()])

            ItemFactory(owner=owner, category=category, available=True, is_giveaway=False)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "Helpful Neighbors" in content
            assert f'href="/circles/{circle.id}"' in content
            assert "1 borrowable item" in content
            assert "It has 2 members." in content
            assert "0 giveaways" not in content
            assert "0 requests" not in content

    def test_home_feed_no_circle_viewer_shows_public_activity_context_for_recommendation(
        self, client, app, auth_user
    ):
        """Homepage prompt should show total member activity counts for the recommended circle."""
        with app.app_context():
            viewer = auth_user()
            category = CategoryFactory()
            owner = UserFactory()
            circle = CircleFactory(name="Helpful Neighbors")
            circle.members.extend([owner, UserFactory()])

            ItemFactory(owner=owner, category=category, available=True, is_giveaway=False)
            ItemFactory(
                owner=owner,
                category=category,
                available=True,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            ItemRequestFactory(user=owner, visibility="public", status="open")
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "1 borrowable item" in content
            assert "1 giveaway" in content
            assert "1 request" in content

    def test_home_feed_distance_filter_hides_far_requests_and_giveaways(
        self, client, app, auth_user
    ):
        """Test distance filter applies to request and giveaway activity."""
        with app.app_context():
            viewer = auth_user()
            viewer.latitude = 40.7128  # NYC
            viewer.longitude = -74.0060

            near_user = UserFactory(latitude=40.7400, longitude=-74.0100)  # Nearby NYC
            far_user = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
            category = CategoryFactory()
            circle = CircleFactory()
            circle.members.extend([viewer, near_user, far_user])

            ItemRequestFactory(user=near_user, title="Near Distance Request", visibility="public")
            ItemRequestFactory(user=far_user, title="Far Distance Request", visibility="public")

            ItemFactory(
                owner=near_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
                name="Near Distance Giveaway",
            )
            ItemFactory(
                owner=far_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
                name="Far Distance Giveaway",
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/?distance=5")
            content = response.data.decode("utf-8")

            assert "Near Distance Request" in content
            assert "Far Distance Request" not in content
            assert "Near Distance Giveaway" in content
            assert "Far Distance Giveaway" not in content

    def test_home_feed_type_checkboxes_hide_unchecked_event_types(self, client, app, auth_user):
        """Test type checkbox filters hide unchecked activity event types."""
        with app.app_context():
            viewer = auth_user()
            owner = UserFactory()
            borrower = UserFactory()
            joiner = UserFactory(first_name="Joiner", last_name="Person")
            category = CategoryFactory()

            circle = CircleFactory()
            circle.members.extend([viewer, owner, borrower])

            ItemRequestFactory(user=owner, title="Type Filter Request", visibility="public")
            ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
                name="Type Filter Giveaway",
            )

            lent_item = ItemFactory(owner=owner, category=category, name="Type Filter Lent Item")
            LoanRequestFactory(item=lent_item, borrower=borrower, status="approved")

            join_event = CircleJoinRequestFactory(circle=circle, user=joiner, status="approved")
            db.session.add(join_event)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/?types_present=1&types=requests&types=giveaways")
            content = response.data.decode("utf-8")

            assert "Type Filter Request" in content
            assert "Type Filter Giveaway" in content
            assert "Type Filter Lent Item" not in content
            assert f"{joiner.full_name} joined {circle.name}" not in content

    def test_home_feed_circle_join_links_to_specific_circle_and_hides_combined_metadata_row(
        self, client, app, auth_user
    ):
        """Circle-join feed cards should link to the joined circle and not render the combined metadata row."""
        with app.app_context():
            viewer = auth_user()
            joiner = UserFactory(first_name="Circle", last_name="Joiner")
            circle = CircleFactory(name="Neighborhood Circle")
            circle.members.append(viewer)

            join_event = CircleJoinRequestFactory(circle=circle, user=joiner, status="approved")
            db.session.add(join_event)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert f'href="/circles/{circle.id}"' in content
            assert "View Circle" in content
            assert "View Circles" not in content
            assert "activity-feed-meta" not in content

    def test_find_page_requires_login(self, client):
        """Test /find requires authentication."""
        response = client.get("/find")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_find_page_with_authenticated_user(self, client, app, auth_user):
        """Test /find shows the search/find experience for authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/find")
            assert response.status_code == 200
            assert b"Find Items" in response.data
            assert b"Join a circle to get started" in response.data

    def test_index_anonymous_user_sees_landing_page(self, client, app):
        """Test that anonymous users see the landing page with CTAs."""
        response = client.get("/")
        assert response.status_code == 200
        response_text = response.data.decode("utf-8")
        assert "Get Started" in response_text
        assert "How Meutch Works" in response_text
        assert "See It In Action" in response_text

    def test_find_authenticated_user_pagination(self, client, app, auth_user):
        """Test that authenticated users get pagination controls on /find."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            category = CategoryFactory()

            # Create a circle and add both users to it so auth_user can see other_user's items
            circle = Circle(name="Test Circle", description="Test", circle_type="open")
            db.session.add(circle)
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            # Create more than 12 items for the other user (not auth_user)
            for i in range(15):
                ItemFactory(owner=other_user, category=category, available=True)

            login_user(client, user.email)
            response = client.get("/find")
            assert response.status_code == 200

            # Should have pagination controls since we have 15 items (> 12 per page)
            response_text = response.data.decode("utf-8")
            assert 'aria-label="Items pages"' in response_text  # Pagination nav element
            assert (
                "Page 1 of 2" in response_text or "page-item" in response_text
            )  # Pagination indicators

            # Test that page 2 exists and works
            page2_response = client.get("/find?page=2")
            assert page2_response.status_code == 200
            page2_text = page2_response.data.decode("utf-8")
            assert 'aria-label="Items pages"' in page2_text

    def test_find_public_giveaway_visible_without_query(self, client, app, auth_user):
        """Public giveaways from any circle member should appear on /find even without a search query."""
        with app.app_context():
            user = auth_user()
            # owner is in a separate circle from the viewer — not a shared circle
            owner = UserFactory()
            category = CategoryFactory()

            # Put each user in their own circle (no shared circles)
            user_circle = Circle(name="User Circle", description="", circle_type="open")
            owner_circle = Circle(name="Owner Circle", description="", circle_type="open")
            db.session.add_all([user_circle, owner_circle])
            user_circle.members.append(user)
            owner_circle.members.append(owner)
            db.session.commit()

            public_giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/find")
            assert response.status_code == 200
            assert public_giveaway.name.encode() in response.data

    def test_find_public_giveaway_visible_with_query(self, client, app, auth_user):
        """Public giveaways from any circle member should appear on /find with a search query."""
        with app.app_context():
            user = auth_user()
            owner = UserFactory()
            category = CategoryFactory()

            user_circle = Circle(name="User Circle 2", description="", circle_type="open")
            owner_circle = Circle(name="Owner Circle 2", description="", circle_type="open")
            db.session.add_all([user_circle, owner_circle])
            user_circle.members.append(user)
            owner_circle.members.append(owner)
            db.session.commit()

            public_giveaway = ItemFactory(
                owner=owner,
                category=category,
                name="UniquePublicGiveawayItem",
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/find?q=UniquePublicGiveawayItem")
            assert response.status_code == 200
            assert public_giveaway.name.encode() in response.data

    def test_about_page(self, client):
        """Test about page loads correctly."""
        response = client.get("/about")
        assert response.status_code == 200

    def test_privacy_policy_page(self, client):
        """Test privacy policy page loads correctly."""
        response = client.get("/privacy-policy")
        assert response.status_code == 200

    def test_terms_page(self, client):
        """Test terms and conditions page loads correctly."""
        response = client.get("/terms")
        assert response.status_code == 200


class TestContactRoutes:
    """Test contact form routes."""

    def test_get_contact_page_authenticated(self, client, app, auth_user):
        """Test GET /contact as authenticated user returns 200 and renders form."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/contact")
            assert response.status_code == 200
            assert b"Contact Us" in response.data
            assert b"Category" in response.data
            assert b"Message" in response.data
            assert b"Send" in response.data

    def test_get_contact_page_unauthenticated(self, client):
        """Test GET /contact as unauthenticated user returns 302 to login."""
        response = client.get("/contact")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_valid_contact_form(self, client, app, auth_user):
        """Test POST with valid data redirects, flashes success, sends email."""
        with app.app_context():
            from app import db

            user = auth_user()
            UserFactory(is_admin=True)
            db.session.commit()

            login_user(client, user.email)
            response = client.post(
                "/contact",
                data={
                    "category": "bug_report",
                    "message": "I found a bug in the search feature that needs fixing.",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Your message has been sent" in response.data

    def test_post_empty_message_shows_error(self, client, app, auth_user):
        """Test POST with empty message re-renders with validation error."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.post(
                "/contact",
                data={
                    "category": "bug_report",
                    "message": "",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This field is required" in response.data

    def test_post_short_message_shows_error(self, client, app, auth_user):
        """Test POST with message < 10 chars shows error."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.post(
                "/contact",
                data={
                    "category": "bug_report",
                    "message": "Hi",
                },
            )
            assert response.status_code == 200
            assert b"between 10 and 2000 characters" in response.data

    def test_contact_link_present_for_authenticated(self, client, app, auth_user):
        """Test authenticated page contains contact link (in footer)."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Contact" in response.data
            assert b"/contact" in response.data

    def test_contact_link_hidden_for_unauthenticated(self, client):
        """Test anonymous page does not link directly to /contact."""
        response = client.get("/")
        assert response.status_code == 200
        # The "Contact Us" text appears in the footer for unauthenticated (linking to login),
        # so href=/contact should NOT be present.
        assert b'href="/contact"' not in response.data

    def test_footer_shows_contact_for_authenticated(self, client, app, auth_user):
        """Test footer has contact link for authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b'"Contact Us"' in response.data or b"Contact Us" in response.data

    def test_footer_shows_contact_for_unauthenticated(self, client):
        """Test footer shows contact link (to login) for unauthenticated users."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Contact Us" in response.data

    def test_no_admins_shows_info_message(self, client, app, auth_user):
        """Test when no admins exist, flash an info message and redirect."""
        with app.app_context():
            user = auth_user()
            # Don't create any admin users
            login_user(client, user.email)
            response = client.post(
                "/contact",
                data={
                    "category": "bug_report",
                    "message": "I found a bug in the search feature that needs fixing.",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"currently unavailable" in response.data
