from datetime import datetime, UTC, timedelta
from sqlalchemy import and_, func, or_, select
from app import db
from app.models import Circle, CircleJoinRequest, Item, ItemRequest, LoanRequest, User, circle_members
from app.utils.geocoding import format_distance


DEFAULT_GIVEAWAY_DISTANCE_MILES = 20
HOMEPAGE_FEED_EVENT_TYPES = {'requests', 'giveaways', 'loans', 'circle_joins'}


def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _get_scoped_circle_ids(user, selected_circle_ids=None):
    user_circle_ids = {circle.id for circle in user.circles}
    if not selected_circle_ids:
        return user_circle_ids
    selected_set = {str(circle_id) for circle_id in selected_circle_ids if circle_id}
    return {circle_id for circle_id in user_circle_ids if str(circle_id) in selected_set}


def _shared_circle_user_ids_query(scoped_circle_ids):
    if not scoped_circle_ids:
        return None
    return select(circle_members.c.user_id).where(
        circle_members.c.circle_id.in_(scoped_circle_ids)
    ).distinct()


def _effective_giveaway_distance(max_distance, distance_explicit):
    if distance_explicit:
        return max_distance
    if max_distance is not None:
        return max_distance
    return DEFAULT_GIVEAWAY_DISTANCE_MILES


def _normalize_scope(scope):
    return 'circles' if scope == 'circles' else 'all'


def _normalize_event_types(included_event_types):
    if included_event_types is None:
        return HOMEPAGE_FEED_EVENT_TYPES

    normalized = set()
    for event_type in included_event_types:
        if event_type in HOMEPAGE_FEED_EVENT_TYPES:
            normalized.add(event_type)
    return normalized


def _within_time_window(event_time, since=None, until=None):
    event_time_utc = _utc(event_time)
    since_utc = _utc(since)
    until_utc = _utc(until)

    if event_time_utc is None:
        return False
    if since_utc is not None and event_time_utc < since_utc:
        return False
    if until_utc is not None and event_time_utc > until_utc:
        return False
    return True


def _distance_filter_items(items, user, max_distance):
    if max_distance is None or not user.is_geocoded:
        return list(items)

    filtered = []
    for item in items:
        if not item.owner or not item.owner.is_geocoded:
            filtered.append(item)
            continue
        distance = user.distance_to(item.owner)
        if distance is not None and distance <= max_distance:
            filtered.append(item)
    return filtered


def _distance_filter_requests(item_requests, user, max_distance):
    if max_distance is None or not user.is_geocoded:
        return list(item_requests)

    filtered = []
    for item_request in item_requests:
        if not item_request.user or not item_request.user.is_geocoded:
            filtered.append(item_request)
            continue
        distance = user.distance_to(item_request.user)
        if distance is not None and distance <= max_distance:
            filtered.append(item_request)
    return filtered


