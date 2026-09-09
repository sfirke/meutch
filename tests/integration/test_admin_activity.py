"""Integration tests for the admin Activity page."""

import re
from datetime import UTC, datetime, timedelta

from app import db
from app.admin.routes import ACTIVITY_PER_PAGE
from app.models import ActivityLog
from app.utils import activity_events
from conftest import login_user
from tests.factories import ActivityLogFactory, UserFactory

ATTEMPT_COUNT_PATTERN = re.compile(r"attempt_count</dt>\s*<dd[^>]*>(\d+)</dd>")


def _rendered_attempt_counts(response):
    """The attempt_count of every row on the page, in the order they are rendered."""
    return [int(match) for match in ATTEMPT_COUNT_PATTERN.findall(response.data.decode("utf-8"))]


class TestActivityPageAccess:
    """Mirrors TestAdminDashboardAccess -- the page is admin-only for the same reasons."""

    def test_requires_login(self, client):
        response = client.get("/admin/activity")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_blocks_non_admin(self, client, db_session):
        user = UserFactory(is_admin=False)
        db_session.commit()

        login_user(client, user.email)

        assert client.get("/admin/activity").status_code == 403

    def test_allows_admin(self, client, db_session):
        admin = UserFactory(is_admin=True)
        db_session.commit()

        login_user(client, admin.email)

        response = client.get("/admin/activity")
        assert response.status_code == 200
        assert b"Activity Log" in response.data


class TestActivityPageRendering:
    def test_renders_an_entry_with_its_label_actor_and_client(self, client, db_session):
        admin = UserFactory(is_admin=True, first_name="Ada", last_name="Admin")
        ActivityLogFactory(actor=admin, subject=admin, ip_address="203.0.113.99")
        db_session.commit()

        login_user(client, admin.email)
        content = client.get("/admin/activity").data.decode("utf-8")

        assert "Signed in" in content
        assert "Ada Admin" in content
        assert "203.0.113.99" in content
        assert "Chrome" in content

    def test_renders_an_anonymous_failed_sign_in_with_the_typed_address(self, client, db_session):
        admin = UserFactory(is_admin=True)
        ActivityLogFactory(
            event_type=activity_events.AUTH_LOGIN_FAILED,
            actor=None,
            subject=None,
            context={"attempted_email": "you@gmial.com", "account_exists": False},
        )
        db_session.commit()

        login_user(client, admin.email)
        content = client.get("/admin/activity").data.decode("utf-8")

        assert "Sign-in failed" in content
        assert "you@gmial.com" in content
        assert "Not signed in" in content

    def test_an_unregistered_event_type_falls_back_to_its_raw_name(self, client, db_session):
        admin = UserFactory(is_admin=True)
        ActivityLogFactory(event_type="some.future.event", actor=admin, subject=admin)
        db_session.commit()

        login_user(client, admin.email)
        content = client.get("/admin/activity").data.decode("utf-8")

        assert "some.future.event" in content

    def test_an_entry_about_a_deleted_account_still_renders(self, client, db_session):
        admin = UserFactory(is_admin=True)
        departed = UserFactory(first_name="Gone", last_name="Away", is_deleted=True)
        ActivityLogFactory(actor=departed, subject=departed)
        db_session.commit()

        login_user(client, admin.email)
        response = client.get("/admin/activity")

        assert response.status_code == 200
        assert b"Gone Away" in response.data

    def test_empty_log_says_so(self, client, db_session, app):
        """Reachable in practice only with the kill switch on, which is exactly when
        an admin most needs the page to say something rather than nothing."""
        admin = UserFactory(is_admin=True)
        db_session.commit()

        app.config["ACTIVITY_LOG_ENABLED"] = False
        try:
            login_user(client, admin.email)
            content = client.get("/admin/activity").data.decode("utf-8")
        finally:
            app.config["ACTIVITY_LOG_ENABLED"] = True

        assert "No activity recorded yet." in content


