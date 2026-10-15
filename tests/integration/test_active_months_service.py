from datetime import UTC, datetime

from app import db
from app.models import circle_members
from app.services.active_months_service import month_start, user_active_months
from tests.factories import CircleFactory, ItemFactory, ItemRequestFactory, UserFactory


def _join(user, circle, joined_at):
    circle.members.append(user)
    db.session.flush()
    db.session.execute(
        circle_members.update()
        .where(circle_members.c.user_id == user.id, circle_members.c.circle_id == circle.id)
        .values(joined_at=joined_at)
    )


def _user_in_shared_circle(joined_at=datetime(2026, 1, 1, tzinfo=UTC)):
    user = UserFactory()
    circle = CircleFactory()
    _join(user, circle, joined_at)
    _join(UserFactory(), circle, joined_at)
    return user


def test_counts_finished_months_and_flags_current_month(db_session):
    user = _user_in_shared_circle()
    ItemFactory(owner=user, created_at=datetime(2026, 4, 3, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime(2026, 4, 20, tzinfo=UTC))
    ItemRequestFactory(user=user, created_at=datetime(2026, 6, 9, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime.now(UTC))
    db_session.commit()

    summary = user_active_months(user)

    assert summary.months_counted == 2
    assert summary.active_this_month is True
    assert summary.current_month == month_start(datetime.now(UTC)).date()
    assert summary.in_shared_circle is True


def test_months_before_april_2026_do_not_count(db_session):
    user = _user_in_shared_circle()
    ItemFactory(owner=user, created_at=datetime(2026, 3, 31, tzinfo=UTC))
    db_session.commit()

    summary = user_active_months(user)

    assert summary.months_counted == 0
    assert summary.active_this_month is False


def test_activity_before_joining_shared_circle_does_not_count(db_session):
    user = _user_in_shared_circle(joined_at=datetime(2026, 6, 1, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime(2026, 5, 15, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime(2026, 7, 15, tzinfo=UTC))
    db_session.commit()

    assert user_active_months(user).months_counted == 1


def test_user_alone_in_circle_is_not_counted(db_session):
    user = UserFactory()
    _join(user, CircleFactory(), datetime(2026, 1, 1, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime(2026, 5, 15, tzinfo=UTC))
    ItemFactory(owner=user, created_at=datetime.now(UTC))
    db_session.commit()

    summary = user_active_months(user)

    assert summary.months_counted == 0
    assert summary.active_this_month is False
    assert summary.in_shared_circle is False


def test_user_in_no_circle_is_not_in_shared_circle(db_session):
    user = UserFactory()
    db_session.commit()

    assert user_active_months(user).in_shared_circle is False
