from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.services import auth_service
from app.services.exceptions import ConflictError
from conftest import TEST_PASSWORD
from tests.factories import UserFactory


class TestAuthService:
    def test_register_user_with_coordinates_normalizes_email_and_sets_location(self, app):
        with app.app_context():
            with patch("app.services.auth_service.send_confirmation_email", return_value=True):
                result = auth_service.register_user(
                    email="MixedCase@Example.com",
                    first_name="Mixed",
                    last_name="Case",
                    password=TEST_PASSWORD,
                    digest_frequency="weekly",
                    location_method="coordinates",
                    latitude=40.7128,
                    longitude=-74.0060,
                )

            assert result.email_sent is True
            assert result.location_method == "coordinates"
            assert result.geocoding_failed is False
            assert result.user.email == "mixedcase@example.com"
            assert result.user.latitude == 40.7128
            assert result.user.longitude == -74.0060

    def test_register_user_marks_geocoding_failed_when_address_lookup_returns_none(self, app):
        with app.app_context():
            with patch("app.utils.geocoding.geocode_address", return_value=None):
                with patch("app.services.auth_service.send_confirmation_email", return_value=True):
                    result = auth_service.register_user(
                        email="address@example.com",
                        first_name="Address",
                        last_name="Failure",
                        password=TEST_PASSWORD,
                        digest_frequency="weekly",
                        location_method="address",
                        street="123 Nowhere",
                        city="No City",
                        state="NC",
                        zip_code="12345",
                        country="USA",
                    )

            assert result.geocoding_failed is True
            assert result.user.latitude is None
            assert result.user.longitude is None

    def test_authenticate_user_is_case_insensitive_and_updates_last_login(self, app):
        with app.app_context():
            user = UserFactory(email="test@example.com", email_confirmed=True, last_login=None)
            db.session.commit()

            result = auth_service.authenticate_user("TEST@example.com", TEST_PASSWORD)

            db.session.refresh(user)
            assert result.status == auth_service.LOGIN_STATUS_SUCCESS
            assert result.user.id == user.id
            assert user.last_login is not None

    def test_authenticate_user_returns_unconfirmed_without_updating_last_login(self, app):
        with app.app_context():
            user = UserFactory(email_confirmed=False, last_login=None)
            db.session.commit()

            result = auth_service.authenticate_user(user.email, TEST_PASSWORD)

            db.session.refresh(user)
            assert result.status == auth_service.LOGIN_STATUS_UNCONFIRMED
            assert result.user.id == user.id
            assert user.last_login is None

    def test_confirm_email_token_returns_expired_for_stale_token(self, app):
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            token = user.generate_confirmation_token()
            user.email_confirmation_sent_at = datetime.now(UTC) - timedelta(hours=25)
            db.session.commit()

            result = auth_service.confirm_email_token(token)

            db.session.refresh(user)
            assert result.status == auth_service.CONFIRM_EMAIL_STATUS_EXPIRED
            assert user.email_confirmed is False

    def test_check_existing_email_confirmed(self, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()

            result = auth_service.check_existing_email(user.email)

            assert result.exists is True
            assert result.is_confirmed is True

    def test_check_existing_email_unconfirmed(self, app):
        with app.app_context():
            user = UserFactory(email_confirmed=False)
            db.session.commit()

            result = auth_service.check_existing_email(user.email)

            assert result.exists is True
            assert result.is_confirmed is False

    def test_check_existing_email_nonexistent(self, app):
        with app.app_context():
            result = auth_service.check_existing_email("nobody@example.com")

            assert result.exists is False
            assert result.is_confirmed is False

    def test_register_user_catches_integrity_error_confirmed(self, app):
        with app.app_context():
            _user = UserFactory(email="conflict@example.com", email_confirmed=True)
            db.session.commit()

            with (
                patch("app.services.auth_service.send_confirmation_email", return_value=True),
                patch.object(
                    auth_service.db.session,
                    "commit",
                    side_effect=IntegrityError("mock", "orig", "stmt"),
                ),
            ):
                with pytest.raises(ConflictError) as excinfo:
                    auth_service.register_user(
                        email="conflict@example.com",
                        first_name="Conflict",
                        last_name="User",
                        password=TEST_PASSWORD,
                        digest_frequency="weekly",
                        location_method="skip",
                    )

            assert "already registered" in str(excinfo.value).lower()
            assert "forgot password" in str(excinfo.value).lower()

    def test_register_user_catches_integrity_error_unconfirmed(self, app):
        with app.app_context():
            _user = UserFactory(email="unconfirmed@example.com", email_confirmed=False)
            db.session.commit()

            with (
                patch("app.services.auth_service.send_confirmation_email", return_value=True),
                patch.object(
                    auth_service.db.session,
                    "commit",
                    side_effect=IntegrityError("mock", "orig", "stmt"),
                ),
            ):
                with pytest.raises(ConflictError) as excinfo:
                    auth_service.register_user(
                        email="unconfirmed@example.com",
                        first_name="Unconfirmed",
                        last_name="User",
                        password=TEST_PASSWORD,
                        digest_frequency="weekly",
                        location_method="skip",
                    )

            assert (
                "hasn't been confirmed" in str(excinfo.value).lower()
                or "not confirmed" in str(excinfo.value).lower()
            )

    def test_resend_confirmation_email_for_user_returns_already_confirmed(self, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            db.session.commit()

            result = auth_service.resend_confirmation_email_for_user(user.email)

            assert result.status == auth_service.RESEND_CONFIRMATION_STATUS_ALREADY_CONFIRMED
            assert result.user.id == user.id

    def test_request_password_reset_returns_not_found_for_missing_user(self, app):
        with app.app_context():
            result = auth_service.request_password_reset("missing@example.com")

            assert result.status == auth_service.PASSWORD_RESET_REQUEST_STATUS_NOT_FOUND

    def test_reset_password_succeeds_and_clears_token(self, app):
        with app.app_context():
            user = UserFactory()
            token = user.generate_password_reset_token()
            db.session.commit()

            result = auth_service.reset_password(token, "newpassword123")

            db.session.refresh(user)
            assert result.status == auth_service.PASSWORD_RESET_STATUS_SUCCESS
            assert user.password_reset_token is None
            assert user.check_password("newpassword123") is True

    def test_reset_password_returns_expired_for_stale_token(self, app):
        with app.app_context():
            user = UserFactory()
            token = user.generate_password_reset_token()
            user.password_reset_sent_at = datetime.now(UTC) - timedelta(hours=2)
            db.session.commit()

            result = auth_service.reset_password(token, "newpassword123")

            db.session.refresh(user)
            assert result.status == auth_service.PASSWORD_RESET_STATUS_EXPIRED
            assert user.password_reset_token == token
            assert user.check_password(TEST_PASSWORD) is True
