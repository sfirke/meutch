import random
from types import SimpleNamespace

from app.utils.circle_members import sample_circle_members, build_circle_member_samples


def _member(name, profile_image_url=None):
    return SimpleNamespace(first_name=name, profile_image_url=profile_image_url)


def test_sample_circle_members_prioritizes_custom_avatars():
    members = [
        _member('NoAvatarA'),
        _member('HasAvatarA', 'https://cdn.example.com/a.jpg'),
        _member('NoAvatarB'),
        _member('HasAvatarB', 'https://cdn.example.com/b.jpg'),
    ]

    sample = sample_circle_members(members, limit=3, rng=random.Random(7))

    assert len(sample) == 3
    assert all(member.profile_image_url for member in sample[:2])


def test_sample_circle_members_randomizes_order_within_groups():
    members = [
        _member('HasAvatarA', 'https://cdn.example.com/a.jpg'),
        _member('HasAvatarB', 'https://cdn.example.com/b.jpg'),
        _member('HasAvatarC', 'https://cdn.example.com/c.jpg'),
        _member('NoAvatarA'),
        _member('NoAvatarB'),
    ]

    sample_one = sample_circle_members(members, limit=5, rng=random.Random(1))
    sample_two = sample_circle_members(members, limit=5, rng=random.Random(2))

    assert [member.first_name for member in sample_one] != [member.first_name for member in sample_two]


def test_build_circle_member_samples_returns_map_by_circle_id():
    circle_one = SimpleNamespace(
        id='circle-1',
        members=[_member('HasAvatar', 'https://cdn.example.com/a.jpg'), _member('NoAvatar')]
    )
    circle_two = SimpleNamespace(id='circle-2', members=[])

    sample_map = build_circle_member_samples([circle_one, circle_two], limit=1)

    assert set(sample_map.keys()) == {'circle-1', 'circle-2'}
    assert len(sample_map['circle-1']) == 1
    assert sample_map['circle-2'] == []