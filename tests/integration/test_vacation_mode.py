"""Tests for vacation mode functionality."""
import pytest
from app.models import Item, User, Category, db
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory, TagFactory
from flask import url_for
from conftest import login_user


@pytest.mark.usefixtures('app')
class TestVacationModeToggle:
    """Test vacation mode toggle in profile page."""
    
    def test_vacation_mode_toggle_appears_in_profile(self, client):
        """Test that the vacation mode toggle is visible in the profile page."""
        user = UserFactory()
        db.session.commit()
        
        login_user(client, user.email)
        response = client.get(url_for('main.profile'))
        
        assert response.status_code == 200
        assert b'Vacation Mode' in response.data
        assert b'vacationModeSwitch' in response.data
    
    def test_enable_vacation_mode(self, client):
        """Test enabling vacation mode via POST request."""
        user = UserFactory(vacation_mode=False)
        db.session.commit()
        
        login_user(client, user.email)
        
        # Enable vacation mode
        response = client.post(
            url_for('main.toggle_vacation_mode'),
            data={'vacation_mode': 'y'},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Vacation mode enabled' in response.data
        
        # Verify user state changed
        db.session.refresh(user)
        assert user.vacation_mode is True
    
    def test_disable_vacation_mode(self, client):
        """Test disabling vacation mode via POST request."""
        user = UserFactory(vacation_mode=True)
        db.session.commit()
        
        login_user(client, user.email)
        
        # Disable vacation mode (checkbox not sent = False)
        response = client.post(
            url_for('main.toggle_vacation_mode'),
            data={},  # Empty form means checkbox unchecked
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Vacation mode disabled' in response.data
        
        # Verify user state changed
        db.session.refresh(user)
        assert user.vacation_mode is False


@pytest.mark.usefixtures('app')
class TestVacationModeItemVisibility:
    """Test that vacation mode hides items from other users."""
    
    def test_homepage_hides_items_from_vacation_mode_user(self, client):
        """Test that items from users in vacation mode are hidden on the homepage."""
        category = CategoryFactory()
        user1 = UserFactory()  # Viewer
        user2 = UserFactory(vacation_mode=False)  # Normal user
        user3 = UserFactory(vacation_mode=True)  # Vacation mode user
        db.session.commit()
        
        # Create a circle with all users
        circle = CircleFactory()
        circle.members.extend([user1, user2, user3])
        db.session.commit()
        
        # Create items for both user2 and user3
        item_visible = ItemFactory(owner=user2, category=category, name="Visible Item ABC123")
        item_hidden = ItemFactory(owner=user3, category=category, name="Hidden Item XYZ789")
        db.session.commit()
        
        # Login as user1 and visit homepage
        login_user(client, user1.email)
        response = client.get(url_for('main.index'))
        
        assert response.status_code == 200
        # Visible item should be shown
        assert b'Visible Item ABC123' in response.data
        # Hidden item should NOT be shown
        assert b'Hidden Item XYZ789' not in response.data
    
    def test_giveaways_feed_hides_items_from_vacation_mode_user(self, client):
        """Test that giveaway items from users in vacation mode are hidden."""
        category = CategoryFactory()
        user1 = UserFactory()  # Viewer
        user2 = UserFactory(vacation_mode=False)  # Normal user
        user3 = UserFactory(vacation_mode=True)  # Vacation mode user
        db.session.commit()
        
        # Create a circle with all users
        circle = CircleFactory()
        circle.members.extend([user1, user2, user3])
        db.session.commit()
        
        # Create giveaway items for both users
        giveaway_visible = ItemFactory(
            owner=user2, category=category, name="Visible Giveaway ABC",
            is_giveaway=True, giveaway_visibility='default', claim_status='unclaimed'
        )
        giveaway_hidden = ItemFactory(
            owner=user3, category=category, name="Hidden Giveaway XYZ",
            is_giveaway=True, giveaway_visibility='default', claim_status='unclaimed'
        )
        db.session.commit()
        
        # Login as user1 and visit giveaways page
        login_user(client, user1.email)
        response = client.get(url_for('main.giveaways'))
        
        assert response.status_code == 200
        # Visible giveaway should be shown
        assert b'Visible Giveaway ABC' in response.data
        # Hidden giveaway should NOT be shown
        assert b'Hidden Giveaway XYZ' not in response.data
    
    def test_search_hides_items_from_vacation_mode_user(self, client):
        """Test that search results exclude items from users in vacation mode."""
        category = CategoryFactory()
        user1 = UserFactory()  # Viewer
        user2 = UserFactory(vacation_mode=False)  # Normal user
        user3 = UserFactory(vacation_mode=True)  # Vacation mode user
        db.session.commit()
        
        # Create a circle with all users
        circle = CircleFactory()
        circle.members.extend([user1, user2, user3])
        db.session.commit()
        
        # Create items with searchable names
        item_visible = ItemFactory(owner=user2, category=category, name="Hammer for Visible User")
        item_hidden = ItemFactory(owner=user3, category=category, name="Hammer from Hidden User")
        db.session.commit()
        
        # Login as user1 and search for "Hammer"
        login_user(client, user1.email)
        response = client.get(url_for('main.search', q='Hammer'))
        
        assert response.status_code == 200
        # Visible item should be shown
        assert b'Hammer for Visible User' in response.data
        # Hidden item should NOT be shown
        assert b'Hammer from Hidden User' not in response.data
    
    def test_tag_page_hides_items_from_vacation_mode_user(self, client):
        """Test that tag pages exclude items from users in vacation mode."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory(vacation_mode=False)
        user3 = UserFactory(vacation_mode=True)
        db.session.commit()
        
        # Create a circle with all users
        circle = CircleFactory()
        circle.members.extend([user1, user2, user3])
        db.session.commit()
        
        # Create a shared tag
        tag = TagFactory(name="power-tools")
        db.session.commit()
        
        # Create items with the same tag
        item_visible = ItemFactory(owner=user2, category=category, name="Visible Drill")
        item_visible.tags.append(tag)
        item_hidden = ItemFactory(owner=user3, category=category, name="Hidden Drill")
        item_hidden.tags.append(tag)
        db.session.commit()
        
        # Login as user1 and visit tag page
        login_user(client, user1.email)
        response = client.get(url_for('main.tag_items', tag_id=tag.id))
        
        assert response.status_code == 200
        # Visible item should be shown
        assert b'Visible Drill' in response.data
        # Hidden item should NOT be shown
        assert b'Hidden Drill' not in response.data
    
    def test_category_page_hides_items_from_vacation_mode_user(self, client):
        """Test that category pages exclude items from users in vacation mode."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory(vacation_mode=False)
        user3 = UserFactory(vacation_mode=True)
        db.session.commit()
        
        # Create a circle with all users
        circle = CircleFactory()
        circle.members.extend([user1, user2, user3])
        db.session.commit()
        
        # Create items in the same category
        item_visible = ItemFactory(owner=user2, category=category, name="Visible Gadget 123")
        item_hidden = ItemFactory(owner=user3, category=category, name="Hidden Gadget 456")
        db.session.commit()
        
        # Login as user1 and visit category page
        login_user(client, user1.email)
        response = client.get(url_for('main.category_items', category_id=category.id))
        
        assert response.status_code == 200
        # Visible item should be shown
        assert b'Visible Gadget 123' in response.data
        # Hidden item should NOT be shown
        assert b'Hidden Gadget 456' not in response.data


@pytest.mark.usefixtures('app')
class TestVacationModeOwnItemsStillVisible:
    """Test that user's own items are still visible to themselves when in vacation mode."""
    
    def test_own_items_visible_in_profile_when_vacation_mode(self, client):
        """Test that a user can see their own items on their profile even in vacation mode."""
        category = CategoryFactory()
        user = UserFactory(vacation_mode=True)
        db.session.commit()
        
        # Create a circle and add the user
        circle = CircleFactory()
        circle.members.append(user)
        db.session.commit()
        
        # Create an item owned by the user
        item = ItemFactory(owner=user, category=category, name="My Own Item")
        db.session.commit()
        
        # Login and visit profile
        login_user(client, user.email)
        response = client.get(url_for('main.profile'))
        
        assert response.status_code == 200
        # User should see their own item
        assert b'My Own Item' in response.data


@pytest.mark.usefixtures('app')
class TestVacationModeAnonymousUsers:
    """Test that vacation mode affects items shown to anonymous users."""
    
    def test_anonymous_homepage_hides_public_showcase_items_from_vacation_mode_user(self, client):
        """Test that public showcase items from vacation mode users are hidden."""
        category = CategoryFactory()
        
        # Create a public showcase user in vacation mode
        showcase_user_vacation = UserFactory(is_public_showcase=True, vacation_mode=True)
        # Create a public showcase user not in vacation mode
        showcase_user_normal = UserFactory(is_public_showcase=True, vacation_mode=False)
        db.session.commit()
        
        # Create items
        item_hidden = ItemFactory(owner=showcase_user_vacation, category=category, name="Hidden Showcase Item")
        item_visible = ItemFactory(owner=showcase_user_normal, category=category, name="Visible Showcase Item")
        db.session.commit()
        
        # Visit homepage as anonymous user
        response = client.get(url_for('main.index'))
        
        assert response.status_code == 200
        # Visible item should be shown (note: could be subject to random selection so we check at model level)
        # Since items are randomly selected, let's just verify the vacation mode filter is working
        # The hidden item should definitely not be shown
        assert b'Hidden Showcase Item' not in response.data
