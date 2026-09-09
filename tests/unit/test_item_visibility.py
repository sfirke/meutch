"""Unit tests for the shared item-detail visibility rules."""

from app import db
from app.utils.item_share import generate_item_share_token
from app.utils.item_visibility import build_item_access_state
from tests.factories import (
    CircleFactory,
    GiveawayInterestFactory,
    ItemFactory,
    LoanRequestFactory,
    UserFactory,
)


def _circle_mates():
    """Return two users who share a circle."""
    owner = UserFactory()
    viewer = UserFactory()
    circle = CircleFactory()
    circle.members.extend([owner, viewer])
    db.session.flush()
    return owner, viewer


def test_owner_can_always_view_own_item(app):
    with app.app_context():
        owner = UserFactory()
        item = ItemFactory(owner=owner, is_giveaway=True, giveaway_visibility="default")

        state = build_item_access_state(item, owner)

        assert state["can_view"] is True
        assert state["is_owner"] is True


def test_circles_only_giveaway_hidden_from_stranger(app):
    with app.app_context():
        owner = UserFactory()
        stranger = UserFactory()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )

        state = build_item_access_state(item, stranger)

        assert state["can_view"] is False
        # Not the claimed-giveaway dead end -- a stranger simply has no access.
        assert state["claimed_unavailable"] is False


def test_circles_only_giveaway_visible_to_circle_mate(app):
    with app.app_context():
        owner, viewer = _circle_mates()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )

        state = build_item_access_state(item, viewer)

        assert state["can_view"] is True
        assert state["shares_circle_with_owner"] is True


def test_public_giveaway_visible_to_stranger(app):
    with app.app_context():
        owner = UserFactory()
        stranger = UserFactory()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )

        assert build_item_access_state(item, stranger)["can_view"] is True


def test_selected_recipient_keeps_access_during_pickup(app):
    """The chosen recipient can still open the item while the handoff is pending."""
    with app.app_context():
        owner = UserFactory()
        recipient = UserFactory()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="pending_pickup",
            claimed_by_id=recipient.id,
        )

        assert build_item_access_state(item, recipient)["can_view"] is True


def test_interested_user_keeps_access_without_a_shared_circle(app):
    """Interest survives leaving the circle, or the owner switching to circles only."""
    with app.app_context():
        owner = UserFactory()
        interested = UserFactory()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )
        GiveawayInterestFactory(item=item, user=interested, status="active")

        assert build_item_access_state(item, interested)["can_view"] is True


def test_claimed_giveaway_hidden_from_outsiders(app):
    with app.app_context():
        owner, viewer = _circle_mates()
        item = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="claimed",
        )

        state = build_item_access_state(item, viewer)

        assert state["can_view"] is False
        assert state["claimed_unavailable"] is True


def test_regular_item_needs_circle_token_or_loan(app):
    with app.app_context():
        owner = UserFactory()
        stranger = UserFactory()
        item = ItemFactory(owner=owner, is_giveaway=False)

        assert build_item_access_state(item, stranger)["can_view"] is False

        token_state = build_item_access_state(
            item, stranger, share_token=generate_item_share_token(item)
        )
        assert token_state["can_view"] is True
        assert token_state["has_token_access"] is True

        LoanRequestFactory(item=item, borrower=stranger, status="approved")
        loan_state = build_item_access_state(item, stranger)
        assert loan_state["can_view"] is True
        assert loan_state["is_active_borrower"] is True
