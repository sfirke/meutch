from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.main import bp as main_bp
from app.models import Category, Item, Tag, User
from app.utils.home_feed import build_homepage_feed_events

from .helpers import (
    HOMEPAGE_DISTANCE_OPTIONS,
    _build_find_context,
    _parse_homepage_feed_filters,
)


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("main/landing.html")

    items = []
    giveaway_items = []
    feed_events = []
    pagination = None
    total_items = 0
    remaining_items = 0
    query = ""
    all_categories = []
    user_circles = []
    selected_categories = []
    selected_circles = []
    item_type = "both"
    has_circles = False
    result_count = 0
    selected_feed_scope = "all"
    selected_feed_types = ["requests", "giveaways", "circle_joins", "loans"]
    selected_feed_distance = "none"
    feed_distance_options = sorted(HOMEPAGE_DISTANCE_OPTIONS)

    user_circles = sorted(
        list(current_user.circles), key=lambda circle: (circle.name or "").lower()
    )
    has_circles = len(user_circles) > 0
    selected_circles = request.args.getlist("circles")
    filter_state = _parse_homepage_feed_filters(current_user)
    selected_feed_scope = filter_state["scope"]
    selected_feed_types = filter_state["selected_feed_types"]
    selected_feed_distance = filter_state["distance_param_value"]

    feed_events = build_homepage_feed_events(
        current_user,
        selected_circle_ids=selected_circles,
        scope=selected_feed_scope,
        giveaway_distance=filter_state["distance"],
        giveaway_distance_explicit=filter_state["distance_explicit"],
        included_event_types=selected_feed_types,
    )

    return render_template(
        "main/index.html",
        items=items,
        giveaway_items=giveaway_items,
        feed_events=feed_events,
        pagination=pagination,
        total_items=total_items,
        remaining_items=remaining_items,
        query=query,
        categories=all_categories,
        user_circles=user_circles,
        selected_categories=selected_categories,
        selected_circles=selected_circles,
        item_type=item_type,
        has_circles=has_circles,
        result_count=result_count,
        selected_feed_scope=selected_feed_scope,
        selected_feed_types=selected_feed_types,
        selected_feed_distance=selected_feed_distance,
        feed_distance_options=feed_distance_options,
    )


@main_bp.route("/find")
@login_required
def find():
    find_context = _build_find_context(current_user)
    return render_template("main/find.html", **find_context)


@main_bp.route("/giveaways")
@login_required
def giveaways():
    return redirect(url_for("main.index"))


@main_bp.route("/tag/<uuid:tag_id>")
@login_required
def tag_items(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    page = request.args.get("page", 1, type=int)
    item_type = request.args.get("item_type", "both")
    per_page = 12
    has_circles = len(current_user.circles) > 0

    if not has_circles:
        return render_template(
            "main/tag_items.html",
            tag=tag,
            items=[],
            pagination=None,
            no_circles=True,
            item_type=item_type,
        )

    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
    items_query = (
        Item.query.join(Item.tags)
        .join(User, Item.owner_id == User.id)
        .filter(
            Tag.id == tag_id,
            Item.owner_id.in_(shared_circle_user_ids),
            User.vacation_mode.is_(False),
        )
    )

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

    items_pagination = (
        items_query.options(
            joinedload(Item.owner), joinedload(Item.category), joinedload(Item.tags)
        )
        .order_by(Item.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "main/tag_items.html",
        tag=tag,
        items=items_pagination.items,
        pagination=items_pagination,
        no_circles=False,
        item_type=item_type,
    )


@main_bp.route("/category/<uuid:category_id>")
@login_required
def category_items(category_id):
    category = Category.query.get_or_404(category_id)
    page = request.args.get("page", 1, type=int)
    item_type = request.args.get("item_type", "both")
    per_page = 12
    has_circles = len(current_user.circles) > 0

    if not has_circles:
        return render_template(
            "main/category_items.html",
            category=category,
            items=[],
            pagination=None,
            no_circles=True,
            item_type=item_type,
        )

    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
    items_query = Item.query.join(User, Item.owner_id == User.id).filter(
        Item.category_id == category_id,
        Item.owner_id.in_(shared_circle_user_ids),
        User.vacation_mode.is_(False),
    )

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

    items_pagination = (
        items_query.options(
            joinedload(Item.owner), joinedload(Item.category), joinedload(Item.tags)
        )
        .order_by(Item.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "main/category_items.html",
        category=category,
        items=items_pagination.items,
        pagination=items_pagination,
        no_circles=False,
        item_type=item_type,
    )
