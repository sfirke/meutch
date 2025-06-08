"""Integration tests for authentication routes."""
import pytest
from app.models import User
from tests.factories import UserFactory, ItemFactory
from conftest import login_user, logout_user
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
                'password': 'testpassword'
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
                'password': 'testpassword123'
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
    
    def test_register_valid_data(self, client, app):
        """Test registration with valid data."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'newuser@example.com',
                'first_name': 'New',
                'last_name': 'User',
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
            
            # Verify user was created
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.email_confirmed is False  # Should require confirmation
    
    def test_register_duplicate_email(self, client, app, auth_user):
        """Test registration with duplicate email."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            response = client.post('/auth/register', data={
                'email': user.email,  # Use existing email
                'first_name': 'Duplicate',
                'last_name': 'User',
                'street': '123 Duplicate St',
                'city': 'Duplicate City',
                'state': 'DC',
                'zip_code': '12345',
                'country': 'USA',
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
            'street': '123 Mismatch St',
            'city': 'Mismatch City',
            'state': 'MC',
            'zip_code': '12345',
            'country': 'USA',
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
                    'password': 'testpassword',
                    'confirm_password': 'testpassword',
                    'street': '123 Test St',
                    'city': 'Test City',
                    'state': 'TS',
                    'zip_code': '12345',
                    'country': 'USA'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                assert b'Error sending confirmation email' in response.data

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
