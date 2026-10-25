from app.utils.request_queries import can_view_request, describe_seeking_mismatch
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
