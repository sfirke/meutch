from datetime import UTC, datetime, timedelta

from app import db
from app.models import CircleJoinRequest, circle_members
from app.utils.circle_queries import (
    build_circle_recommendations,
    get_admin_circle_pending_counts,
    get_circle_member_activity_counts,
    get_listed_circles,
    get_ordered_circle_members,
    should_show_circle_members,
)
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ItemFactory,
    ItemRequestFactory,
    UserFactory,
)


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
                user_id=early_member.id,
                circle_id=circle.id,
                joined_at=now - timedelta(days=2),
                is_admin=False,
            )
        )
        db.session.execute(
            circle_members.insert().values(
                user_id=later_member.id,
                circle_id=circle.id,
                joined_at=now - timedelta(days=1),
                is_admin=False,
            )
        )
        db.session.execute(
            circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=now,
                is_admin=True,
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


def test_get_circle_member_activity_counts_counts_active_member_content_across_visibility_scopes(
    app,
):
    with app.app_context():
        category = CategoryFactory()
        owner = UserFactory()
        vacation_owner = UserFactory(vacation_mode=True)
        circle = CircleFactory()
        circle.members.extend([owner, vacation_owner])

        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )
        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )
        ItemFactory(
            owner=vacation_owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )
        ItemFactory(owner=owner, category=category, available=True, is_giveaway=False)

        ItemRequestFactory(user=owner, visibility="public", status="open")
        ItemRequestFactory(user=owner, visibility="circles", status="open")
        ItemRequestFactory(user=vacation_owner, visibility="public", status="open")
        ItemRequestFactory(user=owner, visibility="public", status="deleted")
        db.session.commit()

        counts = get_circle_member_activity_counts(circle)

        assert counts == {
            "borrowable_items": 1,
            "giveaways": 2,
            "requests": 2,
        }


def test_build_circle_recommendations_prioritizes_distance_tiers_then_membership(app):
    with app.app_context():
        viewer = UserFactory(latitude=40.7128, longitude=-74.0060)

        block_closed = CircleFactory(circle_type="closed", latitude=40.7190, longitude=-74.0060)
        one_to_two_large = CircleFactory(circle_type="closed", latitude=40.7320, longitude=-74.0060)
        one_to_two_small = CircleFactory(circle_type="open", latitude=40.7300, longitude=-74.0060)

        block_closed.members.append(UserFactory())
        one_to_two_large.members.extend(
            [UserFactory(), UserFactory(), UserFactory(), UserFactory()]
        )
        one_to_two_small.members.extend([UserFactory(), UserFactory()])
        db.session.commit()

        recommendations = build_circle_recommendations(
            viewer,
            circles=[one_to_two_small, one_to_two_large, block_closed],
            limit=3,
        )

        assert [recommendation["circle"].id for recommendation in recommendations] == [
            block_closed.id,
            one_to_two_large.id,
            one_to_two_small.id,
        ]


def test_build_circle_recommendations_uses_total_member_activity_for_display(app):
    with app.app_context():
        viewer = UserFactory()
        category = CategoryFactory()
        owner = UserFactory()
        circle = CircleFactory()
        circle.members.extend([owner, UserFactory()])

        ItemFactory(owner=owner, category=category, available=True, is_giveaway=False)
        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )
        ItemFactory(
            owner=owner,
            category=category,
            available=True,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )
        ItemRequestFactory(user=owner, visibility="public", status="open")
        db.session.commit()

        recommendation = build_circle_recommendations(viewer, circles=[circle], limit=1)[0]

        assert recommendation["member_activity_counts"] == {
            "borrowable_items": 1,
            "giveaways": 2,
            "requests": 1,
        }
        assert (
            recommendation["visible_display_text"]
            == "1 borrowable item, 2 giveaways, and 1 request"
        )
