import random


def sample_circle_members(members, limit=8, rng=None):
    """Return a randomized sample, prioritizing members with custom avatars."""
    if not members or limit <= 0:
        return []

    members_list = list(members)
    members_with_custom_avatar = [
        member for member in members_list if getattr(member, 'profile_image_url', None)
    ]
    members_without_custom_avatar = [
        member for member in members_list if not getattr(member, 'profile_image_url', None)
    ]

    randomizer = rng or random
    randomizer.shuffle(members_with_custom_avatar)
    randomizer.shuffle(members_without_custom_avatar)

    prioritized_members = members_with_custom_avatar + members_without_custom_avatar
    return prioritized_members[:limit]


def build_circle_member_samples(circles, limit=5, user_circle_ids=None):
    """Build sampled member lists keyed by circle ID for template rendering.

    Only includes member samples for open circles or circles where the current
    user is a member. Pass user_circle_ids as a set of circle IDs the user
    belongs to; omit (or pass empty) for unauthenticated / non-member views.
    """
    if not circles:
        return {}

    user_circle_ids = user_circle_ids or set()
    
    samples = {}
    for circle in circles:
        # Only show member samples for open circles or if user is a member
        if circle.circle_type == 'open' or circle.id in user_circle_ids:
            samples[circle.id] = sample_circle_members(circle.members, limit=limit)
    
    return samples
