import logging
from datetime import UTC, datetime

from app import db
from app.models import Circle, CircleJoinRequest, Message, circle_members
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.email import (
    send_circle_join_request_decision_email,
    send_circle_join_request_notification_email,
)
from app.utils.geocoding import GeocodingError, build_address_string, geocode_address
from app.utils.storage import delete_file, is_valid_file_upload, upload_circle_image

logger = logging.getLogger(__name__)


def _count_circle_admins(circle_id):
    return db.session.query(circle_members).filter_by(circle_id=circle_id, is_admin=True).count()


def _clean_circle_description(description):
    return description.strip() if description else ""


def _find_circle_by_name(name, *, exclude_circle_id=None):
    query = Circle.query.filter(db.func.lower(Circle.name) == db.func.lower(name))
    if exclude_circle_id is not None:
        query = query.filter(Circle.id != exclude_circle_id)
    return query.first()


def _apply_circle_location(
    circle,
    *,
    location_method,
    latitude=None,
    longitude=None,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
):
    geocoding_failed = False

    if location_method == "coordinates":
        circle.latitude = latitude
        circle.longitude = longitude
        logger.info(
            "Circle %s provided coordinates directly: (%s, %s)",
            circle.name,
            circle.latitude,
            circle.longitude,
        )
        return geocoding_failed

    if location_method != "address":
        return geocoding_failed

    address = build_address_string(street, city, state, zip_code, country)

    try:
        coordinates = geocode_address(
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
        )
        if coordinates:
            circle.latitude, circle.longitude = coordinates
            logger.info("Successfully geocoded address for circle %s", circle.name)
        else:
            geocoding_failed = True
            logger.warning("Failed to geocode address for circle %s: %s", circle.name, address)
    except GeocodingError as exc:
        geocoding_failed = True
        logger.error("Geocoding error for circle %s: %s", circle.name, exc)
    except Exception as exc:  # pragma: no cover - defensive logging only
        geocoding_failed = True
        logger.error("Unexpected error during geocoding for circle %s: %s", circle.name, exc)

    return geocoding_failed


def _upload_circle_image_or_raise(image_file):
    if not image_file or not is_valid_file_upload(image_file):
        return None

    image_url = upload_circle_image(image_file)
    if image_url is None:
        raise InvalidActionError(
            "Image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.)."
        )
    return image_url


def _promote_earliest_member(circle_id, excluded_user_id):
    next_admin_assoc = (
        db.session.query(circle_members)
        .filter(
            circle_members.c.circle_id == circle_id,
            circle_members.c.user_id != excluded_user_id,
        )
        .order_by(circle_members.c.joined_at)
        .first()
    )
    if not next_admin_assoc:
        return None

    stmt = (
        circle_members.update()
        .where(
            (circle_members.c.circle_id == circle_id)
            & (circle_members.c.user_id == next_admin_assoc.user_id)
        )
        .values(is_admin=True)
    )
    db.session.execute(stmt)
    return next_admin_assoc.user_id


def join_circle(circle, user, message_text=None):
    if user in circle.members:
        raise InformationalError("You are already a member of this circle.")

    if circle.requires_join_approval:
        join_request = CircleJoinRequest(
            circle_id=circle.id,
            user_id=user.id,
            message=message_text,
        )
        db.session.add(join_request)
        db.session.commit()

        try:
            send_circle_join_request_notification_email(join_request)
        except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
            logger.error(
                "Failed to send email notification for circle join request %s: %s",
                join_request.id,
                exc,
            )
        return join_request

    stmt = circle_members.insert().values(
        user_id=user.id,
        circle_id=circle.id,
        joined_at=datetime.now(UTC),
        is_admin=False,
    )
    db.session.execute(stmt)
    db.session.commit()
    return None


def handle_join_request(circle, join_request, acting_user, action):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("You must be an admin to perform this action.")

    if join_request.circle_id != circle.id:
        raise InvalidActionError("Invalid join request.")

    if join_request.status != "pending":
        raise InformationalError("This join request has already been handled.")

    if action == "approve":
        stmt = circle_members.insert().values(
            user_id=join_request.user_id,
            circle_id=circle.id,
            joined_at=datetime.now(UTC),
            is_admin=False,
        )
        db.session.execute(stmt)
        join_request.status = "approved"
        decision_message = Message(
            sender_id=acting_user.id,
            recipient_id=join_request.user_id,
            circle_id=circle.id,
            body=f"Your request to join '{circle.name}' has been approved.",
        )
        db.session.add(decision_message)
    elif action == "reject":
        join_request.status = "rejected"
        decision_message = Message(
            sender_id=acting_user.id,
            recipient_id=join_request.user_id,
            circle_id=circle.id,
            body=f"Your request to join '{circle.name}' has been denied.",
        )
        db.session.add(decision_message)
    else:
        raise InvalidActionError("Invalid action.")

    db.session.commit()

    try:
        send_circle_join_request_decision_email(join_request)
    except Exception as exc:  # pragma: no cover - behavior is unchanged if email sending fails
        logger.error(
            "Failed to send email notification for circle join request decision %s: %s",
            join_request.id,
            exc,
        )

    return action


