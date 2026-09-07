from flask import abort, render_template, request
from flask_login import current_user, login_required

from app import db
from app.main import bp as main_bp
from app.models import Category, Item, Tag
from app.utils.circle_queries import build_circle_recommendations
from app.utils.home_feed import build_homepage_feed_events
from app.utils.item_queries import build_category_items_pagination, build_tag_items_pagination
from app.utils.profile_visibility import viewable_profile_user_ids

from .helpers import (
    HOMEPAGE_DISTANCE_OPTIONS,
    _build_find_context,
    _parse_homepage_feed_filters,
)


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("main/landing.html")

    show_public_giveaway_nudge = False
    featured_circle_recommendation = None

    user_circles = sorted(
        list(current_user.circles), key=lambda circle: (circle.name or "").lower()
    )
    has_circles = len(user_circles) > 0
    if not has_circles:
        show_public_giveaway_nudge = (
            Item.query.filter(
                Item.owner_id == current_user.id,
                Item.is_giveaway.is_(True),
                Item.giveaway_visibility == "public",
            ).first()
            is not None
        )
        circle_recommendations = build_circle_recommendations(current_user, limit=1)
        if circle_recommendations:
            featured_circle_recommendation = circle_recommendations[0]

    selected_circles = request.args.getlist("circles")
    filter_state = _parse_homepage_feed_filters(current_user)

    feed_events = build_homepage_feed_events(
        current_user,
        selected_circle_ids=selected_circles,
        scope=filter_state["scope"],
        giveaway_distance=filter_state["distance"],
        giveaway_distance_explicit=filter_state["distance_explicit"],
        included_event_types=filter_state["selected_feed_types"],
        include_own_activity=filter_state["show_own_activity"],
        include_claimed_giveaways=filter_state["show_claimed_giveaways"],
    )
    # Only link actor names to profiles the viewer is actually allowed to open —
    # public requests and giveaways surface people outside the viewer's circles.
    linkable_actor_ids = viewable_profile_user_ids(
        current_user, (event.get("actor_id") for event in feed_events)
    )

    return render_template(
        "main/index.html",
        feed_events=feed_events,
        linkable_actor_ids=linkable_actor_ids,
        has_circles=has_circles,
        show_public_giveaway_nudge=show_public_giveaway_nudge,
        featured_circle_recommendation=featured_circle_recommendation,
        selected_feed_scope=filter_state["scope"],
        selected_feed_types=filter_state["selected_feed_types"],
        selected_feed_distance=filter_state["distance_param_value"],
        selected_show_own_activity=filter_state["show_own_activity"],
        selected_show_claimed_giveaways=filter_state["show_claimed_giveaways"],
        feed_distance_options=sorted(HOMEPAGE_DISTANCE_OPTIONS),
    )


@main_bp.route("/find")
@login_required
def find():
    find_context = _build_find_context(current_user)
    return render_template("main/find.html", **find_context)


@main_bp.route("/tag/<uuid:tag_id>")
@login_required
def tag_items(tag_id):
    tag = db.session.get(Tag, tag_id)
    if not tag:
        abort(404)
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

    items_pagination = build_tag_items_pagination(
        current_user,
        tag_id=tag_id,
        item_type=item_type,
        page=page,
        per_page=per_page,
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
    category = db.session.get(Category, category_id)
    if not category:
        abort(404)
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

    items_pagination = build_category_items_pagination(
        current_user,
        category_id=category_id,
        item_type=item_type,
        page=page,
        per_page=per_page,
    )

    return render_template(
        "main/category_items.html",
        category=category,
        items=items_pagination.items,
        pagination=items_pagination,
        no_circles=False,
        item_type=item_type,
    )
