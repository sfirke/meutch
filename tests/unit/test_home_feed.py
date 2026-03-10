from datetime import date

from app import db
from app.models import LoanRequest
from app.utils.home_feed import (
    build_recent_lent_events,
    build_visible_requests_events,
    build_visible_giveaway_events,
    consolidate_circle_join_activity,
)
from tests.factories import CategoryFactory, CircleFactory, ItemFactory, UserFactory, ItemRequestFactory


def test_consolidate_circle_join_activity_merges_by_user():
    join_rows = [
        {
            'user_id': 'user-1',
            'user_name': 'Alex Doe',
            'circle_id': 'circle-large',
            'circle_name': 'Large Circle',
            'created_at': None,
        },
        {
            'user_id': 'user-1',
            'user_name': 'Alex Doe',
            'circle_id': 'circle-small',
            'circle_name': 'Small Circle',
            'created_at': None,
        },
    ]
    circle_sizes = {
        'circle-large': 9,
        'circle-small': 3,
    }

    events = consolidate_circle_join_activity(join_rows, circle_sizes)

    assert len(events) == 1
    assert events[0]['circle_id'] == 'circle-small'
    assert events[0]['extra_circle_count'] == 1
    assert ' + 1 more of your circles' in events[0]['title']


def test_build_visible_giveaway_events_defaults_to_20_miles(app):
    with app.app_context():
        viewer = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
        near_owner = UserFactory(latitude=40.7400, longitude=-74.0100)  # Nearby NYC
        far_owner = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
        category = CategoryFactory()
        circle = CircleFactory()
        circle.members.extend([viewer, near_owner, far_owner])

        near_item = ItemFactory(
            owner=near_owner,
            category=category,
            is_giveaway=True,
            giveaway_visibility='default',
            claim_status='unclaimed',
            name='Nearby Giveaway',
        )
        far_item = ItemFactory(
            owner=far_owner,
            category=category,
            is_giveaway=True,
            giveaway_visibility='default',
            claim_status='unclaimed',
            name='Far Giveaway',
        )
        db.session.commit()

        scoped_circle_ids = {circle.id}

        default_events = build_visible_giveaway_events(
            viewer,
            scoped_circle_ids=scoped_circle_ids,
            max_distance=None,
            distance_explicit=False,
        )
        default_item_ids = {event['item_id'] for event in default_events}

        explicit_no_distance_events = build_visible_giveaway_events(
            viewer,
            scoped_circle_ids=scoped_circle_ids,
            max_distance=None,
            distance_explicit=True,
        )
        explicit_item_ids = {event['item_id'] for event in explicit_no_distance_events}

        assert near_item.id in default_item_ids
        assert far_item.id not in default_item_ids
        assert near_item.id in explicit_item_ids
        assert far_item.id in explicit_item_ids


def test_build_recent_lent_events_hides_borrower_identity(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        borrower = UserFactory(first_name='VeryUniqueBorrower', last_name='Name')
        category = CategoryFactory()
        circle = CircleFactory()
        circle.members.extend([viewer, owner, borrower])

        item = ItemFactory(owner=owner, category=category, name='Shared Drill')
        loan = LoanRequest(
            item_id=item.id,
            borrower_id=borrower.id,
            start_date=date.today(),
            end_date=date.today(),
            status='approved',
        )
        db.session.add(loan)
        db.session.commit()

        events = build_recent_lent_events(viewer, scoped_circle_ids={circle.id})

        assert len(events) == 1
        event = events[0]
        assert event['event_type'] == 'lent'
        assert 'borrower_name' not in event
        assert 'VeryUniqueBorrower' not in event['actor_name']


def test_build_visible_requests_events_defaults_to_20_miles_for_geocoded_user(app):
    with app.app_context():
        viewer = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
        near_requester = UserFactory(latitude=40.7400, longitude=-74.0100)  # Nearby NYC
        far_requester = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
        circle = CircleFactory()
        circle.members.extend([viewer, near_requester, far_requester])

        near_request = ItemRequestFactory(user=near_requester, title='Nearby Request', visibility='public')
        far_request = ItemRequestFactory(user=far_requester, title='Far Request', visibility='public')
        db.session.commit()

        scoped_circle_ids = {circle.id}

        default_events = build_visible_requests_events(
            viewer,
            scoped_circle_ids=scoped_circle_ids,
            scope='all',
            max_distance=None,
            distance_explicit=False,
        )
        default_request_ids = {event['request_id'] for event in default_events}

        explicit_no_distance_events = build_visible_requests_events(
            viewer,
            scoped_circle_ids=scoped_circle_ids,
            scope='all',
            max_distance=None,
            distance_explicit=True,
        )
        explicit_request_ids = {event['request_id'] for event in explicit_no_distance_events}

        assert near_request.id in default_request_ids
        assert far_request.id not in default_request_ids
        assert near_request.id in explicit_request_ids
        assert far_request.id in explicit_request_ids
