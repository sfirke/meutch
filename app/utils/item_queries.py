from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload

from app.models import Item, Tag, User, circle_members
from app.utils.geocoding import sort_items_by_owner_distance
from app.utils.pagination import ListPagination

DEFAULT_ITEMS_PER_PAGE = 12


def _normalize_item_type(item_type):
    if item_type in {"loans", "giveaways", "both"}:
        return item_type
    return "both"


def _normalize_sort_by(sort_by):
    if sort_by in {"date", "distance"}:
        return sort_by
    return "date"


def _selected_circle_user_ids_query(user, selected_circle_ids=None):
    if selected_circle_ids:
        return (
            select(circle_members.c.user_id)
            .where(circle_members.c.circle_id.in_(selected_circle_ids))
            .distinct()
        )
    return user.get_shared_circle_user_ids_query()


def _available_items_filter():
    return or_(
        Item.is_giveaway.is_(False),
        and_(
            Item.is_giveaway.is_(True),
            or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
        ),
    )


def _apply_available_items_filter(query, item_type):
    normalized_item_type = _normalize_item_type(item_type)
    if normalized_item_type == "loans":
        return query.filter(Item.is_giveaway.is_(False))
    if normalized_item_type == "giveaways":
        return query.filter(
            Item.is_giveaway.is_(True),
            or_(Item.claim_status == "unclaimed", Item.claim_status.is_(None)),
        )
    return query.filter(_available_items_filter())


def _discoverable_item_visibility_filter(shared_circle_user_ids, all_circle_user_ids):
    return or_(
        and_(
            or_(Item.is_giveaway.is_(False), Item.giveaway_visibility == "default"),
            Item.owner_id.in_(shared_circle_user_ids),
        ),
        and_(
            Item.giveaway_visibility == "public",
            Item.owner_id.in_(all_circle_user_ids),
        ),
    )


def _sort_items(items, user, sort_by):
    if sort_by == "distance":
        return sort_items_by_owner_distance(items, user)
    return sorted(items, key=lambda item: item.created_at or datetime.min, reverse=True)


def _build_find_items_query(
    user, search_query, selected_category_ids=None, selected_circle_ids=None
):
    shared_circle_user_ids = _selected_circle_user_ids_query(user, selected_circle_ids)
    all_circle_user_ids = select(circle_members.c.user_id).distinct()

    items_query = (
        Item.query.join(User, Item.owner_id == User.id)
        .outerjoin(Item.tags)
        .outerjoin(Item.category)
        .filter(
            User.vacation_mode.is_(False),
            Item.owner_id != user.id,
            _discoverable_item_visibility_filter(shared_circle_user_ids, all_circle_user_ids),
        )
    )

    if search_query:
        items_query = items_query.filter(
            or_(
                Item.name.ilike(f"%{search_query}%"),
                Item.description.ilike(f"%{search_query}%"),
                Tag.name.ilike(f"%{search_query}%"),
            )
        )

    if selected_category_ids:
        items_query = items_query.filter(Item.category_id.in_(selected_category_ids))

    return items_query


def _build_find_pagination(
    user,
    query,
    selected_category_ids=None,
    selected_circle_ids=None,
    item_type="both",
    sort_by="date",
    page=1,
    per_page=DEFAULT_ITEMS_PER_PAGE,
):
    normalized_sort_by = _normalize_sort_by(sort_by)
    items_query = _build_find_items_query(
        user,
        search_query=query,
        selected_category_ids=selected_category_ids,
        selected_circle_ids=selected_circle_ids,
    )
    items_query = _apply_available_items_filter(items_query, item_type).distinct()

    if query or normalized_sort_by == "distance":
        all_items = items_query.all()
        sorted_items = _sort_items(all_items, user, normalized_sort_by)
        return ListPagination(items=sorted_items, page=page, per_page=per_page)

    return items_query.order_by(Item.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )


def build_find_results(
    user,
    query="",
    selected_category_ids=None,
    selected_circle_ids=None,
    item_type="both",
    sort_by="date",
    page=1,
    per_page=DEFAULT_ITEMS_PER_PAGE,
):
    user_circles = sorted(list(user.circles), key=lambda circle: (circle.name or "").lower())
    has_circles = len(user_circles) > 0
    normalized_item_type = _normalize_item_type(item_type)
    normalized_sort_by = _normalize_sort_by(sort_by)

    if not has_circles:
        return {
            "items": [],
            "pagination": None,
            "result_count": 0,
            "user_circles": user_circles,
            "has_circles": has_circles,
            "item_type": normalized_item_type,
            "sort_by": normalized_sort_by,
        }

    pagination = _build_find_pagination(
        user,
        query=query,
        selected_category_ids=selected_category_ids,
        selected_circle_ids=selected_circle_ids,
        item_type=normalized_item_type,
        sort_by=normalized_sort_by,
        page=page,
        per_page=per_page,
    )

    return {
        "items": pagination.items,
        "pagination": pagination,
        "result_count": pagination.total,
        "user_circles": user_circles,
        "has_circles": has_circles,
        "item_type": normalized_item_type,
        "sort_by": normalized_sort_by,
    }


def _shared_circle_items_query(user):
    shared_circle_user_ids = user.get_shared_circle_user_ids_query()
    return Item.query.join(User, Item.owner_id == User.id).filter(
        Item.owner_id.in_(shared_circle_user_ids),
        User.vacation_mode.is_(False),
    )


def _paginate_circle_items_query(items_query, item_type, page, per_page):
    return (
        _apply_available_items_filter(items_query, item_type)
        .options(joinedload(Item.owner), joinedload(Item.category), joinedload(Item.tags))
        .order_by(Item.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )


def build_tag_items_pagination(
    user, tag_id, item_type="both", page=1, per_page=DEFAULT_ITEMS_PER_PAGE
):
    items_query = _shared_circle_items_query(user).join(Item.tags).filter(Tag.id == tag_id)
    return _paginate_circle_items_query(items_query, item_type, page, per_page)


def build_category_items_pagination(
    user,
    category_id,
    item_type="both",
    page=1,
    per_page=DEFAULT_ITEMS_PER_PAGE,
):
    items_query = _shared_circle_items_query(user).filter(Item.category_id == category_id)
    return _paginate_circle_items_query(items_query, item_type, page, per_page)
