import pytest
import re
from unittest.mock import patch
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


def test_browse_shows_private_not_unlisted_and_defaults_radius_25(client, app):
    """Browse mode should show listed circles (public/private), hide unlisted, and default to 25 miles."""
    with app.app_context():
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        login_user(client, user.email)

        public_circle = Circle(
            name='Visible Public Circle',
            description='Public listing',
            visibility='public',
            requires_approval=False,
            latitude=40.7130,
            longitude=-74.0062,
        )
        private_circle = Circle(
            name='Visible Private Circle',
            description='Private listing',
            visibility='private',
            requires_approval=True,
            latitude=40.7131,
            longitude=-74.0061,
        )
        unlisted_circle = Circle(
            name='Hidden Unlisted Circle',
            description='Should not appear in browse',
            visibility='unlisted',
            requires_approval=True,
            latitude=40.7132,
            longitude=-74.0063,
        )

        db.session.add_all([public_circle, private_circle, unlisted_circle])
        db.session.commit()

        response = client.get('/circles', follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'Visible Public Circle' in html
        assert 'Visible Private Circle' in html
        assert 'Hidden Unlisted Circle' not in html
        assert re.search(r'<option[^>]*value="25"[^>]*selected|<option[^>]*selected[^>]*value="25"', html)


def test_distance_filter_results_sorted_by_membership_desc(client, app):
    """Distance filter should apply first, then circles should be ordered by membership descending."""
    with app.app_context():
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        login_user(client, user.email)

        large_circle = Circle(
            name='Large Nearby Circle',
            description='Many members',
            visibility='public',
            requires_approval=False,
            latitude=40.7130,
            longitude=-74.0062,
        )
        small_circle = Circle(
            name='Small Nearby Circle',
            description='Few members',
            visibility='private',
            requires_approval=True,
            latitude=40.7131,
            longitude=-74.0061,
        )
        far_circle = Circle(
            name='Far Circle',
            description='Outside radius',
            visibility='public',
            requires_approval=False,
            latitude=41.7128,
            longitude=-75.0060,
        )

        db.session.add_all([large_circle, small_circle, far_circle])
        large_circle.members.extend([UserFactory(), UserFactory(), UserFactory()])
        small_circle.members.append(UserFactory())
        db.session.commit()

        response = client.post(
            '/circles',
            data={'search_circles': True, 'search_query': '', 'radius': '25'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'Large Nearby Circle' in html
        assert 'Small Nearby Circle' in html
        assert 'Far Circle' not in html
        assert html.index('Large Nearby Circle') < html.index('Small Nearby Circle')


def test_browse_results_render_circle_thumbnail_and_precomputed_facepile(client, app):
    """Browse list should show circle image thumbnails and use precomputed member samples."""
    with app.app_context():
        user = UserFactory(latitude=40.7128, longitude=-74.0060)
        login_user(client, user.email)

        circle = Circle(
            name='Thumbnail Circle',
            description='Circle with image and members',
            visibility='public',
            requires_approval=False,
            image_url='https://cdn.example.com/circle-thumb.jpg',
            latitude=40.7130,
            longitude=-74.0062,
        )
        db.session.add(circle)

        members = [
            UserFactory(first_name='Member One', profile_image_url='https://cdn.example.com/one.jpg'),
            UserFactory(first_name='Member Two', profile_image_url='https://cdn.example.com/two.jpg'),
            UserFactory(first_name='Member Three'),
            UserFactory(first_name='Member Four'),
        ]
        for member in members:
            circle.members.append(member)
        db.session.commit()

        sampled_members = members[:2]

        with patch('app.circles.routes.build_circle_member_samples', return_value={circle.id: sampled_members}) as mock_sampler:
            response = client.get('/circles', follow_redirects=True)

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'Thumbnail Circle' in html
        assert 'circle-result-thumbnail' in html
        assert 'https://cdn.example.com/circle-thumb.jpg' in html
        assert html.count('share-member-avatar') >= 2
        assert '+2 more' in html
        mock_sampler.assert_called_once()
