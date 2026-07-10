"""Integration tests for item routes."""

import io
import json
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from app import db
from app.models import Item
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    ItemImageFactory,
    LoanRequestFactory,
    MessageFactory,
    TagFactory,
    UserFactory,
)


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
