"""API discovery and system endpoints."""

from flask import current_app

from app.api.v1 import bp
from app.api.v1.operational import api_rollout_status


@bp.get("/", strict_slashes=False)
def api_index():
    """Return API discovery metadata for the current version."""
    return {
        "name": "meutch",
        "version": "v1",
        "status": api_rollout_status(),
        "links": {
            "self": "/api/v1/",
            "health": "/api/v1/health",
        },
    }


@bp.get("/health")
def api_health():
    """Return a lightweight health signal for the API surface."""
    return {
        "status": api_rollout_status(),
        "version": "v1",
        "api_enabled": current_app.config["API_V1_ENABLED"],
        "write_enabled": current_app.config["API_V1_WRITE_ENABLED"],
    }
