from datetime import UTC, datetime, timedelta

from app import db
from app.utils.item_queries import (
    build_category_items_pagination,
    build_find_results,
    build_tag_items_pagination,
)
from tests.factories import CategoryFactory, CircleFactory, ItemFactory, TagFactory, UserFactory


def test_build_find_results_includes_public_giveaway_from_other_circle(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        category = CategoryFactory()

        viewer_circle = CircleFactory()
        owner_circle = CircleFactory()
        viewer_circle.members.append(viewer)
        owner_circle.members.append(owner)

        public_giveaway = ItemFactory(
            owner=owner,
            category=category,
            is_giveaway=True,
            giveaway_visibility="public",
            claim_status="unclaimed",
        )
        db.session.commit()

        results = build_find_results(viewer)

        assert results["has_circles"] is True
        assert results["result_count"] == 1
        assert results["items"][0].id == public_giveaway.id


def test_build_tag_items_pagination_hides_claimed_giveaways(app):
    with app.app_context():
        viewer = UserFactory()
        owner = UserFactory()
        claimer = UserFactory()
        tag = TagFactory()
        circle = CircleFactory()
        circle.members.extend([viewer, owner, claimer])

        unclaimed = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="unclaimed",
        )
        unclaimed.tags.append(tag)

        claimed = ItemFactory(
            owner=owner,
            is_giveaway=True,
            giveaway_visibility="default",
            claim_status="claimed",
            claimed_by=claimer,
            claimed_at=datetime.now(UTC) - timedelta(days=2),
        )
        claimed.tags.append(tag)
        db.session.commit()

        pagination = build_tag_items_pagination(viewer, tag.id, item_type="giveaways")

        assert pagination.total == 1
        assert [item.id for item in pagination.items] == [unclaimed.id]


def test_build_category_items_pagination_only_returns_shared_circle_items(app):
    with app.app_context():
        viewer = UserFactory()
        shared_owner = UserFactory()
        other_owner = UserFactory()
        category = CategoryFactory()

        shared_circle = CircleFactory()
        other_circle = CircleFactory()
        shared_circle.members.extend([viewer, shared_owner])
        other_circle.members.append(other_owner)

        visible_item = ItemFactory(owner=shared_owner, category=category)
        ItemFactory(owner=other_owner, category=category)
        db.session.commit()

        pagination = build_category_items_pagination(viewer, category.id)

        assert pagination.total == 1
        assert [item.id for item in pagination.items] == [visible_item.id]
