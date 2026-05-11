import json
from datetime import UTC, datetime

from flask import request, session
from flask_login import current_user
from sqlalchemy import and_, or_, select

from app.models import Category, Item, Tag, User, circle_members
from app.utils.geocoding import sort_items_by_owner_distance
from app.utils.home_feed import HOMEPAGE_FEED_EVENT_TYPES
from app.utils.item_share import token_grants_item_access
from app.utils.pagination import ListPagination
from app.utils.storage import (
    MAX_UPLOAD_FILE_SIZE_BYTES,
    MAX_UPLOAD_FILE_SIZE_LABEL,
    get_file_size,
    has_allowed_image_extension,
    is_valid_file_upload,
)

HOMEPAGE_DISTANCE_OPTIONS = {5, 10, 20, 25, 50}


def _build_item_detail_url(item_id, share_token=None):
    from flask import url_for

    if share_token:
        return url_for("main.item_detail", item_id=item_id, share_token=share_token)
    return url_for("main.item_detail", item_id=item_id)


def _parse_json_string_list(raw_value, field_name):
    if not raw_value:
        return []

    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(
            f"{field_name} data was invalid. Please reload the page and try again."
        ) from exc

    if not isinstance(parsed, list) or any(not isinstance(entry, str) for entry in parsed):
        raise ValueError(f"{field_name} data was invalid. Please reload the page and try again.")

    return parsed


def _collect_item_image_uploads(files):
    valid_files = []
    errors = []

    for uploaded_file in files or []:
        filename = getattr(uploaded_file, "filename", "") or ""
        filename = filename.strip()

        if not filename:
            continue

        if not has_allowed_image_extension(filename):
            errors.append(f"{filename} is not a supported image format.")
            continue

        file_size = get_file_size(uploaded_file)
        if file_size is None or file_size <= 0:
            errors.append(f"{filename} could not be read. Please choose a valid image file.")
            continue

        if file_size > MAX_UPLOAD_FILE_SIZE_BYTES:
            errors.append(f"{filename} exceeds the {MAX_UPLOAD_FILE_SIZE_LABEL} size limit.")
            continue

        if not is_valid_file_upload(uploaded_file):
            errors.append(f"{filename} is not a valid image upload.")
            continue

        valid_files.append(uploaded_file)

    return valid_files, errors


def _generated_item_share_link(item_id):
    entry = session.get(f"generated-item-share-link:{item_id}")
    if not entry:
        return None
    if datetime.now(UTC).timestamp() > entry.get("expires_at", 0):
        session.pop(f"generated-item-share-link:{item_id}", None)
        return None
    return entry["url"]


def _conversation_other_user_id(message, viewer_id):
    if message.sender_id == viewer_id:
        return message.recipient_id
    if message.recipient_id == viewer_id:
        return message.sender_id
    return None


def _shares_circle_or_has_item_token_access(item, share_token=None):
    if item.owner_id == current_user.id:
        return True

    if current_user.shares_circle_with(item.owner):
        return True

    return token_grants_item_access(share_token, item)


def _parse_homepage_feed_filters(user):
    scope = request.args.get("scope", "all")
    if scope not in {"all", "circles"}:
        scope = "all"

    selected_types_raw = request.args.getlist("types")
    types_explicit = "types_present" in request.args
    if types_explicit:
        selected_feed_types = [
            event_type
            for event_type in selected_types_raw
            if event_type in HOMEPAGE_FEED_EVENT_TYPES
        ]
    else:
        selected_feed_types = ["requests", "giveaways", "circle_joins", "loans"]

    distance_explicit = "distance" in request.args
    distance_value_raw = request.args.get("distance")
    selected_distance = None
    if distance_value_raw and distance_value_raw != "none":
        try:
            parsed_distance = int(distance_value_raw)
        except (TypeError, ValueError):
            parsed_distance = None
        if parsed_distance in HOMEPAGE_DISTANCE_OPTIONS:
            selected_distance = parsed_distance

    if not distance_explicit and user.is_geocoded:
        selected_distance = 20

    distance_param_value = "none" if selected_distance is None else str(selected_distance)

    return {
        "scope": scope,
        "selected_feed_types": selected_feed_types,
        "distance": selected_distance,
        "distance_explicit": distance_explicit,
        "distance_param_value": distance_param_value,
    }


