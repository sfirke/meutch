"""Version 1 API blueprint."""

from flask import Blueprint

from app.api.v1.errors import register_blueprint_error_handlers

bp = Blueprint("api_v1", __name__)
register_blueprint_error_handlers(bp)

from app.api.v1 import discovery  # noqa: E402, F401
