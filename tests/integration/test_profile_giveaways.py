"""Integration tests for profile giveaway display."""
import pytest
from datetime import datetime, UTC, timedelta
from app import db
from app.models import Item
from tests.factories import UserFactory, ItemFactory, CategoryFactory
from conftest import login_user


class TestProfileGiveawaysSeparation:
    """Test that profile separates active and past giveaways."""
    
    def test_profile_shows_active_giveaways(self, client, app, auth_user):
        """Test that profile displays unclaimed giveaways in active section."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            
            # Create unclaimed giveaway
            unclaimed_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed',
                name='Unclaimed Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'My Active Giveaways' in response.data
            assert b'Unclaimed Item' in response.data
    
    def test_profile_claimed_giveaways_cannot_be_deleted(self, client, app, auth_user):
        """Test that claimed giveaways don't have delete/edit buttons and can't be deleted."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create claimed giveaway
            claimed_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name='Claimed Giveaway'
            )
            item_id = claimed_giveaway.id
            db.session.commit()
            
            login_user(client, user.email)
            
            # Check profile page shows the claimed giveaway in past section
            response = client.get('/profile')
            assert response.status_code == 200
            assert b'Claimed Giveaway' in response.data
            assert b'My Past Giveaways' in response.data
            
            # Verify no edit or delete buttons are present on page
            assert b'btn-warning' not in response.data, "Edit button should not appear for past giveaways"
            assert b'btn-danger' not in response.data, "Delete button should not appear for past giveaways"
            
            # Try to delete the claimed giveaway via POST
            response = client.post(
                f'/item/{item_id}/delete',
                follow_redirects=True
            )
            
            # Should get an error message
            assert b'cannot delete a giveaway that has been claimed' in response.data or b'completed transaction' in response.data
            
            # Verify the item still exists
            item = db.session.get(Item, item_id)
            assert item is not None
    
    def test_profile_shows_pending_pickup_in_active(self, client, app, auth_user):
        """Test that profile displays pending_pickup giveaways in active section."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create pending_pickup giveaway
            pending_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=recipient,
                name='Pending Pickup Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'My Active Giveaways' in response.data
            assert b'Pending Pickup Item' in response.data
    
    def test_profile_shows_recently_claimed_in_past(self, client, app, auth_user):
        """Test that profile displays recently claimed giveaways in past section."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create claimed giveaway (10 days ago)
            claimed_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=10),
                name='Recently Claimed Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'My Past Giveaways' in response.data
            # Check that the visible "My Active Giveaways" heading is NOT present
            # (the HTML comment contains this text, so we check for the actual h4 heading)
            assert b'>My Active Giveaways<' not in response.data
            assert b'Recently Claimed Item' in response.data
    
    def test_profile_hides_old_claimed_giveaways(self, client, app, auth_user):
        """Test that profile does not display giveaways claimed > 90 days ago."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create old claimed giveaway (91 days ago)
            old_claimed_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=91),
                name='Old Claimed Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'Old Claimed Item' not in response.data
    
    def test_profile_shows_giveaway_exactly_90_days_old(self, client, app, auth_user):
        """Test that profile displays giveaways claimed exactly 90 days ago."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create giveaway claimed exactly 90 days ago (minus 1 hour to avoid timing issues)
            ninety_day_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=90, hours=-1),
                name='Ninety Day Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'My Past Giveaways' in response.data
            assert b'Ninety Day Item' in response.data
    
    def test_profile_shows_both_active_and_past_giveaways(self, client, app, auth_user):
        """Test that profile displays both sections when user has both types."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create unclaimed giveaway
            unclaimed = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed',
                name='Active Item'
            )
            
            # Create claimed giveaway
            claimed = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name='Past Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'My Active Giveaways' in response.data
            assert b'My Past Giveaways' in response.data
            assert b'Active Item' in response.data
            assert b'Past Item' in response.data
    
    def test_profile_no_giveaways_shows_regular_items(self, client, app, auth_user):
        """Test that profile shows regular items section when no giveaways exist."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            
            # Create regular item (not a giveaway)
            regular_item = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=False,
                name='Regular Lending Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            assert b'Regular Lending Item' in response.data
    
    def test_profile_past_giveaways_sorted_by_claimed_date(self, client, app, auth_user):
        """Test that past giveaways are sorted by claimed date (newest first)."""
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            # Create giveaways with different claimed dates
            older_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=20),
                name='Older Claimed Item'
            )
            
            newer_giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name='Newer Claimed Item'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            
            assert response.status_code == 200
            content = response.data.decode('utf-8')
            
            # Verify both appear
            assert 'Newer Claimed Item' in content
            assert 'Older Claimed Item' in content
            
            # Verify newer appears before older in the HTML
            newer_pos = content.find('Newer Claimed Item')
            older_pos = content.find('Older Claimed Item')
            assert newer_pos < older_pos
