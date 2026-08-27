"""Unit tests for the shared profile-visibility rules."""

from datetime import UTC, datetime

from app import db
from app.models import circle_members
from app.utils.profile_visibility import (
    PROFILE_ACCESS_ADMIN,
    PROFILE_ACCESS_CIRCLE,
    PROFILE_ACCESS_CONVERSATION,
    PROFILE_ACCESS_JOIN_REQUEST,
    PROFILE_ACCESS_SELF,
    can_view_profile,
    profile_access_reason,
    viewable_profile_user_ids,
)
from tests.factories import (
    CircleFactory,
    CircleJoinRequestFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    UserFactory,
)


def _admin_of(circle, user):
    """Make user an admin member of circle."""
    db.session.execute(
        circle_members.insert().values(
            user_id=user.id,
            circle_id=circle.id,
            joined_at=datetime.now(UTC),
            is_admin=True,
        )
    )


def _conversation_between(user_a, user_b):
    conversation = ConversationFactory()
    ConversationParticipantFactory(conversation=conversation, user=user_a)
    ConversationParticipantFactory(conversation=conversation, user=user_b)
    return conversation


def test_viewable_ids_includes_circle_mates_and_excludes_strangers(app):
    with app.app_context():
        viewer = UserFactory()
        circle_mate = UserFactory()
        stranger = UserFactory()
        circle = CircleFactory()
        circle.members.extend([viewer, circle_mate])
        db.session.commit()

        viewable = viewable_profile_user_ids(viewer, [circle_mate.id, stranger.id])

        assert viewable == {circle_mate.id}


def test_viewable_ids_includes_conversation_partners_in_both_directions(app):
    with app.app_context():
        viewer = UserFactory()
        partner = UserFactory()
        stranger = UserFactory()
        _conversation_between(viewer, partner)
        db.session.commit()

        assert viewable_profile_user_ids(viewer, [partner.id, stranger.id]) == {partner.id}
        assert viewable_profile_user_ids(partner, [viewer.id, stranger.id]) == {viewer.id}


def test_viewable_ids_ignores_conversations_the_viewer_is_not_in(app):
    with app.app_context():
        viewer = UserFactory()
        other_a = UserFactory()
        other_b = UserFactory()
        _conversation_between(other_a, other_b)
        db.session.commit()

        assert viewable_profile_user_ids(viewer, [other_a.id, other_b.id]) == set()


def test_viewable_ids_skips_viewer_deleted_users_and_blanks(app):
    with app.app_context():
        viewer = UserFactory()
        deleted_mate = UserFactory(is_deleted=True)
        circle = CircleFactory()
        circle.members.extend([viewer, deleted_mate])
        db.session.commit()

        viewable = viewable_profile_user_ids(viewer, [viewer.id, deleted_mate.id, None])

        assert viewable == set()


def test_viewable_ids_returns_all_candidates_for_admin(app):
    with app.app_context():
        admin = UserFactory(is_admin=True)
        stranger = UserFactory()
        db.session.commit()

        assert viewable_profile_user_ids(admin, [stranger.id]) == {stranger.id}


def test_viewable_ids_includes_pending_join_requesters_to_administered_circles(app):
    with app.app_context():
        admin = UserFactory()
        requester = UserFactory()
        stranger = UserFactory()
        circle = CircleFactory()
        _admin_of(circle, admin)
        CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
        db.session.commit()

        viewable = viewable_profile_user_ids(admin, [requester.id, stranger.id])

        assert viewable == {requester.id}


def test_viewable_ids_excludes_join_requesters_for_plain_members(app):
    with app.app_context():
        member = UserFactory()
        requester = UserFactory()
        circle = CircleFactory()
        circle.members.append(member)
        CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
        db.session.commit()

        assert viewable_profile_user_ids(member, [requester.id]) == set()


def test_viewable_ids_excludes_settled_join_requests(app):
    with app.app_context():
        admin = UserFactory()
        approved = UserFactory()
        rejected = UserFactory()
        circle = CircleFactory()
        _admin_of(circle, admin)
        CircleJoinRequestFactory(circle=circle, user=approved, status="approved")
        CircleJoinRequestFactory(circle=circle, user=rejected, status="rejected")
        db.session.commit()

        assert viewable_profile_user_ids(admin, [approved.id, rejected.id]) == set()


def test_access_reason_for_self_and_admin(app):
    with app.app_context():
        viewer = UserFactory()
        site_admin = UserFactory(is_admin=True)
        stranger = UserFactory()
        db.session.commit()

        assert profile_access_reason(viewer, viewer) == PROFILE_ACCESS_SELF
        assert profile_access_reason(site_admin, stranger) == PROFILE_ACCESS_ADMIN


def test_access_reason_reports_circle_conversation_and_join_request(app):
    with app.app_context():
        viewer = UserFactory()
        circle_mate = UserFactory()
        partner = UserFactory()
        requester = UserFactory()

        shared_circle = CircleFactory()
        shared_circle.members.extend([viewer, circle_mate])

        administered_circle = CircleFactory()
        _admin_of(administered_circle, viewer)
        CircleJoinRequestFactory(circle=administered_circle, user=requester, status="pending")

        _conversation_between(viewer, partner)
        db.session.commit()

        assert profile_access_reason(viewer, circle_mate) == PROFILE_ACCESS_CIRCLE
        assert profile_access_reason(viewer, partner) == PROFILE_ACCESS_CONVERSATION
        assert profile_access_reason(viewer, requester) == PROFILE_ACCESS_JOIN_REQUEST


def test_access_reason_is_none_for_strangers_deleted_users_and_missing_users(app):
    with app.app_context():
        viewer = UserFactory()
        stranger = UserFactory()
        deleted_mate = UserFactory(is_deleted=True)
        circle = CircleFactory()
        circle.members.extend([viewer, deleted_mate])
        db.session.commit()

        assert profile_access_reason(viewer, stranger) is None
        assert profile_access_reason(viewer, deleted_mate) is None
        assert profile_access_reason(viewer, None) is None
        assert not can_view_profile(viewer, stranger)
        assert can_view_profile(viewer, viewer)
