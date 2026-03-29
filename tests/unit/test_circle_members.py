import random

from tests.factories import UserFactory, CircleFactory
from app.utils.circle_members import sample_circle_members, build_circle_member_samples


def test_sample_circle_members_prioritizes_custom_avatars(app, db_session):
    """Test that members with custom avatars are prioritized in the sample."""
    members = [
        UserFactory(first_name='NoAvatarA', profile_image_url=None),
        UserFactory(first_name='HasAvatarA', profile_image_url='https://cdn.example.com/a.jpg'),
        UserFactory(first_name='NoAvatarB', profile_image_url=None),
        UserFactory(first_name='HasAvatarB', profile_image_url='https://cdn.example.com/b.jpg'),
    ]
    db_session.commit()

    sample = sample_circle_members(members, limit=3, rng=random.Random(7))

    assert len(sample) == 3
    assert all(member.profile_image_url for member in sample[:2])


def test_sample_circle_members_randomizes_order_within_groups(app, db_session):
    """Test that randomization is applied within each group (with/without avatars)."""
    members = [
        UserFactory(first_name='HasAvatarA', profile_image_url='https://cdn.example.com/a.jpg'),
        UserFactory(first_name='HasAvatarB', profile_image_url='https://cdn.example.com/b.jpg'),
        UserFactory(first_name='HasAvatarC', profile_image_url='https://cdn.example.com/c.jpg'),
        UserFactory(first_name='NoAvatarA', profile_image_url=None),
        UserFactory(first_name='NoAvatarB', profile_image_url=None),
    ]
    db_session.commit()

    sample_one = sample_circle_members(members, limit=5, rng=random.Random(1))
    sample_two = sample_circle_members(members, limit=5, rng=random.Random(2))

    assert [member.first_name for member in sample_one] != [member.first_name for member in sample_two]


def test_build_circle_member_samples_returns_map_by_circle_id(app, db_session):
    """Test that circle member samples are keyed correctly by circle ID."""
    circle_one = CircleFactory()
    circle_one.members = [
        UserFactory(first_name='HasAvatar', profile_image_url='https://cdn.example.com/a.jpg'),
        UserFactory(first_name='NoAvatar', profile_image_url=None)
    ]

    circle_two = CircleFactory()
    circle_two.members = []

    db_session.commit()

    sample_map = build_circle_member_samples([circle_one, circle_two], limit=1)

    assert set(sample_map.keys()) == {circle_one.id, circle_two.id}
    assert len(sample_map[circle_one.id]) == 1
    assert sample_map[circle_two.id] == []