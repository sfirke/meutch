"""Authentication endpoints for the versioned API surface."""

from flask import request
from flask_jwt_extended import get_jwt, jwt_required

from app.api.v1 import bp
from app.api.v1.errors import build_error_response
from app.api.v1.jwt_auth import current_user
from app.api.v1.schemas.auth import (
    CurrentUserResponseSchema,
    EmailRequestSchema,
    LoginRequestSchema,
    MessageResponseSchema,
    RegisterRequestSchema,
    RegistrationResponseSchema,
    ResetPasswordRequestSchema,
    TokenBundleSchema,
)
from app.services import api_token_service, auth_service

LOGIN_REQUEST_SCHEMA = LoginRequestSchema()
REGISTER_REQUEST_SCHEMA = RegisterRequestSchema()
EMAIL_REQUEST_SCHEMA = EmailRequestSchema()
RESET_PASSWORD_REQUEST_SCHEMA = ResetPasswordRequestSchema()

TOKEN_BUNDLE_SCHEMA = TokenBundleSchema()
MESSAGE_RESPONSE_SCHEMA = MessageResponseSchema()
CURRENT_USER_RESPONSE_SCHEMA = CurrentUserResponseSchema()
REGISTRATION_RESPONSE_SCHEMA = RegistrationResponseSchema()


def _load_request_data(schema):
    return schema.load(request.get_json(silent=True) or {})


@bp.post("/auth/login")
def login():
    """Authenticate credentials and return an access/refresh token pair."""
    data = _load_request_data(LOGIN_REQUEST_SCHEMA)
    token_bundle = api_token_service.issue_login_tokens(data["email"], data["password"])
    return TOKEN_BUNDLE_SCHEMA.dump(token_bundle)


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    """Rotate a refresh token and return a new token pair."""
    token_bundle = api_token_service.rotate_refresh_token(current_user, get_jwt())
    return TOKEN_BUNDLE_SCHEMA.dump(token_bundle)


@bp.post("/auth/logout")
@jwt_required(verify_type=False)
def logout():
    """Revoke the current JWT session."""
    api_token_service.revoke_token_family(get_jwt())
    return MESSAGE_RESPONSE_SCHEMA.dump({"message": "You have been logged out."})


@bp.get("/auth/me")
@jwt_required()
def me():
    """Return the identity of the authenticated API user."""
    return CURRENT_USER_RESPONSE_SCHEMA.dump({"user": current_user})


@bp.post("/auth/register")
def register():
    """Create a new account while preserving the existing email-confirmation flow."""
    registration_data = _load_request_data(REGISTER_REQUEST_SCHEMA)
    registration_result = api_token_service.register_api_user(**registration_data)
    return (
        REGISTRATION_RESPONSE_SCHEMA.dump(
            {
                "user": registration_result.user,
                "email_confirmation_sent": registration_result.email_sent,
                "location_method": registration_result.location_method,
                "geocoding_failed": registration_result.geocoding_failed,
            }
        ),
        201,
    )


@bp.post("/auth/resend-confirmation")
def resend_confirmation():
    """Re-trigger the existing confirmation-email workflow."""
    data = _load_request_data(EMAIL_REQUEST_SCHEMA)
    resend_result = auth_service.resend_confirmation_email_for_user(data["email"])

    if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_SEND_FAILED:
        return build_error_response(
            "EMAIL_SEND_FAILED",
            "Unable to send a confirmation email right now.",
            status_code=503,
        )

    return MESSAGE_RESPONSE_SCHEMA.dump(
        {
            "message": (
                "If the account exists and still needs confirmation, a new confirmation email "
                "has been sent."
            )
        }
    )


@bp.post("/auth/forgot-password")
def forgot_password():
    """Start the existing password-reset email workflow."""
    data = _load_request_data(EMAIL_REQUEST_SCHEMA)
    reset_request = auth_service.request_password_reset(data["email"])

    if reset_request.status == auth_service.PASSWORD_RESET_REQUEST_STATUS_SEND_FAILED:
        return build_error_response(
            "EMAIL_SEND_FAILED",
            "Unable to send password reset instructions right now.",
            status_code=503,
        )

    return MESSAGE_RESPONSE_SCHEMA.dump(
        {
            "message": (
                "If an account with that email exists, password reset instructions have been "
                "sent."
            )
        }
    )


@bp.post("/auth/reset-password")
def reset_password():
    """Reset a password using the existing web-token flow."""
    data = _load_request_data(RESET_PASSWORD_REQUEST_SCHEMA)
    token_status = auth_service.get_password_reset_token_status(data["token"])

    if token_status.status == auth_service.PASSWORD_RESET_TOKEN_STATUS_INVALID:
        return build_error_response(
            "INVALID_RESET_TOKEN",
            "Invalid or expired reset token.",
            status_code=400,
        )

    if token_status.status == auth_service.PASSWORD_RESET_TOKEN_STATUS_EXPIRED:
        return build_error_response(
            "EXPIRED_RESET_TOKEN",
            "Reset token has expired.",
            status_code=400,
        )

    reset_result = auth_service.reset_password(data["token"], data["password"])
    if reset_result.status == auth_service.PASSWORD_RESET_STATUS_SUCCESS:
        return MESSAGE_RESPONSE_SCHEMA.dump(
            {"message": "Your password has been reset successfully."}
        )

    return build_error_response(
        "INVALID_RESET_TOKEN",
        "Invalid or expired reset token.",
        status_code=400,
    )
