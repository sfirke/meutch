"""Integration tests for authentication routes."""
import pytest
from app.models import User
from tests.factories import UserFactory, ItemFactory
from conftest import login_user, TEST_PASSWORD
from unittest.mock import patch

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

    @pytest.mark.filterwarnings("ignore::DeprecationWarning:flask_login")
    def test_login_with_remember_device_sets_cookie(self, client, app, auth_user):
        """Test login with remember_device sets remember cookie."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': TEST_PASSWORD,
                'remember_device': 'y'
            }, follow_redirects=False)

            assert response.status_code == 302
            set_cookie_headers = response.headers.getlist('Set-Cookie')
            assert any('remember_token=' in header for header in set_cookie_headers)

    def test_login_without_remember_device_no_remember_cookie(self, client, app, auth_user):
        """Test login without remember_device does not set remember cookie."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=False)

            assert response.status_code == 302
            set_cookie_headers = response.headers.getlist('Set-Cookie')
            assert not any('remember_token=' in header for header in set_cookie_headers)
    
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

    def test_register_redirects_to_resend_confirmation(self, client):
        """Test registration redirects to confirmation guidance page, not login."""
        response = client.post('/auth/register', data={
            'email': 'redirectuser@example.com',
            'first_name': 'Redirect',
            'last_name': 'User',
            'location_method': 'skip',
            'password': 'redirectpassword123',
            'confirm_password': 'redirectpassword123'
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/auth/resend-confirmation' in response.location
    
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


class TestRedirectAfterLogin:
    """Test redirect functionality after login.
    
    These tests cover the full redirect-after-login flow:
    1. User tries to access a protected page
    2. Gets redirected to login with ?next= parameter
    3. Logs in successfully
    4. Gets redirected back to the original page
    """
    
    def test_login_without_next_redirects_to_home(self, client, app, auth_user):
        """Test login without 'next' parameter redirects to home page."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Welcome to Meutch' in response.data
    
    def test_login_with_valid_next_redirects_correctly(self, client, app, auth_user):
        """Test login with valid 'next' parameter redirects to intended page."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login?next=/profile', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should be redirected to profile page
            assert b'My Profile' in response.data or b'Profile' in response.data
    
    def test_login_with_external_url_ignores_next(self, client, app, auth_user):
        """Test that external URLs in 'next' parameter are ignored for security."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login?next=http://evil.com/phishing', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should redirect to home page instead of external URL
            assert b'Welcome to Meutch' in response.data
    
    def test_login_with_protocol_relative_url_ignores_next(self, client, app, auth_user):
        """Test that protocol-relative URLs are ignored for security."""
        with app.app_context():
            user = auth_user()
            response = client.post('/auth/login?next=//evil.com/phishing', data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should redirect to home page instead
            assert b'Welcome to Meutch' in response.data
    
    def test_full_redirect_flow_after_unauthorized_access(self, client, app, auth_user):
        """Test complete flow: unauthorized access -> login -> redirect back.
        
        This is the end-to-end test that validates the entire redirect feature:
        1. Accessing a protected route (without being logged in) sets 'next' parameter
        2. Login page is displayed with the 'next' parameter
        3. Form submission with 'next' parameter succeeds
        4. User is redirected to the originally requested page
        """
        with app.app_context():
            user = auth_user()
            
            # Step 1: Try to access protected route (circles page)
            response = client.get('/circles/', follow_redirects=False)
            assert response.status_code == 302
            assert '/auth/login' in response.location
            assert 'next=' in response.location  # Verify next parameter is set
            
            # Extract the redirect URL with next parameter
            login_url = response.location
            
            # Step 2: Go to login page (should have 'next' parameter)
            response = client.get(login_url)
            assert response.status_code == 200
            assert b'Log In' in response.data
            
            # Step 3: Login with the 'next' parameter in the URL
            response = client.post(login_url, data={
                'email': user.email,
                'password': TEST_PASSWORD
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should be redirected back to circles page
            assert b'Your Circles' in response.data or b'Circles' in response.data
    
    def test_login_message_shown_on_unauthorized_access(self, client, app):
        """Test that a login message is shown when accessing protected routes."""
        with app.app_context():
            # Try to access a protected route
            response = client.get('/profile', follow_redirects=True)
            
            assert response.status_code == 200
            # Should show login message
            assert b'Please log in to access this page' in response.data or b'Log In' in response.data
    
    def test_login_form_preserves_next_parameter(self, client, app):
        """Test that the login form's action URL includes the 'next' parameter.
        
        This test validates the HTML template, not just the backend logic.
        Without the 'next' parameter in the form action, the parameter would be
        lost when the form is submitted via POST.
        """
        with app.app_context():
            # Access login page with 'next' parameter
            response = client.get('/auth/login?next=/profile')
            
            assert response.status_code == 200
            # The form action should include the 'next' parameter
            # This ensures the parameter survives the form POST
            assert b'action="/auth/login?next=' in response.data or \
                   b'action="/auth/login?next=%2Fprofile' in response.data


class TestCSRFErrorHandler:
    """Test that CSRF errors are handled gracefully."""

    def test_csrf_error_redirects_to_login_with_message(self, app):
        """Test that a CSRF error shows a user-friendly message and redirects to login."""
        from conftest import TestConfig
        from app import create_app, db

        class CSRFEnabledConfig(TestConfig):
            WTF_CSRF_ENABLED = True
            WTF_CSRF_CHECK_DEFAULT = True

        csrf_app = create_app(CSRFEnabledConfig)
        with csrf_app.app_context():
            db.create_all()
            client = csrf_app.test_client()
            # POST without a valid CSRF token triggers CSRFError; follow redirect to login page
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password',
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'session has expired' in response.data or b'log in again' in response.data
