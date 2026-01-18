"""Unit tests for giveaway-related models."""
import pytest
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Item
from tests.factories import ItemFactory, UserFactory


class TestItemGiveawayFields:
    """Test Item model giveaway fields."""
    
    def test_item_is_giveaway_defaults_to_false(self, app):
        """Test that is_giveaway defaults to False."""
        with app.app_context():
            item = ItemFactory()
            db.session.commit()
            assert item.is_giveaway is False
    
    def test_item_can_be_created_as_giveaway(self, app):
        """Test creating item as giveaway with all fields."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='pending_pickup',
                claimed_by_id=user.id
            )
            db.session.commit()
            
            assert item.is_giveaway is True
            assert item.giveaway_visibility == 'public'
            assert item.claim_status == 'pending_pickup'
            assert item.claimed_by_id == user.id
            assert item.claimed_at is None  # Not set until handoff confirmed
