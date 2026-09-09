"""Integration tests for tag and category browsing."""

import uuid

from app import db
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ItemFactory,
    TagFactory,
    UserFactory,
)


class TestTagAndCategoryBrowsing:
    """Test tag and category browsing functionality."""

    def test_tag_items_page_valid_tag(self, client, app):
        """Test tag items page with valid tag."""
        with app.app_context():
            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and a shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            # Create a tag and some items with that tag
            tag = TagFactory(name="electronics")
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
            db.session.commit()

            response = client.get(f"/tag/{tag.id}")
            assert response.status_code == 200
            assert b'Items Tagged "electronics"' in response.data
            assert b"Laptop" in response.data
            assert b"Phone" in response.data
            assert excluded_item.name.encode() not in response.data

    def test_tag_items_page_invalid_tag(self, client, app):
        """Test tag items page with invalid tag ID."""
        with app.app_context():
            user = UserFactory()
            login_user(client, user.email)

            fake_tag_id = str(uuid.uuid4())
            response = client.get(f"/tag/{fake_tag_id}")
            assert response.status_code == 404

    def test_tag_items_page_no_items(self, client, app):
        """Test tag items page with tag that has no items."""
        with app.app_context():
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
            user = UserFactory()
            login_user(client, user.email)

            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)

            tag = TagFactory(name="test-pagination")
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
            assert excluded_item.name.encode() not in response.data

    def test_category_items_page_invalid_category(self, client, app):
        """Test category items page with invalid category ID."""
        with app.app_context():
            user = UserFactory()
            login_user(client, user.email)

            fake_category_id = str(uuid.uuid4())
            response = client.get(f"/category/{fake_category_id}")
            assert response.status_code == 404

    def test_category_items_page_no_items(self, client, app):
        """Test category items page with category that has no items."""
        with app.app_context():
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
