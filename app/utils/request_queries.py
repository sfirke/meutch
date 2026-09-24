def can_view_request(item_request, viewer_user):
    if not item_request or item_request.status == "deleted":
        return False
    if viewer_user.id == item_request.user_id:
        return True
    if item_request.visibility == "public":
        return True
    return viewer_user.shares_circle_with(item_request.user)


def describe_seeking_mismatch(item_request, item):
    """Explain how *item* fails to match what *item_request* is seeking.

    Returns a short sentence for display, or ``None`` when the item suits the
    request.  Requests seeking "either" never mismatch.  A mismatch is worth
    surfacing rather than filtering out: someone offering a loan to a giveaway
    request may still be exactly what the requester wants, but both sides
    should know the terms differ before a conversation starts.
    """
    if item_request.seeking == "giveaway" and not item.is_giveaway:
        return "They're asking for a giveaway, but this item is listed for loan."

    if item_request.seeking == "loan" and item.is_giveaway:
        return "They're asking to borrow, but this item is listed as a giveaway."

    return None
