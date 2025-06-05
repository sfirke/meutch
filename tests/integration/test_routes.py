"""Integration tests for main routes."""
import pytest
from app.models import Item, User, Category
from tests.factories import UserFactory, ItemFactory, CategoryFactory
from conftest import login_user, logout_user

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
    
    def test_user_profile_public(self, client, app, auth_user):
        """Test viewing another user's profile."""
        with app.app_context():
            other_user = UserFactory()
            ItemFactory(owner=other_user)  # Give them an item
            
            response = client.get(f'/user/{other_user.id}')
            assert response.status_code == 200
            assert other_user.full_name.encode() in response.data
