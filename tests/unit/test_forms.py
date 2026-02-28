"""Unit tests for forms."""
import pytest
from app.forms import (
    LoginForm, RegistrationForm, ListItemForm, EditProfileForm,
    MessageForm, CircleCreateForm, LoanRequestForm, OptionalFileAllowed
)
from app.models import Category
from tests.factories import CategoryFactory, UserFactory
from datetime import date, timedelta
from werkzeug.datastructures import FileStorage
from io import BytesIO

class TestLoginForm:
    """Test LoginForm."""
    
    def test_valid_login_form(self, app):
        """Test valid login form."""
        with app.app_context():
            form_data = {
                'email': 'test@example.com',
                'password': 'password123'
            }
            form = LoginForm(data=form_data)
            assert form.validate() is True
    
    def test_invalid_email_format(self, app):
        """Test invalid email format."""
        with app.app_context():
            form_data = {
                'email': 'invalid-email',
                'password': 'password123'
            }
            form = LoginForm(data=form_data)
            assert form.validate() is False
            assert 'Invalid email format.' in form.email.errors
    
    def test_missing_password(self, app):
        """Test missing password."""
        with app.app_context():
            form_data = {
                'email': 'test@example.com',
                'password': ''
            }
            form = LoginForm(data=form_data)
            assert form.validate() is False
            assert 'Password is required.' in form.password.errors

    def test_login_form_with_remember_device(self, app):
        """Test valid login form with remember_device checked."""
        with app.app_context():
            form_data = {
                'email': 'test@example.com',
                'password': 'password123',
                'remember_device': True
            }
            form = LoginForm(data=form_data)
            assert form.validate() is True
            assert form.remember_device.data is True

class TestRegistrationForm:
    """Test RegistrationForm."""
    
    def test_valid_registration_form(self, app):
        """Test valid registration form with address."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'address',
                'street': '123 Main St',
                'city': 'Anytown',
                'state': 'CA',
                'zip_code': '12345',
                'country': 'USA',
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is True
    
    def test_valid_registration_form_coordinates(self, app):
        """Test valid registration form with coordinates."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'coordinates',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is True
    
    def test_password_confirmation_mismatch(self, app):
        """Test password confirmation mismatch."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'address',
                'street': '123 Main St',
                'city': 'Anytown',
                'state': 'CA',
                'zip_code': '12345',
                'country': 'USA',
                'password': 'password123',
                'confirm_password': 'differentpassword'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is False
            assert 'Passwords must match.' in form.confirm_password.errors
    
    def test_duplicate_email(self, app):
        """Test duplicate email validation."""
        with app.app_context():
            # Create existing user
            existing_user = UserFactory(email='existing@example.com')
            
            form_data = {
                'email': 'existing@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'address',
                'street': '123 Main St',
                'city': 'Anytown',
                'state': 'CA',
                'zip_code': '12345',
                'country': 'USA',
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is False
            assert 'This email is already registered. Please choose a different one.' in form.email.errors
    
    def test_address_method_missing_fields(self, app):
        """Test address method with missing required fields."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'address',
                'street': '123 Main St',
                # Missing city, state, zip_code, country
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is False
            assert any('is required when entering an address' in str(error) for error in form.errors.values())
    
    def test_coordinates_method_missing_fields(self, app):
        """Test coordinates method with missing required fields."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'coordinates',
                # Missing latitude and longitude
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is False
            assert 'Latitude is required when entering coordinates directly.' in form.latitude.errors
            assert 'Longitude is required when entering coordinates directly.' in form.longitude.errors

    def test_skip_location_method(self, app):
        """Test skip location method (no location fields required)."""
        with app.app_context():
            form_data = {
                'email': 'newuser@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'location_method': 'skip',
                # No location fields provided
                'password': 'password123',
                'confirm_password': 'password123'
            }
            form = RegistrationForm(data=form_data)
            assert form.validate() is True


class TestListItemForm:
    """Test ListItemForm."""
    
    def test_valid_list_item_form(self, app):
        """Test valid list item form."""
        with app.app_context():
            category = CategoryFactory()
            form_data = {
                'name': 'Test Item',
                'description': 'A test item description',
                'category': str(category.id),
                'tags': 'electronics, vintage'
            }
            form = ListItemForm(data=form_data)
            assert form.validate() is True
    
    def test_missing_required_fields(self, app):
        """Test missing required fields."""
        with app.app_context():
            form_data = {
                'name': '',  # Required field
                'description': 'A test item description',
                'category': '',  # Required field
                'tags': 'electronics, vintage'
            }
            form = ListItemForm(data=form_data)
            assert form.validate() is False
            assert any('This field is required.' in error for error in form.name.errors)
            assert any('This field is required.' in error for error in form.category.errors)
    
    def test_giveaway_without_visibility(self, app):
        """Test giveaway item without visibility selection (should fail)."""
        with app.app_context():
            category = CategoryFactory()
            form_data = {
                'name': 'Free Item',
                'description': 'A giveaway item',
                'category': str(category.id),
                'is_giveaway': True,
                'giveaway_visibility': ''  # Missing required visibility
            }
            form = ListItemForm(data=form_data)
            assert form.validate() is False
            assert 'Please select a visibility option for this giveaway.' in form.giveaway_visibility.errors

class TestEditProfileForm:
    """Test EditProfileForm."""
    
    def test_valid_edit_profile_form(self, app):
        """Test valid edit profile form."""
        with app.app_context():
            form_data = {
                'about_me': 'This is my bio'
            }
            form = EditProfileForm(data=form_data)
            assert form.validate() is True
    
    def test_about_me_too_long(self, app):
        """Test about_me field too long."""
        with app.app_context():
            form_data = {
                'about_me': 'x' * 501  # Exceeds 500 character limit
            }
            form = EditProfileForm(data=form_data)
            assert form.validate() is False

class TestMessageForm:
    """Test MessageForm."""
    
    def test_valid_message_form(self, app):
        """Test valid message form."""
        with app.app_context():
            form_data = {
                'body': 'This is a test message'
            }
            form = MessageForm(data=form_data)
            assert form.validate() is True
    
    def test_empty_message(self, app):
        """Test empty message."""
        with app.app_context():
            form_data = {
                'body': ''
            }
            form = MessageForm(data=form_data)
            assert form.validate() is False
            assert any('This field is required.' in error for error in form.body.errors)

class TestCircleCreateForm:
    """Test CircleCreateForm."""
    
    def test_valid_circle_create_form(self, app):
        """Test valid circle create form."""
        with app.app_context():
            form_data = {
                'name': 'Test Circle',
                'description': 'A test circle description',
                'requires_approval': False
            }
            form = CircleCreateForm(data=form_data)
            assert form.validate() is True
    
    def test_missing_circle_name(self, app):
        """Test missing circle name."""
        with app.app_context():
            form_data = {
                'name': '',
                'description': 'A test circle description',
                'requires_approval': False
            }
            form = CircleCreateForm(data=form_data)
            assert form.validate() is False
            assert 'Circle name is required.' in form.name.errors

class TestLoanRequestForm:
    """Test LoanRequestForm date validations."""
    
    def test_valid_loan_request_form(self, app):
        """Test valid loan request form."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() + timedelta(days=1)
                end_date = date.today() + timedelta(days=7)

                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'I would like to borrow this item for a week.',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is True
    
    def test_start_date_in_past(self, app):
        """Test start date in the past."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() - timedelta(days=1)
                end_date = date.today() + timedelta(days=7)
                
                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'Test message',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is False
                assert any('Start date cannot be in the past' in str(error) for error in form.start_date.errors)
    
    def test_end_date_in_past(self, app):
        """Test end date in the past."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() + timedelta(days=1)
                end_date = date.today() - timedelta(days=1)

                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'Test message',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is False
                assert any('End date must be after start date' in str(error) for error in form.end_date.errors)
    
    def test_end_date_before_start_date(self, app):
        """Test end date before start date."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() + timedelta(days=7)
                end_date = date.today() + timedelta(days=1)
                
                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'Test message',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is False
                assert any('End date must be after start date' in str(error) for error in form.end_date.errors)

    def test_empty_message_fails_validation(self, app):
        """Test that an empty message fails validation with an informative error."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() + timedelta(days=1)
                end_date = date.today() + timedelta(days=7)

                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': '',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is False
                assert any('Please include a message with your request' in str(error) for error in form.message.errors)

    def test_message_too_short_fails_validation(self, app):
        """Test that a message shorter than 10 characters fails validation."""
        with app.app_context():
            with app.test_request_context():
                start_date = date.today() + timedelta(days=1)
                end_date = date.today() + timedelta(days=7)

                form_data = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'Hi',
                    'csrf_token': 'test_token'
                }
                form = LoanRequestForm(data=form_data)
                assert form.validate() is False
                assert any('Message must be between 10 and 1000 characters' in str(error) for error in form.message.errors)

