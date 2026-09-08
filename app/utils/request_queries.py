from app.utils.home_feed import (
    build_visible_requests_query,
    effective_feed_distance,
    filter_requests_by_distance,
    format_actor_distance,
)
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


def describe_seeking_mismatch(item_request, item):
    """Explain how *item* fails to match what *item_request* is seeking.

    Returns a short sentence for display, or ``None`` when the item suits the
    request.  Requests seeking "either" never mismatch.  A mismatch is worth
    surfacing rather than filtering out: someone offering a loan to a giveaway
    request may still be exactly what the requester wants, but both sides
    should know the terms differ before a conversation starts.
    """
    if item_request.seeking == "giveaway" and not item.is_giveaway:
        return "They're asking for a giveaway, but this item is listed for loan."

    if item_request.seeking == "loan" and item.is_giveaway:
        return "They're asking to borrow, but this item is listed as a giveaway."

    return None


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
    """Return one page of the requests the user can see, newest first."""
    scoped_circle_ids = _get_scoped_circle_ids(user, selected_circle_ids)
    visible_requests_query = build_visible_requests_query(
        user,
        scoped_circle_ids=scoped_circle_ids,
        scope=scope,
        max_distance=distance,
        distance_explicit=distance_explicit,
    )
    if visible_requests_query is None:
        return ListPagination(items=[], page=page, per_page=per_page)

    max_distance = effective_feed_distance(distance, distance_explicit)
    if max_distance is None or not user.is_geocoded:
        # Nothing has to be measured in Python, so the database can do the
        # counting and slicing and hand back only the rows for this page.
        pagination = visible_requests_query.paginate(page=page, per_page=per_page, error_out=False)
    else:
        # The exact distance test only runs in Python, so the whole visible set
        # has to come back before it can be paged.  The query has already been
        # narrowed to a bounding box around the user, which is what keeps that
        # set small.
        visible_requests = filter_requests_by_distance(
            visible_requests_query.all(), user, max_distance
        )
        pagination = ListPagination(items=visible_requests, page=page, per_page=per_page)

    for item_request in pagination.items:
        item_request.api_distance = format_actor_distance(user, item_request.user)

    return pagination
