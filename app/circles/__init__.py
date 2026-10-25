from flask import Blueprint

bp = Blueprint("circles", __name__)

from app.circles import routes  # noqa: E402, F401
