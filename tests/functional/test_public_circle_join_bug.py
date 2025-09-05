"""Functional test to ensure public circles can be joined by other users."""
from flask import url_for
from app.models import Circle
from app import db
from tests.factories import UserFactory
from conftest import TEST_PASSWORD


def test_public_circle_join_flow(client, app):
    with app.app_context():
        # Create two users
        creator = UserFactory(email='creator_public@test.com')
        joiner = UserFactory(email='joiner_public@test.com')

        # Creator logs in and creates a public circle (requires_approval=False)
        client.post('/auth/login', data={
            'email': creator.email,
            'password': TEST_PASSWORD
        }, follow_redirects=True)

        response = client.post('/circles', data={
            'create_circle': True,
            'name': 'Public Circle Test',
            'description': 'A public circle for testing',
            # requires_approval unchecked / False
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Public Circle Test' in response.data

        circle = Circle.query.filter_by(name='Public Circle Test').first()
        assert circle is not None
        assert circle.requires_approval is False

        # Logout creator
        client.get('/auth/logout', follow_redirects=True)

        # Joiner logs in and attempts to join the public circle
        client.post('/auth/login', data={
            'email': joiner.email,
            'password': TEST_PASSWORD
        }, follow_redirects=True)

        # Joiner should be able to view the circle details page before joining
        response = client.get(f'/circles/{circle.id}', follow_redirects=True)
        assert response.status_code == 200
        assert b'Public Circle Test' in response.data
        # Page should show a join button for public circles
        assert b'Join Circle' in response.data

        # For public circles, POST to join should immediately add the member
        response = client.post(f'/circles/join/{circle.id}', follow_redirects=True)
        assert response.status_code == 200

        # Reload circle from DB and confirm membership
        db.session.refresh(circle)
        assert joiner in circle.members
