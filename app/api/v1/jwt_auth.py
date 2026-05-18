"""JWT manager callbacks for API authentication."""

from uuid import UUID

from flask_jwt_extended import current_user

from app import db
from app.api.v1.errors import build_error_response
from app.models import User
from app.services import api_token_service


def register_jwt_callbacks(jwt):
    """Attach JWT callbacks that follow the shared API error contract."""

    @jwt.user_lookup_loader
    def load_jwt_user(_jwt_header, jwt_data):
        try:
            user_id = UUID(jwt_data["sub"])
        except (KeyError, ValueError):
            return None

        return db.session.get(User, user_id)

    @jwt.user_lookup_error_loader
    def handle_missing_user(_jwt_header, _jwt_data):
        return build_error_response(
            "INVALID_TOKEN",
            "The supplied token is invalid.",
            status_code=401,
        )

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_data):
        return api_token_service.is_token_revoked(jwt_data)

    @jwt.unauthorized_loader
    def handle_missing_token(_reason):
        return build_error_response(
            "AUTHENTICATION_REQUIRED",
            "Authentication is required to access this resource.",
            status_code=401,
        )

    @jwt.invalid_token_loader
    def handle_invalid_token(_reason):
        return build_error_response(
            "INVALID_TOKEN",
            "The supplied token is invalid.",
            status_code=401,
        )

    @jwt.expired_token_loader
    def handle_expired_token(_jwt_header, _jwt_data):
        return build_error_response(
            "TOKEN_EXPIRED",
            "The token has expired.",
            status_code=401,
        )

    @jwt.revoked_token_loader
    def handle_revoked_token(_jwt_header, _jwt_data):
        return build_error_response(
            "TOKEN_REVOKED",
            "The token is no longer valid.",
            status_code=401,
        )

    @jwt.needs_fresh_token_loader
    def handle_stale_token(_jwt_header, _jwt_data):
        return build_error_response(
            "FRESH_TOKEN_REQUIRED",
            "A fresh token is required to access this resource.",
            status_code=401,
        )


__all__ = ["current_user", "register_jwt_callbacks"]
