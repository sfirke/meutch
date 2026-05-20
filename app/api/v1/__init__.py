"""Version 1 API blueprint."""

from importlib import import_module

from flask import Blueprint

from app.api.v1.errors import register_blueprint_error_handlers

bp = Blueprint("api_v1", __name__)
register_blueprint_error_handlers(bp)

import_module("app.api.v1.auth")
import_module("app.api.v1.circles")
import_module("app.api.v1.discovery")
import_module("app.api.v1.feed")
import_module("app.api.v1.items")
import_module("app.api.v1.messages")
import_module("app.api.v1.profile")
import_module("app.api.v1.reference")
import_module("app.api.v1.requests")
