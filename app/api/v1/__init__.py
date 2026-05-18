"""Version 1 API blueprint."""

from importlib import import_module

from flask import Blueprint

from app.api.v1.errors import register_blueprint_error_handlers

bp = Blueprint("api_v1", __name__)
register_blueprint_error_handlers(bp)

import_module("app.api.v1.auth")
import_module("app.api.v1.discovery")