class TestOptionalFileAllowed:
    """Test OptionalFileAllowed validator."""
    
    def test_empty_file_allowed(self, app):
        """Test that empty file is allowed."""
        with app.app_context():
            with app.test_request_context():
                validator = OptionalFileAllowed(['jpg', 'png'])
                
                class MockForm:
                    pass
                
                class MockField:
                    data = None
                
                form = MockForm()
                field = MockField()
                
                # Should not raise any exception
                validator(form, field)
    
    def test_valid_file_extension(self, app):
        """Test valid file extension."""
        with app.app_context():
            with app.test_request_context():
                validator = OptionalFileAllowed(['jpg', 'png'])
                
                # Create a proper mock file
                mock_file = FileStorage(
                    stream=BytesIO(b'fake image data'),
                    filename='test.jpg',
                    content_type='image/jpeg'
                )
                
                class MockForm:
                    pass
                
                class MockField:
                    data = mock_file
                
                form = MockForm()
                field = MockField()
                
                # Should not raise ValidationError for valid extension
                validator(form, field)
    
    def test_invalid_file_extension(self, app):
        """Test invalid file extension."""
        with app.app_context():
            with app.test_request_context():
                from wtforms.validators import StopValidation
                validator = OptionalFileAllowed(['jpg', 'png'])
                
                # Create a mock file with invalid extension
                mock_file = FileStorage(
                    stream=BytesIO(b'fake data'),
                    filename='test.txt',
                    content_type='text/plain'
                )
                
                class MockForm:
                    pass
                
                class MockField:
                    data = mock_file
                    
                    def gettext(self, text):
                        return text
                
                form = MockForm()
                field = MockField()
                
                # Should raise StopValidation for invalid extension
                with pytest.raises(StopValidation):
                    validator(form, field)
