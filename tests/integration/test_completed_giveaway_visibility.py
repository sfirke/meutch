"""
Tests for completed giveaway visibility in various views.

Completed (claimed) giveaways should not appear in public feeds
but should remain visible to owner and recipient for 90 days.
"""
from datetime import datetime, UTC, timedelta
import pytest
from app import db
from app.models import Item, User, circle_members
from tests.factories import UserFactory, ItemFactory, CircleFactory
from conftest import login_user


class TestCompletedGiveawayVisibility:
    """Test that completed giveaways don't show in public views."""
    
    def test_claimed_giveaway_not_in_home_page(self, client, app, auth_user):
        """Test that claimed giveaways don't appear on home page."""
        user_email = None
        with app.app_context():
            # Create a circle and users
            circle = CircleFactory()
            owner = UserFactory()
            claimer = UserFactory()
            current_user = auth_user()
            user_email = current_user.email
            
            # Add users to circle
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(current_user)
            
            # Create unclaimed and claimed giveaways
            unclaimed_giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            unclaimed_name = unclaimed_giveaway.name
            
            claimed_giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )
            claimed_name = claimed_giveaway.name

            pending_giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            pending_name = pending_giveaway.name
            
            db.session.commit()
            
        # Log in the user
        from conftest import login_user
        login_user(client, email=user_email)
            
        # Test as authenticated user
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode()
        
        # Unclaimed should appear
        assert unclaimed_name in html
        
        # Claimed should NOT appear
        assert claimed_name not in html

        # Pending pickup should NOT appear to other users
        assert pending_name not in html
    
    def test_claimed_giveaway_not_in_giveaways_feed(self, client, app, auth_user):
        """Test that claimed giveaways don't appear in giveaways feed."""
        with app.app_context():
            circle = CircleFactory()
            owner = UserFactory()
            claimer = UserFactory()
            current_user = auth_user()
            
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(current_user)
            
            unclaimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            pending = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            
            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get('/giveaways')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Unclaimed should appear
            assert unclaimed.name in html
            
            # Pending pickup should NOT appear to other users
            assert pending.name not in html
            
            # Claimed should NOT appear
            assert claimed.name not in html
    
    def test_claimed_giveaway_not_in_search_results(self, client, app, auth_user):
        """Test that claimed giveaways don't appear in search results."""
        with app.app_context():
            circle = CircleFactory()
            owner = UserFactory()
            claimer = UserFactory()
            current_user = auth_user()
            
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(current_user)
            
            unclaimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed',
                name='Searchable Item Unclaimed'
            )
            
            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name='Searchable Item Claimed'
            )

            pending = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer,
                name='Searchable Item Pending'
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            # Search for both items
            response = client.get('/search?q=Searchable&item_type=both')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Unclaimed should appear
            assert 'Searchable Item Unclaimed' in html
            
            # Claimed should NOT appear
            assert 'Searchable Item Claimed' not in html

            # Pending pickup should NOT appear to other users
            assert pending.name not in html
    
    def test_claimed_giveaway_not_in_category_view(self, client, app, auth_user):
        """Test that claimed giveaways don't appear in category pages."""
        with app.app_context():
            circle = CircleFactory()
            owner = UserFactory()
            claimer = UserFactory()
            current_user = auth_user()
            
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(current_user)
            
            # Both items in same category
            from tests.factories import CategoryFactory
            category = CategoryFactory()
            
            unclaimed = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            claimed = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )

            pending = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get(f'/category/{category.id}?item_type=giveaways')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Unclaimed should appear
            assert unclaimed.name in html
            
            # Claimed should NOT appear
            assert claimed.name not in html

            # Pending pickup should NOT appear to other users
            assert pending.name not in html
    
    def test_claimed_giveaway_not_in_tag_view(self, client, app, auth_user):
        """Test that claimed giveaways don't appear in tag pages."""
        with app.app_context():
            circle = CircleFactory()
            owner = UserFactory()
            claimer = UserFactory()
            current_user = auth_user()
            
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(current_user)
            
            from tests.factories import TagFactory
            tag = TagFactory()
            
            unclaimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            unclaimed.tags.append(tag)
            
            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )
            claimed.tags.append(tag)

            pending = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            pending.tags.append(tag)
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get(f'/tag/{tag.id}?item_type=giveaways')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Unclaimed should appear
            assert unclaimed.name in html
            
            # Claimed should NOT appear
            assert claimed.name not in html

            # Pending pickup should NOT appear to other users
            assert pending.name not in html
    
    def test_claimed_giveaway_visible_to_owner_in_profile(self, client, app, auth_user):
        """Test that claimed giveaways appear in owner's profile for 90 days."""
        with app.app_context():
            current_user = auth_user()
            circle = CircleFactory()
            circle.members.append(current_user)
            
            claimer = UserFactory()
            
            claimed = ItemFactory(
                owner=current_user,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Should appear in past giveaways section
            assert claimed.name in html
            assert 'Past Giveaways' in html
    
    def test_claimed_giveaway_hidden_after_90_days_in_profile(self, client, app, auth_user):
        """Test that claimed giveaways disappear from profile after 90 days."""
        with app.app_context():
            current_user = auth_user()
            circle = CircleFactory()
            circle.members.append(current_user)
            
            claimer = UserFactory()
            
            # Create a giveaway claimed 91 days ago
            old_claimed = ItemFactory(
                owner=current_user,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=91)
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Should NOT appear (too old)
            assert old_claimed.name not in html
    
    def test_public_claimed_giveaway_not_in_anonymous_home_page(self, client, app):
        """Test that claimed public giveaways don't show to anonymous users."""
        with app.app_context():
            owner = UserFactory(is_public_showcase=True)
            claimer = UserFactory()
            
            unclaimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed'
            )
            
            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )

            pending = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            
            db.session.commit()
            
            # Anonymous user should see unclaimed but not claimed
            response = client.get('/')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Unclaimed should appear
            assert unclaimed.name in html
            
            # Claimed should NOT appear
            assert claimed.name not in html

            # Pending pickup should NOT appear to anonymous users
            assert pending.name not in html
    
    def test_pending_pickup_giveaway_visible_to_owner_only(self, client, app, auth_user):
        """Test pending_pickup giveaways are visible to owner but hidden from others."""
        owner_email = None
        other_user_email = None
        pending_name = None
        pending_id = None
        with app.app_context():
            circle = CircleFactory()
            owner = auth_user()
            claimer = UserFactory()
            other_user = UserFactory()
            owner_email = owner.email
            other_user_email = other_user.email
            
            circle.members.append(owner)
            circle.members.append(claimer)
            circle.members.append(other_user)
            
            pending = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer
            )
            pending_name = pending.name
            pending_id = pending.id
            
            db.session.commit()
        
        # Owner should see pending pickup in profile and my_giveaways section on /giveaways
        login_user(client, email=owner_email)
        response = client.get('/profile')
        assert response.status_code == 200
        assert pending_name in response.data.decode()

        response = client.get('/giveaways')
        assert response.status_code == 200
        assert pending_name in response.data.decode()

        # Other users should not see pending pickup in discovery views
        client.get('/logout', follow_redirects=True)
        login_user(client, email=other_user_email)

        response = client.get('/')
        assert response.status_code == 200
        assert pending_name not in response.data.decode()
        
        response = client.get('/giveaways')
        assert response.status_code == 200
        assert pending_name not in response.data.decode()
        
        response = client.get(f'/search?q={pending_name}&item_type=both')
        assert response.status_code == 200
        assert f'/item/{pending_id}'.encode() not in response.data


