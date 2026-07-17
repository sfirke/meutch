"""Version 1 API blueprint."""

from importlib import import_module
from time import perf_counter
from uuid import uuid4

from flask import Blueprint, current_app, g, request

from app.api.v1.errors import build_error_response, register_blueprint_error_handlers
from app.api.v1.operational import is_mutating_request, is_read_only_exempt_request

bp = Blueprint("api_v1", __name__)
register_blueprint_error_handlers(bp)


@bp.before_request
def apply_api_operational_guards():
    """Attach request metadata and enforce API rollout controls."""
    g.api_request_started_at = perf_counter()
    incoming_request_id = request.headers.get("X-Request-ID", "").strip()
    g.api_request_id = incoming_request_id or str(uuid4())

    if not current_app.config["API_V1_ENABLED"] and request.endpoint != "api_v1.api_health":
        return build_error_response(
            "API_DISABLED",
            "The API is temporarily unavailable.",
            status_code=503,
        )

    if (
        not current_app.config["API_V1_WRITE_ENABLED"]
        and is_mutating_request()
        and not is_read_only_exempt_request()
    ):
        return build_error_response(
            "API_READ_ONLY",
            "The API is temporarily in read-only mode.",
            status_code=503,
        )

    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH")
    if max_bytes is not None:
        content_length = request.content_length
        if content_length is not None and content_length > max_bytes:
            return build_error_response(
                "PAYLOAD_TOO_LARGE",
                "The request body exceeds the maximum allowed size.",
                status_code=413,
            )

    return None


@bp.after_request
def log_api_response(response):
    """Emit request-scoped API logs and return stable response headers."""
    request_id = getattr(g, "api_request_id", None)
    if request_id is not None:
        response.headers["X-Request-ID"] = request_id

    response.headers["X-API-Version"] = "v1"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"

    started_at = getattr(g, "api_request_started_at", None)
    duration_ms = None
    if started_at is not None:
        duration_ms = int((perf_counter() - started_at) * 1000)

    current_app.logger.info(
        (
            "api_request method=%s path=%s endpoint=%s status=%s duration_ms=%s "
            "request_id=%s remote_addr=%s"
        ),
        request.method,
        request.path,
        request.endpoint,
        response.status_code,
        duration_ms,
        request_id,
        request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return response


import_module("app.api.v1.auth")
import_module("app.api.v1.circles")
import_module("app.api.v1.discovery")
import_module("app.api.v1.feed")
import_module("app.api.v1.items")
import_module("app.api.v1.loans")
import_module("app.api.v1.messages")
import_module("app.api.v1.profile")
import_module("app.api.v1.reference")
import_module("app.api.v1.requests")
