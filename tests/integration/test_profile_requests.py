"""Integration tests for My Requests section on the profile page."""
import uuid
import pytest
from datetime import datetime, UTC, timedelta
from app import db
from app.models import ItemRequest
from tests.factories import UserFactory, ItemRequestFactory
from conftest import login_user


class TestProfileMyRequests:
    """Test that the profile My Activity tab shows the user's own requests."""

    def test_profile_shows_own_active_request(self, client, app, auth_user):
        """Active (open, not expired) request appears in the My Activity tab."""
        with app.app_context():
            user = auth_user()
            title = f'My active request {uuid.uuid4().hex[:8]}'
            ItemRequestFactory(
                user=user,
                title=title,
                status='open',
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=my-activity')

            assert response.status_code == 200
            assert title.encode() in response.data

    def test_profile_shows_own_recently_fulfilled_request(self, client, app, auth_user):
        """Fulfilled request within 90 days appears under Recently Fulfilled."""
        with app.app_context():
            user = auth_user()
            title = f'My fulfilled request {uuid.uuid4().hex[:8]}'
            ItemRequestFactory(
                user=user,
                title=title,
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=30),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=my-activity')

            assert response.status_code == 200
            assert title.encode() in response.data

    def test_profile_hides_own_fulfilled_request_older_than_90_days(self, client, app, auth_user):
        """Fulfilled request older than 90 days is NOT shown on the profile."""
        with app.app_context():
            user = auth_user()
            title = f'Old fulfilled request {uuid.uuid4().hex[:8]}'
            ItemRequestFactory(
                user=user,
                title=title,
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=91),
                expires_at=datetime.now(UTC) - timedelta(days=60),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=my-activity')

            assert response.status_code == 200
            assert title.encode() not in response.data

    def test_profile_hides_own_expired_open_request(self, client, app, auth_user):
        """Expired open request (expires_at in the past) is NOT shown as active."""
        with app.app_context():
            user = auth_user()
            title = f'Expired open request {uuid.uuid4().hex[:8]}'
            ItemRequestFactory(
                user=user,
                title=title,
                status='open',
                expires_at=datetime.now(UTC) - timedelta(days=10),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=my-activity')

            assert response.status_code == 200
            assert title.encode() not in response.data

    def test_profile_does_not_show_other_users_requests(self, client, app, auth_user):
        """Another user's open request does NOT appear on the current user's profile."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            title = f'Other user request {uuid.uuid4().hex[:8]}'
            ItemRequestFactory(
                user=other_user,
                title=title,
                status='open',
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=my-activity')

            assert response.status_code == 200
            assert title.encode() not in response.data
