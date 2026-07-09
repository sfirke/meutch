"""Integration tests for main routes."""

import io
import json
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from app import db
from app.models import Circle, Item, Message, User
from app.utils.digest_tokens import generate_digest_manage_token
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    CircleJoinRequestFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    ItemFactory,
    ItemImageFactory,
    ItemRequestFactory,
    LoanRequestFactory,
    MessageFactory,
    TagFactory,
    UserFactory,
    UserWebLinkFactory,
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


class TestItemRoutes:
    """Test item-related routes."""

    def test_list_item_get_requires_login(self, client):
        """Test that listing items requires login."""
        response = client.get("/list-item")
        assert response.status_code == 302  # Redirect to login

    def test_list_item_get_authenticated(self, client, app, auth_user):
        """Test list item page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get("/list-item")
            assert response.status_code == 200
            assert b"List a New Item" in response.data

    def test_list_item_post_valid(self, client, app, auth_user):
        """Test creating a new item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data={
                    "name": "Test Item",
                    "description": "A test item",
                    "category": str(category.id),
                    "tags": "electronics, test",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"has been listed successfully!" in response.data

            # Verify item was created
            item = Item.query.filter_by(name="Test Item").first()
            assert item is not None
            assert item.owner_id == user.id
            assert len(item.tags) == 2

    def test_list_item_post_escapes_html_in_name(self, client, app, auth_user):
        """Test that HTML in item names is escaped in the flash message to prevent XSS."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            xss_name = '<script>alert("xss")</script>'
            response = client.post(
                "/list-item",
                data={
                    "name": xss_name,
                    "description": "A test item",
                    "category": str(category.id),
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"has been listed successfully!" in response.data
            # The raw script tag must NOT appear unescaped
            assert b"<script>alert" not in response.data
            # The escaped version should be present
            assert b"&lt;script&gt;" in response.data

    def test_list_item_post_create_another_redirects_to_list_form(self, client, app, auth_user):
        """Test create-another submit action returns user to the list-item form."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post(
                "/list-item",
                data={
                    "name": "Another Item",
                    "description": "A test item for create another flow",
                    "category": str(category.id),
                    "submit_and_create_another": "List Item & Create Another",
                },
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert response.headers["Location"].endswith("/list-item")

            item = Item.query.filter_by(name="Another Item").first()
            assert item is not None
            assert item.owner_id == user.id

    def test_list_item_post_duplicate_creation_token_reuses_existing_item(
        self, client, app, auth_user
    ):
        """Posting the same creation token twice should reuse the original item instead of creating a duplicate."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            creation_token = uuid.uuid4()
            login_user(client, user.email)

            post_data = {
                "name": "Duplicate Guard Item",
                "description": "A test item",
                "category": str(category.id),
                "tags": "electronics, test",
                "creation_token": str(creation_token),
            }

            first_response = client.post("/list-item", data=post_data, follow_redirects=True)
            assert first_response.status_code == 200
            assert b"has been listed successfully!" in first_response.data

            second_response = client.post("/list-item", data=post_data, follow_redirects=True)

            assert second_response.status_code == 200
            assert (
                b"We already listed this item from your earlier submission" in second_response.data
            )

            item = Item.query.filter_by(owner_id=user.id, creation_token=creation_token).one()
            assert item.name == "Duplicate Guard Item"
            assert Item.query.filter_by(owner_id=user.id, name="Duplicate Guard Item").count() == 1

    def test_list_item_duplicate_creation_token_create_another_redirects_back_to_form(
        self, client, app, auth_user
    ):
        """Duplicate retries should preserve the create-another flow without creating a second item."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            creation_token = uuid.uuid4()
            login_user(client, user.email)

            post_data = {
                "name": "Duplicate Create Another",
                "description": "A test item",
                "category": str(category.id),
                "creation_token": str(creation_token),
                "submit_and_create_another": "List Item & Create Another",
            }

            first_response = client.post("/list-item", data=post_data, follow_redirects=True)
            assert first_response.status_code == 200
            assert b"List a New Item" in first_response.data

            second_response = client.post("/list-item", data=post_data, follow_redirects=True)

            assert second_response.status_code == 200
            assert b"List a New Item" in second_response.data
            assert (
                b"We already listed this item from your earlier submission" in second_response.data
            )
            assert (
                Item.query.filter_by(owner_id=user.id, name="Duplicate Create Another").count() == 1
            )

    def test_item_detail_requires_login(self, client, app):
        """Test that item detail requires login."""
        with app.app_context():
            item = ItemFactory()
            response = client.get(f"/item/{item.id}")
            assert response.status_code == 302  # Redirect to login

    def test_item_detail_authenticated(self, client, app, auth_user):
        """Test item detail page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(owner)
            item = ItemFactory(owner=owner)
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            assert item.name.encode() in response.data

    def test_item_detail_uses_thumbnail_carousel_for_multiple_images(self, client, app, auth_user):
        """Multi-image item detail should render a thumbnail strip below the carousel."""
        with app.app_context():
            viewer = auth_user()
            owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(viewer)
            circle.members.append(owner)
            item = ItemFactory(owner=owner)
            ItemImageFactory(item=item, position=0)
            ItemImageFactory(item=item, position=1)
            ItemImageFactory(item=item, position=2)
            db.session.commit()

            login_user(client, viewer.email)

            response = client.get(f"/item/{item.id}")

            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "itemImageCarousel" in content
            assert "item-thumbnail" in content
            assert 'data-bs-slide-to="2"' in content

    def test_edit_item_own_item(self, client, app, auth_user):
        """Test editing own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}/edit")
            assert response.status_code == 200
            assert b"Edit Item" in response.data

    def test_edit_item_not_owner(self, client, app, auth_user):
        """Test editing item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)

            response = client.get(f"/item/{item.id}/edit", follow_redirects=True)
            assert response.status_code == 200
            assert b"You do not have permission to edit this item." in response.data

    def test_edit_item_post_valid(self, client, app, auth_user):
        """Test updating an item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)

            response = client.post(
                f"/item/{item.id}/edit",
                data={
                    "name": "Updated Item Name",
                    "description": "Updated description",
                    "category": str(category.id),
                    "tags": "updated, tags",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Item has been updated." in response.data

            # Verify item was updated
            updated_item = db.session.get(Item, item.id)
            assert updated_item.name == "Updated Item Name"
            assert updated_item.description == "Updated description"

    def test_edit_item_redirects_to_item_detail(self, client, app, auth_user):
        """After editing an item, the user should be redirected to the item's detail page."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)

            # Don't follow redirects so we can inspect the Location header
            response = client.post(
                f"/item/{item.id}/edit",
                data={
                    "name": "Redirected Name",
                    "description": "Redirect description",
                    "category": str(category.id),
                    "tags": "redirect, test",
                },
                follow_redirects=False,
            )

            # Expect a redirect (302) to the item detail page
            assert response.status_code in (301, 302)
            location = response.headers.get("Location", "")
            assert f"/item/{item.id}" in location

            # Confirm the database was updated
            updated = db.session.get(Item, item.id)
            assert updated.name == "Redirected Name"

    def test_edit_item_rejects_invalid_image_order_payload(self, client, app, auth_user):
        """Test that tampered image ordering data is rejected instead of being silently ignored."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category, name="Original Name")
            login_user(client, user.email)

            response = client.post(
                f"/item/{item.id}/edit",
                data={
                    "name": "Tampered Name",
                    "description": "Updated description",
                    "category": str(category.id),
                    "image_order": "not-json",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Photo order data was invalid." in response.data

            unchanged_item = db.session.get(Item, item.id)
            assert unchanged_item.name == "Original Name"

    def test_edit_item_persists_existing_image_reorder(self, client, app, auth_user):
        """Submitted image_order should update existing image positions."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category, name="Original Name")
            image_1 = ItemImageFactory(item=item, position=0)
            image_2 = ItemImageFactory(item=item, position=1)
            image_3 = ItemImageFactory(item=item, position=2)
            db.session.commit()

            login_user(client, user.email)

            response = client.post(
                f"/item/{item.id}/edit",
                data={
                    "name": "Original Name",
                    "description": "Updated description",
                    "category": str(category.id),
                    "image_order": json.dumps([str(image_3.id), str(image_1.id), str(image_2.id)]),
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Item has been updated." in response.data

            db.session.expire_all()
            updated_item = db.session.get(Item, item.id)

            assert [str(image.id) for image in updated_item.images] == [
                str(image_3.id),
                str(image_1.id),
                str(image_2.id),
            ]
            assert [image.position for image in updated_item.images] == [0, 1, 2]

    def test_edit_item_retains_category(self, client, app, auth_user):
        """Test that the category is retained when editing an item."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(
                owner=user,
                category=category,
                name="Original Item",
                description="Original description",
            )
            # Add tags to verify they are also retained (as reference)
            tag1 = TagFactory(name="tag1")
            tag2 = TagFactory(name="tag2")
            item.tags.append(tag1)
            item.tags.append(tag2)
            db.session.commit()

            login_user(client, user.email)

            # GET request to edit page
            response = client.get(f"/item/{item.id}/edit")
            assert response.status_code == 200
            response_text = response.data.decode("utf-8")

            # Verify the category is present and pre-selected in the form
            assert (
                str(category.id) in response_text
            ), f"Category ID {category.id} should be present in the edit form"
            # Check that the category option has the "selected" attribute
            assert (
                f'<option selected value="{category.id}">{category.name}</option>' in response_text
                or f'<option value="{category.id}" selected>{category.name}</option>'
                in response_text
            ), "Category should be pre-selected in the edit form"

            # Verify tags are also populated (as reference)
            assert (
                "tag1, tag2" in response_text or "tag2, tag1" in response_text
            ), "Tags should be pre-populated in the edit form"

    def test_delete_item_own_item(self, client, app, auth_user):
        """Test deleting own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            item = ItemFactory(owner=user)
            item_id = item.id
            login_user(client, user.email)

            response = client.post(f"/item/{item.id}/delete", follow_redirects=True)
            assert response.status_code == 200
            assert b"Item deleted successfully." in response.data

            # Verify item was deleted
            deleted_item = db.session.get(Item, item_id)
            assert deleted_item is None

    def test_delete_item_not_owner(self, client, app, auth_user):
        """Test deleting item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)

            response = client.post(f"/item/{item.id}/delete", follow_redirects=True)
            assert response.status_code == 200
            assert b"You can only delete your own items." in response.data

    def test_delete_item_with_active_loan_is_blocked(self, client, app, auth_user):
        """Owners must resolve active loans before deleting an item."""
        with app.app_context():
            owner = auth_user()
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=2),
                end_date=date.today() + timedelta(days=5),
            )
            loan_message = MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="I still have this item and can return it this weekend.",
            )
            item_id = item.id
            loan_conversation_id = loan_message.conversation_id
            db.session.commit()

            login_user(client, owner.email)

            response = client.post(f"/item/{item.id}/delete", follow_redirects=False)

            assert response.status_code == 302
            assert response.headers["Location"].endswith(f"/conversation/{loan_conversation_id}")
            assert db.session.get(Item, item_id) is not None

    def test_delete_modal_for_active_loan_shows_resolution_guidance(self, client, app, auth_user):
        """Delete modal should send owners to the active loan instead of offering deletion."""
        with app.app_context():
            owner = auth_user()
            borrower = UserFactory(first_name="Taylor", last_name="Borrower")
            item = ItemFactory(owner=owner, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=7),
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="Thanks again for lending this to me.",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/item/{item.id}")

            assert response.status_code == 200
            assert b"This item is currently out on loan" in response.data
            assert b"Mark the item returned or cancel the loan before deleting it." in response.data
            assert b"View Active Loan" in response.data

    def test_add_item_image_upload_failure(self, app, client, auth_user):
        """Test adding item when image upload fails."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            with patch(
                "app.services.item_service.upload_item_images",
                side_effect=ValueError("upload failed"),
            ):
                response = client.post(
                    "/list-item",
                    data={
                        "name": "Test Item",
                        "description": "Test Description",
                        "category": str(category.id),
                        "image": (io.BytesIO(b"fake image data"), "test.jpg"),
                        "tags": "electronics, test",
                    },
                    follow_redirects=True,
                    content_type="multipart/form-data",
                )

                assert response.status_code == 200
                assert b"Image upload failed" in response.data

                # Verify item was not created due to upload failure
                item = Item.query.filter_by(name="Test Item").first()
                assert item is None, "Item should not be created when image upload fails"


class TestSearchRoutes:
    """Test search functionality."""


class TestTagAndCategoryBrowsing:
    """Test tag and category browsing functionality."""

    def test_tag_items_page_valid_tag(self, client, app):
        """Test tag items page with valid tag."""
        with app.app_context():
            # Create a user and login
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and a shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            # Create a tag and some items with that tag
            tag = TagFactory(name="electronics")

            # Get or create categories - use factory-generated unique names
            electronics_category = CategoryFactory()

            books_category = CategoryFactory()

            # Create items with this tag - owned by user in shared circle
            item1 = ItemFactory(name="Laptop", category=electronics_category, owner=item_owner)
            item2 = ItemFactory(name="Phone", category=electronics_category, owner=item_owner)
            excluded_item = ItemFactory(
                name="ZZZ_NOT_RENDERED_TAG_ITEM_ZZZ",
                category=books_category,
                owner=item_owner,
            )  # Different category, no tag

            item1.tags.append(tag)
            item2.tags.append(tag)
            # item3 has no tags

            db.session.commit()

            response = client.get(f"/tag/{tag.id}")
            assert response.status_code == 200
            assert b'Items Tagged "electronics"' in response.data
            assert b"Laptop" in response.data
            assert b"Phone" in response.data
            assert (
                excluded_item.name.encode() not in response.data
            )  # Should not appear since it doesn't have the tag

    def test_tag_items_page_invalid_tag(self, client, app):
        """Test tag items page with invalid tag ID."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            import uuid

            fake_tag_id = str(uuid.uuid4())
            response = client.get(f"/tag/{fake_tag_id}")
            assert response.status_code == 404

    def test_tag_items_page_no_items(self, client, app):
        """Test tag items page with tag that has no items."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # User must be in a circle to see the "no items" message (not the "join a circle" message)
            circle = CircleFactory()
            circle.members.append(user)

            tag = TagFactory(name="unused-tag")
            db.session.commit()

            response = client.get(f"/tag/{tag.id}")
            assert response.status_code == 200
            assert b'Items Tagged "unused-tag"' in response.data
            assert b'No items found with the tag "unused-tag"' in response.data

    def test_tag_items_pagination(self, client, app):
        """Test tag items page pagination."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            tag = TagFactory(name="test-pagination")

            # Get or create category
            category = CategoryFactory()

            # Create more than 12 items (current per_page) with this tag - owned by circle member
            items = []
            import datetime as dt
            from datetime import UTC, timedelta

            base_time = dt.datetime.now(UTC)
            for i in range(15):
                item = ItemFactory(name=f"Item {i}", category=category, owner=item_owner)
                # Set created_at explicitly to ensure proper ordering (older items get older timestamps)
                item.created_at = base_time - timedelta(minutes=15 - i)
                item.tags.append(tag)
                items.append(item)

            db.session.commit()

            # Test first page (newest items first)
            response = client.get(f"/tag/{tag.id}")
            assert response.status_code == 200
            assert b"Item 14" in response.data  # Newest item should be on page 1
            assert b"Item 3" in response.data  # Last item on page 1 (12 items per page)
            assert b"Item 2" not in response.data  # Should be on page 2

            # Test second page
            response = client.get(f"/tag/{tag.id}?page=2")
            assert response.status_code == 200
            assert b"Item 2" in response.data  # First item on page 2
            assert b"Item 0" in response.data  # Oldest item should be on page 2
            assert b"Item 14" not in response.data  # Should be on page 1

    def test_category_items_page_valid_category(self, client, app):
        """Test category items page with valid category."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            # Create categories
            category = CategoryFactory()

            books_category = CategoryFactory()

            # Create items in this category - owned by circle member
            ItemFactory(name="Laptop", category=category, owner=item_owner)
            ItemFactory(name="Phone", category=category, owner=item_owner)
            excluded_item = ItemFactory(
                name="ZZZ_NOT_RENDERED_CATEGORY_ITEM_ZZZ",
                category=books_category,
                owner=item_owner,
            )  # Different category

            db.session.commit()

            response = client.get(f"/category/{category.id}")
            assert response.status_code == 200
            assert b"Items in" in response.data
            assert b"Laptop" in response.data
            assert b"Phone" in response.data
            assert (
                excluded_item.name.encode() not in response.data
            )  # Should not appear since it's in a different category

    def test_category_items_page_invalid_category(self, client, app):
        """Test category items page with invalid category ID."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            import uuid

            fake_category_id = str(uuid.uuid4())
            response = client.get(f"/category/{fake_category_id}")
            assert response.status_code == 404

    def test_category_items_page_no_items(self, client, app):
        """Test category items page with category that has no items."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # User must be in a circle to see the "no items" message
            circle = CircleFactory()
            circle.members.append(user)

            category = CategoryFactory()

            db.session.commit()

            response = client.get(f"/category/{category.id}")
            assert response.status_code == 200
            assert f'Items in "{category.name}"'.encode() in response.data
            assert f'No items found in the "{category.name}" category'.encode() in response.data

    def test_category_items_pagination(self, client, app):
        """Test category items page pagination."""
        with app.app_context():
            from conftest import login_user

            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            category = CategoryFactory()

            # Create more than 12 items (current per_page) in this category - owned by circle member
            items = []
            import datetime as dt
            from datetime import UTC, timedelta

            base_time = dt.datetime.now(UTC)
            for i in range(15):
                item = ItemFactory(name=f"Item {i}", category=category, owner=item_owner)
                # Set created_at explicitly to ensure proper ordering (older items get older timestamps)
                item.created_at = base_time - timedelta(minutes=15 - i)
                items.append(item)

            db.session.commit()

            # Test first page (newest items first)
            response = client.get(f"/category/{category.id}")
            assert response.status_code == 200
            assert b"Item 14" in response.data  # Newest item should be on page 1
            assert b"Item 3" in response.data  # Last item on page 1 (12 items per page)
            assert b"Item 2" not in response.data  # Should be on page 2

            # Test second page
            response = client.get(f"/category/{category.id}?page=2")
            assert response.status_code == 200
            assert b"Item 2" in response.data  # First item on page 2
            assert b"Item 0" in response.data  # Oldest item should be on page 2
            assert b"Item 14" not in response.data  # Should be on page 1


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
                    # intentionally omit loans + requests public so they become False
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


class TestAccountDeletion:
    """Test account deletion functionality."""

    def test_delete_account_page_requires_login(self, client):
        """Test that delete account page requires login."""
        response = client.get("/delete_account")
        assert response.status_code == 302  # Redirect to login

    def test_delete_account_soft_delete_preserves_user_data(self, client, app, auth_user):
        """Test that account deletion uses soft delete to preserve user data for history."""
        with app.app_context():
            user = auth_user()
            user_id = user.id
            user_email = user.email

            login_user(client, user.email)

            response = client.post(
                "/delete_account", data={"confirmation": "DELETE MY ACCOUNT"}, follow_redirects=True
            )

            assert response.status_code == 200

            # Verify user was soft deleted (not hard deleted)
            soft_deleted_user = db.session.get(User, user_id)
            assert soft_deleted_user is not None
            assert soft_deleted_user.is_deleted is True
            assert soft_deleted_user.deleted_at is not None
            assert "deleted_" in soft_deleted_user.email  # Email should be anonymized
            assert soft_deleted_user.email != user_email  # Email changed


class TestDigestManageRoutes:
    """Integration tests for anonymous digest manage links."""

    def test_digest_manage_valid_token(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()

            token = generate_digest_manage_token(user)
            response = client.get(f"/digest/manage/{token}")

            assert response.status_code == 200
            assert b"Manage Digest Emails" in response.data
            assert b"One-click unsubscribe" in response.data
            assert b"Switch to daily" in response.data
            assert b"Switch to weekly" not in response.data  # Already on weekly

    def test_digest_manage_shows_only_alternative_frequency(self, client, app):
        """Test that only the alternative frequency button is shown."""
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()

            token = generate_digest_manage_token(user)
            response = client.get(f"/digest/manage/{token}")

            assert response.status_code == 200
            assert b"Switch to weekly" in response.data
            assert b"Switch to daily" not in response.data  # Already on daily

    def test_digest_manage_invalid_token(self, client):
        response = client.get("/digest/manage/not-a-valid-token")
        assert response.status_code == 400
        assert b"invalid" in response.data.lower()

    def test_digest_manage_expired_token(self, client):
        with patch(
            "app.main.views.profile.verify_digest_manage_token", return_value=(None, "expired")
        ):
            response = client.get("/digest/manage/expired-token")

        assert response.status_code == 410
        assert b"expired" in response.data.lower()

    def test_digest_unsubscribe_sets_frequency_none(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/unsubscribe/{token}")
            assert response.status_code == 200
            assert b"unsubscribed" in response.data.lower()

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_NONE

    def test_digest_set_frequency_updates_to_daily(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/daily")
            assert response.status_code == 200
            assert b"Digest frequency updated to" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_DAILY

    def test_digest_set_frequency_updates_to_weekly(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/weekly")
            assert response.status_code == 200
            assert b"Digest frequency updated to" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_WEEKLY

    def test_digest_set_frequency_rejects_invalid_frequency(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/none")
            assert response.status_code == 400
            assert b"Invalid digest frequency option" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_WEEKLY


class TestMessagingRoutes:
    """Test messaging inbox routes."""

    def test_mark_all_read_marks_unread_messages(self, client, app):
        """POST /messages/mark-all-read marks unread messages as read."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            msg = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()
            msg_id = msg.id

            login_user(client, recipient.email)
            # The CSRF token is disabled in tests so we can POST without it
            response = client.post(
                "/messages/mark-all-read?status=inbox",
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Entire inbox marked as read." in response.data

            db.session.expire_all()
            assert db.session.get(Message, msg_id).is_read is True

    def test_messages_inbox_forms_have_csrf_token(self, client, app):
        """Every POST form in the inbox must include a hidden csrf_token input
        whose value is populated by csrf_token()."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # The page should contain at least one <form method="POST">.
            import re

            post_forms = re.findall(r'<form[^>]*method="POST"[^>]*>', html)
            assert len(post_forms) >= 1, "Expected at least one POST form"

            # Each form should render a hidden csrf_token input.
            # csrf_token() returns the raw token string, so the template
            # must wrap it: <input type="hidden" name="csrf_token" value="...">
            csrf_inputs = re.findall(r'<input[^>]*name="csrf_token"[^>]*>', html)
            # When WTF_CSRF_ENABLED=False, csrf_token() returns '' so the
            # input renders with an empty value — which is fine for tests.
            assert (
                len(csrf_inputs) >= 1
            ), "Expected at least one csrf_token hidden input in the page"

    def test_messages_inbox_shows_avatar_image_when_profile_image_url_set(self, client, app):
        """When the other user has a profile_image_url, the inbox must render
        an <img> tag instead of showing initials."""
        with app.app_context():
            sender = UserFactory(
                profile_image_url="https://example.com/avatars/alice.jpg",
                first_name="Alice",
                last_name="Smith",
            )
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # The avatar for Alice should be an <img> with the correct src
            assert (
                'src="https://example.com/avatars/alice.jpg"' in html
            ), "Expected avatar <img> for user with profile_image_url"
            # Initials should NOT appear inside Alice's avatar div
            import re

            avatar_pattern = re.compile(r'<div class="conv-avatar">(.*?)</div>', re.DOTALL)
            alice_avatar_found = False
            for match in avatar_pattern.finditer(html):
                content = match.group(1)
                if "https://example.com/avatars/alice.jpg" in content:
                    alice_avatar_found = True
                    assert (
                        "AS" not in content
                    ), "Initials should not appear in avatar div when profile image is set"
                    assert (
                        "<img" in content
                    ), "Expected <img> tag in avatar div when profile_image_url is set"
            assert alice_avatar_found, "Could not find Alice's avatar div in the page"

    def test_messages_inbox_shows_initials_when_no_profile_image(self, client, app):
        """When the other user has no profile_image_url, the inbox must render
        initials as a fallback."""
        with app.app_context():
            sender = UserFactory(
                profile_image_url=None,
                first_name="Bob",
                last_name="Jones",
            )
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # Initials should appear for this user
            assert "BJ" in html, "Expected initials 'BJ' for user without profile image"
            # No <img> tag in the avatar div for this user
            # (the div should contain the initials text, not an img)
            import re

            # Find the conv-avatar div that contains "BJ"
            avatar_pattern = re.compile(r'<div class="conv-avatar">(.*?)</div>', re.DOTALL)
            for match in avatar_pattern.finditer(html):
                content = match.group(1)
                if "BJ" in content:
                    assert (
                        "<img" not in content
                    ), "No <img> expected in avatar div when user has no profile image"
                    break

    def test_bulk_archive_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-archive preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=False
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-archive?page=2&sort=oldest&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=oldest" in response.location
            assert "status=inbox" in response.location

    def test_bulk_mark_read_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-mark-read preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=True
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-mark-read?page=3&sort=unread&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=3" in response.location
            assert "sort=unread" in response.location
            assert "status=inbox" in response.location

    def test_bulk_mark_unread_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-mark-unread preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=True
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-mark-unread?page=2&sort=newest&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=newest" in response.location
            assert "status=inbox" in response.location

    def test_mark_all_read_preserves_page_and_sort(self, client, app):
        """POST /messages/mark-all-read preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=False
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/mark-all-read?page=5&sort=oldest&status=archived",
            )

            assert response.status_code == 302
            assert "page=5" in response.location
            assert "sort=oldest" in response.location
            assert "status=archived" in response.location

    def test_bulk_unarchive_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-unarchive preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(
                conversation=conversation, user=recipient, is_archived=True
            )
            ConversationParticipantFactory(conversation=conversation, user=sender)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=True
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-unarchive?page=2&sort=name_asc&status=archived",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=name_asc" in response.location
            assert "status=archived" in response.location
