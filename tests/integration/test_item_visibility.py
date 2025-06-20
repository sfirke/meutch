import pytest
from app.models import Item, User, Category, Circle, db, circle_members
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from flask import url_for

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