class TestGiveawayBadgeText:
    """Test that the badge displays 'Rehomed' for claimed giveaways."""
    
    def test_rehomed_badge_on_claimed_giveaway_in_profile(self, client, app, auth_user):
        """Test that claimed giveaways show 'Rehomed' badge in profile."""
        with app.app_context():
            current_user = auth_user()
            circle = CircleFactory()
            circle.members.append(current_user)
            
            claimer = UserFactory()
            
            claimed = ItemFactory(
                owner=current_user,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                available=False
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Should show Rehomed badge
            assert 'Rehomed' in html
            assert 'bg-success' in html
            
            # Should NOT show old "Claimed" text in this context
            # Note: "Claimed" appears in other contexts so we check specifically
            # that the badge is present with the Rehomed text
            assert 'fa-heart' in html
    
    def test_pending_pickup_badge_shows_correctly(self, client, app, auth_user):
        """Test that pending_pickup giveaways show correct badge."""
        with app.app_context():
            current_user = auth_user()
            circle = CircleFactory()
            circle.members.append(current_user)
            
            claimer = UserFactory()
            
            pending = ItemFactory(
                owner=current_user,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=claimer,
                available=False
            )
            
            db.session.commit()
            
            login_user(client, email=current_user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            html = response.data.decode()
            
            # Should show Pending Pickup badge
            assert 'Pending Pickup' in html
            assert 'bg-warning' in html


class TestClaimedGiveawayDirectUrlVisibility:
    """Test direct URL visibility rules for claimed giveaways."""

    def test_claimed_giveaway_direct_url_unavailable_to_unrelated_user(self, client, app, auth_user):
        """Unrelated users should see unavailable page for claimed giveaway details."""
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()
            unrelated_user = auth_user()

            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=10)
            )
            db.session.commit()

            login_user(client, email=unrelated_user.email)
            response = client.get(f'/item/{claimed.id}')
            assert response.status_code == 200
            assert b'This item has found its new home.' in response.data
            assert claimed.name.encode() not in response.data

    def test_claimed_giveaway_direct_url_visible_to_owner_and_recipient_within_90_days(self, client, app):
        """Owner and recipient can view claimed giveaway details within 90 days."""
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()

            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=20)
            )
            db.session.commit()

            login_user(client, email=owner.email)
            owner_response = client.get(f'/item/{claimed.id}')
            assert owner_response.status_code == 200
            assert claimed.name.encode() in owner_response.data
            assert b'This item has found its new home.' not in owner_response.data

            client.get('/logout', follow_redirects=True)
            login_user(client, email=recipient.email)
            recipient_response = client.get(f'/item/{claimed.id}')
            assert recipient_response.status_code == 200
            assert claimed.name.encode() in recipient_response.data
            assert b'This item has found its new home.' not in recipient_response.data

    def test_claimed_giveaway_direct_url_unavailable_after_90_days_for_everyone(self, client, app):
        """No user, including owner/recipient, can view claimed giveaway after 90 days."""
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()

            claimed = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=91)
            )
            db.session.commit()

            login_user(client, email=owner.email)
            owner_response = client.get(f'/item/{claimed.id}')
            assert owner_response.status_code == 200
            assert b'This item has found its new home.' in owner_response.data
            assert claimed.name.encode() not in owner_response.data

            client.get('/logout', follow_redirects=True)
            login_user(client, email=recipient.email)
            recipient_response = client.get(f'/item/{claimed.id}')
            assert recipient_response.status_code == 200
            assert b'This item has found its new home.' in recipient_response.data
            assert claimed.name.encode() not in recipient_response.data