def _build_find_context(user):
    items = []
    pagination = None
    query = request.args.get("q", "").strip()
    selected_categories = request.args.getlist("categories")
    selected_circles = request.args.getlist("circles")
    item_type = request.args.get("item_type", "both")
    sort_by = request.args.get("sort", "date")
    if sort_by not in ("date", "distance"):
        sort_by = "date"
    page = request.args.get("page", 1, type=int)
    per_page = 12
    result_count = 0

    user_circles = sorted(list(user.circles), key=lambda circle: (circle.name or "").lower())
    has_circles = len(user_circles) > 0
    all_categories = Category.query.order_by(Category.name).all()

    if has_circles:
        if query:
            shared_circle_user_ids = user.get_shared_circle_user_ids_query()

            if selected_circles:
                shared_circle_user_ids = (
                    select(circle_members.c.user_id)
                    .where(circle_members.c.circle_id.in_(selected_circles))
                    .distinct()
                )

            all_circle_user_ids = select(circle_members.c.user_id).distinct()

            items_query = (
                Item.query.join(User, Item.owner_id == User.id)
                .outerjoin(Item.tags)
                .outerjoin(Item.category)
                .filter(
                    User.vacation_mode.is_(False),
                    Item.owner_id != user.id,
                    and_(
                        or_(
                            and_(
                                or_(
                                    Item.is_giveaway.is_(False),
                                    Item.giveaway_visibility == "default",
                                ),
                                Item.owner_id.in_(shared_circle_user_ids),
                            ),
                            and_(
                                Item.giveaway_visibility == "public",
                                Item.owner_id.in_(all_circle_user_ids),
                            ),
                        ),
                        or_(
                            Item.name.ilike(f"%{query}%"),
                            Item.description.ilike(f"%{query}%"),
                            Tag.name.ilike(f"%{query}%"),
                        ),
                    ),
                )
            )

            if selected_categories:
                items_query = items_query.filter(Item.category_id.in_(selected_categories))

            if item_type == "loans":
                items_query = items_query.filter(Item.is_giveaway.is_(False))
            elif item_type == "giveaways":
                items_query = items_query.filter(
                    Item.is_giveaway.is_(True),
                    or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
                )
            else:
                items_query = items_query.filter(
                    or_(
                        Item.is_giveaway.is_(False),
                        and_(
                            Item.is_giveaway.is_(True),
                            or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
                        ),
                    )
                )

            items_query = items_query.distinct()
            all_items = items_query.all()
            if sort_by == "distance":
                sorted_items = sort_items_by_owner_distance(all_items, user)
            else:
                sorted_items = sorted(
                    all_items, key=lambda x: x.created_at or datetime.min, reverse=True
                )
            pagination = ListPagination(items=sorted_items, page=page, per_page=per_page)
            items = pagination.items
            result_count = pagination.total
        else:
            shared_circle_user_ids = user.get_shared_circle_user_ids_query()

            if selected_circles:
                shared_circle_user_ids = (
                    select(circle_members.c.user_id)
                    .where(circle_members.c.circle_id.in_(selected_circles))
                    .distinct()
                )

            all_circle_user_ids = select(circle_members.c.user_id).distinct()

            base_query = Item.query.join(User, Item.owner_id == User.id).filter(
                Item.owner_id != user.id,
                User.vacation_mode.is_(False),
                or_(
                    and_(
                        or_(Item.is_giveaway.is_(False), Item.giveaway_visibility == "default"),
                        Item.owner_id.in_(shared_circle_user_ids),
                    ),
                    and_(
                        Item.giveaway_visibility == "public", Item.owner_id.in_(all_circle_user_ids)
                    ),
                ),
                or_(
                    Item.is_giveaway.is_(False),
                    and_(
                        Item.is_giveaway.is_(True),
                        or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
                    ),
                ),
            )

            if selected_categories:
                base_query = base_query.filter(Item.category_id.in_(selected_categories))

            if item_type == "loans":
                base_query = base_query.filter(Item.is_giveaway.is_(False))
            elif item_type == "giveaways":
                base_query = base_query.filter(
                    Item.is_giveaway.is_(True),
                    or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
                )

            if sort_by == "distance":
                all_items = base_query.all()
                sorted_items = sort_items_by_owner_distance(all_items, user)
                pagination = ListPagination(items=sorted_items, page=page, per_page=per_page)
            else:
                base_query = base_query.order_by(Item.created_at.desc())
                pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items
            result_count = pagination.total

    return {
        "items": items,
        "pagination": pagination,
        "query": query,
        "categories": all_categories,
        "user_circles": user_circles,
        "selected_categories": selected_categories,
        "selected_circles": selected_circles,
        "item_type": item_type,
        "sort_by": sort_by,
        "has_circles": has_circles,
        "result_count": result_count,
    }
