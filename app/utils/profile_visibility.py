"""Shared rules for who may view another user's profile.

The single-user checks live on ``User`` (``shares_circle_with`` and
``has_conversation_with``).  This module adds the batched version used when
rendering many people at once — e.g. the home feed — so a name is only turned
into a profile link when the viewer can actually open that profile.
"""

from sqlalchemy import select

from app import db
from app.models import ConversationParticipant, User, circle_members


def viewable_profile_user_ids(viewer, candidate_ids):
    """Return the subset of candidate_ids whose profiles viewer may open.

    Mirrors the access rules enforced by ``main.user_profile``: a shared circle
    or a shared conversation, and never a deleted account.  The viewer's own id
    is never included — callers decide separately whether to link a user to
    their own profile.

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

    if not viewable:
        return viewable

    deleted_ids = set(
        db.session.execute(
            select(User.id).where(User.id.in_(viewable), User.is_deleted.is_(True))
        ).scalars()
    )
    return viewable - deleted_ids
