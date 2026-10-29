"""Integration tests for the announcement banner and dismissing it."""

import re
import uuid

from app import db
from app.models import AnnouncementDismissal
from conftest import login_user
from tests.factories import AnnouncementFactory, UserFactory

ABOUT_URL = "/about"


def _dismiss_url(announcement_id):
    return f"/announcements/{announcement_id}/dismiss"


def _csrf_token(html):
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)


def _dismissal_count(announcement):
    return AnnouncementDismissal.query.filter_by(announcement_id=announcement.id).count()


class TestBanner:
    def test_logged_in_user_sees_banner_with_link(self, client, db_session):
        user = UserFactory()
        AnnouncementFactory(
            message="Weighing two designs",
            link_url="https://github.com/sfirke/meutch/discussions/1",
            link_text="Chime in",
        )
        db_session.commit()

        login_user(client, user.email)
        content = client.get(ABOUT_URL).data.decode("utf-8")

        assert "Weighing two designs" in content
        assert 'href="https://github.com/sfirke/meutch/discussions/1"' in content
        assert "Chime in" in content

    def test_anonymous_visitor_sees_no_banner(self, client, db_session):
        AnnouncementFactory(message="Weighing two designs")
        db_session.commit()

        assert b"Weighing two designs" not in client.get(ABOUT_URL).data

    def test_message_is_escaped(self, client, db_session):
        user = UserFactory()
        AnnouncementFactory(message="<script>alert(1)</script>")
        db_session.commit()

        login_user(client, user.email)
        content = client.get(ABOUT_URL).data.decode("utf-8")

        assert "<script>alert(1)</script>" not in content
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


class TestDismiss:
    def test_form_post_redirects_back_and_hides_banner(self, client, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory(message="Weighing two designs")
        db_session.commit()
        login_user(client, user.email)

        response = client.post(
            _dismiss_url(announcement.id), headers={"Referer": f"http://localhost:5000{ABOUT_URL}"}
        )

        assert response.status_code == 302
        assert response.location == ABOUT_URL
        assert b"Weighing two designs" not in client.get(ABOUT_URL).data

    def test_off_site_referrer_falls_back_to_index(self, client, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory()
        db_session.commit()
        login_user(client, user.email)

        response = client.post(
            _dismiss_url(announcement.id), headers={"Referer": "https://evil.example/phish"}
        )

        assert response.status_code == 302
        assert response.location == "/"

    def test_fetch_request_gets_json(self, client, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory()
        db_session.commit()
        login_user(client, user.email)

        response = client.post(
            _dismiss_url(announcement.id), headers={"X-Requested-With": "XMLHttpRequest"}
        )

        assert response.status_code == 200
        assert response.get_json() == {"dismissed": True}
        assert _dismissal_count(announcement) == 1

    def test_dismissing_twice_is_fine(self, client, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory()
        db_session.commit()
        login_user(client, user.email)

        headers = {"X-Requested-With": "XMLHttpRequest"}
        assert client.post(_dismiss_url(announcement.id), headers=headers).status_code == 200
        assert client.post(_dismiss_url(announcement.id), headers=headers).status_code == 200
        assert _dismissal_count(announcement) == 1

    def test_non_dismissible_returns_400(self, client, db_session):
        user = UserFactory()
        announcement = AnnouncementFactory(dismissible=False)
        db_session.commit()
        login_user(client, user.email)

        assert client.post(_dismiss_url(announcement.id)).status_code == 400
        assert _dismissal_count(announcement) == 0

    def test_nonexistent_returns_404(self, client, db_session):
        user = UserFactory()
        db_session.commit()
        login_user(client, user.email)

        assert client.post(_dismiss_url(uuid.uuid4())).status_code == 404

    def test_requires_login(self, client, db_session):
        announcement = AnnouncementFactory()
        db_session.commit()

        response = client.post(_dismiss_url(announcement.id))

        assert response.status_code == 302
        assert "/login" in response.location
        assert _dismissal_count(announcement) == 0

    def test_rejects_missing_csrf_token(self, csrf_app):
        user = UserFactory()
        announcement = AnnouncementFactory()
        db.session.commit()

        client = csrf_app.test_client(user=user)
        token = _csrf_token(client.get(ABOUT_URL).data.decode("utf-8"))
        referer = {"Referer": f"https://localhost:5000{ABOUT_URL}"}

        client.post(_dismiss_url(announcement.id), headers=referer)
        assert _dismissal_count(announcement) == 0

        client.post(_dismiss_url(announcement.id), data={"csrf_token": token}, headers=referer)
        assert _dismissal_count(announcement) == 1
