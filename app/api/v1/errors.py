"""API error handling helpers."""

from dataclasses import dataclass

from flask import current_app
from flask_jwt_extended.exceptions import (
    FreshTokenRequired,
    InvalidHeaderError,
    JWTDecodeError,
    NoAuthorizationError,
    RevokedTokenError,
    UserClaimsVerificationError,
    UserLookupError,
    WrongTokenError,
)
from jwt.exceptions import ExpiredSignatureError
from jwt.exceptions import InvalidTokenError as PyJwtInvalidTokenError
from marshmallow import ValidationError
from werkzeug.exceptions import (
    Forbidden,
    HTTPException,
    MethodNotAllowed,
    NotFound,
    TooManyRequests,
    Unauthorized,
)

from app.services.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
    ServiceError,
)

API_V1_PATH_PREFIX = "/api/v1"


@dataclass(frozen=True)
class ErrorMapping:
    """Stable API error contract for a mapped exception."""

    code: str
    status_code: int
    default_message: str
    default_description: str | None = None


SERVICE_ERROR_MAPPINGS = {
    AuthenticationError: ErrorMapping(
        code="UNAUTHORIZED",
        status_code=401,
        default_message="Authentication is required to perform this action.",
    ),
    AuthorizationError: ErrorMapping(
        code="FORBIDDEN",
        status_code=403,
        default_message="You are not allowed to perform this action.",
    ),
    ConflictError: ErrorMapping(
        code="CONFLICT",
        status_code=409,
        default_message="The requested action conflicts with the current resource state.",
    ),
    InformationalError: ErrorMapping(
        code="BAD_REQUEST",
        status_code=400,
        default_message="The request could not be processed.",
    ),
    InvalidActionError: ErrorMapping(
        code="INVALID_ACTION",
        status_code=400,
        default_message="The requested action is not allowed.",
    ),
}

HTTP_ERROR_MAPPINGS = {
    401: ErrorMapping(
        code="UNAUTHORIZED",
        status_code=401,
        default_message="Authentication is required to access this resource.",
        default_description=Unauthorized.description,
    ),
    403: ErrorMapping(
        code="FORBIDDEN",
        status_code=403,
        default_message="You are not allowed to access this resource.",
        default_description=Forbidden.description,
    ),
    404: ErrorMapping(
        code="NOT_FOUND",
        status_code=404,
        default_message="The requested resource was not found.",
        default_description=NotFound.description,
    ),
    405: ErrorMapping(
        code="METHOD_NOT_ALLOWED",
        status_code=405,
        default_message="This method is not allowed for the requested resource.",
        default_description=MethodNotAllowed.description,
    ),
    429: ErrorMapping(
        code="RATE_LIMIT_EXCEEDED",
        status_code=429,
        default_message="Too many requests. Please try again later.",
        default_description=TooManyRequests.description,
    ),
}


def is_api_request_path(path):
    """Return True when a request path targets the v1 API surface."""
    return path == API_V1_PATH_PREFIX or path.startswith(f"{API_V1_PATH_PREFIX}/")


def build_error_response(code, message, *, status_code, details=None):
    """Return a standardized JSON error response payload."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }, status_code


def build_error_response_with_headers(code, message, *, status_code, details=None, headers=None):
    """Return a standardized JSON error response payload with optional headers."""
    error_response = build_error_response(
        code,
        message,
        status_code=status_code,
        details=details,
    )
    if headers:
        return error_response[0], error_response[1], headers
    return error_response


def _resolve_service_error_mapping(error):
    for error_type, mapping in SERVICE_ERROR_MAPPINGS.items():
        if isinstance(error, error_type):
            return mapping

    return ErrorMapping(
        code="BAD_REQUEST",
        status_code=400,
        default_message="The request could not be processed.",
    )


def build_service_error_response(error):
    """Translate a service exception into the shared API error format."""
    mapping = _resolve_service_error_mapping(error)
    message = str(error) or mapping.default_message
    details = getattr(error, "details", None)
    return build_error_response(
        mapping.code,
        message,
        status_code=mapping.status_code,
        details=details,
    )


def build_http_error_response(error):
    """Translate a routing or HTTP exception into the shared API error format."""
    mapping = HTTP_ERROR_MAPPINGS.get(error.code)

    if mapping is None:
        description = getattr(error, "description", None)
        message = description or "An unexpected error occurred."
        return build_error_response("ERROR", message, status_code=error.code)

    message = mapping.default_message

    if error.code != 429 and error.description and error.description != mapping.default_description:
        message = error.description

    headers = None
    if error.code == 429:
        retry_after = getattr(error, "retry_after", None)
        if retry_after is None and getattr(error, "response", None) is not None:
            retry_after = error.response.headers.get("Retry-After")
        if retry_after is not None:
            headers = {"Retry-After": str(retry_after)}

    return build_error_response_with_headers(
        mapping.code,
        message,
        status_code=mapping.status_code,
        headers=headers,
    )


def build_validation_error_response(error):
    """Translate a Marshmallow ValidationError into the shared API error format."""
    return build_error_response(
        "VALIDATION_ERROR",
        "Input validation failed.",
        status_code=422,
        details=error.messages,
    )


def register_blueprint_error_handlers(blueprint):
    """Attach API-specific error handlers to the versioned blueprint."""

    @blueprint.errorhandler(ServiceError)
    def handle_service_error(error):
        return build_service_error_response(error)

    @blueprint.errorhandler(ValidationError)
    def handle_validation_error(error):
        return build_validation_error_response(error)

    @blueprint.errorhandler(Forbidden)
    def handle_forbidden(error):
        return build_http_error_response(error)

    @blueprint.errorhandler(Unauthorized)
    def handle_unauthorized(error):
        return build_http_error_response(error)

    @blueprint.errorhandler(NotFound)
    def handle_not_found(error):
        return build_http_error_response(error)

    @blueprint.errorhandler(MethodNotAllowed)
    def handle_method_not_allowed(error):
        return build_http_error_response(error)

    @blueprint.errorhandler(TooManyRequests)
    def handle_too_many_requests(error):
        return build_http_error_response(error)

    @blueprint.errorhandler(Exception)
    def handle_unexpected_exception(error):
        if isinstance(error, NoAuthorizationError):
            return build_error_response(
                "AUTHENTICATION_REQUIRED",
                "Authentication is required to access this resource.",
                status_code=401,
            )

        if isinstance(error, RevokedTokenError):
            return build_error_response(
                "TOKEN_REVOKED",
                "The token is no longer valid.",
                status_code=401,
            )

        if isinstance(error, FreshTokenRequired):
            return build_error_response(
                "FRESH_TOKEN_REQUIRED",
                "A fresh token is required to access this resource.",
                status_code=401,
            )

        if isinstance(error, ExpiredSignatureError):
            return build_error_response(
                "TOKEN_EXPIRED",
                "The token has expired.",
                status_code=401,
            )

        if isinstance(
            error,
            (
                InvalidHeaderError,
                JWTDecodeError,
                PyJwtInvalidTokenError,
                UserClaimsVerificationError,
                UserLookupError,
                WrongTokenError,
            ),
        ):
            return build_error_response(
                "INVALID_TOKEN",
                "The supplied token is invalid.",
                status_code=401,
            )

        if isinstance(error, HTTPException):
            return build_http_error_response(error)

        current_app.logger.exception("Unhandled API exception")
        return build_error_response(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )
