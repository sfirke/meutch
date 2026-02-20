"""Unit tests for ItemRequestForm."""
import pytest
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from werkzeug.datastructures import MultiDict
from app.forms import ItemRequestForm
from app.models import ItemRequest


class TestItemRequestForm:
    """Test ItemRequestForm validation."""

    def test_valid_form(self, app):
        """Test valid form with all fields."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Plastic googly eyes',
                    'description': 'I need eight for a craft project',
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is True

    def test_valid_form_no_description(self, app):
        """Test valid form without optional description."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Melon baller',
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'loan',
                    'visibility': 'public',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is True

    def test_missing_title(self, app):
        """Test form requires title."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': '',
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False
                assert form.title.errors

    def test_title_too_long(self, app):
        """Test title max length validation."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'x' * 101,
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False
                assert form.title.errors

    def test_description_too_long(self, app):
        """Test description max length validation."""
        with app.app_context():
            with app.test_request_context():
                # Must use MultiDict (formdata) so Optional() sees submitted data
                # and passes through to the Length() validator. Using data= kwarg
                # populates object_data, which Optional() treats as "not submitted".
                form = ItemRequestForm(MultiDict([
                    ('title', 'Test'),
                    ('description', 'x' * 1001),
                    ('expires_at', (date.today() + timedelta(days=30)).isoformat()),
                    ('seeking', 'either'),
                    ('visibility', 'circles'),
                ]))
                assert form.validate() is False
                assert form.description.errors

    def test_missing_expiration(self, app):
        """Test form requires expiration date."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False
                assert form.expires_at.errors

    def test_expiration_in_past(self, app):
        """Test expiration date cannot be in the past."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today() - timedelta(days=1),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False
                assert any('past' in e.lower() for e in form.expires_at.errors)

    def test_expiration_too_far_future(self, app):
        """Test expiration date cannot be more than 6 months out."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today() + relativedelta(months=6) + timedelta(days=1),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False
                assert any('6 months' in e.lower() for e in form.expires_at.errors)

    def test_expiration_at_max_boundary(self, app):
        """Test expiration date at exactly 6 months is valid."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today() + relativedelta(months=6),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is True

    def test_expiration_today_is_valid(self, app):
        """Test expiration date of today is valid."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today(),
                    'seeking': 'either',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is True

    def test_valid_seeking_values(self, app):
        """Test all valid seeking values."""
        with app.app_context():
            with app.test_request_context():
                for seeking in ('loan', 'giveaway', 'either'):
                    form_data = {
                        'title': 'Test',
                        'expires_at': date.today() + timedelta(days=30),
                        'seeking': seeking,
                        'visibility': 'circles',
                    }
                    form = ItemRequestForm(data=form_data)
                    assert form.validate() is True, f"Failed for seeking={seeking}"

    def test_invalid_seeking_value(self, app):
        """Test invalid seeking value."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'invalid',
                    'visibility': 'circles',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False

    def test_valid_visibility_values(self, app):
        """Test all valid visibility values."""
        with app.app_context():
            with app.test_request_context():
                for visibility in ('circles', 'public'):
                    form_data = {
                        'title': 'Test',
                        'expires_at': date.today() + timedelta(days=30),
                        'seeking': 'either',
                        'visibility': visibility,
                    }
                    form = ItemRequestForm(data=form_data)
                    assert form.validate() is True, f"Failed for visibility={visibility}"

    def test_invalid_visibility_value(self, app):
        """Test invalid visibility value."""
        with app.app_context():
            with app.test_request_context():
                form_data = {
                    'title': 'Test',
                    'expires_at': date.today() + timedelta(days=30),
                    'seeking': 'either',
                    'visibility': 'invalid',
                }
                form = ItemRequestForm(data=form_data)
                assert form.validate() is False

    def test_form_choices_match_model_constants(self, app):
        """Test that form choices reference the model constants (DRY principle)."""
        with app.app_context():
            with app.test_request_context():
                form = ItemRequestForm()
                # Verify form fields use the exact same constants from the model
                assert form.seeking.choices == ItemRequest.SEEKING_CHOICES
                assert form.visibility.choices == ItemRequest.VISIBILITY_CHOICES
