from app.utils.request_queries import can_view_request
from tests.factories import CircleFactory, ItemRequestFactory, UserFactory


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
