from flask import Blueprint

from app.main.views import browse, giveaways, items, loans, messaging, profile, public  # noqa: F401

bp = Blueprint("main", __name__)
