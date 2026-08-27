"""Integration tests for profile access with circle-based restrictions."""

from datetime import UTC, date, datetime, timedelta

import pytest
from flask import url_for

from app.models import circle_members, db
from app.services import giveaway_service, loan_service, message_service
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    CircleJoinRequestFactory,
    ConversationFactory,
    ConversationParticipantFactory,
    ItemFactory,
    ItemRequestFactory,
    UserFactory,
)


@pytest.mark.usefixtures("app")
class TestProfileAccessControl:
    """Test that profile access is restricted based on circle membership."""

    def test_profile_requires_login(self, client):
        """Test that profile page redirects to login when not authenticated."""
        user = UserFactory()
        db.session.commit()

        response = client.get(url_for("main.user_profile", user_id=user.id))
        assert response.status_code == 302
        assert "login" in response.location

    def test_profile_accessible_when_shared_circle(self, client):
        """Test that users can view profiles of users in their circles."""
        user1 = UserFactory(first_name="Viewer", last_name="User")
        user2 = UserFactory(first_name="Profile", last_name="Owner")
        db.session.commit()

        circle = CircleFactory()

        # Add both users to the same circle
        circle.members.append(user1)
        circle.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.user_profile", user_id=user2.id))

        assert response.status_code == 200
        assert b"Profile Owner" in response.data

    def test_profile_not_accessible_when_no_shared_circle(self, client):
        """Test that users cannot view profiles of users not in their circles."""
        user1 = UserFactory()
        user2 = UserFactory()
        db.session.commit()

        # Create separate circles
        circle1 = CircleFactory(name="Circle A")
        circle2 = CircleFactory(name="Circle B")

        # Users in different circles
        circle1.members.append(user1)
        circle2.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.user_profile", user_id=user2.id))

        # Should redirect with warning
        assert response.status_code == 302
        # Follow redirect to index
        response = client.get(url_for("main.user_profile", user_id=user2.id), follow_redirects=True)
        assert b"You can only view profiles of users in your circles" in response.data

    def test_profile_not_accessible_when_no_circles(self, client):
        """Test that users without circles cannot view other profiles."""
        user1 = UserFactory()  # No circles
        user2 = UserFactory()
        db.session.commit()

        circle = CircleFactory()
        circle.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.user_profile", user_id=user2.id))

        # Should redirect with warning
        assert response.status_code == 302

    def test_admin_can_view_any_profile(self, client):
        """Test that admin users can view any profile regardless of circles."""
        admin_user = UserFactory(is_admin=True, first_name="Admin", last_name="User")
        regular_user = UserFactory(first_name="Regular", last_name="User")
        db.session.commit()

        # They don't share any circles
        circle = CircleFactory()
        circle.members.append(regular_user)
        db.session.commit()

        login_user(client, admin_user.email)
        response = client.get(url_for("main.user_profile", user_id=regular_user.id))

        assert response.status_code == 200
        assert b"Regular User" in response.data

    def test_user_can_view_own_profile(self, client):
        """Test that users can always view their own profile."""
        user = UserFactory(first_name="Self", last_name="Viewer")
        db.session.commit()

        # User has no circles
        login_user(client, user.email)
        response = client.get(url_for("main.user_profile", user_id=user.id))

        assert response.status_code == 200
        assert b"Self Viewer" in response.data

    def test_profile_accessible_one_shared_of_many_circles(self, client):
        """Test profile access when users share only one of many circles."""
        user1 = UserFactory()
        user2 = UserFactory(first_name="Partial", last_name="Overlap")
        db.session.commit()

        circle1 = CircleFactory(name="Shared Circle")
        circle2 = CircleFactory(name="User1 Only")
        circle3 = CircleFactory(name="User2 Only")

        # user1 in circles 1 and 2
        circle1.members.append(user1)
        circle2.members.append(user1)
        # user2 in circles 1 and 3
        circle1.members.append(user2)
        circle3.members.append(user2)
        db.session.commit()

        login_user(client, user1.email)
        response = client.get(url_for("main.user_profile", user_id=user2.id))

        assert response.status_code == 200
        assert b"Partial Overlap" in response.data

    def test_profile_displays_shared_circle_links(self, client, app):
        """Profile should show only shared circles with links to those circles."""
        with app.app_context():
            viewer = UserFactory(first_name="Viewer", last_name="User")
            profile_owner = UserFactory(first_name="Profile", last_name="Owner")

            shared_circle = CircleFactory(name="Repair Circle")
            viewer_only_circle = CircleFactory(name="Viewer Only Circle")
            profile_only_circle = CircleFactory(name="Profile Only Circle")

            shared_circle.members.extend([viewer, profile_owner])
            viewer_only_circle.members.append(viewer)
            profile_only_circle.members.append(profile_owner)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(url_for("main.user_profile", user_id=profile_owner.id))

            assert response.status_code == 200
            assert b"Circles in common:" in response.data
            assert b"Repair Circle" in response.data
            assert f"/circles/{shared_circle.id}".encode() in response.data
            assert b"Viewer Only Circle" not in response.data
            assert b"Profile Only Circle" not in response.data

    def test_profile_nonexistent_user_does_not_leak_existence(self, client):
        """Non-admins should not learn if a non-shared user exists (or not)."""
        import uuid

        viewer = UserFactory()
        db.session.commit()

        login_user(client, viewer.email)
        response = client.get(url_for("main.user_profile", user_id=uuid.uuid4()))
        # Redirect to index with generic warning (same behavior as unauthorized access)
        assert response.status_code == 302

    def _isolate(self, *users):
        """Put each user in a circle of their own so none of them share circles."""
        for index, user in enumerate(users):
            circle = CircleFactory(name=f"Solo Circle {index} {user.id}")
            circle.members.append(user)
        db.session.commit()

    def test_profile_accessible_both_ways_via_loan_conversation(self, client):
        """Requesting a loan opens a conversation, and both people can then view each other."""
        owner = UserFactory(first_name="Item", last_name="Owner")
        borrower = UserFactory(first_name="Borrower", last_name="Person")
        category = CategoryFactory()
        db.session.commit()

        item = ItemFactory(owner=owner, category=category, name="Shared Drill")
        db.session.commit()
        self._isolate(owner, borrower)

        loan_service.create_loan_request(
            item, borrower.id, date.today(), date.today() + timedelta(days=3), "May I borrow this?"
        )
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for("main.user_profile", user_id=borrower.id))
        assert response.status_code == 200
        assert b"Borrower Person" in response.data
        assert b"have a message thread" in response.data

        login_user(client, borrower.email)
        response = client.get(url_for("main.user_profile", user_id=owner.id))
        assert response.status_code == 200
        assert b"Item Owner" in response.data

    def test_profile_access_survives_completed_loan(self, client):
        """Access outlives the loan — the conversation is what grants it."""
        owner = UserFactory()
        borrower = UserFactory(first_name="Past", last_name="Borrower")
        category = CategoryFactory()
        db.session.commit()

        item = ItemFactory(owner=owner, category=category, name="Returned Drill")
        db.session.commit()
        self._isolate(owner, borrower)

        message = loan_service.create_loan_request(
            item, borrower.id, date.today(), date.today() + timedelta(days=3), "Borrowing this"
        )
        message.loan_request.status = "completed"
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for("main.user_profile", user_id=borrower.id))

        assert response.status_code == 200
        assert b"Past Borrower" in response.data

    def test_profile_note_hidden_when_shared_circle_and_conversation(self, client):
        """The explanatory note is not shown when access comes from a shared circle."""
        owner = UserFactory(first_name="Shared", last_name="Owner")
        borrower = UserFactory(first_name="Borrower", last_name="Two")
        category = CategoryFactory()
        db.session.commit()

        item = ItemFactory(owner=owner, category=category, name="Shared Drill Two")
        circle = CircleFactory(name="Shared Circle")
        circle.members.extend([owner, borrower])
        db.session.commit()

        loan_service.create_loan_request(
            item, borrower.id, date.today(), date.today() + timedelta(days=3), "Please?"
        )
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for("main.user_profile", user_id=borrower.id))

        assert response.status_code == 200
        assert b"Borrower Two" in response.data
        assert b"have a message thread" not in response.data

    def test_profile_accessible_both_ways_via_giveaway_interest(self, client):
        """Expressing interest in a giveaway opens a conversation, granting mutual access."""
        owner = UserFactory(first_name="Giveaway", last_name="Owner")
        claimant = UserFactory(first_name="Giveaway", last_name="Claimant")
        giveaway = ItemFactory(
            owner=owner,
            category=CategoryFactory(),
            is_giveaway=True,
            claim_status="unclaimed",
        )
        db.session.commit()
        self._isolate(owner, claimant)

        giveaway_service.express_interest(giveaway, claimant.id, "I would love this")
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for("main.user_profile", user_id=claimant.id))
        assert response.status_code == 200
        assert b"Giveaway Claimant" in response.data

        login_user(client, claimant.email)
        response = client.get(url_for("main.user_profile", user_id=owner.id))
        assert response.status_code == 200
        assert b"Giveaway Owner" in response.data

    def test_profile_access_survives_giveaway_handoff(self, client):
        """A completed handoff does not revoke access to the person you gave the item to."""
        owner = UserFactory()
        claimant = UserFactory(first_name="Past", last_name="Claimant")
        giveaway = ItemFactory(
            owner=owner,
            category=CategoryFactory(),
            is_giveaway=True,
            claim_status="unclaimed",
        )
        db.session.commit()
        self._isolate(owner, claimant)

        giveaway_service.express_interest(giveaway, claimant.id, "Yes please")
        giveaway.claim_status = "claimed"
        giveaway.claimed_by_id = claimant.id
        db.session.commit()

        login_user(client, owner.email)
        response = client.get(url_for("main.user_profile", user_id=claimant.id))

        assert response.status_code == 200
        assert b"Past Claimant" in response.data

    def test_profile_accessible_both_ways_via_item_request_conversation(self, client):
        """Answering someone's public item request grants access in both directions."""
        requester = UserFactory(first_name="Request", last_name="Author")
        helper = UserFactory(first_name="Helpful", last_name="Neighbor")
        db.session.commit()

        item_request = ItemRequestFactory(
            user=requester, title="Need a ladder", visibility="public"
        )
        db.session.commit()
        self._isolate(requester, helper)

        message_service.start_request_conversation(item_request, helper, "I have one you can use")
        db.session.commit()

        login_user(client, requester.email)
        response = client.get(url_for("main.user_profile", user_id=helper.id))
        assert response.status_code == 200
        assert b"Helpful Neighbor" in response.data

        login_user(client, helper.email)
        response = client.get(url_for("main.user_profile", user_id=requester.id))
        assert response.status_code == 200
        assert b"Request Author" in response.data

    def test_profile_blocked_for_deleted_user_with_conversation(self, client):
        """A shared conversation does not expose a deleted account's profile."""
        viewer = UserFactory()
        departed = UserFactory()
        db.session.commit()

        conversation = ConversationFactory()
        ConversationParticipantFactory(conversation=conversation, user=viewer)
        ConversationParticipantFactory(conversation=conversation, user=departed)
        departed.is_deleted = True
        db.session.commit()

        login_user(client, viewer.email)
        response = client.get(url_for("main.user_profile", user_id=departed.id))

        assert response.status_code == 302

    def test_profile_blocked_unrelated_user_no_circles(self, client):
        """Unrelated user (no circles, no conversation) is still blocked."""
        viewer = UserFactory(first_name="Curious", last_name="Viewer")
        target = UserFactory(first_name="Unrelated", last_name="Target")
        db.session.commit()
        self._isolate(viewer, target)

        login_user(client, viewer.email)
        response = client.get(url_for("main.user_profile", user_id=target.id))

        assert response.status_code == 302


