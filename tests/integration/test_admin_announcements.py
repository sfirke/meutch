"""Integration tests for the admin Announcements page."""

from datetime import UTC, date, datetime, timedelta

from app.models import Announcement
from conftest import login_user
from tests.factories import AnnouncementDismissalFactory, AnnouncementFactory, UserFactory

PAGE_URL = "/admin/announcements"


def _login_admin(client, db_session):
    admin = UserFactory(is_admin=True)
    db_session.commit()
    login_user(client, admin.email)
    return admin


def _form_data(**overrides):
    data = {"message": "Weighing two designs", "level": "info", "dismissible": "y"}
    data.update(overrides)
    return data


class TestAccess:
    def test_requires_login(self, client):
        response = client.get(PAGE_URL)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_blocks_non_admin(self, client, db_session):
        user = UserFactory(is_admin=False)
        announcement = AnnouncementFactory()
        db_session.commit()
        login_user(client, user.email)

        assert client.get(PAGE_URL).status_code == 403
        assert client.post(PAGE_URL, data=_form_data()).status_code == 403
        assert client.post(f"{PAGE_URL}/{announcement.id}/end").status_code == 403
        assert Announcement.query.count() == 1


class TestCreate:
    def test_creates_announcement(self, client, db_session):
        admin = _login_admin(client, db_session)

        response = client.post(
            PAGE_URL,
            data=_form_data(
                link_url="https://github.com/sfirke/meutch/discussions/1",
                link_text="Chime in",
                level="warning",
            ),
        )

        assert response.status_code == 302
        announcement = Announcement.query.one()
        assert announcement.message == "Weighing two designs"
        assert announcement.link_text == "Chime in"
        assert announcement.level == Announcement.LEVEL_WARNING
        assert announcement.dismissible is True
        assert announcement.created_by_id == admin.id
        assert announcement.ends_at is None
        assert announcement.is_active

    def test_end_date_runs_through_that_day(self, client, db_session):
        _login_admin(client, db_session)
        today = datetime.now(UTC).date()

        client.post(PAGE_URL, data=_form_data(ends_at=today.isoformat()))

        announcement = Announcement.query.one()
        assert announcement.ends_at == datetime.combine(
            today + timedelta(days=1), datetime.min.time()
        )
        assert announcement.is_active

    def test_future_start_is_scheduled(self, client, db_session):
        _login_admin(client, db_session)
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)

        client.post(PAGE_URL, data=_form_data(starts_at=tomorrow.isoformat()))

        assert Announcement.query.one().status == Announcement.STATUS_SCHEDULED

    def test_unchecked_dismissible_is_saved(self, client, db_session):
        _login_admin(client, db_session)
        data = _form_data()
        del data["dismissible"]

        client.post(PAGE_URL, data=data)

        assert Announcement.query.one().dismissible is False

    def test_rejects_http_link(self, client, db_session):
        _login_admin(client, db_session)

        response = client.post(PAGE_URL, data=_form_data(link_url="http://example.com"))

        assert response.status_code == 400
        assert b"Links must start with https://" in response.data
        assert Announcement.query.count() == 0

    def test_rejects_end_before_start(self, client, db_session):
        _login_admin(client, db_session)

        response = client.post(
            PAGE_URL,
            data=_form_data(starts_at=date(2030, 5, 2).isoformat(), ends_at="2030-05-01"),
        )

        assert response.status_code == 400
        assert Announcement.query.count() == 0

    def test_rejects_link_text_without_url(self, client, db_session):
        _login_admin(client, db_session)

        response = client.post(PAGE_URL, data=_form_data(link_text="Chime in"))

        assert response.status_code == 400
        assert b"Link text needs a link URL" in response.data
        assert Announcement.query.count() == 0


class TestListAndEnd:
    def test_end_now_makes_it_inactive(self, client, db_session):
        _login_admin(client, db_session)
        announcement = AnnouncementFactory()
        db_session.commit()

        response = client.post(f"{PAGE_URL}/{announcement.id}/end")

        assert response.status_code == 302
        db_session.refresh(announcement)
        assert announcement.status == Announcement.STATUS_ENDED

    def test_end_now_on_scheduled_announcement(self, client, db_session):
        _login_admin(client, db_session)
        announcement = AnnouncementFactory(
            starts_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3)
        )
        db_session.commit()

        client.post(f"{PAGE_URL}/{announcement.id}/end")

        db_session.refresh(announcement)
        assert announcement.status == Announcement.STATUS_ENDED

    def test_lists_announcements_with_dismissal_counts(self, client, db_session):
        _login_admin(client, db_session)
        dismissed = AnnouncementFactory(message="Dismissed twice")
        AnnouncementDismissalFactory(announcement=dismissed)
        AnnouncementDismissalFactory(announcement=dismissed)
        AnnouncementFactory(message="Never dismissed")
        db_session.commit()

        content = client.get(PAGE_URL).data.decode("utf-8")

        assert "Dismissed twice" in content
        assert "Never dismissed" in content
        assert "data-dismissal-count>2</td>" in content
        assert "data-dismissal-count>0</td>" in content

    def test_lists_latest_start_first(self, client, db_session):
        _login_admin(client, db_session)
        now = datetime.now(UTC).replace(tzinfo=None)
        AnnouncementFactory(message="Started yesterday", starts_at=now - timedelta(days=1))
        AnnouncementFactory(message="Started today", starts_at=now - timedelta(minutes=1))
        db_session.commit()

        content = client.get(PAGE_URL).data.decode("utf-8")

        assert content.index("Started today") < content.index("Started yesterday")