def build_visible_requests_events(
    user,
    scoped_circle_ids=None,
    scope='all',
    max_distance=None,
    distance_explicit=False,
    since=None,
    until=None,
):
    now = datetime.now(UTC)
    fulfilled_cutoff = _utc(since) or (now - timedelta(days=7))
    until_utc = _utc(until)
    shared_circle_user_ids = _shared_circle_user_ids_query(scoped_circle_ids)
    normalized_scope = _normalize_scope(scope)

    base_query = ItemRequest.query.join(User, ItemRequest.user_id == User.id).filter(
        ItemRequest.user_id != user.id,
        User.is_deleted == False,
        User.vacation_mode == False,
        or_(
            and_(
                ItemRequest.status == 'open',
                ItemRequest.expires_at > now,
            ),
            and_(
                ItemRequest.status == 'fulfilled',
                ItemRequest.fulfilled_at > fulfilled_cutoff,
            ),
        ),
    )

    if until_utc is not None:
        base_query = base_query.filter(ItemRequest.created_at <= until_utc)

    if normalized_scope == 'circles':
        if shared_circle_user_ids is None:
            return []
        base_query = base_query.filter(ItemRequest.user_id.in_(shared_circle_user_ids))
    else:
        if shared_circle_user_ids is None:
            base_query = base_query.filter(ItemRequest.visibility == 'public')
        else:
            base_query = base_query.filter(
                or_(
                    ItemRequest.visibility == 'public',
                    and_(
                        ItemRequest.visibility == 'circles',
                        ItemRequest.user_id.in_(shared_circle_user_ids),
                    ),
                )
            )

    visible_requests = base_query.order_by(ItemRequest.created_at.desc()).all()
    effective_distance = _effective_giveaway_distance(max_distance, distance_explicit)
    visible_requests = _distance_filter_requests(visible_requests, user, effective_distance)

    events = []
    for item_request in visible_requests:
        event_time = _utc(item_request.fulfilled_at) if item_request.status == 'fulfilled' else _utc(item_request.created_at)
        if not _within_time_window(event_time, since=since, until=until):
            continue
        distance = None
        if user.is_geocoded and item_request.user and item_request.user.is_geocoded:
            raw = user.distance_to(item_request.user)
            distance = format_distance(raw) if raw is not None else None
        events.append({
            'event_type': 'request',
            'created_at': event_time,
            'request_id': item_request.id,
            'title': item_request.title,
            'description': item_request.description,
            'status': item_request.status,
            'actor_name': item_request.user.full_name if item_request.user else 'Deleted User',
            'actor_avatar_url': item_request.user.profile_image_url if item_request.user else None,
            'image_url': None,
            'action': 'requested',
            'visibility': item_request.visibility,
            'distance': distance,
        })
    return events


def build_visible_giveaway_events(
    user,
    scoped_circle_ids=None,
    scope='all',
    max_distance=None,
    distance_explicit=False,
    since=None,
    until=None,
):
    if not scoped_circle_ids:
        return []

    shared_circle_user_ids = _shared_circle_user_ids_query(scoped_circle_ids)
    all_circle_user_ids = select(circle_members.c.user_id).distinct()
    normalized_scope = _normalize_scope(scope)

    if normalized_scope == 'circles':
        visibility_filter = Item.owner_id.in_(shared_circle_user_ids)
    else:
        visibility_filter = or_(
            and_(
                or_(Item.giveaway_visibility == 'default', Item.giveaway_visibility.is_(None)),
                Item.owner_id.in_(shared_circle_user_ids),
            ),
            and_(
                Item.giveaway_visibility == 'public',
                Item.owner_id.in_(all_circle_user_ids),
            ),
        )

    base_query = Item.query.join(User, Item.owner_id == User.id).filter(
        Item.is_giveaway == True,
        User.vacation_mode == False,
        and_(
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None)),
            visibility_filter,
            Item.owner_id != user.id,
        ),
    )

    if _utc(until) is not None:
        base_query = base_query.filter(Item.created_at <= _utc(until))

    giveaway_items = base_query.order_by(Item.created_at.desc()).all()
    effective_distance = _effective_giveaway_distance(max_distance, distance_explicit)
    giveaway_items = _distance_filter_items(giveaway_items, user, effective_distance)

    events = []
    for item in giveaway_items:
        event_time = _utc(item.created_at)
        if not _within_time_window(event_time, since=since, until=until):
            continue
        distance = None
        if user.is_geocoded and item.owner and item.owner.is_geocoded:
            raw = user.distance_to(item.owner)
            distance = format_distance(raw) if raw is not None else None
        events.append({
            'event_type': 'giveaway',
            'created_at': event_time,
            'item_id': item.id,
            'title': item.name,
            'description': item.description,
            'actor_name': item.owner.full_name if item.owner else 'Deleted User',
            'actor_avatar_url': item.owner.profile_image_url if item.owner else None,
            'image_url': item.image_url,
            'action': 'posted a giveaway',
            'distance': distance,
        })
    return events