def cancel_join_request(circle_id, user_id):
    pending_request = CircleJoinRequest.query.filter_by(
        circle_id=circle_id,
        user_id=user_id,
        status="pending",
    ).first()
    if not pending_request:
        return False

    db.session.delete(pending_request)
    db.session.commit()
    return True


def create_circle(
    creator,
    *,
    name,
    description,
    circle_type,
    image_file=None,
    location_method="skip",
    latitude=None,
    longitude=None,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
):
    cleaned_name = name.strip()
    if _find_circle_by_name(cleaned_name):
        raise ConflictError("A circle with this name already exists.")

    circle = Circle(
        name=cleaned_name,
        description=_clean_circle_description(description),
        circle_type=circle_type,
        image_url=_upload_circle_image_or_raise(image_file),
    )

    geocoding_failed = _apply_circle_location(
        circle,
        location_method=location_method,
        latitude=latitude,
        longitude=longitude,
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        country=country,
    )

    db.session.add(circle)
    db.session.flush()
    db.session.execute(
        circle_members.insert().values(
            user_id=creator.id,
            circle_id=circle.id,
            joined_at=datetime.now(UTC),
            is_admin=True,
        )
    )
    db.session.commit()

    return {
        "circle": circle,
        "geocoding_failed": geocoding_failed,
        "image_removed": False,
        "image_updated": bool(circle.image_url),
    }


def update_circle(
    circle,
    acting_user,
    *,
    name,
    description,
    circle_type,
    image_file=None,
    delete_image=False,
    location_method="skip",
    latitude=None,
    longitude=None,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("Only circle admins can edit circle details.")

    cleaned_name = name.strip()
    if _find_circle_by_name(cleaned_name, exclude_circle_id=circle.id):
        raise ConflictError("A circle with this name already exists.")

    circle.name = cleaned_name
    circle.description = _clean_circle_description(description)
    circle.circle_type = circle_type

    geocoding_failed = _apply_circle_location(
        circle,
        location_method=location_method,
        latitude=latitude,
        longitude=longitude,
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        country=country,
    )

    image_removed = False
    image_updated = False
    if delete_image and circle.image_url:
        delete_file(circle.image_url)
        circle.image_url = None
        image_removed = True

    if image_file and is_valid_file_upload(image_file):
        if circle.image_url:
            delete_file(circle.image_url)
        image_url = upload_circle_image(image_file)
        if image_url is None:
            raise InvalidActionError(
                "Image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.)."
            )
        circle.image_url = image_url
        image_updated = True

    db.session.commit()
    return {
        "circle": circle,
        "geocoding_failed": geocoding_failed,
        "image_removed": image_removed,
        "image_updated": image_updated,
    }


def leave_circle(circle, acting_user):
    if acting_user not in circle.members:
        raise InformationalError("You are not a member of this circle.")

    if circle.is_admin(acting_user) and len(circle.members) > 1:
        admin_count = _count_circle_admins(circle.id)
        if admin_count == 1:
            _promote_earliest_member(circle.id, acting_user.id)

    circle.members.remove(acting_user)

    if len(circle.members) == 0:
        if circle.image_url:
            delete_file(circle.image_url)
        db.session.delete(circle)
        db.session.commit()
        return {"circle_deleted": True}

    db.session.commit()
    return {"circle_deleted": False}


def remove_member(circle, member_user, acting_user):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("You must be an admin to remove members.")

    if member_user not in circle.members:
        raise ConflictError("User is not a member of this circle.")

    if member_user == acting_user:
        raise InvalidActionError("Use the leave circle button to remove yourself.")

    circle.members.remove(member_user)
    db.session.commit()
    return member_user


def toggle_admin(circle, user_id, acting_user, action):
    if not circle.is_admin(acting_user):
        raise AuthorizationError("You must be an admin to perform this action.")

    user_member = (
        db.session.query(circle_members)
        .filter_by(
            circle_id=circle.id,
            user_id=user_id,
        )
        .first()
    )
    if not user_member:
        raise ConflictError("User is not a member of this circle.")

    if action == "add":
        is_admin = True
    elif action == "remove":
        if (
            user_id == acting_user.id
            and user_member.is_admin
            and _count_circle_admins(circle.id) <= 1
        ):
            raise ConflictError("Cannot remove the last admin. Make someone else an admin first.")
        is_admin = False
    else:
        raise InvalidActionError("Invalid action.")

    stmt = (
        circle_members.update()
        .where((circle_members.c.circle_id == circle.id) & (circle_members.c.user_id == user_id))
        .values(is_admin=is_admin)
    )
    db.session.execute(stmt)
    db.session.commit()
    return is_admin
