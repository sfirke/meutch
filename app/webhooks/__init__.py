from flask import Blueprint

bp = Blueprint("webhooks", __name__)

from app.webhooks import mailgun  # noqa: E402, F401