def build_recent_lent_events(user, scoped_circle_ids=None, days=30, since=None, until=None):
    if not scoped_circle_ids:
        return []

    recent_cutoff = _utc(since) or (datetime.now(UTC) - timedelta(days=days))
    until_utc = _utc(until)
    shared_circle_user_ids = _shared_circle_user_ids_query(scoped_circle_ids)

    base_query = LoanRequest.query.join(Item, LoanRequest.item_id == Item.id).join(User, Item.owner_id == User.id).filter(
        LoanRequest.status == 'approved',
        LoanRequest.borrower_id.isnot(None),
        LoanRequest.created_at >= recent_cutoff,
        Item.owner_id != user.id,
        User.vacation_mode == False,
        Item.owner_id.in_(shared_circle_user_ids),
    )

    if until_utc is not None:
        base_query = base_query.filter(LoanRequest.created_at <= until_utc)

    loans = base_query.order_by(LoanRequest.created_at.desc()).all()

    events = []
    for loan in loans:
        item = loan.item
        if not item:
            continue
        if not _within_time_window(loan.created_at, since=since, until=until):
            continue
        owner_name = item.owner.full_name if item.owner else 'Deleted User'
        events.append({
            'event_type': 'lent',
            'created_at': _utc(loan.created_at),
            'loan_request_id': loan.id,
            'item_id': item.id,
            'title': item.name,
            'description': item.description,
            'actor_name': owner_name,
            'actor_avatar_url': item.owner.profile_image_url if item.owner else None,
            'image_url': item.image_url,
            'action': 'lent out',
        })
    return events


def consolidate_circle_join_activity(join_rows, circle_sizes):
    grouped = {}
    for row in join_rows:
        grouped.setdefault(row['user_id'], []).append(row)

    events = []
    for user_rows in grouped.values():
        user_rows.sort(key=lambda entry: (
            circle_sizes.get(entry['circle_id'], float('inf')),
            (entry['circle_name'] or '').lower(),
        ))
        primary_circle = user_rows[0]
        extra_count = len(user_rows) - 1

        if extra_count > 0:
            action = "joined"
            title = f"{primary_circle['circle_name']} + {extra_count} more of your circles"
        else:
            action = "joined"
            title = primary_circle['circle_name']

        events.append({
            'event_type': 'circle_join',
            'created_at': primary_circle['created_at'],
            'user_id': primary_circle['user_id'],
            'actor_name': primary_circle['user_name'],
            'actor_avatar_url': primary_circle.get('user_avatar_url'),
            'image_url': primary_circle.get('circle_image_url'),
            'circle_id': primary_circle['circle_id'],
            'title': title,
            'description': None,
            'extra_circle_count': extra_count,
            'action': action,
        })

    return events


def build_circle_join_events(user, scoped_circle_ids=None, days=30, since=None, until=None):
    if not scoped_circle_ids:
        return []

    recent_cutoff = _utc(since) or (datetime.now(UTC) - timedelta(days=days))
    until_utc = _utc(until)
    base_query = db.session.query(CircleJoinRequest).join(User, CircleJoinRequest.user_id == User.id).join(
        Circle, CircleJoinRequest.circle_id == Circle.id
    ).filter(
        CircleJoinRequest.status == 'approved',
        CircleJoinRequest.created_at >= recent_cutoff,
        CircleJoinRequest.user_id != user.id,
        CircleJoinRequest.circle_id.in_(scoped_circle_ids),
        User.is_deleted == False,
    )

    if until_utc is not None:
        base_query = base_query.filter(CircleJoinRequest.created_at <= until_utc)

    join_requests = base_query.all()

    if not join_requests:
        return []

    circle_sizes_query = db.session.query(
        circle_members.c.circle_id,
        func.count(circle_members.c.user_id),
    ).filter(
        circle_members.c.circle_id.in_(scoped_circle_ids),
    ).group_by(circle_members.c.circle_id).all()
    circle_sizes = {circle_id: size for circle_id, size in circle_sizes_query}

    join_rows = []
    for join_request in join_requests:
        if not _within_time_window(join_request.created_at, since=since, until=until):
            continue
        join_rows.append({
            'user_id': join_request.user_id,
            'user_name': join_request.user.full_name if join_request.user else 'Deleted User',
            'user_avatar_url': join_request.user.profile_image_url if join_request.user else None,
            'circle_id': join_request.circle_id,
            'circle_name': join_request.circle.name if join_request.circle else 'Unknown Circle',
            'circle_image_url': join_request.circle.image_url if join_request.circle else None,
            'created_at': _utc(join_request.created_at),
        })

    return consolidate_circle_join_activity(join_rows, circle_sizes)


