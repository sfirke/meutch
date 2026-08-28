"""Shared item-detail visibility helpers."""

from app.models import GiveawayInterest, LoanRequest
from app.utils.giveaway_visibility import can_view_claimed_giveaway
from app.utils.item_share import token_grants_item_access


def _has_giveaway_interest(item, viewer):
    """Whether viewer has expressed interest in this giveaway."""
    return GiveawayInterest.query.filter_by(item_id=item.id, user_id=viewer.id).first() is not None


def build_item_access_state(item, viewer, share_token=None):
    """Return item-detail access metadata for a specific viewer.

    Giveaways follow the visibility their owner chose when listing them:
    ``public`` giveaways are open to every signed-in user, and every other
    giveaway ("Circles only" in the listing form) is limited to people who
    share a circle with the owner.  Someone who already expressed interest, or
    who has been selected as the recipient, keeps their access even if the
    shared circle later goes away, so nobody is stranded mid-handoff.  Claimed
    giveaways narrow further to the two people in the handoff.

    Regular items are never listed publicly, so they need a shared circle, a
    valid share token, or an active approved loan.
    """
    is_owner = item.owner_id == viewer.id
    shares_circle_with_owner = False
    has_token_access = False
    is_active_borrower = False
    claimed_unavailable = False

    if item.owner is not None and not is_owner:
        shares_circle_with_owner = viewer.shares_circle_with(item.owner)

    if not item.is_giveaway and not is_owner:
        has_token_access = token_grants_item_access(share_token, item)
        is_active_borrower = (
            LoanRequest.query.filter_by(
                item_id=item.id,
                borrower_id=viewer.id,
                status="approved",
            ).first()
            is not None
        )
        can_view = shares_circle_with_owner or has_token_access or is_active_borrower
    elif item.is_giveaway and item.claim_status == "claimed":
        can_view = can_view_claimed_giveaway(item, viewer)
        claimed_unavailable = not can_view
    elif item.is_giveaway and not is_owner and item.giveaway_visibility != "public":
        can_view = (
            shares_circle_with_owner
            or viewer.id == item.claimed_by_id
            or _has_giveaway_interest(item, viewer)
        )
    else:
        can_view = True

    return {
        "can_view": can_view,
        "claimed_unavailable": claimed_unavailable,
        "is_owner": is_owner,
        "shares_circle_with_owner": shares_circle_with_owner,
        "has_token_access": has_token_access,
        "is_active_borrower": is_active_borrower,
    }
