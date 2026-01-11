"""Integration tests for giveaway routes and functionality."""
import pytest
from app import db
from app.models import Item, Category
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from conftest import TEST_PASSWORD


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
            from datetime import datetime, UTC, timedelta
            
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest
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
            from app.models import GiveawayInterest, Message
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
            from app.models import GiveawayInterest
            from datetime import datetime, UTC, timedelta
            
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
        """Test owner can randomly select a recipient."""
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
            
            # Create interest records
            from app.models import GiveawayInterest
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
            
            # Select random
            response = client.post(
                f'/item/{giveaway.id}/select-recipient',
                data={'selection_method': 'random'},
                follow_redirects=True
            )
            
            assert response.status_code == 200
            
            # Verify one of the users was selected
            db.session.refresh(giveaway)
            assert giveaway.claimed_by_id in [user1.id, user2.id]
            assert giveaway.claim_status == 'pending_pickup'
    
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
            from app.models import GiveawayInterest, Message
            
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
            
            client.post('/auth/login', data={'email': owner.email, 'password': TEST_PASSWORD}, follow_redirects=True)
            
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
            from app.models import GiveawayInterest
            
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
            
            client.post('/auth/login', data={'email': non_owner.email, 'password': TEST_PASSWORD}, follow_redirects=True)
            
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
            
            client.post('/auth/login', data={'email': owner.email, 'password': TEST_PASSWORD}, follow_redirects=True)
            
            response = client.get(
                f'/item/{giveaway.id}/message-requester/{random_user.id}',
                follow_redirects=True
            )
            
            assert response.status_code == 200
            assert b'not expressed interest' in response.data
    
    def test_redirects_to_existing_conversation(self, client, app, auth_user):
        """Test that accessing message route redirects to existing conversation."""
        with app.app_context():
            from app.models import GiveawayInterest, Message
            
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
            
            client.post('/auth/login', data={'email': owner.email, 'password': TEST_PASSWORD}, follow_redirects=True)
            
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
            from app.models import GiveawayInterest
            
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

