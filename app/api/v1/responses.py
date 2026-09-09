"""Shared JSON response helpers for the API surface."""


def build_pagination_metadata(pagination):
    """Return the standard pagination metadata for a collection response."""
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def build_collection_response(collection_name, items, *, pagination=None):
    """Build a standard collection payload without a top-level success wrapper."""
    payload = {collection_name: items}

    if pagination is not None:
        payload["pagination"] = build_pagination_metadata(pagination)

    return payload
