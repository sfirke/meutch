"""Unit tests for ItemRequest model."""
import pytest
from datetime import datetime, UTC, timedelta
from app.models import ItemRequest
from tests.factories import UserFactory, ItemRequestFactory


class TestItemRequestCreation:
    """Test ItemRequest model creation and defaults."""

    def test_item_request_creation(self, app):
        """Test basic item request creation."""
        with app.app_context():
            req = ItemRequestFactory()
            assert req.id is not None
            assert req.user_id is not None
            assert req.title is not None
            assert req.status == 'open'
            assert req.seeking == 'either'
            assert req.visibility == 'circles'
            assert req.fulfilled_at is None

    def test_item_request_with_custom_fields(self, app):
        """Test creating a request with custom field values."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user,
                title='Melon baller',
                description='Need one for a party',
                seeking='giveaway',
                visibility='public',
            )
            assert req.title == 'Melon baller'
            assert req.description == 'Need one for a party'
            assert req.seeking == 'giveaway'
            assert req.visibility == 'public'
            assert req.user == user

    def test_item_request_repr(self, app):
        """Test string representation."""
        with app.app_context():
            req = ItemRequestFactory(title='Test Item')
            repr_str = repr(req)
            assert 'Test Item' in repr_str
            assert 'ItemRequest' in repr_str

    def test_item_request_user_relationship(self, app):
        """Test that requests are linked to users via backref."""
        with app.app_context():
            user = UserFactory()
            req1 = ItemRequestFactory(user=user)
            req2 = ItemRequestFactory(user=user)
            assert len(user.requests) == 2
            assert req1 in user.requests
            assert req2 in user.requests


class TestItemRequestExpiration:
    """Test expiration-related properties."""

    def test_is_expired_future_date(self, app):
        """Test that a request with future expiration is not expired."""
        with app.app_context():
            req = ItemRequestFactory(expires_at=datetime.now(UTC) + timedelta(days=30))
            assert req.is_expired is False

    def test_is_expired_past_date(self, app):
        """Test that a request with past expiration is expired."""
        with app.app_context():
            req = ItemRequestFactory(expires_at=datetime.now(UTC) - timedelta(days=1))
            assert req.is_expired is True

    def test_is_active_open_and_not_expired(self, app):
        """Test is_active for open, non-expired request."""
        with app.app_context():
            req = ItemRequestFactory(
                status='open',
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            assert req.is_active is True

    def test_is_active_open_but_expired(self, app):
        """Test is_active for open but expired request."""
        with app.app_context():
            req = ItemRequestFactory(
                status='open',
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            assert req.is_active is False

    def test_is_active_fulfilled(self, app):
        """Test is_active for fulfilled request."""
        with app.app_context():
            req = ItemRequestFactory(status='fulfilled')
            assert req.is_active is False


class TestItemRequestFulfillment:
    """Test fulfillment-related properties."""

    def test_is_fulfilled(self, app):
        """Test is_fulfilled property."""
        with app.app_context():
            req = ItemRequestFactory(status='fulfilled')
            assert req.is_fulfilled is True

    def test_is_not_fulfilled(self, app):
        """Test is_fulfilled for open request."""
        with app.app_context():
            req = ItemRequestFactory(status='open')
            assert req.is_fulfilled is False


class TestItemRequestShowInFeed:
    """Test show_in_feed property."""

    def test_show_in_feed_active_request(self, app):
        """Test active request shows in feed."""
        with app.app_context():
            req = ItemRequestFactory(
                status='open',
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            assert req.show_in_feed is True

    def test_show_in_feed_expired_request(self, app):
        """Test expired request doesn't show in feed."""
        with app.app_context():
            req = ItemRequestFactory(
                status='open',
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            assert req.show_in_feed is False

    def test_show_in_feed_fulfilled_over_7_days(self, app):
        """Test fulfilled request older than 7 days doesn't show."""
        with app.app_context():
            req = ItemRequestFactory(
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=8),
            )
            assert req.show_in_feed is False

    def test_show_in_feed_deleted_request(self, app):
        """Test deleted request doesn't show in feed."""
        with app.app_context():
            req = ItemRequestFactory(status='deleted')
            assert req.show_in_feed is False

    def test_show_in_feed_fulfilled_at_boundary(self, app):
        """Test fulfilled request at exactly 6 days shows in feed."""
        with app.app_context():
            req = ItemRequestFactory(
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=6),
            )
            assert req.show_in_feed is True


class TestItemRequestSeeking:
    """Test seeking choices constant."""

    def test_seeking_choices_exist(self, app):
        """Test that SEEKING_CHOICES is defined."""
        assert len(ItemRequest.SEEKING_CHOICES) == 3
        values = [c[0] for c in ItemRequest.SEEKING_CHOICES]
        assert 'loan' in values
        assert 'giveaway' in values
        assert 'either' in values

    def test_visibility_choices_exist(self, app):
        """Test that VISIBILITY_CHOICES is defined."""
        assert len(ItemRequest.VISIBILITY_CHOICES) == 2
        values = [c[0] for c in ItemRequest.VISIBILITY_CHOICES]
        assert 'circles' in values
        assert 'public' in values
