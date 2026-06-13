from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import GiveawayInterest, Item, ItemImage, LoanRequest, Message, Tag
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError
from app.utils.storage import MAX_ITEM_IMAGE_COUNT, delete_item_images, upload_item_images

PUBLIC_GIVEAWAY_LOCATION_MESSAGE = (
    "You must set your location before making a giveaway public. "
    "Public giveaways are visible to everyone on Meutch and users will have no idea where the "
    "item is located. Please update your location in your profile settings."
)
ITEM_IMAGE_LIMIT_MESSAGE = (
    f"Maximum {MAX_ITEM_IMAGE_COUNT} images per item. Please remove some images first."
)


@dataclass
class ItemCreationResult:
    item: Item
    was_created: bool


def _get_item_by_creation_token(owner_id, creation_token):
    if creation_token is None:
        return None

    return Item.query.filter_by(owner_id=owner_id, creation_token=creation_token).first()


def get_giveaway_conversion_blocker(item):
    active_loan = LoanRequest.query.filter_by(item_id=item.id, status="approved").first()
    if active_loan:
        return active_loan, "active"

    pending_loan = LoanRequest.query.filter_by(item_id=item.id, status="pending").first()
    if pending_loan:
        return pending_loan, "pending"

    return None, None


def get_loan_conversion_blocker(item):
    if item.claim_status == "claimed":
        return "claimed"

    if item.claim_status == "pending_pickup":
        return "pending_pickup"

    active_interest = GiveawayInterest.query.filter(
        GiveawayInterest.item_id == item.id,
        GiveawayInterest.status.in_(["active", "selected"]),
    ).first()
    if active_interest:
        return "interested_users"

    return None


def get_item_delete_blocker(item):
    active_loan = LoanRequest.query.filter_by(item_id=item.id, status="approved").first()
    if active_loan:
        return "active_loan", active_loan

    if item.is_giveaway and item.claim_status == "pending_pickup":
        return "pending_pickup", None

    if item.is_giveaway and item.claim_status == "claimed":
        return "claimed", None

    return None, None


def _raise_item_transition_conflict(item, is_giveaway):
    if is_giveaway:
        _, blocking_loan_type = get_giveaway_conversion_blocker(item)
        if blocking_loan_type == "active":
            raise ConflictError(
                "This item has an active loan. Mark it returned or cancel the loan before converting it to a giveaway."
            )
        if blocking_loan_type == "pending":
            raise ConflictError(
                "This item has a pending loan request. Resolve the request before converting it to a giveaway."
            )
        return

    if not item.is_giveaway:
        return

    conversion_blocker = get_loan_conversion_blocker(item)
    if conversion_blocker == "interested_users":
        raise ConflictError(
            "This giveaway already has interested users. It cannot be converted back into a loan item."
        )
    if conversion_blocker == "pending_pickup":
        raise ConflictError(
            "This giveaway is pending pickup. Complete the handoff or release it back to everyone before converting it to a loan item."
        )
    if conversion_blocker == "claimed":
        raise ConflictError(
            "This giveaway has already been handed off. Completed giveaways cannot be converted back into loan items."
        )


def _sync_item_tags(item, raw_tag_input):
    item.tags.clear()
    with db.session.no_autoflush:
        for tag_name in _normalize_tag_names(raw_tag_input):
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            item.tags.append(tag)


def _normalize_tag_names(raw_tag_input):
    if not raw_tag_input:
        return []

    tag_values = raw_tag_input
    if isinstance(raw_tag_input, str):
        tag_values = raw_tag_input.split(",")

    normalized_names = []
    seen_names = set()
    for raw_tag in tag_values:
        if raw_tag is None:
            continue
        tag_name = str(raw_tag).strip().lower()
        if not tag_name or tag_name in seen_names:
            continue
        normalized_names.append(tag_name)
        seen_names.add(tag_name)

    return normalized_names


def _normalize_text_value(value):
    if value is None:
        return None

    return value.strip() if isinstance(value, str) else value


