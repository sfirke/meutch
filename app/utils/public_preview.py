"""Which records get a public /share preview page for logged-out visitors."""


def is_public_giveaway(item):
    return item.is_giveaway and item.giveaway_visibility == "public"


def is_public_request(item_request):
    return item_request.visibility == "public" and item_request.status != "deleted"


def is_searchable_circle(circle):
    return circle.circle_type != "secret"
