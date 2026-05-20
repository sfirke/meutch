from app.models import ItemRequest
from app.utils.home_feed import build_visible_requests_events
from app.utils.pagination import ListPagination


def _get_scoped_circle_ids(user, selected_circle_ids=None):
    user_circle_ids = {circle.id for circle in user.circles}
    if not selected_circle_ids:
        return user_circle_ids

    selected_set = {str(circle_id) for circle_id in selected_circle_ids if circle_id}
    return {circle_id for circle_id in user_circle_ids if str(circle_id) in selected_set}


def can_view_request(item_request, viewer_user):
    if not item_request or item_request.status == "deleted":
        return False
    if viewer_user.id == item_request.user_id:
        return True
    if item_request.visibility == "public":
        return True
    return viewer_user.shares_circle_with(item_request.user)


def build_visible_requests_pagination(
    user,
    *,
    selected_circle_ids=None,
    scope="all",
    distance=None,
    distance_explicit=False,
    page=1,
    per_page=12,
):
    scoped_circle_ids = _get_scoped_circle_ids(user, selected_circle_ids)
    visible_request_events = build_visible_requests_events(
        user,
        scoped_circle_ids=scoped_circle_ids,
        scope=scope,
        max_distance=distance,
        distance_explicit=distance_explicit,
    )
    request_ids = [event["request_id"] for event in visible_request_events]
    if not request_ids:
        return ListPagination(items=[], page=page, per_page=per_page)

    visible_requests_by_id = {
        item_request.id: item_request
        for item_request in ItemRequest.query.filter(ItemRequest.id.in_(request_ids)).all()
    }
    distance_by_id = {event["request_id"]: event["distance"] for event in visible_request_events}

    ordered_requests = []
    for request_id in request_ids:
        item_request = visible_requests_by_id.get(request_id)
        if item_request is None:
            continue
        item_request.api_distance = distance_by_id[request_id]
        ordered_requests.append(item_request)

    return ListPagination(items=ordered_requests, page=page, per_page=per_page)