def _ensure_item_owner(item, acting_user):
    if item.owner_id != acting_user.id:
        raise AuthorizationError("You can only manage your own items.")


def _ensure_item_image_capacity(existing_count, new_count):
    if existing_count + new_count > MAX_ITEM_IMAGE_COUNT:
        raise InformationalError(ITEM_IMAGE_LIMIT_MESSAGE)


def _ensure_public_giveaway_owner_is_geocoded(owner, is_giveaway, giveaway_visibility):
    if is_giveaway and giveaway_visibility == "public" and not owner.is_geocoded:
        raise InformationalError(PUBLIC_GIVEAWAY_LOCATION_MESSAGE)


def create_item(
    owner,
    name,
    description,
    category_id,
    is_giveaway,
    giveaway_visibility,
    raw_tag_input,
    uploaded_files,
    creation_token=None,
):
    existing_item = _get_item_by_creation_token(owner.id, creation_token)
    if existing_item is not None:
        return ItemCreationResult(item=existing_item, was_created=False)

    _ensure_public_giveaway_owner_is_geocoded(owner, is_giveaway, giveaway_visibility)
    _ensure_item_image_capacity(0, len(uploaded_files or []))

    image_urls = []
    if uploaded_files:
        image_urls = upload_item_images(uploaded_files)

    new_item = Item(
        name=_normalize_text_value(name),
        description=_normalize_text_value(description),
        owner=owner,
        category_id=category_id,
        creation_token=creation_token,
        is_giveaway=is_giveaway,
        giveaway_visibility=giveaway_visibility if is_giveaway else None,
        claim_status="unclaimed" if is_giveaway else None,
    )
    db.session.add(new_item)

    for position, url in enumerate(image_urls):
        db.session.add(ItemImage(item=new_item, url=url, position=position))

    _sync_item_tags(new_item, raw_tag_input)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if image_urls:
            delete_item_images(image_urls)

        existing_item = _get_item_by_creation_token(owner.id, creation_token)
        if existing_item is not None:
            return ItemCreationResult(item=existing_item, was_created=False)

        raise
    except Exception:
        db.session.rollback()
        if image_urls:
            delete_item_images(image_urls)
        raise

    return ItemCreationResult(item=new_item, was_created=True)


def update_item(
    item,
    name,
    description,
    category_id,
    is_giveaway,
    giveaway_visibility,
    raw_tag_input,
    new_files,
    delete_entries,
    order_entries,
):
    _ensure_public_giveaway_owner_is_geocoded(item.owner, is_giveaway, giveaway_visibility)
    _raise_item_transition_conflict(item, is_giveaway)

    existing_images = list(item.images)
    existing_image_ids = {str(img.id) for img in existing_images}
    delete_ids = {entry for entry in delete_entries if entry in existing_image_ids}
    surviving_images = [img for img in existing_images if str(img.id) not in delete_ids]
    _ensure_item_image_capacity(len(surviving_images), len(new_files or []))

    new_urls = []
    if new_files:
        new_urls = upload_item_images(new_files)

    item.name = _normalize_text_value(name)
    item.description = _normalize_text_value(description)
    item.category_id = category_id
    item.is_giveaway = is_giveaway
    item.giveaway_visibility = giveaway_visibility if is_giveaway else None
    if is_giveaway and not item.claim_status:
        item.claim_status = "unclaimed"
    elif not is_giveaway:
        item.claim_status = None

    _sync_item_tags(item, raw_tag_input)

    removed_urls = []
    for image in existing_images:
        if str(image.id) in delete_ids:
            removed_urls.append(image.url)
            db.session.delete(image)

    existing_by_id = {str(img.id): img for img in surviving_images}
    ordered_entries = []
    ordered_existing_ids = set()
    new_url_iter = iter(new_urls)

    for entry_id in order_entries:
        if entry_id.startswith("new-"):
            url = next(new_url_iter, None)
            if url is not None:
                ordered_entries.append(("new", url))
            continue

        image = existing_by_id.get(entry_id)
        if image is not None and entry_id not in ordered_existing_ids:
            ordered_entries.append(("existing", image))
            ordered_existing_ids.add(entry_id)

    for image in surviving_images:
        image_id = str(image.id)
        if image_id not in ordered_existing_ids:
            ordered_entries.append(("existing", image))

    for url in new_url_iter:
        ordered_entries.append(("new", url))

    for position, (entry_type, entry_value) in enumerate(ordered_entries):
        if entry_type == "existing":
            entry_value.position = position
        else:
            db.session.add(ItemImage(item=item, url=entry_value, position=position))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if new_urls:
            delete_item_images(new_urls)
        raise

    if removed_urls:
        delete_item_images(removed_urls)


