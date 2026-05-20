"""Shared item-detail visibility helpers."""

from app.models import LoanRequest
from app.utils.giveaway_visibility import can_view_claimed_giveaway
from app.utils.item_share import token_grants_item_access


def build_item_access_state(item, viewer, share_token=None):
    """Return item-detail access metadata for a specific viewer."""
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
