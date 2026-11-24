"""Integration tests for the API announcement endpoints."""

import uuid

from app import db
from app.models import AnnouncementDismissal
from tests.factories import AnnouncementFactory, UserFactory

from .api_test_helpers import auth_headers, login_api_user

CURRENT_URL = "/api/v1/announcements/current"


def _dismiss_url(announcement_id):
    return f"/api/v1/announcements/{announcement_id}/dismiss"


def _dismissal_count(announcement_id):
    return AnnouncementDismissal.query.filter_by(announcement_id=announcement_id).count()


def _token(client, db_session):
    user = UserFactory(email_confirmed=True)
    db_session.commit()
    return login_api_user(client, user.email)


class TestCurrentAnnouncement:
    def test_returns_active_announcement(self, client, db_session):
        announcement = AnnouncementFactory(
            message="Site maintenance Sunday",
            link_url="https://example.com/notes",
            link_text="Details",
            level="warning",
        )
        token = _token(client, db_session)

        response = client.get(CURRENT_URL, headers=auth_headers(token))

        assert response.status_code == 200
        assert response.get_json() == {
            "announcement": {
                "id": str(announcement.id),
                "message": "Site maintenance Sunday",
                "link_url": "https://example.com/notes",
                "link_text": "Details",
                "level": "warning",
                "dismissible": True,
            }
        }

    def test_returns_null_when_none_active(self, client, db_session):
        token = _token(client, db_session)

        response = client.get(CURRENT_URL, headers=auth_headers(token))

        assert response.status_code == 200
        assert response.get_json() == {"announcement": None}

    def test_requires_auth(self, client, db_session):
        assert client.get(CURRENT_URL).status_code == 401


class TestDismissAnnouncement:
    def test_dismiss_hides_it_from_current(self, client, db_session):
        announcement = AnnouncementFactory()
        token = _token(client, db_session)

        response = client.post(_dismiss_url(announcement.id), headers=auth_headers(token))

        assert response.status_code == 200
        assert response.get_json() == {"dismissed": True}
        current = client.get(CURRENT_URL, headers=auth_headers(token)).get_json()
        assert current == {"announcement": None}

    def test_dismissing_twice_is_fine(self, client, db_session):
        announcement = AnnouncementFactory()
        token = _token(client, db_session)

        for _ in range(2):
            response = client.post(_dismiss_url(announcement.id), headers=auth_headers(token))
            assert response.status_code == 200
        assert _dismissal_count(announcement.id) == 1

    def test_non_dismissible_is_rejected(self, client, db_session):
        announcement = AnnouncementFactory(dismissible=False)
        token = _token(client, db_session)

        response = client.post(_dismiss_url(announcement.id), headers=auth_headers(token))

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_ACTION"
        assert _dismissal_count(announcement.id) == 0

    def test_nonexistent_returns_404(self, client, db_session):
        token = _token(client, db_session)

        response = client.post(_dismiss_url(uuid.uuid4()), headers=auth_headers(token))

        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "NOT_FOUND"

    def test_requires_auth(self, client, db_session):
        announcement = AnnouncementFactory()
        db.session.commit()

        assert client.post(_dismiss_url(announcement.id)).status_code == 401
