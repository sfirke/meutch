"""Integration tests for claimed giveaway filtering on the /user/<uuid> profile route."""

from datetime import UTC, datetime, timedelta

from app import db
from conftest import login_user
from tests.factories import ItemFactory, UserFactory


class TestUserProfileClaimedGiveawayFiltering:
    """Test that /user/<uuid> hides claimed giveaways older than 7 days.

    The /user/<uuid> route shows items only to the owner and admins
    (can_view_items is admin-or-self), so these tests use the owner
    viewing their own profile via the route and admins viewing others.
    """

    def test_user_profile_shows_recently_claimed_giveaway(self, client, app, auth_user):
        """Giveaways claimed 5 days ago remain visible on the user profile."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name="Recently Claimed Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Recently Claimed Giveaway" in response.data

    def test_user_profile_hides_old_claimed_giveaway(self, client, app, auth_user):
        """Giveaways claimed 8 days ago are hidden from the user profile."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=8),
                name="Old Claimed Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Old Claimed Giveaway" not in response.data

    def test_user_profile_shows_claimed_exactly_7_days(self, client, app, auth_user):
        """Giveaways claimed exactly 7 days ago (minus 1 hour) stay visible."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=7, hours=-1),
                name="Seven Day Claimed Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Seven Day Claimed Giveaway" in response.data

    def test_user_profile_shows_unclaimed_giveaways(self, client, app, auth_user):
        """Unclaimed giveaways are always visible regardless of item age."""
        with app.app_context():
            owner = auth_user()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
                created_at=datetime.now(UTC) - timedelta(days=30),
                name="Old Unclaimed Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Old Unclaimed Giveaway" in response.data

    def test_user_profile_shows_non_giveaway_items(self, client, app, auth_user):
        """Regular (non-giveaway) items are always visible regardless of age."""
        with app.app_context():
            owner = auth_user()

            ItemFactory(
                owner=owner,
                is_giveaway=False,
                created_at=datetime.now(UTC) - timedelta(days=30),
                name="Old Regular Item",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Old Regular Item" in response.data

    def test_admin_can_see_items_on_user_profile(self, client, app):
        """Admins can access any profile; the 7-day claimed window still applies."""
        with app.app_context():
            admin = UserFactory(is_admin=True)
            owner = UserFactory()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                name="Recent Claimed For Admin",
            )
            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=8),
                name="Old Claimed For Admin",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, admin.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            # Recently claimed giveaway is visible to admin
            assert b"Recent Claimed For Admin" in response.data
            # Old claimed giveaway is still excluded (same 7-day window)
            assert b"Old Claimed For Admin" not in response.data

    def test_rehomed_badge_on_recently_claimed(self, client, app, auth_user):
        """Claimed giveaways within the window render the Rehomed badge."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=5),
                available=False,
                name="Badged Claimed Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Badged Claimed Giveaway" in response.data
            assert b"Rehomed" in response.data

    def test_no_badge_on_old_claimed_excluded(self, client, app, auth_user):
        """Old claimed giveaways are not rendered at all (no badge, no card)."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                claimed_at=datetime.now(UTC) - timedelta(days=8),
                available=False,
                name="Old Excluded Giveaway",
            )
            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
                name="Still Visible Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Old Excluded Giveaway" not in response.data
            assert b"Still Visible Giveaway" in response.data

    def test_user_profile_shows_claimed_without_claimed_at(self, client, app, auth_user):
        """Claimed giveaways with no claimed_at (data-integrity edge) remain visible."""
        with app.app_context():
            owner = auth_user()
            claimer = UserFactory()

            ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="claimed",
                claimed_by=claimer,
                name="Claimed No Date Giveaway",
            )
            owner_id = owner.id
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/user/{owner_id}")

            assert response.status_code == 200
            assert b"Claimed No Date Giveaway" in response.data
