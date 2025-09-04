import pytest
from app.models import Circle, db
from tests.factories import UserFactory
from conftest import login_user


def test_unlisted_circle_not_found_by_name_but_found_by_uuid(client, app):
    """Verify that unlisted circles do not appear in name searches but are discoverable by exact UUID."""
    with app.app_context():
        # Create a test user and login
        user = UserFactory()
        login_user(client, user.email)

        # Create an unlisted circle
        circle = Circle(
            name='Hidden Gems Club',
            description='A club for rare finds',
            visibility='unlisted',
            requires_approval=True
        )
        db.session.add(circle)
        db.session.commit()

        # Attempt to search by partial name via the search endpoint
        response = client.post('/circles', data={'search_circles': True, 'search_query': 'Hidden'}, follow_redirects=True)
        assert response.status_code == 200
        # Should NOT contain our unlisted circle name in the search results
        assert b'Hidden Gems Club' not in response.data

        # Now try to find by UUID via the uuid search
        response = client.post('/circles', data={'find_by_uuid': True, 'circle_uuid': str(circle.id)}, follow_redirects=True)
        assert response.status_code == 200
        # Should now include the circle name in the results
        assert b'Hidden Gems Club' in response.data

        # Cleanup
        db.session.delete(circle)
        db.session.commit()
