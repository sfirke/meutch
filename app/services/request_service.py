"""Request workflow service helpers."""

from datetime import UTC, datetime, timedelta

from app import db
from app.models import ItemRequest
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError

FULFILLED_REQUEST_WINDOW_DAYS = 90

PUBLIC_REQUEST_LOCATION_MESSAGE = (
    "You must set your location before making a request public. "
    "Public requests are visible to everyone on Meutch and users will have no idea where you "
    "are located. Please update your location in your profile settings."
)


def _normalize_description(description):
    cleaned_description = description.strip() if description else ""
    return cleaned_description or None


def _normalize_expires_at(expires_on):
    return datetime.combine(expires_on, datetime.min.time())


def _ensure_request_owner(item_request, acting_user):
    if item_request.user_id != acting_user.id:
        raise AuthorizationError("You are not allowed to modify this request.")


def _ensure_public_request_owner_is_geocoded(owner, visibility):
    if visibility == "public" and not owner.is_geocoded:
        raise InformationalError(PUBLIC_REQUEST_LOCATION_MESSAGE)


def create_request(owner, title, description, expires_on, seeking, visibility):
    _ensure_public_request_owner_is_geocoded(owner, visibility)

    item_request = ItemRequest(
        user_id=owner.id,
        title=title.strip(),
        description=_normalize_description(description),
        expires_at=_normalize_expires_at(expires_on),
        seeking=seeking,
        visibility=visibility,
    )
    db.session.add(item_request)
    db.session.commit()
    return item_request


def update_request(item_request, acting_user, title, description, expires_on, seeking, visibility):
    _ensure_request_owner(item_request, acting_user)
    _ensure_public_request_owner_is_geocoded(acting_user, visibility)
    if item_request.status == "deleted":
        raise ConflictError("This request has already been removed.")
    if item_request.status == "fulfilled":
        raise ConflictError("Fulfilled requests cannot be edited.")

    item_request.title = title.strip()
    item_request.description = _normalize_description(description)
    item_request.expires_at = _normalize_expires_at(expires_on)
    item_request.seeking = seeking
    item_request.visibility = visibility
    db.session.commit()
    return item_request


def delete_request(item_request, acting_user):
    _ensure_request_owner(item_request, acting_user)
    if item_request.status == "deleted":
        raise ConflictError("This request has already been removed.")

    item_request.status = "deleted"
    db.session.commit()
    return item_request


def fulfill_request(item_request, acting_user, fulfilled_at=None):
    _ensure_request_owner(item_request, acting_user)
    if item_request.status == "deleted":
        raise ConflictError("This request has already been removed.")
    if item_request.status == "fulfilled":
        raise ConflictError("This request has already been fulfilled.")

    item_request.status = "fulfilled"
    item_request.fulfilled_at = fulfilled_at or datetime.now(UTC)
    db.session.commit()
    return item_request


def list_user_requests(user, status="active", page=1, per_page=12):
    """Return a paginated list of requests posted by *user*.

    Args:
        user: The requester whose requests should be listed.
        status: ``"active"`` (open and unexpired, newest first) or
            ``"fulfilled"`` (fulfilled within the last 90 days, ordered by
            ``fulfilled_at``).
        page: 1-based page number (default 1).
        per_page: Requests per page (default 12).

    Returns:
        A Flask-SQLAlchemy Pagination object.

    Raises:
        ValueError: If *status* is not ``"active"`` or ``"fulfilled"``.
    """
    now = datetime.now(UTC)
    query = ItemRequest.query.filter(ItemRequest.user_id == user.id)
    if status == "active":
        query = query.filter(
            ItemRequest.status == "open",
            ItemRequest.not_expired_clause(),
        ).order_by(ItemRequest.created_at.desc())
    elif status == "fulfilled":
        query = query.filter(
            ItemRequest.status == "fulfilled",
            ItemRequest.fulfilled_at >= now - timedelta(days=FULFILLED_REQUEST_WINDOW_DAYS),
        ).order_by(ItemRequest.fulfilled_at.desc())
    else:
        raise ValueError(f"Unknown request status: {status}")
    return query.paginate(page=page, per_page=per_page, error_out=False)
