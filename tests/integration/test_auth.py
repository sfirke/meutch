"""Integration tests for authentication routes."""
import pytest
from app.models import User
from tests.factories import UserFactory, ItemFactory
from conftest import login_user, logout_user, TEST_PASSWORD
from unittest.mock import patch, Mock

class TestAuthenticationRoutes:
    """Test authentication routes."""
    
    def test_login_page(self, client):
        """Test login page loads correctly."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Log In' in response.data
    
    def test_login_valid_credentials(self, client, app, auth_user):
        """Test login with valid credentials."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Welcome to Meutch' in response.data  # Redirected to home
    
    def test_login_invalid_credentials(self, client, app, auth_user):
        """Test login with invalid credentials."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': 'wrongpassword'
            })
            
            assert response.status_code == 200
            assert b'Invalid email or password' in response.data
    
    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'password'
        })
        
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data
    
    def test_login_unconfirmed_email(self, client, app):
        """Test login with unconfirmed email."""
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': TEST_PASSWORD
            })
            
            assert response.status_code == 200
            assert b'Please confirm your email' in response.data
    
    def test_logout(self, client, app, auth_user):
        """Test logout functionality."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            # First login
            login_user(client, user.email)
            
            # Then logout
            response = client.get('/auth/logout', follow_redirects=True)
            assert response.status_code == 200
            # Just verify we're redirected to main page instead of looking for logout message
            assert b'Welcome to Meutch' in response.data
    
    def test_register_page(self, client):
        """Test registration page loads correctly."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'Register' in response.data
    
    def test_register_valid_data_with_address(self, client, app):
        """Test registration with valid data using address input."""
        with app.app_context():
            with patch('app.auth.routes.geocode_address', return_value=(40.7128, -74.0060)):
                response = client.post('/auth/register', data={
                    'email': 'newuser@example.com',
                    'first_name': 'New',
                    'last_name': 'User',
                    'location_method': 'address',
                    'street': '123 New St',
                    'city': 'New City',
                    'state': 'NC',
                    'zip_code': '12345',
                    'country': 'USA',
                    'password': 'newpassword123',
                    'confirm_password': 'newpassword123'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                assert b'A confirmation email has been sent to you by email.' in response.data
                
                # Verify user was created with coordinates
                user = User.query.filter_by(email='newuser@example.com').first()
                assert user is not None
                assert user.email_confirmed is False  # Should require confirmation
                assert user.latitude == 40.7128
                assert user.longitude == -74.0060

    def test_register_valid_data_with_coordinates(self, client, app):
        """Test registration with valid data using direct coordinates."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'coorduser@example.com',
                'first_name': 'Coord',
                'last_name': 'User',
                'location_method': 'coordinates',
                'latitude': '34.0522',
                'longitude': '-118.2437',
                'password': 'coordpassword123',
                'confirm_password': 'coordpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'A confirmation email has been sent to you by email.' in response.data
            
            # Verify user was created with coordinates
            user = User.query.filter_by(email='coorduser@example.com').first()
            assert user is not None
            assert user.email_confirmed is False  # Should require confirmation
            assert user.latitude == 34.0522
            assert user.longitude == -118.2437

    def test_register_valid_data_skip_location(self, client, app):
        """Test registration with valid data skipping location."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'skipuser@example.com',
                'first_name': 'Skip',
                'last_name': 'User',
                'location_method': 'skip',
                'password': 'skippassword123',
                'confirm_password': 'skippassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'A confirmation email has been sent to you by email.' in response.data
            
            # Verify user was created without coordinates
            user = User.query.filter_by(email='skipuser@example.com').first()
            assert user is not None
            assert user.email_confirmed is False  # Should require confirmation
            assert user.latitude is None
            assert user.longitude is None
    
    def test_register_duplicate_email(self, client, app, auth_user):
        """Test registration with duplicate email."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            response = client.post('/auth/register', data={
                'email': user.email,  # Use existing email
                'first_name': 'Duplicate',
                'last_name': 'User',
                'location_method': 'skip',
                'password': 'duplicatepassword123',
                'confirm_password': 'duplicatepassword123'
            })
            
            assert response.status_code == 200
            assert b'This email is already registered. Please choose a different one.' in response.data
    
    def test_register_password_mismatch(self, client):
        """Test registration with password mismatch."""
        response = client.post('/auth/register', data={
            'email': 'mismatch@example.com',
            'first_name': 'Mismatch',
            'last_name': 'User',
            'location_method': 'skip',
            'password': 'password123',
            'confirm_password': 'differentpassword123'
        })
        
        assert response.status_code == 200
        assert b'Passwords must match' in response.data
    
    def test_register_email_error(self, app, client):
        """Test registration when email sending fails."""
        with app.app_context():
            with patch('app.auth.routes.send_confirmation_email', return_value=False):
                response = client.post('/auth/register', data={
                    'email': 'test@example.com',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'password': TEST_PASSWORD,
                    'confirm_password': TEST_PASSWORD,
                    'location_method': 'skip'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                assert b'Error sending confirmation email' in response.data
    
    def test_case_insensitive_login(self, client, app):
        """Test that login is case-insensitive for email addresses."""
        with app.app_context():
            # Create a user with lowercase email
            user = UserFactory(email='test@example.com', email_confirmed=True)
            
            # Test login with a small set of different cases (original + one variant)
            test_emails = [
                'test@example.com',    # Original
                'Test@example.com',    # Capitalized first letter
            ]
            
            for email in test_emails:
                response = client.post('/auth/login', data={
                    'email': email,
                    'password': TEST_PASSWORD
                }, follow_redirects=True)
                
                assert response.status_code == 200, f"Failed for email: {email}"
                assert b'Welcome to Meutch' in response.data, f"Failed for email: {email}"
                
                # Logout after each test
                client.get('/auth/logout')

    def test_case_insensitive_registration_duplicate_prevention(self, client, app):
        """Test that registration prevents duplicates regardless of case."""
        with app.app_context():
            # Register with lowercase email
            response = client.post('/auth/register', data={
                'email': 'unique@example.com',
                'first_name': 'First',
                'last_name': 'User',
                'password': 'password123',
                'confirm_password': 'password123',
                'location_method': 'skip'
            }, follow_redirects=True)
            assert response.status_code == 200
            
            # Try to register again with a small set of different cases - should fail
            test_emails = [
                'Unique@example.com',    # Capitalized first letter
                'UNIQUE@EXAMPLE.COM',    # All uppercase
            ]
            
            for email in test_emails:
                response = client.post('/auth/register', data={
                    'email': email,
                    'first_name': 'Duplicate',
                    'last_name': 'User',
                    'password': 'password123',
                    'confirm_password': 'password123',
                    'location_method': 'skip'
                })
                
                assert response.status_code == 200, f"Failed for email: {email}"
                assert b'This email is already registered' in response.data, f"Failed for email: {email}"

    def test_case_insensitive_resend_confirmation(self, client, app):
        """Test that resend confirmation is case-insensitive for email addresses."""
        with app.app_context():
            # Create an unconfirmed user with lowercase email
            user = UserFactory(email='confirm@example.com', email_confirmed=False)
            
            # Test resend confirmation with a small set of different cases
            test_emails = [
                'confirm@example.com',    # Original
                'Confirm@example.com',    # Capitalized first letter
            ]
            
            for email in test_emails:
                response = client.post('/auth/resend-confirmation', data={
                    'email': email
                })
                
                assert response.status_code == 200, f"Failed for email: {email}"
                assert b'A new confirmation email has been sent' in response.data, f"Failed for email: {email}"

    def test_registration_stores_lowercase_email(self, client, app):
        """Test that registration stores emails in lowercase format."""
        with app.app_context():
            # Register with mixed case email
            response = client.post('/auth/register', data={
                'email': 'TestUser@EXAMPLE.COM',
                'first_name': 'Test',
                'last_name': 'User',
                'password': 'password123',
                'confirm_password': 'password123',
                'location_method': 'skip'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check that the email is stored in lowercase
            user = User.query.filter_by(first_name='Test', last_name='User').first()
            assert user is not None
            assert user.email == 'testuser@example.com'  # Should be stored as lowercase

class TestProtectedRoutes:
    """Test that protected routes require authentication."""
    
    def test_list_item_requires_auth(self, client):
        """Test that listing items requires authentication."""
        response = client.get('/list-item')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_profile_requires_auth(self, client):
        """Test that profile requires authentication."""
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_messages_requires_auth(self, client):
        """Test that messages require authentication."""
        response = client.get('/messages')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_item_detail_requires_auth(self, client, app):
        """Test that item detail requires authentication."""
        with app.app_context():
            item = ItemFactory()
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 302
            assert '/auth/login' in response.location

    def test_tag_items_requires_auth(self, client, app):
        """Test that tag items page requires authentication."""
        with app.app_context():
            from tests.factories import TagFactory
            tag = TagFactory()
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 302
            assert '/auth/login' in response.location

    def test_category_items_requires_auth(self, client, app):
        """Test that category items page requires authentication."""
        with app.app_context():
            from tests.factories import CategoryFactory
            category = CategoryFactory()
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 302
            assert '/auth/login' in response.location

class TestEmailConfirmation:
    """Test email confirmation functionality."""
    
    def test_resend_confirmation_page(self, client):
        """Test resend confirmation page."""
        response = client.get('/auth/resend-confirmation')
        assert response.status_code == 200
        assert b'Resend Confirmation' in response.data
    
    def test_resend_confirmation_valid_email(self, client, app):
        """Test resending confirmation for valid unconfirmed email."""
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            
            response = client.post('/auth/resend-confirmation', data={
                'email': user.email
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'confirmation email has been sent' in response.data
    
    def test_resend_confirmation_already_confirmed(self, client, app):
        """Test resending confirmation for already confirmed email."""
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            
            response = client.post('/auth/resend-confirmation', data={
                'email': user.email
            })
            
            assert response.status_code == 302  # Redirects to login
            assert '/auth/login' in response.location
    
    def test_resend_confirmation_nonexistent_email(self, client):
        """Test resending confirmation for nonexistent email."""
        response = client.post('/auth/resend-confirmation', data={
            'email': 'nonexistent@example.com'
        })
        
        assert response.status_code == 200
        assert b'No account found' in response.data

class TestPasswordReset:
    """Test password reset functionality."""
    
    def test_forgot_password_page(self, client):
        """Test forgot password page."""
        response = client.get('/auth/forgot-password')
        assert response.status_code == 200
        assert b'Forgot Password' in response.data
    
    def test_forgot_password_valid_email(self, client, app, auth_user):
        """Test forgot password with valid email."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            response = client.post('/auth/forgot-password', data={
                'email': user.email
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Password reset instructions have been sent to your email.' in response.data
    
    def test_forgot_password_invalid_email(self, client):
        """Test forgot password with invalid email."""
        response = client.post('/auth/forgot-password', data={
            'email': 'nonexistent@example.com'
        })
        
        assert response.status_code == 302
        assert response.location.endswith('/auth/login')
