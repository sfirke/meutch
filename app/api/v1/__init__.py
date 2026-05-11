"""Version 1 API blueprint."""

from flask import Blueprint

bp = Blueprint("api_v1", __name__)

from app.api.v1 import discovery  # noqa: E402, F401
