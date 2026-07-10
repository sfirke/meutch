"""Integration tests for anonymous digest manage links."""

from unittest.mock import patch

from app import db
from app.models import User
from app.utils.digest_tokens import generate_digest_manage_token
from tests.factories import UserFactory


class TestDigestManageRoutes:
    """Integration tests for anonymous digest manage links."""

    def test_digest_manage_valid_token(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()

            token = generate_digest_manage_token(user)
            response = client.get(f"/digest/manage/{token}")

            assert response.status_code == 200
            assert b"Manage Digest Emails" in response.data
            assert b"One-click unsubscribe" in response.data
            assert b"Switch to daily" in response.data
            assert b"Switch to weekly" not in response.data  # Already on weekly

    def test_digest_manage_shows_only_alternative_frequency(self, client, app):
        """Test that only the alternative frequency button is shown."""
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()

            token = generate_digest_manage_token(user)
            response = client.get(f"/digest/manage/{token}")

            assert response.status_code == 200
            assert b"Switch to weekly" in response.data
            assert b"Switch to daily" not in response.data  # Already on daily

    def test_digest_manage_invalid_token(self, client):
        response = client.get("/digest/manage/not-a-valid-token")
        assert response.status_code == 400
        assert b"invalid" in response.data.lower()

    def test_digest_manage_expired_token(self, client):
        with patch(
            "app.main.views.profile.verify_digest_manage_token", return_value=(None, "expired")
        ):
            response = client.get("/digest/manage/expired-token")

        assert response.status_code == 410
        assert b"expired" in response.data.lower()

    def test_digest_unsubscribe_sets_frequency_none(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/unsubscribe/{token}")
            assert response.status_code == 200
            assert b"unsubscribed" in response.data.lower()

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_NONE

    def test_digest_set_frequency_updates_to_daily(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/daily")
            assert response.status_code == 200
            assert b"Digest frequency updated to" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_DAILY

    def test_digest_set_frequency_updates_to_weekly(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="daily")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/weekly")
            assert response.status_code == 200
            assert b"Digest frequency updated to" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_WEEKLY

    def test_digest_set_frequency_rejects_invalid_frequency(self, client, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly")
            db.session.commit()
            token = generate_digest_manage_token(user)

            response = client.get(f"/digest/frequency/{token}/none")
            assert response.status_code == 400
            assert b"Invalid digest frequency option" in response.data

            updated_user = db.session.get(User, user.id)
            assert updated_user.digest_frequency == User.DIGEST_FREQUENCY_WEEKLY
