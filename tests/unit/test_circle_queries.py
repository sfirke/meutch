from datetime import UTC, datetime, timedelta

from app import db
from app.models import CircleJoinRequest, circle_members
from app.utils.circle_queries import (
    get_admin_circle_pending_counts,
    get_listed_circles,
    get_ordered_circle_members,
    should_show_circle_members,
)
from tests.factories import CircleFactory, UserFactory


def test_get_admin_circle_pending_counts_only_counts_pending_admin_circles(app):
    with app.app_context():
        admin = UserFactory()
        member = UserFactory()
        requester = UserFactory()
        admin_circle = CircleFactory()
        other_circle = CircleFactory()

        db.session.execute(
            circle_members.insert().values(
                user_id=admin.id,
                circle_id=admin_circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True,
            )
        )
        db.session.execute(
            circle_members.insert().values(
                user_id=admin.id,
                circle_id=other_circle.id,
                joined_at=datetime.now(UTC),
                is_admin=False,
            )
        )
        db.session.add(
            CircleJoinRequest(circle_id=admin_circle.id, user_id=requester.id, status="pending")
        )
        db.session.add(
            CircleJoinRequest(circle_id=admin_circle.id, user_id=member.id, status="approved")
        )
        db.session.add(
            CircleJoinRequest(circle_id=other_circle.id, user_id=UserFactory().id, status="pending")
        )
        db.session.commit()

        counts = get_admin_circle_pending_counts(admin.id)

        assert counts == {str(admin_circle.id): 1}


def test_should_show_circle_members_requires_membership_for_closed_circle(app):
    with app.app_context():
        member = UserFactory()
        outsider = UserFactory()
        closed_circle = CircleFactory(circle_type="closed")
        open_circle = CircleFactory(circle_type="open")
        closed_circle.members.append(member)
        db.session.commit()

        assert should_show_circle_members(closed_circle, outsider) is False
        assert should_show_circle_members(closed_circle, member) is True
        assert should_show_circle_members(open_circle, outsider) is True


def test_get_ordered_circle_members_sorts_admins_first_then_joined_at(app):
    with app.app_context():
        circle = CircleFactory()
        admin = UserFactory()
        early_member = UserFactory()
        later_member = UserFactory()
        now = datetime.now(UTC)

        db.session.execute(
            circle_members.insert().values(
                user_id=later_member.id,
                circle_id=circle.id,
                joined_at=now,
                is_admin=False,
            )
        )
        db.session.execute(
            circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=now - timedelta(days=2),
                is_admin=True,
            )
        )
        db.session.execute(
            circle_members.insert().values(
                user_id=early_member.id,
                circle_id=circle.id,
                joined_at=now - timedelta(days=1),
                is_admin=False,
            )
        )
        db.session.commit()

        ordered_members = get_ordered_circle_members(circle.id)

        assert [member.User.id for member in ordered_members] == [
            admin.id,
            early_member.id,
            later_member.id,
        ]


def test_get_listed_circles_excludes_secret_and_sorts_by_membership(app):
    with app.app_context():
        viewer = UserFactory()
        large_circle = CircleFactory(circle_type="open")
        small_circle = CircleFactory(circle_type="closed")
        secret_circle = CircleFactory(circle_type="secret")
        large_circle.members.extend([UserFactory(), UserFactory(), UserFactory()])
        small_circle.members.append(UserFactory())
        db.session.commit()

        circles = get_listed_circles(viewer)

        assert [circle.id for circle in circles] == [large_circle.id, small_circle.id]
        assert secret_circle.id not in {circle.id for circle in circles}
