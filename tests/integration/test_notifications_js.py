"""
Tests for the notifications JavaScript utility
"""
from tests.factories import UserFactory
from conftest import login_user


class TestNotificationsJS:
    """Test that notifications.js is loaded site-wide"""
    
    def test_notifications_js_loaded_on_homepage(self, client, app):
        """Test that notifications.js is loaded on the homepage"""
        with app.app_context():
            response = client.get('/')
            assert response.status_code == 200
            
            # Check that notifications.js is included
            assert b'notifications.js' in response.data
            
            # Check that toast container is present
            assert b'toast-container' in response.data
    
    def test_notifications_js_loaded_on_authenticated_pages(self, client, app, auth_user):
        """Test that notifications.js is loaded on authenticated pages"""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            # Check list item page
            response = client.get('/list-item')
            assert response.status_code == 200
            assert b'notifications.js' in response.data
            assert b'toast-container' in response.data
            
            # Check profile page
            response = client.get('/profile')
            assert response.status_code == 200
            assert b'notifications.js' in response.data
            assert b'toast-container' in response.data
    
    def test_notifications_js_loaded_before_other_scripts(self, client, app):
        """Test that notifications.js is loaded before feature-specific scripts"""
        with app.app_context():
            response = client.get('/')
            assert response.status_code == 200
            
            # Find position of notifications.js
            content = response.data.decode('utf-8')
            notifications_pos = content.find('notifications.js')
            timezone_pos = content.find('timezone.js')
            pagination_pos = content.find('pagination.js')
            
            # Verify notifications.js comes first
            assert notifications_pos > 0
            assert timezone_pos > notifications_pos
            assert pagination_pos > notifications_pos
