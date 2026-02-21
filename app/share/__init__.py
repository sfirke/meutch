from flask import Blueprint

bp = Blueprint('share', __name__)

from app.share import routes  # noqa: E402, F401
