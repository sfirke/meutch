"""Unit tests for giveaway-related models."""
import pytest
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Item, GiveawayInterest
from tests.factories import ItemFactory, UserFactory, GiveawayInterestFactory


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
    
    def test_item_claimed_by_set_null_on_user_delete(self, app):
        """Test that claimed_by_id becomes NULL when user deletes account (SET NULL behavior)."""
        with app.app_context():
            claimer = UserFactory()
            item = ItemFactory(
                is_giveaway=True,
                claim_status='claimed',
                claimed_by_id=claimer.id,
                claimed_at=datetime.now(UTC)
            )
            db.session.commit()
            
            item_id = item.id
            
            # Delete the user who claimed the item
            db.session.delete(claimer)
            db.session.commit()
            
            # Refresh item from database
            item = db.session.get(Item, item_id)
            
            # claimed_by_id should be NULL, but claim_status and claimed_at preserved
            assert item.claimed_by_id is None
            assert item.claim_status == 'claimed'
            assert item.claimed_at is not None


class TestGiveawayInterest:
    """Test GiveawayInterest model."""
    
    def test_giveaway_interest_creation(self, app):
        """Test creating a GiveawayInterest record with all fields."""
        with app.app_context():
            interest = GiveawayInterestFactory(message="I need this!")
            db.session.commit()
            
            assert interest.id is not None
            assert interest.item_id is not None
            assert interest.user_id is not None
            assert interest.message == "I need this!"
            assert interest.status == 'active'
            assert interest.created_at is not None
    
    def test_giveaway_interest_unique_constraint(self, app):
        """Test that user cannot express interest twice in same item."""
        with app.app_context():
            giveaway = ItemFactory(is_giveaway=True)
            user = UserFactory()
            
            # First interest
            GiveawayInterestFactory(item=giveaway, user=user)
            db.session.commit()
            
            # Attempt duplicate interest - should fail
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user.id,
                status='active'
            )
            db.session.add(interest2)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
    
    def test_giveaway_interest_cascade_delete_constraints(self, app):
        """Verify database has ON DELETE CASCADE for foreign keys."""
        with app.app_context():
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            fks = inspector.get_foreign_keys('giveaway_interest')
            
            # Check both foreign keys have CASCADE
            item_fk = next((fk for fk in fks if 'item_id' in fk['constrained_columns']), None)
            user_fk = next((fk for fk in fks if 'user_id' in fk['constrained_columns']), None)
            
            assert item_fk is not None
            assert item_fk['options'].get('ondelete') == 'CASCADE'
            assert user_fk is not None
            assert user_fk['options'].get('ondelete') == 'CASCADE'