def _assemble_feed_events(
    user,
    selected_circle_ids=None,
    request_scope='all',
    giveaway_scope='all',
    giveaway_distance=None,
    giveaway_distance_explicit=False,
    included_event_types=None,
    since=None,
    until=None,
    max_events=100,
):
    scoped_circle_ids = _get_scoped_circle_ids(user, selected_circle_ids)
    normalized_event_types = _normalize_event_types(included_event_types)

    events = []
    if 'requests' in normalized_event_types:
        events.extend(
            build_visible_requests_events(
                user,
                scoped_circle_ids=scoped_circle_ids,
                scope=request_scope,
                max_distance=giveaway_distance,
                distance_explicit=giveaway_distance_explicit,
                since=since,
                until=until,
            )
        )
    if 'giveaways' in normalized_event_types:
        events.extend(
            build_visible_giveaway_events(
                user,
                scoped_circle_ids=scoped_circle_ids,
                scope=giveaway_scope,
                max_distance=giveaway_distance,
                distance_explicit=giveaway_distance_explicit,
                since=since,
                until=until,
            )
        )
    if 'loans' in normalized_event_types:
        events.extend(
            build_recent_lent_events(
                user,
                scoped_circle_ids=scoped_circle_ids,
                since=since,
                until=until,
            )
        )
    if 'circle_joins' in normalized_event_types:
        events.extend(
            build_circle_join_events(
                user,
                scoped_circle_ids=scoped_circle_ids,
                since=since,
                until=until,
            )
        )

    events.sort(key=lambda event: event.get('created_at') or datetime.min.replace(tzinfo=UTC), reverse=True)
    return events[:max_events]


def build_homepage_feed_events(
    user,
    selected_circle_ids=None,
    scope='all',
    giveaway_distance=None,
    giveaway_distance_explicit=False,
    included_event_types=None,
    max_events=100,
):
    return _assemble_feed_events(
        user,
        selected_circle_ids=selected_circle_ids,
        request_scope=scope,
        giveaway_scope=scope,
        giveaway_distance=giveaway_distance,
        giveaway_distance_explicit=giveaway_distance_explicit,
        included_event_types=included_event_types,
        max_events=max_events,
    )


def _digest_included_event_types(user):
    included = []
    if user.digest_include_requests:
        included.append('requests')
    if user.digest_include_giveaways:
        included.append('giveaways')
    if user.digest_include_circle_joins:
        included.append('circle_joins')
    if user.digest_include_loans:
        included.append('loans')
    return included


def build_digest_payload(user, since=None, until=None, max_events=200):
    window_end = _utc(until) or datetime.now(UTC)
    window_start = _utc(since) or _utc(user.digest_last_sent_at) or (window_end - timedelta(days=7))

    included_event_types = _digest_included_event_types(user)
    events = _assemble_feed_events(
        user,
        selected_circle_ids=None,
        request_scope='all' if user.digest_requests_include_public else 'circles',
        giveaway_scope='all' if user.digest_giveaways_include_public else 'circles',
        giveaway_distance=user.digest_radius_miles,
        giveaway_distance_explicit=True,
        included_event_types=included_event_types,
        since=window_start,
        until=window_end,
        max_events=max_events,
    )

    giveaways = [event for event in events if event.get('event_type') == 'giveaway']
    requests = [event for event in events if event.get('event_type') == 'request']
    circle_joins = [event for event in events if event.get('event_type') == 'circle_join']
    loans = [event for event in events if event.get('event_type') == 'lent']

    return {
        'window_start': window_start,
        'window_end': window_end,
        'events': events,
        'giveaways': giveaways,
        'requests': requests,
        'circle_joins': circle_joins,
        'loans': loans,
        'summary_stats': {
            'total_new_items': len(giveaways) + len(requests),
            'giveaways_count': len(giveaways),
            'borrow_requests_count': len(requests),
        },
    }