"""Feed activity endpoints for API v1."""

from flask import request
from flask_jwt_extended import jwt_required

from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.feed import FeedEventSchema
from app.api.v1.schemas.query import FeedQuerySchema
from app.utils.home_feed import build_homepage_feed_events
from app.utils.pagination import ListPagination

FEED_QUERY_SCHEMA = FeedQuerySchema()
FEED_EVENT_SCHEMA = FeedEventSchema(many=True)
DEFAULT_GEOLOCATED_FEED_DISTANCE = 20


@bp.get("/feed")
@jwt_required()
def list_feed_events():
    """Return paginated feed events for the authenticated user."""
    query_data = load_query_data(FEED_QUERY_SCHEMA)
    distance_explicit = "distance" in request.args
    selected_distance = query_data["distance"]
    if not distance_explicit and current_user.is_geocoded:
        selected_distance = DEFAULT_GEOLOCATED_FEED_DISTANCE

    events = build_homepage_feed_events(
        current_user,
        selected_circle_ids=query_data["circles"],
        scope=query_data["scope"],
        giveaway_distance=selected_distance,
        giveaway_distance_explicit=distance_explicit,
        included_event_types=query_data["types"],
        include_own_activity=query_data["show_own_activity"],
        max_events=None,
    )
    pagination = ListPagination(
        items=events,
        page=query_data["page"],
        per_page=query_data["per_page"],
    )

    return build_collection_response(
        "events",
        FEED_EVENT_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )
