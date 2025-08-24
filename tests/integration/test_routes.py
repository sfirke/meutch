"""Integration tests for main routes."""
import pytest
from app import db
from app.models import Item, User, Category
from tests.factories import UserFactory, ItemFactory, CategoryFactory
from conftest import login_user
from unittest.mock import patch
import io

class TestMainRoutes:
    """Test main application routes."""
    
    def test_index_page(self, client, app):
        """Test index page loads correctly."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Welcome to Meutch' in response.data
    
    def test_index_with_authenticated_user(self, client, app, auth_user):
        """Test index page with authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/')
            assert response.status_code == 200
            assert b'Your Circles' in response.data
    
    def test_index_anonymous_user_limited_items(self, client, app):
        """Test that anonymous users see limited items with 'more' message."""
        with app.app_context():
            # Create more than 12 items to test the limit
            category = CategoryFactory()
            user = UserFactory()
            
            # Create a public circle and add the user to it
            from app.models import Circle
            circle = Circle(name="Test Public Circle", description="Test", requires_approval=False)
            db.session.add(circle)
            circle.members.append(user)
            db.session.commit()
            
            for i in range(15):
                ItemFactory(owner=user, category=category, available=True)
            
            response = client.get('/')
            assert response.status_code == 200
            # Should show the "more" message since we have more than 12 items
            response_text = response.data.decode('utf-8')
            assert 'more</strong> available items' in response_text
            assert b'Sign Up' in response.data
    
    def test_index_authenticated_user_pagination(self, client, app, auth_user):
        """Test that authenticated users get pagination controls."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            
            # Create a public circle and add the user to it
            from app.models import Circle
            circle = Circle(name="Test Public Circle", description="Test", requires_approval=False)
            db.session.add(circle)
            circle.members.append(user)
            db.session.commit()
            
            # Create more than 12 items to trigger pagination
            for i in range(15):
                ItemFactory(owner=user, category=category, available=True)
            
            login_user(client, user.email)
            response = client.get('/')
            assert response.status_code == 200
            
            # Should have pagination controls since we have 15 items (> 12 per page)
            response_text = response.data.decode('utf-8')
            assert 'aria-label="Items pages"' in response_text  # Pagination nav element
            assert 'Page 1 of 2' in response_text or 'page-item' in response_text  # Pagination indicators
            
            # Test that page 2 exists and works
            page2_response = client.get('/?page=2')
            assert page2_response.status_code == 200
            page2_text = page2_response.data.decode('utf-8')
            assert 'aria-label="Items pages"' in page2_text
    
    def test_index_anonymous_user_few_items_no_more_message(self, client, app):
        """Test that anonymous users don't see 'more' message when items <= 12."""
        with app.app_context():
            # Create only a few items
            category = CategoryFactory()
            user = UserFactory()
            
            # Create a public circle and add the user to it
            from app.models import Circle
            circle = Circle(name="Test Public Circle", description="Test", requires_approval=False)
            db.session.add(circle)
            circle.members.append(user)
            db.session.commit()
            
            for i in range(5):
                ItemFactory(owner=user, category=category, available=True)
            
            response = client.get('/')
            assert response.status_code == 200
            # Should NOT show the "more" message since we have <= 12 items
            response_text = response.data.decode('utf-8')
            assert 'more</strong> available items' not in response_text
    
    def test_about_page(self, client):
        """Test about page loads correctly."""
        response = client.get('/about')
        assert response.status_code == 200

