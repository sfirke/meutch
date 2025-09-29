"""Tests for UserWebLink model and web links functionality."""

import pytest
from app.models import UserWebLink
from app.forms import EditProfileForm

class TestUserWebLink:
    """Test UserWebLink model."""
    
    def test_create_web_link(self, app, auth_user):
        """Test creating a web link."""
        with app.app_context():
            user = auth_user()
            
            web_link = UserWebLink(
                user_id=user.id,
                platform_type='instagram',
                url='https://instagram.com/test_user',
                display_order=1
            )
            
            assert web_link.display_name == 'Instagram'
            assert web_link.url == 'https://instagram.com/test_user'
            assert web_link.display_order == 1
    
    def test_custom_platform_name(self, app, auth_user):
        """Test web link with custom platform name."""
        with app.app_context():
            user = auth_user()
            
            web_link = UserWebLink(
                user_id=user.id,
                platform_type='other',
                platform_name='My Portfolio',
                url='https://myportfolio.example.com',
                display_order=1
            )
            
            assert web_link.display_name == 'My Portfolio'
    
    def test_platform_choices_available(self):
        """Test that platform choices are defined."""
        choices = UserWebLink.PLATFORM_CHOICES
        assert len(choices) > 0
        
        # Check for some expected platforms
        platform_values = [choice[0] for choice in choices]
        assert 'facebook' in platform_values
        assert 'instagram' in platform_values
        assert 'bluesky' in platform_values
        assert 'other' in platform_values

class TestWebLinksForm:
    """Test web links form functionality."""
    
    def test_form_has_web_link_fields(self, app):
        """Test that EditProfileForm has web link fields."""
        with app.app_context():
            form = EditProfileForm()
            
            # Check that web link fields exist
            assert hasattr(form, 'link_1_platform')
            assert hasattr(form, 'link_1_url')
            assert hasattr(form, 'link_1_custom_name')
            assert hasattr(form, 'link_5_platform')
            assert hasattr(form, 'link_5_url')
            assert hasattr(form, 'link_5_custom_name')
    
    def test_form_validation_url_without_platform(self, app):
        """Test form validation fails when URL is provided without platform."""
        with app.app_context():
            form_data = {
                'link_1_url': 'https://example.com',
                'link_1_platform': ''
            }
            form = EditProfileForm(data=form_data)
            assert form.validate() is False
            assert 'Please select a platform when providing a URL.' in form.link_1_platform.errors
    
    def test_form_validation_other_without_custom_name(self, app):
        """Test form validation fails when 'other' is selected without custom name."""
        with app.app_context():
            form_data = {
                'link_1_platform': 'other',
                'link_1_url': 'https://example.com',
                'link_1_custom_name': ''
            }
            form = EditProfileForm(data=form_data)
            assert form.validate() is False
            assert 'Please provide a custom name when selecting "Other".' in form.link_1_custom_name.errors
    
    def test_form_validation_valid_web_link(self, app):
        """Test form validation passes with valid web link data."""
        with app.app_context():
            form_data = {
                'link_1_platform': 'instagram',
                'link_1_url': 'https://instagram.com/test_user',
                'about_me': 'Test bio'
            }
            form = EditProfileForm(data=form_data)
            assert form.validate() is True
