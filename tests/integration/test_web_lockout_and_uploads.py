"""Integration tests for lockout and upload behavior on the web (non-API) surface."""

import io

from app import db
from app.services import auth_service
from conftest import TEST_PASSWORD, login_user
from tests.factories import CategoryFactory


class TestWebLoginLockout:
    def test_locked_account_sees_a_lockout_message_not_bad_credentials(
        self, client, app, auth_user
    ):
        """A locked-out account should be told why, rather than "invalid password"."""
        with app.app_context():
            user = auth_user()
            email = user.email

            for _ in range(auth_service.MAX_FAILED_LOGIN_ATTEMPTS):
                client.post("/login", data={"email": email, "password": "wrongpassword"})

            response = client.post("/login", data={"email": email, "password": TEST_PASSWORD})

            assert response.status_code == 200
            assert b"temporarily locked" in response.data
            assert b"Invalid email or password" not in response.data

    def test_login_form_does_not_reject_a_short_legacy_password(self, client, app, auth_user):
        """Accounts predating the 8-character minimum must still be able to log in."""
        short_password = "old123"
        assert len(short_password) < auth_service.PASSWORD_MIN_LENGTH

        with app.app_context():
            user = auth_user()
            user.set_password(short_password)
            db.session.commit()

            response = client.post(
                "/login",
                data={"email": user.email, "password": short_password},
            )

            assert response.status_code == 302


class TestWebUploadSize:
    def test_photo_sized_upload_is_accepted(self, client, app, auth_user):
        """A multi-megabyte photo is an ordinary upload and must not be refused.

        Regression test: a global 1 MB MAX_CONTENT_LENGTH turned every phone photo
        into a 413, even though the documented per-file limit is 100 MB.
        """
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            payload = b"x" * (2 * 1024 * 1024)
            response = client.post(
                "/list-item",
                data={
                    "name": "Big Photo Item",
                    "description": "Test Description",
                    "category": str(category.id),
                    "image": (io.BytesIO(payload), "test.jpg"),
                },
                content_type="multipart/form-data",
            )

            assert response.status_code != 413
