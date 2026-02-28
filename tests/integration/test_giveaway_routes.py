"""Integration tests for giveaway routes and functionality."""
import pytest
from app import db
from app.models import Item, GiveawayInterest, Message
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from conftest import login_user
from datetime import datetime, UTC, timedelta
from sqlalchemy import text


class TestGiveawayItemCreation:
    """Test giveaway item creation and editing."""
    
    def test_create_giveaway_with_default_visibility(self, client, app, auth_user):
        """Test creating a giveaway item with default (circles only) visibility."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)
            
            response = client.post('/list-item', data={
                'name': 'Free Bike',
                'description': 'Old but functional bike',
                'category': str(category.id),
                'is_giveaway': True,
                'giveaway_visibility': 'default',
                'tags': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify item was created with correct fields
            item = Item.query.filter_by(name='Free Bike').first()
            assert item is not None
            assert item.is_giveaway is True
            assert item.giveaway_visibility == 'default'
            assert item.claim_status == 'unclaimed'
    
    def test_create_giveaway_with_public_visibility(self, client, app, auth_user):
        """Test creating a giveaway item with public visibility."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)
            
            response = client.post('/list-item', data={
                'name': 'Free Books',
                'description': 'Collection of old textbooks',
                'category': str(category.id),
                'is_giveaway': True,
                'giveaway_visibility': 'public',
                'tags': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify item was created with correct fields
            item = Item.query.filter_by(name='Free Books').first()
            assert item is not None
            assert item.is_giveaway is True
            assert item.giveaway_visibility == 'public'
            assert item.claim_status == 'unclaimed'
    
    def test_create_loan_item(self, client, app, auth_user):
        """Test creating a regular loan item (not giveaway)."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)
            
            response = client.post('/list-item', data={
                'name': 'Power Drill',
                'description': 'Cordless power drill',
                'category': str(category.id),
                'tags': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify item was created as loan item
            item = Item.query.filter_by(name='Power Drill').first()
            assert item is not None
            assert item.is_giveaway is False
            assert item.claim_status is None
    
    def test_edit_item_to_giveaway(self, client, app, auth_user):
        """Test editing an existing loan item to become a giveaway."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            # Create a loan item first
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category, is_giveaway=False)
            db.session.commit()
            
            response = client.post(f'/item/{item.id}/edit', data={
                'name': item.name,
                'description': item.description,
                'category': str(category.id),
                'is_giveaway': True,
                'giveaway_visibility': 'public',
                'tags': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify item was updated
            updated_item = db.session.get(Item, item.id)
            assert updated_item.is_giveaway is True
            assert updated_item.giveaway_visibility == 'public'
            assert updated_item.claim_status == 'unclaimed'
    
    def test_edit_giveaway_to_loan(self, client, app, auth_user):
        """Test editing an existing giveaway to become a loan item."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            # Create a giveaway item first
            category = CategoryFactory()
            item = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.post(f'/item/{item.id}/edit', data={
                'name': item.name,
                'description': item.description,
                'category': str(category.id),
                'tags': ''
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify item was updated
            updated_item = db.session.get(Item, item.id)
            assert updated_item.is_giveaway is False
            assert updated_item.giveaway_visibility is None
            assert updated_item.claim_status is None


class TestGiveawaysFeed:
    """Test the giveaway feed page."""
    
    def test_giveaways_page_with_no_circles(self, client, app, auth_user):
        """Test giveaways page shows prompt when user has no circles."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            assert b'join at least one lending circle' in response.data.lower()
    
    def test_giveaways_page_shows_unclaimed_items(self, client, app, auth_user):
        """Test giveaways page shows only unclaimed giveaway items."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory()
            circle.members.append(user)
            login_user(client, user.email)
            
            # Create various items
            category = CategoryFactory()
            other_user = UserFactory()
            circle.members.append(other_user)
            
            # Unclaimed giveaway (should appear)
            giveaway1 = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Lamp',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Claimed giveaway (should NOT appear)
            giveaway2 = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Table',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=user
            )
            
            # Loan item (should NOT appear)
            loan = ItemFactory(
                owner=other_user,
                category=category,
                name='Power Tools',
                is_giveaway=False
            )
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            assert b'Free Lamp' in response.data
            assert b'Free Table' not in response.data
            assert b'Power Tools' not in response.data
    
    def test_giveaways_sorting_by_date(self, client, app, auth_user):
        """Test giveaways page sorts by date correctly."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory()
            circle.members.append(user)
            login_user(client, user.email)
            
            category = CategoryFactory()
            other_user = UserFactory()
            circle.members.append(other_user)
            
            # Create giveaways with explicit different timestamps
            
            giveaway1 = ItemFactory(
                owner=other_user,
                category=category,
                name='Old Giveaway',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            giveaway1.created_at = datetime.now(UTC) - timedelta(hours=2)
            
            giveaway2 = ItemFactory(
                owner=other_user,
                category=category,
                name='New Giveaway',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            giveaway2.created_at = datetime.now(UTC) - timedelta(hours=1)
            
            db.session.commit()
            
            # Test date sorting (newest first)
            response = client.get('/giveaways?sort_by=date')
            
            assert response.status_code == 200
            # Newest should appear before oldest in HTML (lower byte position)
            new_pos = response.data.find(b'New Giveaway')
            old_pos = response.data.find(b'Old Giveaway')
            assert new_pos != -1 and old_pos != -1, "Both giveaways should be found in response"
            assert new_pos < old_pos, "New Giveaway should appear before Old Giveaway when sorting by date"
    
    def test_public_giveaway_visible_without_shared_circles(self, client, app, auth_user):
        """Test that public giveaways are visible to users who don't share circles with owner."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            
            # Create two separate circles - users don't share any circles
            circle1 = CircleFactory()
            circle1.members.append(user)
            
            circle2 = CircleFactory()
            circle2.members.append(other_user)
            
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a public giveaway owned by other_user
            public_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Public Free Item',
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed'
            )
            
            # Create a default (circles-only) giveaway that should NOT appear
            default_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Circles Only Free Item',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            db.session.commit()
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            assert b'Public Free Item' in response.data, "Public giveaway should be visible to all circle members"
            assert b'Circles Only Free Item' not in response.data, "Default visibility giveaway should not be visible without shared circles"
    
    def test_public_giveaway_visible_in_search_without_shared_circles(self, client, app, auth_user):
        """Test that public giveaways appear in search for users who don't share circles with owner."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            
            # Create two separate circles - users don't share any circles
            circle1 = CircleFactory()
            circle1.members.append(user)
            
            circle2 = CircleFactory()
            circle2.members.append(other_user)
            
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a public giveaway owned by other_user
            public_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Searchable Public Giveaway',
                description='This is a public item',
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed'
            )
            
            # Create a default (circles-only) giveaway that should NOT appear
            default_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Searchable Default Giveaway',
                description='This is a default visibility item',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            db.session.commit()
            
            # Search for giveaways
            response = client.get('/search?q=Searchable&item_type=giveaways')
            
            assert response.status_code == 200
            assert b'Searchable Public Giveaway' in response.data, "Public giveaway should appear in search for all circle members"
            assert b'Searchable Default Giveaway' not in response.data, "Default visibility giveaway should not appear in search without shared circles"

    def test_my_giveaways_section_only_shows_active(self, client, app, auth_user):
        """Test that 'My Giveaways' section on feed page only shows active giveaways, not claimed ones."""
        
        with app.app_context():
            user = auth_user()
            recipient = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(recipient)
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create active giveaways (should appear in "My Giveaways")
            active_unclaimed = ItemFactory(
                owner=user,
                category=category,
                name='My Active Unclaimed',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            active_pending = ItemFactory(
                owner=user,
                category=category,
                name='My Active Pending',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=recipient
            )
            
            # Create past giveaway (should NOT appear in "My Giveaways")
            past_claimed = ItemFactory(
                owner=user,
                category=category,
                name='My Past Claimed',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=recipient,
                claimed_at=datetime.now(UTC) - timedelta(days=5)
            )
            
            db.session.commit()
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            # Active giveaways should appear
            assert b'My Active Unclaimed' in response.data, "Unclaimed giveaway should appear in My Giveaways"
            assert b'My Active Pending' in response.data, "Pending pickup giveaway should appear in My Giveaways"
            # Past giveaway should NOT appear
            assert b'My Past Claimed' not in response.data, "Claimed giveaway should NOT appear in My Giveaways"


class TestSearchFiltering:
    """Test search filtering by item type."""
    
    def test_search_with_loans_filter(self, client, app, auth_user):
        """Test search filtering for loans only."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a loan and a giveaway owned by other user
            loan = ItemFactory(
                owner=other_user,
                category=category,
                name='Drill for Loan',
                is_giveaway=False
            )
            
            giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Drill',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get('/search?q=Drill&item_type=loans')
            
            assert response.status_code == 200
            assert b'Drill for Loan' in response.data
            assert b'Free Drill' not in response.data
    
    def test_search_with_giveaways_filter(self, client, app, auth_user):
        """Test search filtering for giveaways only."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a loan and a giveaway owned by other user
            loan = ItemFactory(
                owner=other_user,
                category=category,
                name='Drill for Loan',
                is_giveaway=False
            )
            
            giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Drill',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get('/search?q=Drill&item_type=giveaways')
            
            assert response.status_code == 200
            assert b'Drill for Loan' not in response.data
            assert b'Free Drill' in response.data
    
    def test_search_with_both_filter(self, client, app, auth_user):
        """Test search showing both loans and giveaways."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a loan and a giveaway owned by other user
            loan = ItemFactory(
                owner=other_user,
                category=category,
                name='Drill for Loan',
                is_giveaway=False
            )
            
            giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Drill',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get('/search?q=Drill&item_type=both')
            
            assert response.status_code == 200
            assert b'Drill for Loan' in response.data
            assert b'Free Drill' in response.data
            response_text = response.data.decode('utf-8')
            assert response_text.count('giveaway-ribbon') == 1
            loan_index = response_text.index('Drill for Loan')
            loan_card_snippet = response_text[max(0, loan_index - 500):loan_index + 200]
            assert 'giveaway-ribbon' not in loan_card_snippet


class TestCategoryAndTagFiltering:
    """Test category and tag filtering by item type."""
    
    def test_category_with_giveaways_filter(self, client, app, auth_user):
        """Test category page filtering for giveaways only."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()
            login_user(client, user.email)
            
            category = CategoryFactory()
            
            # Create a loan and a giveaway in same category owned by other user
            loan = ItemFactory(
                owner=other_user,
                category=category,
                name='Loan Item',
                is_giveaway=False
            )
            
            giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Free Item',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get(f'/category/{category.id}?item_type=giveaways')
            
            assert response.status_code == 200
            assert b'Loan Item' not in response.data
            assert b'Free Item' in response.data


class TestGiveawayInterestExpression:
    """Test interest expression for giveaways."""
    
    def test_express_interest_in_giveaway(self, client, app, auth_user):
        """Test user can express interest in an unclaimed giveaway."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={'message': 'I really need this!'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'Your interest has been recorded' in response.data
            
            # Verify interest record was created
            interest = GiveawayInterest.query.filter_by(
                item_id=giveaway.id,
                user_id=user.id
            ).first()
            assert interest is not None
            assert interest.message == 'I really need this!'
            assert interest.status == 'active'
    
    def test_express_interest_without_message(self, client, app, auth_user):
        """Test user can express interest without providing a message."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify interest record was created without message
            interest = GiveawayInterest.query.filter_by(
                item_id=giveaway.id,
                user_id=user.id
            ).first()
            assert interest is not None
            assert interest.message is None
    
    def test_cannot_express_interest_in_own_giveaway(self, client, app, auth_user):
        """Test owner cannot express interest in their own giveaway."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=user,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'cannot express interest in your own giveaway' in response.data
            
            # Verify no interest record was created
            interest = GiveawayInterest.query.filter_by(
                item_id=giveaway.id,
                user_id=user.id
            ).first()
            assert interest is None
    
    def test_cannot_express_interest_twice(self, client, app, auth_user):
        """Test user cannot express interest twice in the same giveaway."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            # First interest expression
            response1 = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={},
                follow_redirects=True
            )
            assert response1.status_code == 200
            
            # Second attempt should fail
            response2 = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={},
                follow_redirects=True
            )
            assert response2.status_code == 200
            assert b'already expressed interest' in response2.data
            
            # Verify only one interest record exists
            count = GiveawayInterest.query.filter_by(
                item_id=giveaway.id,
                user_id=user.id
            ).count()
            assert count == 1
    
    def test_cannot_express_interest_in_claimed_giveaway(self, client, app, auth_user):
        """Test user cannot express interest in a claimed giveaway."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            claimer = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=claimer
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.post(
                f'/item/{giveaway.id}/express-interest',
                data={},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'no longer available' in response.data
    
    def test_withdraw_interest(self, client, app, auth_user):
        """Test user can withdraw their interest in a giveaway."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Create interest record
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user.id,
                message='I want this'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.post(
                f'/item/{giveaway.id}/withdraw-interest',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'Your interest has been withdrawn' in response.data
            
            # Verify interest record was deleted
            interest = GiveawayInterest.query.filter_by(
                item_id=giveaway.id,
                user_id=user.id
            ).first()
            assert interest is None


class TestRecipientSelection:
    """Test recipient selection for giveaways."""
    
    def test_owner_views_interested_users(self, client, app, auth_user):
        """Test owner can view list of interested users."""
        with app.app_context():
            owner = auth_user()
            user1 = UserFactory(first_name='Alice', last_name='Smith')
            user2 = UserFactory(first_name='Bob', last_name='Jones')
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Create interest records
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user1.id,
                message='I need this for my project'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user2.id,
                message='Would love to have this'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(f'/item/{giveaway.id}/select-recipient')
            
            assert response.status_code == 200
            assert b'Alice Smith' in response.data
            assert b'Bob Jones' in response.data
            assert b'I need this for my project' in response.data
            assert b'Would love to have this' in response.data
    
    def test_manual_recipient_selection(self, client, app, auth_user):
        """Test owner can manually select a specific recipient."""
        with app.app_context():
            owner = auth_user()
            user1 = UserFactory(first_name='Alice')
            user2 = UserFactory(first_name='Bob')
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Create interest records
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user1.id
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user2.id
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Select user2 manually
            response = client.post(
                f'/item/{giveaway.id}/select-recipient',
                data={
                    'selection_method': 'manual',
                    'user_id': str(user2.id)
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'has been selected' in response.data
            
            # Verify item status updated
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'pending_pickup'
            assert giveaway.claimed_by_id == user2.id
            assert giveaway.available is False
            assert giveaway.claimed_at is None  # Not set until handoff confirmed
            
            # Verify selected interest status updated
            db.session.refresh(interest2)
            assert interest2.status == 'selected'
            
            # Verify message sent to selected user
            message = Message.query.filter_by(
                recipient_id=user2.id,
                item_id=giveaway.id
            ).first()
            assert message is not None
            assert 'selected' in message.body.lower()
            
            # Verify non-selected user remains in pool
            db.session.refresh(interest1)
            assert interest1.status == 'active'
    
    def test_first_requester_selection(self, client, app, auth_user):
        """Test owner can select first (earliest) requester."""
        with app.app_context():
            owner = auth_user()
            user1 = UserFactory()
            user2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Create interest records with specific timestamps
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user1.id,
                created_at=datetime.now(UTC) - timedelta(hours=2)  # Earlier
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user2.id,
                created_at=datetime.now(UTC) - timedelta(hours=1)  # Later
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Select first requester
            response = client.post(
                f'/item/{giveaway.id}/select-recipient',
                data={'selection_method': 'first'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify first user (user1) was selected
            db.session.refresh(giveaway)
            assert giveaway.claimed_by_id == user1.id
            assert giveaway.claim_status == 'pending_pickup'
    
    def test_random_selection(self, client, app, auth_user):
        """Test owner can randomly select a recipient and selection is actually random."""
        from unittest.mock import patch
        
        with app.app_context():
            owner = auth_user()
            user1 = UserFactory(first_name='Alice')
            user2 = UserFactory(first_name='Bob')
            user3 = UserFactory(first_name='Charlie')
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            # Create interest records
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user1.id
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user2.id
            )
            interest3 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=user3.id
            )
            db.session.add_all([interest1, interest2, interest3])
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Test 1: Mock random.choice to return first interest (user1)
            with patch('app.main.routes.random.choice', return_value=interest1):
                response = client.post(
                    f'/item/{giveaway.id}/select-recipient',
                    data={'selection_method': 'random'},
                    follow_redirects=True
                )
                
                assert response.status_code == 200
                db.session.refresh(giveaway)
                assert giveaway.claimed_by_id == user1.id
                assert giveaway.claim_status == 'pending_pickup'
                assert b'Alice' in response.data  # Verify correct user shown in flash message
            
            # Reset giveaway for second test
            giveaway.claim_status = 'unclaimed'
            giveaway.claimed_by_id = None
            giveaway.available = True
            interest1.status = 'active'
            db.session.commit()
            
            # Test 2: Mock random.choice to return second interest (user2)
            with patch('app.main.routes.random.choice', return_value=interest2):
                response = client.post(
                    f'/item/{giveaway.id}/select-recipient',
                    data={'selection_method': 'random'},
                    follow_redirects=True
                )
                
                assert response.status_code == 200
                db.session.refresh(giveaway)
                assert giveaway.claimed_by_id == user2.id
                assert giveaway.claim_status == 'pending_pickup'
                assert b'Bob' in response.data  # Verify correct user shown in flash message
            
            # Reset giveaway for third test
            giveaway.claim_status = 'unclaimed'
            giveaway.claimed_by_id = None
            giveaway.available = True
            interest2.status = 'active'
            db.session.commit()
            
            # Test 3: Mock random.choice to return third interest (user3)
            with patch('app.main.routes.random.choice', return_value=interest3):
                response = client.post(
                    f'/item/{giveaway.id}/select-recipient',
                    data={'selection_method': 'random'},
                    follow_redirects=True
                )
                
                assert response.status_code == 200
                db.session.refresh(giveaway)
                assert giveaway.claimed_by_id == user3.id
                assert giveaway.claim_status == 'pending_pickup'
                assert b'Charlie' in response.data  # Verify correct user shown in flash message
    
    def test_non_owner_cannot_select_recipient(self, client, app, auth_user):
        """Test non-owner cannot access recipient selection."""
        with app.app_context():
            owner = UserFactory()
            user = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.get(
                f'/item/{giveaway.id}/select-recipient',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'do not have permission' in response.data
    
    def test_cannot_select_recipient_for_regular_item(self, client, app, auth_user):
        """Test owner cannot select recipient for non-giveaway item."""
        with app.app_context():
            owner = auth_user()
            category = CategoryFactory()
            
            regular_item = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=False
            )
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(
                f'/item/{regular_item.id}/select-recipient',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not a giveaway' in response.data


class TestGiveawayOwnerMessaging:
    """Test giveaway owner messaging functionality."""
    
    def test_owner_can_message_requester(self, client, app, auth_user):
        """Test that owner can initiate a message with a giveaway requester."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            # Requester expresses interest
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                message="I really need this!",
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Owner navigates to message form
            response = client.get(
                f'/item/{giveaway.id}/message-requester/{requester.id}'
            )
            
            assert response.status_code == 200
            assert requester.full_name.encode() in response.data
            assert b'I really need this!' in response.data
            assert giveaway.name.encode() in response.data
            
            # Owner sends a message
            response = client.post(
                f'/item/{giveaway.id}/message-requester/{requester.id}',
                data={
                    'body': 'Can you pick this up today?'
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify message was created
            message = Message.query.filter_by(
                sender_id=owner.id,
                recipient_id=requester.id,
                item_id=giveaway.id
            ).first()
            
            assert message is not None
            assert message.body == 'Can you pick this up today?'
    
    def test_non_owner_cannot_message_requester(self, client, app, auth_user):
        """Test that non-owner cannot access the message requester route."""
        with app.app_context():
            
            owner = UserFactory()
            non_owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, non_owner.email)
            
            response = client.get(
                f'/item/{giveaway.id}/message-requester/{requester.id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'do not have permission' in response.data
    
    def test_cannot_message_non_requester(self, client, app, auth_user):
        """Test that owner cannot message someone who hasn't expressed interest."""
        with app.app_context():
            owner = auth_user()
            random_user = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(
                f'/item/{giveaway.id}/message-requester/{random_user.id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not expressed interest' in response.data
    
    def test_redirects_to_existing_conversation(self, client, app, auth_user):
        """Test that accessing message route redirects to existing conversation."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            
            # Create existing message
            existing_message = Message(
                sender_id=requester.id,
                recipient_id=owner.id,
                item_id=giveaway.id,
                body="I have a question"
            )
            db.session.add(existing_message)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(
                f'/item/{giveaway.id}/message-requester/{requester.id}',
                follow_redirects=False
            )
            
            # Should redirect to existing conversation
            assert response.status_code == 302
            assert f'/message/{existing_message.id}' in response.location
    
    def test_message_button_appears_on_select_recipient_page(self, client, app, auth_user):
        """Test that Message button appears for each interested user."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory(first_name="Alice", last_name="Smith")
            requester2 = UserFactory(first_name="Bob", last_name="Jones")
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                message="Need this for work",
                status='active'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(f'/item/{giveaway.id}/select-recipient')
            
            assert response.status_code == 200
            assert b'Alice Smith' in response.data
            assert b'Bob Jones' in response.data
            # Check for Message button/link
            assert b'Message' in response.data
            assert f'/item/{giveaway.id}/message-requester/{requester1.id}'.encode() in response.data
            assert f'/item/{giveaway.id}/message-requester/{requester2.id}'.encode() in response.data


class TestRecipientReassignment:
    """Test changing the recipient of a giveaway that's pending pickup."""
    
    def test_change_recipient_next_in_line(self, client, app, auth_user):
        """Test 'next in line' excludes previous recipient."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory(first_name="First", last_name="User")
            requester2 = UserFactory(first_name="Second", last_name="User")
            requester3 = UserFactory(first_name="Third", last_name="User")
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            giveaway.available = False
            
            # Create interests with different timestamps
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'  # Previously selected
            )
            interest1.created_at = datetime.now(UTC) - timedelta(hours=3)
            
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            interest2.created_at = datetime.now(UTC) - timedelta(hours=2)
            
            interest3 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester3.id,
                status='active'
            )
            interest3.created_at = datetime.now(UTC) - timedelta(hours=1)
            
            db.session.add_all([interest1, interest2, interest3])
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Change recipient to "next in line" (should be requester2, the earliest active)
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify requester2 is now selected (not requester1)
            db.session.refresh(giveaway)
            assert giveaway.claimed_by_id == requester2.id
            assert giveaway.claim_status == 'pending_pickup'
            assert giveaway.claimed_at is None  # Not set until handoff confirmed
            
            # Verify requester1's interest is back to active
            db.session.refresh(interest1)
            assert interest1.status == 'active'
            
            # Verify requester2's interest is now selected
            db.session.refresh(interest2)
            assert interest2.status == 'selected'
    
    def test_change_recipient_random_excludes_previous(self, client, app, auth_user):
        """Test random selection excludes previous recipient."""
        with app.app_context():
            import random as stdlib_random
            
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            giveaway.available = False
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            # With only one remaining option (requester2), random must select them
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'random'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claimed_by_id == requester2.id
    
    def test_change_recipient_manual(self, client, app, auth_user):
        """Test manual reassignment to a specific user."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            giveaway.available = False
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={
                    'selection_method': 'manual',
                    'user_id': str(requester2.id)
                },
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claimed_by_id == requester2.id
            assert giveaway.claim_status == 'pending_pickup'
    
    def test_change_recipient_keeps_pending_pickup_status(self, client, app, auth_user):
        """Test reassignment keeps pending_pickup status and claimed_at as NULL."""
        with app.app_context():
           
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            giveaway.available = False
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest1.created_at = datetime.now(UTC) - timedelta(hours=3)
            
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            interest2.created_at = datetime.now(UTC) - timedelta(hours=2)
            
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'pending_pickup'
            assert giveaway.claimed_by_id == requester2.id
            assert giveaway.claimed_at is None
    
    def test_change_recipient_sends_notifications(self, client, app, auth_user):
        """Test that selected, de-selected users receive notification."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            giveaway.available = False
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            initial_messages = Message.query.count()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify two new messages were created:
            # 1. To requester1 (previous recipient) notifying they were de-selected
            # 2. To requester2 (new recipient) notifying they were selected
            final_messages = Message.query.count()
            assert final_messages == initial_messages + 2
            
            # Verify message to new recipient
            new_recipient_message = Message.query.filter_by(recipient_id=requester2.id).first()
            assert new_recipient_message is not None
            assert 'selected' in new_recipient_message.body.lower()
            
            # Verify message to previous recipient
            prev_recipient_message = Message.query.filter_by(recipient_id=requester1.id).first()
            assert prev_recipient_message is not None
            assert 'different recipient' in prev_recipient_message.body.lower()
    
    def test_change_recipient_no_other_users(self, client, app, auth_user):
        """Test error when no other interested users available."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            
            # Only one interested user (the current one)
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            db.session.add(interest1)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'No other interested users' in response.data
    
    def test_change_recipient_non_owner_denied(self, client, app, auth_user):
        """Test non-owner cannot change recipient."""
        with app.app_context():
            
            owner = UserFactory()
            non_owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, non_owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'do not have permission' in response.data
    
    def test_change_recipient_not_pending_pickup(self, client, app, auth_user):
        """Test cannot change recipient if not pending_pickup."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'  # Not pending_pickup
            )
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='active'
            )
            db.session.add(interest1)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/change-recipient',
                data={'selection_method': 'next'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not pending pickup' in response.data


class TestReleaseToAll:
    """Test releasing a giveaway back to unclaimed status."""
    
    def test_release_to_all_returns_to_unclaimed(self, client, app, auth_user):
        """Test release-to-all returns to unclaimed state."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester
            )
            giveaway.available = False
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='selected'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/release-to-all',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'unclaimed'
            assert giveaway.claimed_by_id is None
            assert giveaway.claimed_at is None
            assert giveaway.available is True
    
    def test_release_to_all_keeps_interests_active(self, client, app, auth_user):
        """Test all existing GiveawayInterest records remain active."""
        with app.app_context():
            
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester1
            )
            
            interest1 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester1.id,
                status='selected'
            )
            interest2 = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester2.id,
                status='active'
            )
            db.session.add_all([interest1, interest2])
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/release-to-all',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify both interests are active
            db.session.refresh(interest1)
            db.session.refresh(interest2)
            assert interest1.status == 'active'
            assert interest2.status == 'active'
    
    def test_release_to_all_notifies_previous_recipient(self, client, app, auth_user):
        """Test that previous recipient is notified on release-to-all."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='selected'
            )
            db.session.add(interest)
            db.session.commit()
            
            initial_messages = Message.query.count()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/release-to-all',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify notification was sent to previous recipient
            final_messages = Message.query.count()
            assert final_messages == initial_messages + 1
            
            notification = Message.query.filter_by(recipient_id=requester.id).first()
            assert notification is not None
            assert 'released' in notification.body.lower()
            assert 'back to everyone' in notification.body.lower()
    
    def test_release_to_all_not_pending_pickup(self, client, app, auth_user):
        """Test cannot release if not pending_pickup."""
        with app.app_context():
            owner = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/release-to-all',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not pending pickup' in response.data


class TestConfirmHandoff:
    """Test confirming the handoff of a giveaway."""
    
    def test_confirm_handoff_transitions_to_claimed(self, client, app, auth_user):
        """Test confirm-handoff transitions to claimed state."""
        with app.app_context():
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester
            )
            giveaway.available = False
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/confirm-handoff',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'claimed'
            assert giveaway.claimed_at is not None
            assert giveaway.claimed_by_id == requester.id
            assert giveaway.available is False
    
    def test_confirm_handoff_sets_claimed_at_timestamp(self, client, app, auth_user):
        """Test that claimed_at is set to current time on confirmation."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester
            )
            giveaway.available = False
            db.session.commit()
            
            before_time = datetime.now(UTC)
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/confirm-handoff',
                follow_redirects=True
            )
            
            after_time = datetime.now(UTC)
            
            assert response.status_code == 200
            
            db.session.refresh(giveaway)
            assert giveaway.claimed_at is not None
            # Ensure claimed_at is timezone-aware for comparison
            claimed_at_utc = giveaway.claimed_at.replace(tzinfo=UTC) if giveaway.claimed_at.tzinfo is None else giveaway.claimed_at
            assert before_time <= claimed_at_utc <= after_time
    
    def test_confirm_handoff_not_pending_pickup(self, client, app, auth_user):
        """Test cannot confirm handoff if not pending_pickup."""
        with app.app_context():
            owner = auth_user()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.post(
                f'/item/{giveaway.id}/confirm-handoff',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not pending pickup' in response.data
    
    def test_claimed_items_not_in_feeds(self, client, app, auth_user):
        """Test claimed items don't appear in giveaway feed."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            
            category = CategoryFactory()
            
            # Claimed giveaway (should NOT appear)
            claimed_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Claimed Item',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='claimed',
                claimed_by=user
            )
            claimed_giveaway.available = False
            
            # Unclaimed giveaway (should appear)
            unclaimed_giveaway = ItemFactory(
                owner=other_user,
                category=category,
                name='Available Item',
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            assert b'Available Item' in response.data
            assert b'Claimed Item' not in response.data
    
    def test_pending_pickup_items_not_visible_to_others(self, client, app, auth_user):
        """Test pending_pickup items (even public ones) don't appear to other users in giveaway feed."""
        with app.app_context():
            user = auth_user()
            owner = UserFactory()
            recipient = UserFactory()
            
            # Create separate circles so user doesn't share circles with owner
            circle1 = CircleFactory()
            circle1.members.append(user)
            
            circle2 = CircleFactory() 
            circle2.members.append(owner)
            circle2.members.append(recipient)
            
            category = CategoryFactory()
            
            # Public giveaway that's pending pickup (should NOT appear to other users)
            pending_giveaway = ItemFactory(
                owner=owner,
                category=category,
                name='Pending Public Item',
                is_giveaway=True,
                giveaway_visibility='public',  # Public visibility
                claim_status='pending_pickup',  # But pending pickup
                claimed_by=recipient
            )
            pending_giveaway.available = False
            
            # Unclaimed public giveaway (should appear)
            unclaimed_giveaway = ItemFactory(
                owner=owner,
                category=category,
                name='Available Public Item',
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed'
            )
            
            db.session.commit()
            
            login_user(client, user.email)
            
            response = client.get('/giveaways')
            
            assert response.status_code == 200
            assert b'Available Public Item' in response.data, "Unclaimed public giveaway should appear"
            assert b'Pending Public Item' not in response.data, "Pending pickup giveaway should NOT appear to other users"


class TestItemDetailPageForGiveaways:
    """Test item detail page UI for different giveaway states."""
    
    def test_owner_sees_pending_pickup_controls(self, client, app, auth_user):
        """Test owner sees Change Recipient, Release to Everyone, and Confirm Handoff buttons."""
        with app.app_context():
            owner = auth_user()
            requester = UserFactory(first_name="John", last_name="Doe")
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='pending_pickup',
                claimed_by=requester
            )
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(f'/item/{giveaway.id}')
            
            assert response.status_code == 200
            assert b'Change Recipient' in response.data
            assert b'Release to Everyone' in response.data
            assert b'Confirm Handoff Complete' in response.data
            assert b'Recipient:' in response.data
            assert b'John Doe' in response.data
    
    def test_owner_sees_claimed_badge(self, client, app, auth_user):
        """Test owner sees claimed badge with recipient name and date."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory(first_name="Jane", last_name="Smith")
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=requester
            )
            giveaway.claimed_at = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(f'/item/{giveaway.id}')
            
            assert response.status_code == 200
            assert b'Jane Smith' in response.data
            assert b'data-utc-timestamp="2025-06-15T12:00:00"' in response.data
            # Should NOT show action buttons for claimed items
            assert b'Change Recipient' not in response.data
            assert b'Release to Everyone' not in response.data
            assert b'Confirm Handoff Complete' not in response.data


class TestDataIntegrity:
    """Test data integrity and edge cases for giveaways."""
    
    def test_claimed_by_persists_when_user_soft_deleted(self, client, app, auth_user):
        """Test claimed_by_id persists when claiming user soft deletes account."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='claimed',
                claimed_by=requester
            )
            giveaway.claimed_at = datetime.now(UTC)
            db.session.commit()
            
            # Soft delete the requester
            requester.is_deleted = True
            requester.deleted_at = datetime.now(UTC)
            db.session.commit()
            
            # Verify item still exists and maintains claim status
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'claimed'
            assert giveaway.claimed_at is not None
            # claimed_by_id should still reference the user (soft delete doesn't cascade)
            assert giveaway.claimed_by_id == requester.id
    
    def test_giveaway_interest_cascade_delete_on_item_delete(self, client, app, auth_user):
        """Test GiveawayInterest records are removed when item deleted."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            interest_id = interest.id
            giveaway_id = giveaway.id
            
            # Login as the owner
            login_user(client, owner.email)
            
            # Delete the giveaway through the app's deletion route
            from app.forms import DeleteItemForm
            delete_form = DeleteItemForm()
            response = client.post(
                f'/item/{giveaway_id}/delete',
                data=delete_form.data,
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify interest record was cascade deleted
            deleted_interest = db.session.get(GiveawayInterest, interest_id)
            assert deleted_interest is None
    
    def test_giveaway_interest_cascade_delete_on_user_delete(self, client, app, auth_user):
        """Test GiveawayInterest records are removed when user hard deleted."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            interest_id = interest.id
            requester_id = requester.id
            
            # Hard delete the requester user using raw SQL to bypass SQLAlchemy's ORM handling
            db.session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(requester_id)})
            db.session.commit()
            
            # Verify interest record was cascade deleted
            deleted_interest = db.session.get(GiveawayInterest, interest_id)
            assert deleted_interest is None
            
            # Verify giveaway still exists
            db.session.refresh(giveaway)
            assert giveaway is not None
    
    def test_cannot_change_from_claimed_back_to_other_states(self, client, app, auth_user):
        """Test that release-to-all fails for claimed items."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='claimed',  # Terminal state
                claimed_by=requester
            )
            giveaway.claimed_at = datetime.now(UTC)
            db.session.commit()
            
            login_user(client, owner.email)
            
            # Try to release to all (should fail)
            response = client.post(
                f'/item/{giveaway.id}/release-to-all',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not pending pickup' in response.data
            
            # Verify status unchanged
            db.session.refresh(giveaway)
            assert giveaway.claim_status == 'claimed'


class TestSelectRecipientReassignmentUI:
    """Test the select_recipient page shows correct UI for reassignment."""
    
    def test_select_recipient_page_shows_initial_selection_ui(self, client, app, auth_user):
        """Test select recipient page shows 'Select Recipient' header for initial selection."""
        with app.app_context():
            
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                claim_status='unclaimed'  # Initial selection
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            response = client.get(f'/item/{giveaway.id}/select-recipient')
            
            assert response.status_code == 200
            assert b'Select Recipient' in response.data
            assert b'First Requester' in response.data
            assert b'Random Selection' in response.data
