"""Operational controls for the versioned API surface."""

from functools import wraps

from flask import current_app, request
from flask_jwt_extended import current_user
from flask_limiter.util import get_remote_address

from app import limiter

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
READ_ONLY_EXEMPT_PATH_PREFIXES = ("/api/v1/auth/",)


def api_rollout_status():
    """Return the externally visible rollout status for API v1."""
    if not current_app.config["API_V1_ENABLED"]:
        return "disabled"
    if not current_app.config["API_V1_WRITE_ENABLED"]:
        return "read_only"
    return "ok"


def is_mutating_request():
    """Return True when the current request mutates API state."""
    return request.method not in SAFE_METHODS


def is_read_only_exempt_request():
    """Allow auth/session actions to remain available during read-only rollouts."""
    return any(request.path.startswith(prefix) for prefix in READ_ONLY_EXEMPT_PATH_PREFIXES)


def _limit_from_config(config_key):
    return lambda: current_app.config[config_key]


def _conditional_limit(config_key, key_func):
    def decorator(view_func):
        limited_view_func = limiter.limit(_limit_from_config(config_key), key_func=key_func)(
            view_func
        )

        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_app.config["API_V1_RATE_LIMITS_ENABLED"]:
                return view_func(*args, **kwargs)
            return limited_view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def remote_address_rate_limit_key():
    """Bucket unauthenticated limits by client address."""
    return get_remote_address() or "unknown"


def jwt_user_or_ip_rate_limit_key():
    """Bucket authenticated limits by user id, falling back to client address."""
    try:
        user_id = getattr(current_user, "id", None)
    except Exception:  # pragma: no cover - defensive proxy fallback only
        user_id = None

    if user_id is not None:
        return f"user:{user_id}"

    return f"ip:{remote_address_rate_limit_key()}"


def auth_limit(config_key):
    """Apply an IP-scoped rate limit sourced from app config."""
    return _conditional_limit(config_key, remote_address_rate_limit_key)


def session_limit(config_key="API_V1_AUTH_SESSION_RATE_LIMIT"):
    """Apply a session-scoped rate limit sourced from app config."""
    return _conditional_limit(config_key, jwt_user_or_ip_rate_limit_key)


def mutation_limit(config_key="API_V1_WRITE_RATE_LIMIT"):
    """Apply an authenticated mutation rate limit sourced from app config."""
    return _conditional_limit(config_key, jwt_user_or_ip_rate_limit_key)


def read_limit(config_key="API_V1_READ_RATE_LIMIT"):
    """Apply a per-user read rate limit sourced from app config."""
    return _conditional_limit(config_key, jwt_user_or_ip_rate_limit_key)
