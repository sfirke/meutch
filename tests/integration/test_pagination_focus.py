"""Integration tests for pagination section focus anchors."""
from app import db
from app.models import Circle
from conftest import login_user
from tests.factories import CategoryFactory, ItemFactory, ItemRequestFactory, UserFactory

ITEMS_PER_PAGE = 12


class TestPaginationFocus:
    """Test pagination links preserve section focus."""

    def test_profile_pagination_links_anchor_to_my_items(self, client, app, auth_user):
        """Profile pagination should keep focus on My Items section."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()

            ItemFactory(owner=user, category=category, is_giveaway=True, claim_status='unclaimed')
            for _ in range(ITEMS_PER_PAGE + 1):
                ItemFactory(owner=user, category=category, is_giveaway=False)

            login_user(client, user.email)
            response = client.get('/profile')

            assert response.status_code == 200
            assert b'id="my-items-section"' in response.data
            assert b'/profile?page=2#my-items-section' in response.data

    def test_giveaways_pagination_links_anchor_to_available_section(self, client, app, auth_user):
        """Giveaways pagination should keep focus on the available-from-others section."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            category = CategoryFactory()

            circle = Circle(name="Pagination Circle", description="Circle for pagination", requires_approval=False)
            db.session.add(circle)
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemFactory(owner=user, category=category, is_giveaway=True, claim_status='unclaimed')
            for _ in range(ITEMS_PER_PAGE + 1):
                ItemFactory(owner=other_user, category=category, is_giveaway=True, claim_status='unclaimed')

            login_user(client, user.email)
            response = client.get('/giveaways')

            assert response.status_code == 200
            assert b'id="available-giveaways-section"' in response.data
            assert b'page=2&amp;sort=date#available-giveaways-section' in response.data

    def test_requests_pagination_links_anchor_to_others_section(self, client, app, auth_user):
        """Requests pagination should keep focus on the from-others section."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()

            circle = Circle(name="Requests Pagination Circle", description="Circle for requests", requires_approval=False)
            db.session.add(circle)
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(user=user, visibility='circles')
            for _ in range(ITEMS_PER_PAGE + 1):
                ItemRequestFactory(user=other_user, visibility='circles')

            login_user(client, user.email)
            response = client.get('/requests/?scope=circles')

            assert response.status_code == 200
            assert b'id="other-requests-section"' in response.data
            assert b'page=2&amp;scope=circles#other-requests-section' in response.data