def append_item_images(item, acting_user, new_files):
    _ensure_item_owner(item, acting_user)
    _ensure_item_image_capacity(len(item.images), len(new_files or []))

    if not new_files:
        return item

    new_urls = upload_item_images(new_files)
    start_position = len(item.images)
    for offset, url in enumerate(new_urls):
        db.session.add(ItemImage(item=item, url=url, position=start_position + offset))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_item_images(new_urls)
        raise

    return item


def reorder_item_images(item, acting_user, image_ids):
    _ensure_item_owner(item, acting_user)

    requested_ids = [str(image_id) for image_id in image_ids]
    existing_images = list(item.images)
    existing_ids = [str(image.id) for image in existing_images]
    if len(requested_ids) != len(existing_ids) or set(requested_ids) != set(existing_ids):
        raise InformationalError("image_ids must include every existing item image exactly once.")

    existing_by_id = {str(image.id): image for image in existing_images}
    for position, image_id in enumerate(requested_ids):
        existing_by_id[image_id].position = position

    db.session.commit()
    return item


def delete_item_image(item, image, acting_user):
    _ensure_item_owner(item, acting_user)

    remaining_images = [
        existing_image for existing_image in item.images if existing_image.id != image.id
    ]
    for position, remaining_image in enumerate(remaining_images):
        remaining_image.position = position

    image_url = image.url
    db.session.delete(image)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    delete_item_images([image_url])
    return item


def delete_item(item, acting_user):
    if item.owner_id != acting_user.id:
        raise AuthorizationError("You can only delete your own items.")

    blocker_type, _ = get_item_delete_blocker(item)
    if blocker_type == "active_loan":
        raise ConflictError(
            "This item is currently out on loan. Mark it returned or cancel the loan before deleting the item."
        )
    if blocker_type == "pending_pickup":
        raise ConflictError(
            "This giveaway is still pending pickup. Mark the handoff complete or release it instead of deleting the item."
        )
    if blocker_type == "claimed":
        raise ConflictError(
            "You cannot delete a giveaway that has been claimed and handed off. This is a completed transaction."
        )

    delete_item_with_cleanup(item)
    return item


def list_user_items(user, search_query=None, page=1, per_page=12):
    """Return a paginated list of items owned by *user*.

    Args:
        user: The owner whose items should be listed.
        search_query: Optional text filter matched against name and description.
        page: 1-based page number (default 1).
        per_page: Items per page (default 12).

    Returns:
        A Flask-SQLAlchemy Pagination object.
    """
    from sqlalchemy import or_

    query = Item.query.filter_by(owner_id=user.id)

    if search_query:
        query = query.filter(
            or_(
                Item.name.ilike(f"%{search_query}%"),
                Item.description.ilike(f"%{search_query}%"),
            )
        )

    return query.order_by(Item.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )


def delete_item_with_cleanup(item):
    image_urls = [image.url for image in item.images]
    Message.query.filter(Message.item_id == item.id).delete()
    LoanRequest.query.filter_by(item_id=item.id).delete()
    GiveawayInterest.query.filter_by(item_id=item.id).delete()
    item.tags.clear()
    db.session.delete(item)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if image_urls:
        delete_item_images(image_urls)
