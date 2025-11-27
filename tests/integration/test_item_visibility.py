import pytest
from app.models import Item, User, Category, Circle, db, circle_members
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from flask import url_for
from conftest import login_user

@pytest.mark.usefixtures('app')
class TestItemVisibility:
    def test_logged_out_user_cannot_see_items_from_private_circle_only_member(self, client):
        # Create a category
        category = CategoryFactory()
        db.session.commit()

        # Create a user and an item
        user = UserFactory()
        item = ItemFactory(owner=user, category=category)
        db.session.commit()

        # Create a private circle and add the user as a member
        private_circle = CircleFactory(requires_approval=True)
        db.session.commit()
        db.session.execute(circle_members.insert().values(user_id=user.id, circle_id=private_circle.id))
        db.session.commit()

        # Ensure user is NOT in any public circle
        # Now, as a logged-out user, visit the homepage
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # The item should NOT be visible
        assert item.name.encode() not in response.data

    def test_logged_out_user_can_see_items_from_public_circle_member(self, client):
        # Create a category
        category = CategoryFactory()
        db.session.commit()

        # Create a user and an item
        user = UserFactory()
        item = ItemFactory(owner=user, category=category)
        db.session.commit()

        # Create a public circle and add the user as a member
        public_circle = CircleFactory(requires_approval=False)
        db.session.commit()
        db.session.execute(circle_members.insert().values(user_id=user.id, circle_id=public_circle.id))
        db.session.commit()

        # Now, as a logged-out user, visit the homepage
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # The item should be visible
        assert item.name.encode() in response.data

    def test_authenticated_user_does_not_see_own_items(self, client):
        """Test that authenticated users don't see their own items on homepage."""
        category = CategoryFactory()
        user = UserFactory()
        db.session.commit()
        
        # Create a circle and add user
        circle = CircleFactory(requires_approval=False)
        db.session.commit()
        db.session.execute(circle_members.insert().values(user_id=user.id, circle_id=circle.id))
        db.session.commit()
        
        # Create an item owned by the user
        item = ItemFactory(owner=user, category=category)
        db.session.commit()
        
        # Login as the user
        login_user(client, user.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # User should NOT see their own item
        assert item.name.encode() not in response.data

    def test_authenticated_user_sees_items_from_shared_circle(self, client):
        """Test that authenticated users see items from users in shared circles."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        db.session.commit()
        
        # Create a circle and add both users
        circle = CircleFactory(requires_approval=False)
        db.session.commit()
        db.session.execute(circle_members.insert().values(user_id=user1.id, circle_id=circle.id))
        db.session.execute(circle_members.insert().values(user_id=user2.id, circle_id=circle.id))
        db.session.commit()
        
        # Create an item owned by user2
        item = ItemFactory(owner=user2, category=category)
        db.session.commit()
        
        # Login as user1
        login_user(client, user1.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # User1 should see user2's item
        assert item.name.encode() in response.data

    def test_authenticated_user_does_not_see_items_from_non_circle_members(self, client):
        """Test that authenticated users don't see items from users not in their circles."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        db.session.commit()
        
        # Create two separate circles
        circle1 = CircleFactory(requires_approval=False)
        circle2 = CircleFactory(requires_approval=False)
        db.session.commit()
        
        # Add user1 to circle1, user3 to circle2 (no overlap)
        db.session.execute(circle_members.insert().values(user_id=user1.id, circle_id=circle1.id))
        db.session.execute(circle_members.insert().values(user_id=user3.id, circle_id=circle2.id))
        db.session.commit()
        
        # Create items for user2 (not in any circle) and user3 (in different circle)
        item2 = ItemFactory(owner=user2, category=category, name="User2 Item")
        item3 = ItemFactory(owner=user3, category=category, name="User3 Item")
        db.session.commit()
        
        # Login as user1
        login_user(client, user1.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # User1 should NOT see items from user2 or user3
        assert item2.name.encode() not in response.data
        assert item3.name.encode() not in response.data

    def test_authenticated_user_sees_items_from_multiple_circles(self, client):
        """Test that authenticated users see items from all their circles."""
        category = CategoryFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        db.session.commit()
        
        # Create two circles
        circle1 = CircleFactory(requires_approval=False, name="Circle 1")
        circle2 = CircleFactory(requires_approval=False, name="Circle 2")
        db.session.commit()
        
        # Add user1 to both circles, user2 to circle1, user3 to circle2
        db.session.execute(circle_members.insert().values(user_id=user1.id, circle_id=circle1.id))
        db.session.execute(circle_members.insert().values(user_id=user1.id, circle_id=circle2.id))
        db.session.execute(circle_members.insert().values(user_id=user2.id, circle_id=circle1.id))
        db.session.execute(circle_members.insert().values(user_id=user3.id, circle_id=circle2.id))
        db.session.commit()
        
        # Create items for user2 and user3
        item2 = ItemFactory(owner=user2, category=category, name="User2 Item from Circle1")
        item3 = ItemFactory(owner=user3, category=category, name="User3 Item from Circle2")
        db.session.commit()
        
        # Login as user1
        login_user(client, user1.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        # User1 should see items from both circles
        assert item2.name.encode() in response.data
        assert item3.name.encode() in response.data

    def test_authenticated_user_with_no_circles_sees_empty_state(self, client):
        """Test that authenticated users with no circles see the 'Join a circle' message."""
        user = UserFactory()
        db.session.commit()
        
        # Login as user (who is not in any circles)
        login_user(client, user.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        # Should see the join circle message
        assert 'Join a circle to see items' in response_text
        assert 'Find Circles to Join' in response_text

    def test_authenticated_user_in_circle_with_no_other_members(self, client):
        """Test authenticated user in a circle alone sees empty state."""
        category = CategoryFactory()
        user = UserFactory()
        db.session.commit()
        
        # Create a circle with only this user
        circle = CircleFactory(requires_approval=False)
        db.session.commit()
        db.session.execute(circle_members.insert().values(user_id=user.id, circle_id=circle.id))
        db.session.commit()
        
        # Login as user
        login_user(client, user.email)
        
        response = client.get(url_for('main.index'))
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        # Should see empty state (no items from circle-mates)
        assert 'No items available' in response_text or 'Join a circle' in response_text
