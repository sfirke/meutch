from flask import Blueprint

bp = Blueprint('requests', __name__)

from app.requests import routes
