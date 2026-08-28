"""Shared rules for who may view another user's profile.

``profile_access_reason`` is the single source of truth: ``main.user_profile``
enforces it, and every template that turns a name into a profile link asks it
first, so a link is only ever rendered when the click will work.  The single-user
checks it composes live on ``User`` (``shares_circle_with``,
``has_conversation_with`` and ``administers_pending_join_request_from``).

``viewable_profile_user_ids`` is the batched version used when rendering many
people at once — e.g. the home feed — and answers the same question with a fixed
number of queries.
"""

from sqlalchemy import select

from app import db
from app.models import CircleJoinRequest, ConversationParticipant, User, circle_members

PROFILE_ACCESS_SELF = "self"
PROFILE_ACCESS_ADMIN = "admin"
PROFILE_ACCESS_CIRCLE = "circle"
PROFILE_ACCESS_CONVERSATION = "conversation"
PROFILE_ACCESS_JOIN_REQUEST = "join_request"


def profile_access_reason(viewer, target_user):
    """Return why viewer may open target_user's profile, or None if they may not.

    Sharing a circle is the usual route in.  Sharing a conversation also grants
    access, in both directions, for as long as the conversation exists —
    borrowing, claiming a giveaway, and answering an item request all open one.
    A circle admin may also view someone with a pending request to join a circle
    they administer.
    """
    if not target_user:
        return None

    if viewer.id == target_user.id:
        return PROFILE_ACCESS_SELF

    if viewer.is_admin:
        return PROFILE_ACCESS_ADMIN

    if target_user.is_deleted:
        return None

    if viewer.shares_circle_with(target_user):
        return PROFILE_ACCESS_CIRCLE

    if viewer.has_conversation_with(target_user):
        return PROFILE_ACCESS_CONVERSATION

    if viewer.administers_pending_join_request_from(target_user):
        return PROFILE_ACCESS_JOIN_REQUEST

    return None


def can_view_profile(viewer, target_user):
    """Whether viewer may open target_user's profile page."""
    return profile_access_reason(viewer, target_user) is not None


def viewable_profile_user_ids(viewer, candidate_ids):
    """Return the subset of candidate_ids whose profiles viewer may open.

    Mirrors ``profile_access_reason``.  The viewer's own id is never included —
    callers decide separately whether to link a user to their own profile.

    Runs a fixed number of queries regardless of how many candidates there are.
    """
    candidates = {user_id for user_id in candidate_ids if user_id and user_id != viewer.id}
    if not candidates:
        return set()

    if viewer.is_admin:
        return candidates

    viewable = set()

    viewer_circle_ids = [circle.id for circle in viewer.circles]
    if viewer_circle_ids:
        viewable |= set(
            db.session.execute(
                select(circle_members.c.user_id)
                .where(
                    circle_members.c.circle_id.in_(viewer_circle_ids),
                    circle_members.c.user_id.in_(candidates),
                )
                .distinct()
            ).scalars()
        )

    remaining = candidates - viewable
    if remaining:
        viewer_conversation_ids = select(ConversationParticipant.conversation_id).where(
            ConversationParticipant.user_id == viewer.id
        )
        viewable |= set(
            db.session.execute(
                select(ConversationParticipant.user_id)
                .where(
                    ConversationParticipant.conversation_id.in_(viewer_conversation_ids),
                    ConversationParticipant.user_id.in_(remaining),
                )
                .distinct()
            ).scalars()
        )

    remaining = candidates - viewable
    if remaining:
        viewer_admin_circle_ids = select(circle_members.c.circle_id).where(
            circle_members.c.user_id == viewer.id,
            circle_members.c.is_admin.is_(True),
        )
        viewable |= set(
            db.session.execute(
                select(CircleJoinRequest.user_id)
                .where(
                    CircleJoinRequest.circle_id.in_(viewer_admin_circle_ids),
                    CircleJoinRequest.status == "pending",
                    CircleJoinRequest.user_id.in_(remaining),
                )
                .distinct()
            ).scalars()
        )

    if not viewable:
        return viewable

    deleted_ids = set(
        db.session.execute(
            select(User.id).where(User.id.in_(viewable), User.is_deleted.is_(True))
        ).scalars()
    )
    return viewable - deleted_ids
