"""Unit tests for batched profile-visibility rules."""

from app import db
from app.utils.profile_visibility import viewable_profile_user_ids
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    UserFactory,
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
