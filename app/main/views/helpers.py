import json
from datetime import UTC, datetime

from flask import request, session, url_for
from flask_login import current_user

from app.models import Category
from app.utils.home_feed import HOMEPAGE_FEED_EVENT_TYPES
from app.utils.item_queries import build_find_results
from app.utils.item_share import token_grants_item_access
from app.utils.storage import (
    MAX_UPLOAD_FILE_SIZE_BYTES,
    MAX_UPLOAD_FILE_SIZE_LABEL,
    get_file_size,
    has_allowed_image_extension,
    is_valid_file_upload,
)

HOMEPAGE_DISTANCE_OPTIONS = {5, 10, 20, 25, 50}
HOMEPAGE_FEED_CHIPS = (
    ("Requests", "requests"),
    ("Giveaways", "giveaways"),
    ("Lending", "loans"),
    ("Circles", "circle_joins"),
)


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
    selected_feed_types = []
    if types_explicit:
        selected_feed_types = [
            event_type
            for event_type in selected_types_raw
            if event_type in HOMEPAGE_FEED_EVENT_TYPES
        ]
    if not selected_feed_types:
        selected_feed_types = [value for _, value in HOMEPAGE_FEED_CHIPS]

    distance_explicit = "distance" in request.args
    distance_value_raw = request.args.get("distance")
    selected_distance = None
    if distance_value_raw and distance_value_raw != "none":
        try:
            parsed_distance = int(distance_value_raw)
        except TypeError, ValueError:
            parsed_distance = None
        if parsed_distance in HOMEPAGE_DISTANCE_OPTIONS:
            selected_distance = parsed_distance

    if not distance_explicit and user.is_geocoded:
        selected_distance = 20

    distance_param_value = "none" if selected_distance is None else str(selected_distance)
    show_own_activity = True
    if "own_activity_present" in request.args:
        show_own_activity = request.args.get("show_own_activity") == "1"
    show_claimed_giveaways = True
    if "claimed_giveaways_present" in request.args:
        show_claimed_giveaways = request.args.get("show_claimed_giveaways") == "1"

    return {
        "scope": scope,
        "selected_feed_types": selected_feed_types,
        "distance": selected_distance,
        "distance_explicit": distance_explicit,
        "distance_param_value": distance_param_value,
        "show_own_activity": show_own_activity,
        "show_claimed_giveaways": show_claimed_giveaways,
    }


def _build_homepage_feed_chips(filter_state):
    """Filter chips for the feed, each linking to the view you get by tapping it."""
    kept_args = {}
    if filter_state["scope"] != "all":
        kept_args["scope"] = filter_state["scope"]
    if filter_state["distance_explicit"]:
        kept_args["distance"] = filter_state["distance_param_value"]
    if not filter_state["show_own_activity"]:
        kept_args["own_activity_present"] = 1
    if not filter_state["show_claimed_giveaways"]:
        kept_args["claimed_giveaways_present"] = 1

    all_types = {value for _, value in HOMEPAGE_FEED_CHIPS}
    selected = filter_state["selected_feed_types"]
    everything = set(selected) == all_types

    chips = [
        {"label": "Everything", "url": url_for("main.index", **kept_args), "selected": everything}
    ]
    for label, value in HOMEPAGE_FEED_CHIPS:
        if everything:
            next_types = [value]
        elif value in selected:
            next_types = [event_type for event_type in selected if event_type != value]
        else:
            next_types = [*selected, value]

        if next_types and set(next_types) != all_types:
            url = url_for("main.index", types_present=1, types=next_types, **kept_args)
        else:
            url = url_for("main.index", **kept_args)
        chips.append({"label": label, "url": url, "selected": not everything and value in selected})
    return chips


def _build_find_context(user):
    query = request.args.get("q", "").strip()
    selected_categories = request.args.getlist("categories")
    selected_circles = request.args.getlist("circles")
    item_type = request.args.get("item_type", "both")
    sort_by = request.args.get("sort", "date")
    page = request.args.get("page", 1, type=int)
    per_page = 12
    all_categories = Category.query.order_by(Category.name).all()
    find_results = build_find_results(
        user,
        query=query,
        selected_category_ids=selected_categories,
        selected_circle_ids=selected_circles,
        item_type=item_type,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
    )

    return {
        "items": find_results["items"],
        "pagination": find_results["pagination"],
        "query": query,
        "categories": all_categories,
        "user_circles": find_results["user_circles"],
        "selected_categories": selected_categories,
        "selected_circles": selected_circles,
        "item_type": find_results["item_type"],
        "sort_by": find_results["sort_by"],
        "has_circles": find_results["has_circles"],
        "result_count": find_results["result_count"],
    }
