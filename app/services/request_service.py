"""Request workflow service helpers."""

from datetime import UTC, datetime

from app import db
from app.models import ItemRequest
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError

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
