from sqlalchemy.exc import IntegrityError

from app import db
from app.models import GiveawayInterest, Item, ItemImage, LoanRequest, Message, Tag
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError
from app.utils.storage import delete_item_images, upload_item_images


def get_item_by_creation_token(owner_id, creation_token):
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
    tag_input = raw_tag_input.strip() if raw_tag_input else ""
    item.tags.clear()
    if not tag_input:
        return

    tag_names = [tag.strip().lower() for tag in tag_input.split(",") if tag.strip()]
    with db.session.no_autoflush:
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            item.tags.append(tag)


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
    existing_item = get_item_by_creation_token(owner.id, creation_token)
    if existing_item is not None:
        raise InformationalError("This item was already listed from your earlier submission.")

    image_urls = []
    if uploaded_files:
        image_urls = upload_item_images(uploaded_files)

    new_item = Item(
        name=name.strip(),
        description=description.strip(),
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
    except IntegrityError as exc:
        db.session.rollback()
        if image_urls:
            delete_item_images(image_urls)

        existing_item = get_item_by_creation_token(owner.id, creation_token)
        if existing_item is not None:
            raise InformationalError(
                "This item was already listed from your earlier submission."
            ) from exc

        raise
    except Exception:
        db.session.rollback()
        if image_urls:
            delete_item_images(image_urls)
        raise

    return new_item


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
    _raise_item_transition_conflict(item, is_giveaway)

    existing_images = list(item.images)
    existing_image_ids = {str(img.id) for img in existing_images}
    delete_ids = {entry for entry in delete_entries if entry in existing_image_ids}
    surviving_images = [img for img in existing_images if str(img.id) not in delete_ids]

    new_urls = []
    if new_files:
        new_urls = upload_item_images(new_files)

    item.name = name
    item.description = description
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
