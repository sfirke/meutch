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


def build_circle_member_samples(circles, limit=5):
    """Build sampled member lists keyed by circle ID for template rendering."""
    if not circles:
        return {}

    return {
        circle.id: sample_circle_members(circle.members, limit=limit)
        for circle in circles
    }