class TestActivityPagePagination:
    def test_identically_timestamped_rows_paginate_without_loss_or_repetition(
        self, client, db_session
    ):
        """Every row appears on exactly one page, even sharing one timestamp.

        A single sign-in writes several rows in the same millisecond, so this is the
        ordinary case rather than a contrived one. Without the id tiebreak in the
        route's ORDER BY, Postgres is free to hand back one row on both pages and drop
        another entirely, and the log would be quietly incomplete.
        """
        admin = UserFactory(is_admin=True)
        shared_timestamp = datetime.now(UTC) - timedelta(days=1)
        row_count = ACTIVITY_PER_PAGE + 5
        for index in range(row_count):
            ActivityLogFactory(
                actor=admin,
                subject=admin,
                occurred_at=shared_timestamp,
                context={"attempt_count": index},
            )
        db_session.commit()

        login_user(client, admin.email)

        first_page = client.get("/admin/activity")
        second_page = client.get("/admin/activity?page=2")

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert first_page.data.count(b"<tr>") == ACTIVITY_PER_PAGE + 1  # + the header row

        seen = _rendered_attempt_counts(first_page) + _rendered_attempt_counts(second_page)
        assert sorted(seen) == list(range(row_count))

    def test_newest_entries_come_first(self, client, db_session):
        admin = UserFactory(is_admin=True)
        base_time = datetime.now(UTC) - timedelta(days=1)
        for index in range(3):
            ActivityLogFactory(
                actor=admin,
                subject=admin,
                occurred_at=base_time + timedelta(minutes=index),
                context={"attempt_count": index},
            )
        db_session.commit()

        login_user(client, admin.email)

        assert _rendered_attempt_counts(client.get("/admin/activity")) == [2, 1, 0]


class TestPruneOverdueWarning:
    def test_no_warning_when_the_oldest_entry_is_inside_the_window(self, client, db_session, app):
        admin = UserFactory(is_admin=True)
        retention_days = app.config["ACTIVITY_LOG_RETENTION_DAYS"]
        ActivityLogFactory(
            actor=admin,
            subject=admin,
            occurred_at=datetime.now(UTC) - timedelta(days=retention_days - 1),
        )
        db_session.commit()

        login_user(client, admin.email)

        assert b"not being pruned" not in client.get("/admin/activity").data

    def test_warns_when_the_oldest_entry_is_well_past_the_window(self, client, db_session, app):
        """Nothing inside the app can tell whether the prune job was ever scheduled,
        so the page says so where an admin will see it."""
        admin = UserFactory(is_admin=True)
        retention_days = app.config["ACTIVITY_LOG_RETENTION_DAYS"]
        ActivityLogFactory(
            actor=admin,
            subject=admin,
            occurred_at=datetime.now(UTC) - timedelta(days=retention_days + 60),
        )
        db_session.commit()

        login_user(client, admin.email)

        assert b"not being pruned" in client.get("/admin/activity").data


class TestActivityTabBar:
    def test_the_dashboard_links_to_the_activity_page(self, client, db_session):
        admin = UserFactory(is_admin=True)
        db_session.commit()

        login_user(client, admin.email)
        content = client.get("/admin/").data.decode("utf-8")

        assert 'href="/admin/activity"' in content
        # The Users and Analytics tabs stay Bootstrap tab buttons on the dashboard.
        assert 'id="admin-users-tab" data-bs-toggle="tab"' in content
        assert 'id="admin-analytics-tab" data-bs-toggle="tab"' in content

    def test_the_activity_page_links_back_rather_than_toggling_missing_panes(
        self, client, db_session
    ):
        admin = UserFactory(is_admin=True)
        db_session.commit()

        login_user(client, admin.email)
        content = client.get("/admin/activity").data.decode("utf-8")

        assert 'href="/admin/?active_tab=users"' in content
        assert 'href="/admin/?active_tab=analytics"' in content
        assert 'data-bs-toggle="tab"' not in content

    def test_the_dashboard_analytics_pane_still_renders(self, client, db_session):
        admin = UserFactory(is_admin=True)
        db_session.commit()

        login_user(client, admin.email)
        response = client.get("/admin/?active_tab=analytics")

        assert response.status_code == 200
        assert b'id="admin-analytics"' in response.data


def test_entries_written_by_log_event_appear_on_the_page(client, db_session):
    """End to end: a real sign-in shows up in the admin panel with no seeding."""
    from conftest import TEST_PASSWORD

    UserFactory(is_admin=True, email="theadmin@example.com")
    db_session.commit()

    login_user(client, "theadmin@example.com", TEST_PASSWORD)

    content = client.get("/admin/activity").data.decode("utf-8")
    assert "Signed in" in content
    assert db.session.query(ActivityLog).count() >= 1