class TestItemRoutes:
    """Test item-related routes."""
    
    def test_list_item_get_requires_login(self, client):
        """Test that listing items requires login."""
        response = client.get('/list-item')
        assert response.status_code == 302  # Redirect to login
    
    def test_list_item_get_authenticated(self, client, app, auth_user):
        """Test list item page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/list-item')
            assert response.status_code == 200
            assert b'List a New Item' in response.data
    
    def test_list_item_post_valid(self, client, app, auth_user):
        """Test creating a new item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            login_user(client, user.email)
            
            response = client.post('/list-item', data={
                'name': 'Test Item',
                'description': 'A test item',
                'category': str(category.id),
                'tags': 'electronics, test'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'has been listed successfully!' in response.data
            
            # Verify item was created
            item = Item.query.filter_by(name='Test Item').first()
            assert item is not None
            assert item.owner_id == user.id
            assert len(item.tags) == 2
    
    def test_item_detail_requires_login(self, client, app):
        """Test that item detail requires login."""
        with app.app_context():
            item = ItemFactory()
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 302  # Redirect to login
    
    def test_item_detail_authenticated(self, client, app, auth_user):
        """Test item detail page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            item = ItemFactory()
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 200
            assert item.name.encode() in response.data
    
    def test_edit_item_own_item(self, client, app, auth_user):
        """Test editing own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}/edit')
            assert response.status_code == 200
            assert b'Edit Item' in response.data
    
    def test_edit_item_not_owner(self, client, app, auth_user):
        """Test editing item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}/edit', follow_redirects=True)
            assert response.status_code == 200
            assert b'You do not have permission to edit this item.' in response.data
    
    def test_edit_item_post_valid(self, client, app, auth_user):
        """Test updating an item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/edit', data={
                'name': 'Updated Item Name',
                'description': 'Updated description',
                'category': str(category.id),
                'tags': 'updated, tags'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Item has been updated.' in response.data
            
            # Verify item was updated
            updated_item = Item.query.get(item.id)
            assert updated_item.name == 'Updated Item Name'
            assert updated_item.description == 'Updated description'
    
    def test_delete_item_own_item(self, client, app, auth_user):
        """Test deleting own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            item = ItemFactory(owner=user)
            item_id = item.id
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'Item deleted successfully.' in response.data
            
            # Verify item was deleted
            deleted_item = Item.query.get(item_id)
            assert deleted_item is None
    
    def test_delete_item_not_owner(self, client, app, auth_user):
        """Test deleting item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'You can only delete your own items.' in response.data
    
    def test_add_item_image_upload_failure(self, app, client, auth_user):
        """Test adding item when image upload fails."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory() 
            login_user(client, user.email)

            with patch('app.main.routes.upload_item_image', return_value=None):
                response = client.post('/list-item', data={
                    'name': 'Test Item',
                    'description': 'Test Description',
                    'category': str(category.id),
                    'image': (io.BytesIO(b'fake image data'), 'test.jpg'),
                    'tags': 'electronics, test'
                }, follow_redirects=True, content_type='multipart/form-data')

                assert response.status_code == 200
                assert b'Image upload failed' in response.data
                
                # Verify item was not created due to upload failure
                item = Item.query.filter_by(name='Test Item').first()
                assert item is None, "Item should not be created when image upload fails"

class TestSearchRoutes:
    """Test search functionality."""
    
    def test_search_get_empty(self, client):
        """Test search page with no query."""
        response = client.get('/search')
        assert response.status_code == 200
    
    def test_search_with_query(self, client, app):
        """Test search with query."""
        with app.app_context():
            item = ItemFactory(name='Unique Test Item')
            
            response = client.get('/search?q=Unique')
            assert response.status_code == 200
            assert item.name.encode() in response.data
    
    def test_search_no_results(self, client, app):
        """Test search with no results."""
        with app.app_context():
            response = client.get('/search?q=nonexistentitem')
            assert response.status_code == 200

class TestTagAndCategoryBrowsing:
    """Test tag and category browsing functionality."""
    
    def test_tag_items_page_valid_tag(self, client, app):
        """Test tag items page with valid tag."""
        with app.app_context():
            from app.models import Tag, Category
            from tests.factories import TagFactory
            
            # Create a tag and some items with that tag
            tag = TagFactory(name='electronics')
            
            # Get or create categories - use existing Electronics category
            electronics_category = Category.query.filter_by(name='Electronics').first()
            if not electronics_category:
                electronics_category = CategoryFactory(name='Electronics')
            
            books_category = Category.query.filter_by(name='Books & Media').first()
            if not books_category:
                books_category = CategoryFactory(name='Books & Media')
            
            # Create items with this tag
            item1 = ItemFactory(name='Laptop', category=electronics_category)
            item2 = ItemFactory(name='Phone', category=electronics_category)
            item3 = ItemFactory(name='Book', category=books_category)  # Different category, no tag
            
            item1.tags.append(tag)
            item2.tags.append(tag)
            # item3 has no tags
            
            from app import db
            db.session.commit()
            
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Items Tagged "electronics"' in response.data
            assert b'Laptop' in response.data
            assert b'Phone' in response.data
            assert b'Book' not in response.data  # Should not appear since it doesn't have the tag
    
    def test_tag_items_page_invalid_tag(self, client, app):
        """Test tag items page with invalid tag ID."""
        import uuid
        fake_tag_id = str(uuid.uuid4())
        response = client.get(f'/tag/{fake_tag_id}')
        assert response.status_code == 404
    
    def test_tag_items_page_no_items(self, client, app):
        """Test tag items page with tag that has no items."""
        with app.app_context():
            from tests.factories import TagFactory
            tag = TagFactory(name='unused-tag')
            
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Items Tagged "unused-tag"' in response.data
            assert b'No items found with the tag "unused-tag"' in response.data
    
    def test_tag_items_pagination(self, client, app):
        """Test tag items page pagination."""
        with app.app_context():
            from app.models import Tag, Category
            from tests.factories import TagFactory
            
            tag = TagFactory(name='test-pagination')
            
            # Get or create category
            category = Category.query.filter_by(name='Electronics').first()
            if not category:
                category = CategoryFactory(name='Test Pagination Category')
            
            # Create more than 12 items (current per_page) with this tag
            items = []
            for i in range(15):
                item = ItemFactory(name=f'Item {i}', category=category)
                item.tags.append(tag)
                items.append(item)
            
            from app import db
            db.session.commit()
            
            # Test first page (newest items first)
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Item 14' in response.data  # Newest item should be on page 1
            assert b'Item 3' in response.data   # Last item on page 1 (12 items per page)
            assert b'Item 2' not in response.data  # Should be on page 2
            
            # Test second page
            response = client.get(f'/tag/{tag.id}?page=2')
            assert response.status_code == 200
            assert b'Item 2' in response.data   # First item on page 2
            assert b'Item 0' in response.data   # Oldest item should be on page 2
            assert b'Item 14' not in response.data  # Should be on page 1
    
    def test_category_items_page_valid_category(self, client, app):
        """Test category items page with valid category."""
        with app.app_context():
            from app.models import Category
            
            # Get or create Electronics category
            category = Category.query.filter_by(name='Electronics').first()
            if not category:
                category = CategoryFactory(name='Test Electronics Category')
                
            # Get or create Books category
            books_category = Category.query.filter_by(name='Books & Media').first()
            if not books_category:
                books_category = CategoryFactory(name='Test Books Category')
            
            # Create items in this category
            item1 = ItemFactory(name='Laptop', category=category)
            item2 = ItemFactory(name='Phone', category=category)
            item3 = ItemFactory(name='Book', category=books_category)  # Different category
            
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert b'Items in' in response.data
            assert b'Laptop' in response.data
            assert b'Phone' in response.data
            assert b'Book' not in response.data  # Should not appear since it's in a different category
    
    def test_category_items_page_invalid_category(self, client, app):
        """Test category items page with invalid category ID."""
        import uuid
        fake_category_id = str(uuid.uuid4())
        response = client.get(f'/category/{fake_category_id}')
        assert response.status_code == 404
    
    def test_category_items_page_no_items(self, client, app):
        """Test category items page with category that has no items."""
        with app.app_context():
            category = CategoryFactory(name='Unique Empty Category')
            
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert b'Items in "Unique Empty Category"' in response.data
            assert b'No items found in the "Unique Empty Category" category' in response.data
    
    def test_category_items_pagination(self, client, app):
        """Test category items page pagination."""
        with app.app_context():
            category = CategoryFactory(name='Unique Test Category for Pagination')
            
            # Create more than 12 items (current per_page) in this category
            items = []
            for i in range(15):
                item = ItemFactory(name=f'Item {i}', category=category)
                items.append(item)
            
            # Test first page (newest items first)
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert b'Item 14' in response.data  # Newest item should be on page 1
            assert b'Item 3' in response.data   # Last item on page 1 (12 items per page)
            assert b'Item 2' not in response.data  # Should be on page 2
            
            # Test second page
            response = client.get(f'/category/{category.id}?page=2')
            assert response.status_code == 200
            assert b'Item 2' in response.data   # First item on page 2
            assert b'Item 0' in response.data   # Oldest item should be on page 2
            assert b'Item 14' not in response.data  # Should be on page 1

class TestProfileRoutes:
    """Test profile-related routes."""
    
    def test_profile_requires_login(self, client):
        """Test that profile requires login."""
        response = client.get('/profile')
        assert response.status_code == 302  # Redirect to login
    
    def test_profile_authenticated(self, client, app, auth_user):
        """Test profile page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            assert b'About Me' in response.data
    
    def test_update_profile(self, client, app, auth_user):
        """Test updating profile."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            
            response = client.post('/profile', data={
                'about_me': 'Updated bio information'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Your profile has been updated.' in response.data
            
            # Verify profile was updated
            updated_user = User.query.get(user.id)
            assert updated_user.about_me == 'Updated bio information'


class TestAccountDeletion:
    """Test account deletion functionality."""
    
    def test_delete_account_page_requires_login(self, client):
        """Test that delete account page requires login."""
        response = client.get('/delete_account')
        assert response.status_code == 302  # Redirect to login
    
    def test_delete_account_soft_delete_preserves_user_data(self, client, app, auth_user):
        """Test that account deletion uses soft delete to preserve user data for history."""
        with app.app_context():
            user = auth_user()
            user_id = user.id
            user_email = user.email
            
            login_user(client, user.email)
            
            response = client.post('/delete_account', data={
                'confirmation': 'DELETE MY ACCOUNT'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify user was soft deleted (not hard deleted)
            soft_deleted_user = db.session.get(User, user_id)
            assert soft_deleted_user is not None
            assert soft_deleted_user.is_deleted is True
            assert soft_deleted_user.deleted_at is not None
            assert "deleted_" in soft_deleted_user.email  # Email should be anonymized
            assert soft_deleted_user.email != user_email  # Email changed
