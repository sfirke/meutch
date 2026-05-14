def can_view_request(item_request, viewer_user):
    if not item_request or item_request.status == "deleted":
        return False
    if viewer_user.id == item_request.user_id:
        return True
    if item_request.visibility == "public":
        return True
    return viewer_user.shares_circle_with(item_request.user)
