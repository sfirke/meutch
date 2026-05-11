"""API discovery and system endpoints."""

from app.api.v1 import bp


@bp.get("/", strict_slashes=False)
def api_index():
    """Return API discovery metadata for the current version."""
    return {
        "name": "meutch",
        "version": "v1",
        "status": "ok",
        "links": {
            "self": "/api/v1/",
            "health": "/api/v1/health",
        },
    }


@bp.get("/health")
def api_health():
    """Return a lightweight health signal for the API surface."""
    return {
        "status": "ok",
        "version": "v1",
    }
