from datetime import UTC, datetime, timedelta

from app import db
from app.utils.request_queries import (
    build_visible_requests_pagination,
    can_view_request,
    describe_seeking_mismatch,
)
from tests.factories import CircleFactory, ItemFactory, ItemRequestFactory, UserFactory


def test_can_view_request_allows_owner(app):
    with app.app_context():
        owner = UserFactory()
        item_request = ItemRequestFactory(user=owner, visibility="circles")

        assert can_view_request(item_request, owner) is True


def test_can_view_request_allows_public_request_for_other_user(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        item_request = ItemRequestFactory(user=owner, visibility="public")

        assert can_view_request(item_request, viewer) is True


def test_can_view_request_requires_shared_circle_for_circles_visibility(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        item_request = ItemRequestFactory(user=owner, visibility="circles")

        assert can_view_request(item_request, viewer) is False


def test_can_view_request_allows_shared_circle_member(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        circle = CircleFactory()
        circle.members.extend([viewer, owner])
        item_request = ItemRequestFactory(user=owner, visibility="circles")

        assert can_view_request(item_request, viewer) is True


def test_describe_seeking_mismatch_flags_loan_item_for_giveaway_request(app):
    with app.app_context():
        item_request = ItemRequestFactory(user=UserFactory(), seeking="giveaway")
        item = ItemFactory(owner=UserFactory(), is_giveaway=False)

        assert "asking for a giveaway" in describe_seeking_mismatch(item_request, item)


def test_describe_seeking_mismatch_flags_giveaway_for_loan_request(app):
    with app.app_context():
        item_request = ItemRequestFactory(user=UserFactory(), seeking="loan")
        item = ItemFactory(owner=UserFactory(), is_giveaway=True)

        assert "asking to borrow" in describe_seeking_mismatch(item_request, item)


def test_describe_seeking_mismatch_allows_matching_kinds(app):
    with app.app_context():
        owner = UserFactory()
        loan_request = ItemRequestFactory(user=owner, seeking="loan")
        giveaway_request = ItemRequestFactory(user=owner, seeking="giveaway")
        loan_item = ItemFactory(owner=owner, is_giveaway=False)
        giveaway_item = ItemFactory(owner=owner, is_giveaway=True)

        assert describe_seeking_mismatch(loan_request, loan_item) is None
        assert describe_seeking_mismatch(giveaway_request, giveaway_item) is None


def test_describe_seeking_mismatch_never_flags_either_requests(app):
    with app.app_context():
        owner = UserFactory()
        item_request = ItemRequestFactory(user=owner, seeking="either")

        assert describe_seeking_mismatch(item_request, ItemFactory(owner=owner)) is None
        assert (
            describe_seeking_mismatch(item_request, ItemFactory(owner=owner, is_giveaway=True))
            is None
        )


def test_build_visible_requests_pagination_pages_in_the_database_without_a_distance_cap(app):
    """With nothing to measure in Python the database does the slicing, so only
    the rows for the requested page come back."""
    with app.app_context():
        viewer = UserFactory(latitude=None, longitude=None)
        author = UserFactory(latitude=None, longitude=None)
        circle = CircleFactory()
        circle.members.extend([viewer, author])
        now = datetime.now(UTC)
        oldest = ItemRequestFactory(
            user=author, title="Oldest", visibility="public", created_at=now - timedelta(hours=2)
        )
        middle = ItemRequestFactory(
            user=author, title="Middle", visibility="public", created_at=now - timedelta(hours=1)
        )
        newest = ItemRequestFactory(
            user=author, title="Newest", visibility="public", created_at=now
        )
        db.session.commit()

        first_page = build_visible_requests_pagination(viewer, page=1, per_page=2)

        assert first_page.total == 3
        assert first_page.pages == 2
        assert [item_request.id for item_request in first_page.items] == [newest.id, middle.id]

        second_page = build_visible_requests_pagination(viewer, page=2, per_page=2)

        assert [item_request.id for item_request in second_page.items] == [oldest.id]


def test_build_visible_requests_pagination_counts_only_requests_within_the_distance_cap(app):
    with app.app_context():
        viewer = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
        near_author = UserFactory(latitude=40.7400, longitude=-74.0100)  # Nearby NYC
        far_author = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
        circle = CircleFactory()
        circle.members.extend([viewer, near_author, far_author])
        near_request = ItemRequestFactory(user=near_author, title="Nearby", visibility="public")
        ItemRequestFactory(user=far_author, title="Far", visibility="public")
        db.session.commit()

        pagination = build_visible_requests_pagination(
            viewer, distance=20, distance_explicit=True, page=1, per_page=10
        )

        assert pagination.total == 1
        assert [item_request.id for item_request in pagination.items] == [near_request.id]
        assert pagination.items[0].api_distance is not None


def test_build_visible_requests_pagination_annotates_distance_only_for_the_page(app):
    """The distance shown alongside a request is derived per page, so a request
    on a later page is left untouched until it is asked for."""
    with app.app_context():
        viewer = UserFactory(latitude=40.7128, longitude=-74.0060)  # NYC
        author = UserFactory(latitude=None, longitude=None)
        circle = CircleFactory()
        circle.members.extend([viewer, author])
        now = datetime.now(UTC)
        ItemRequestFactory(
            user=author, title="Older", visibility="public", created_at=now - timedelta(hours=1)
        )
        ItemRequestFactory(user=author, title="Newer", visibility="public", created_at=now)
        db.session.commit()

        pagination = build_visible_requests_pagination(
            viewer, distance=None, distance_explicit=True, page=1, per_page=1
        )

        assert pagination.total == 2
        assert len(pagination.items) == 1
        # The author has no coordinates, so there is no distance to report.
        assert pagination.items[0].api_distance is None


def test_build_visible_requests_pagination_is_empty_when_nothing_is_visible(app):
    with app.app_context():
        viewer = UserFactory()
        UserFactory()
        db.session.commit()

        pagination = build_visible_requests_pagination(viewer, scope="circles", page=1, per_page=10)

        assert pagination.total == 0
        assert pagination.items == []