@pytest.mark.usefixtures("app")
class TestProfileAccessViaCircleJoinRequest:
    """A pending join request lets the circle's admins size up the requester."""

    def _administered_circle(self, admin, **kwargs):
        circle = CircleFactory(**kwargs)
        db.session.execute(
            circle_members.insert().values(
                user_id=admin.id,
                circle_id=circle.id,
                joined_at=datetime.now(UTC),
                is_admin=True,
            )
        )
        db.session.commit()
        return circle

    def test_admin_can_view_pending_join_requester_profile(self, client):
        """The join-request email links here, so the link has to work."""
        admin = UserFactory()
        requester = UserFactory(first_name="Hopeful", last_name="Joiner")
        db.session.commit()

        circle = self._administered_circle(admin, name="Admin Circle")
        CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
        db.session.commit()

        login_user(client, admin.email)
        response = client.get(url_for("main.user_profile", user_id=requester.id))

        assert response.status_code == 200
        assert b"Hopeful Joiner" in response.data
        assert b"asked to join a circle you administer" in response.data

    def test_plain_member_cannot_view_join_requester_profile(self, client):
        """Only admins review join requests, so only admins get the access."""
        member = UserFactory()
        requester = UserFactory(first_name="Hopeful", last_name="Stranger")
        circle = CircleFactory(name="Member Circle")
        circle.members.append(member)
        CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
        db.session.commit()

        login_user(client, member.email)
        response = client.get(url_for("main.user_profile", user_id=requester.id))

        assert response.status_code == 302

    def test_settled_join_request_does_not_grant_access(self, client):
        """A rejected requester goes back to being a stranger."""
        admin = UserFactory()
        rejected = UserFactory(first_name="Rejected", last_name="Applicant")
        db.session.commit()

        circle = self._administered_circle(admin, name="Settled Circle")
        CircleJoinRequestFactory(circle=circle, user=rejected, status="rejected")
        db.session.commit()

        login_user(client, admin.email)
        response = client.get(url_for("main.user_profile", user_id=rejected.id))

        assert response.status_code == 302
