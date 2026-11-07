from flask import Blueprint

bp = Blueprint("main", __name__)

from app.main.views import (  # noqa: F401, E402
    announcements,
    browse,
    contact,
    giveaways,
    items,
    loans,
    messaging,
    profile,
    public,
)
