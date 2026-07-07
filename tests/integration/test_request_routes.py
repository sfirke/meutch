"""Integration tests for requests routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app import db
from app.models import Conversation, GiveawayInterest, ItemRequest, Message
from conftest import login_user
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    ItemRequestFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestRequestsFeedAccess:
    """Test feed access and authentication."""

    def test_feed_requires_login(self, client, app):
        """Test that the feed requires authentication."""
        response = client.get("/requests/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_feed_shows_no_circles_message(self, client, app, auth_user):
        """Test homepage feed shows no-circles message for users with no circles."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Join a circle to get started" in response.data


class TestRequestsFeedFiltering:
    """Test feed filtering and visibility."""

    def test_feed_default_scope_uses_all(self, client, app, auth_user):
        """Test default feed shows all-scope results (public + shared-circle requests)."""
        with app.app_context():
            user = auth_user()
            shared_circle_user = UserFactory(latitude=40.7140, longitude=-74.0070)
            public_user = UserFactory(latitude=40.7135, longitude=-74.0050)

            circle = CircleFactory()
            circle.members.extend([user, shared_circle_user])
            db.session.commit()

            ItemRequestFactory(
                user=shared_circle_user,
                title="Shared circles request",
                visibility="circles",
            )
            ItemRequestFactory(
                user=public_user,
                title="Public all-scope request",
                visibility="public",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Shared circles request" in response.data
            assert b"Public all-scope request" in response.data

    def test_all_scope_includes_public_and_shared_circles_only(self, client, app, auth_user):
        """Test all scope includes public requests plus shared-circle circles requests."""
        with app.app_context():
            user = auth_user()
            shared_circle_user = UserFactory(latitude=40.7140, longitude=-74.0070)
            public_user = UserFactory(latitude=40.7135, longitude=-74.0050)
            isolated_circle_user = UserFactory(latitude=40.7130, longitude=-74.0065)

            shared_circle = CircleFactory()
            shared_circle.members.extend([user, shared_circle_user])
            isolated_circle = CircleFactory()
            isolated_circle.members.append(isolated_circle_user)
            db.session.commit()

            ItemRequestFactory(
                user=shared_circle_user,
                title="Visible circles request",
                visibility="circles",
            )
            ItemRequestFactory(
                user=public_user,
                title="Visible public request",
                visibility="public",
            )
            ItemRequestFactory(
                user=isolated_circle_user,
                title="Hidden isolated circles request",
                visibility="circles",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Visible circles request" in response.data
            assert b"Visible public request" in response.data
            assert b"Hidden isolated circles request" not in response.data

    def test_feed_shows_circle_members_requests(self, client, app, auth_user):
        """Test that requests from circle members are visible."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Need a screwdriver",
                visibility="circles",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Need a screwdriver" in response.data

    def test_feed_hides_non_circle_members_requests(self, client, app, auth_user):
        """Test that requests from non-circle members are hidden."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            # Create separate circles — no shared membership
            circle1 = CircleFactory()
            circle1.members.append(user)
            circle2 = CircleFactory()
            circle2.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Hidden request",
                visibility="circles",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Hidden request" not in response.data

    def test_feed_shows_public_requests(self, client, app, auth_user):
        """Test that public requests are visible in all scope."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()

            ItemRequestFactory(
                user=other_user,
                title="Public screwdriver request",
                visibility="public",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Public screwdriver request" in response.data

    def test_feed_hides_expired_requests(self, client, app, auth_user):
        """Test that expired requests are not shown in the feed."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Expired request",
                visibility="circles",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Expired request" not in response.data

    def test_feed_shows_recently_fulfilled_requests(self, client, app, auth_user):
        """Test that fulfilled requests from others within 7 days are shown."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Got my screwdriver",
                visibility="circles",
                status="fulfilled",
                fulfilled_at=datetime.now(UTC) - timedelta(days=3),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Got my screwdriver" in response.data
            assert b"Fulfilled" in response.data
            assert b"marked a request fulfilled" in response.data

    def test_feed_hides_old_fulfilled_requests(self, client, app, auth_user):
        """Test that fulfilled requests from others older than 7 days are hidden."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Old fulfilled request",
                visibility="circles",
                status="fulfilled",
                fulfilled_at=datetime.now(UTC) - timedelta(days=8),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Old fulfilled request" not in response.data

    def test_feed_excludes_old_fulfilled_requests_even_when_own(self, client, app, auth_user):
        """Own fulfilled requests past the 7-day window are still hidden by time filtering."""
        with app.app_context():
            user = auth_user()
            db.session.commit()

            ItemRequestFactory(
                user=user,
                title="My request from 30 days ago",
                visibility="circles",
                status="fulfilled",
                fulfilled_at=datetime.now(UTC) - timedelta(days=30),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"My request from 30 days ago" not in response.data

    def test_feed_shows_own_recently_fulfilled_request(self, client, app, auth_user):
        """Own fulfilled requests within the 7-day window are shown by default."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory()
            circle.members.append(user)
            db.session.commit()

            ItemRequestFactory(
                user=user,
                title="My recently fulfilled request",
                visibility="circles",
                status="fulfilled",
                fulfilled_at=datetime.now(UTC) - timedelta(days=3),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"My recently fulfilled request" in response.data

    def test_feed_excludes_expired_requests_even_when_own(self, client, app, auth_user):
        """Own expired requests (expires_at in the past) are still hidden by time filtering."""
        with app.app_context():
            user = auth_user()
            db.session.commit()

            ItemRequestFactory(
                user=user,
                title="My request that expired 30 days ago",
                visibility="circles",
                status="open",
                expires_at=datetime.now(UTC) - timedelta(days=30),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"My request that expired 30 days ago" not in response.data

    def test_feed_hides_deleted_requests(self, client, app, auth_user):
        """Test that deleted requests are never shown."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Deleted request",
                visibility="circles",
                status="deleted",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Deleted request" not in response.data

    def test_feed_hides_vacation_mode_users(self, client, app, auth_user):
        """Test that requests from vacation mode users are hidden."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory(vacation_mode=True)
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title="Vacation request",
                visibility="circles",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Vacation request" not in response.data

    def test_feed_shows_own_open_requests(self, client, app, auth_user):
        """Test that the homepage feed shows a user's own open requests."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory()
            circle.members.append(user)
            db.session.commit()

            ItemRequestFactory(user=user, title="My own request")
            ItemFactory(
                owner=user,
                name="My own giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"My own request" in response.data
            assert b"My own giveaway" in response.data
            assert b"Show my own activity" in response.data

    def test_feed_can_hide_own_open_requests(self, client, app, auth_user):
        """Test that the homepage feed can hide a user's own activity."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.extend([user, other_user])
            db.session.commit()

            ItemRequestFactory(user=user, title="My hidden request")
            ItemRequestFactory(user=other_user, title="Other visible request", visibility="circles")
            ItemFactory(
                owner=user,
                name="My hidden giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            ItemFactory(
                owner=other_user,
                name="Other visible giveaway",
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get(
                "/?own_activity_present=1&types_present=1&types=requests&types=giveaways&distance=none"
            )
            assert response.status_code == 200
            assert b"My hidden request" not in response.data
            assert b"My hidden giveaway" not in response.data
            assert b"Other visible request" in response.data
            assert b"Other visible giveaway" in response.data

    def test_feed_public_distance_filter(self, client, app, auth_user):
        """Test homepage distance controls can narrow and expand visible public requests."""
        with app.app_context():
            user = auth_user()
            # auth_user has coordinates (40.7128, -74.0060) - NYC
            nearby_user = UserFactory(latitude=40.7300, longitude=-74.0000)  # Very close to NYC
            far_user = UserFactory(latitude=34.0522, longitude=-118.2437)  # Los Angeles

            # User needs to be in a circle to access the feed
            circle = CircleFactory()
            circle.members.append(user)
            db.session.commit()

            ItemRequestFactory(user=nearby_user, title="Nearby request", visibility="public")
            ItemRequestFactory(user=far_user, title="Far away request", visibility="public")
            db.session.commit()

            login_user(client, user.email)
            default_response = client.get("/")
            assert default_response.status_code == 200
            assert b"Nearby request" in default_response.data
            assert b"Far away request" not in default_response.data

            no_limit_response = client.get("/?distance=none")
            assert no_limit_response.status_code == 200
            assert b"Nearby request" in no_limit_response.data
            assert b"Far away request" in no_limit_response.data


class TestRequestCreation:
    """Test creating new requests."""

    def test_new_page_loads(self, client, app, auth_user):
        """Test that the new request page loads."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/requests/new")
            assert response.status_code == 200
            assert b"Post a Request" in response.data

    def test_create_request_success(self, client, app, auth_user):
        """Test creating a request successfully."""
        with app.app_context():
            from datetime import date, timedelta

            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data={
                    "title": "Plastic googly eyes",
                    "description": "I need eight for a craft project",
                    "expires_at": (date.today() + timedelta(days=30)).isoformat(),
                    "seeking": "either",
                    "visibility": "circles",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Your request has been posted!" in response.data

            req = ItemRequest.query.filter_by(title="Plastic googly eyes").first()
            assert req is not None
            assert req.user_id == user.id
            assert req.seeking == "either"
            assert req.visibility == "circles"
            assert req.status == "open"

    def test_new_request_form_defaults_visibility_to_public(self, client, app, auth_user):
        """Test new request form renders public as the default visibility."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.get("/requests/new")

            assert response.status_code == 200
            assert b'<option selected value="public">Public</option>' in response.data

    def test_create_request_validation_error(self, client, app, auth_user):
        """Test creating a request with validation errors."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data={
                    "title": "",
                    "expires_at": "",
                    "seeking": "either",
                    "visibility": "circles",
                },
            )

            assert response.status_code == 200
            assert b"Post a Request" in response.data
            # No request should have been created
            assert ItemRequest.query.count() == 0

    def test_create_request_requires_login(self, client, app):
        """Test that creating a request requires authentication."""
        response = client.get("/requests/new")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_create_public_request_without_location_blocked(self, client, app):
        """Test that a user without location cannot create a public request."""
        with app.app_context():
            from datetime import date

            user = UserFactory(latitude=None, longitude=None)
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data={
                    "title": "Need a ladder",
                    "description": "For painting",
                    "expires_at": (date.today() + timedelta(days=30)).isoformat(),
                    "seeking": "either",
                    "visibility": "public",
                },
            )

            assert response.status_code == 200
            assert b"You must set your location" in response.data
            assert ItemRequest.query.filter_by(title="Need a ladder").first() is None

    def test_create_circles_request_without_location_allowed(self, client, app):
        """Test that a user without location can create a circles-only request."""
        with app.app_context():
            from datetime import date

            user = UserFactory(latitude=None, longitude=None)
            login_user(client, user.email)

            response = client.post(
                "/requests/new",
                data={
                    "title": "Need a ladder",
                    "description": "For painting",
                    "expires_at": (date.today() + timedelta(days=30)).isoformat(),
                    "seeking": "either",
                    "visibility": "circles",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Your request has been posted!" in response.data
            assert ItemRequest.query.filter_by(title="Need a ladder").first() is not None


class TestRequestEditing:
    """Test editing requests."""

    def test_edit_page_loads(self, client, app, auth_user):
        """Test that the edit page loads for the owner."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/edit")
            assert response.status_code == 200
            assert b"Edit Request" in response.data

    def test_edit_request_success(self, client, app, auth_user):
        """Test successfully editing a request."""
        with app.app_context():
            from datetime import date, timedelta

            user = auth_user()
            req = ItemRequestFactory(user=user, title="Old title")
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(
                f"/requests/{req_id}/edit",
                data={
                    "title": "New title",
                    "description": "Updated description",
                    "expires_at": (date.today() + timedelta(days=60)).isoformat(),
                    "seeking": "loan",
                    "visibility": "public",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Your request has been updated." in response.data

            updated_req = db.session.get(ItemRequest, req_id)
            assert updated_req.title == "New title"
            assert updated_req.seeking == "loan"
            assert updated_req.visibility == "public"

    def test_edit_other_users_request_forbidden(self, client, app, auth_user):
        """Test that editing another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/edit")
            assert response.status_code == 403

    def test_edit_deleted_request_returns_404(self, client, app, auth_user):
        """Test that editing a deleted request returns 404."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, status="deleted")
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/edit")
            assert response.status_code == 404

    def test_edit_request_to_public_without_location_blocked(self, client, app):
        """Test that editing a request to public is blocked without location."""
        with app.app_context():
            from datetime import date

            user = UserFactory(latitude=None, longitude=None)
            req = ItemRequestFactory(user=user, visibility="circles")
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(
                f"/requests/{req_id}/edit",
                data={
                    "title": "Updated title",
                    "expires_at": (date.today() + timedelta(days=60)).isoformat(),
                    "seeking": "either",
                    "visibility": "public",
                },
            )

            assert response.status_code == 200
            assert b"You must set your location" in response.data
            # Verify request was NOT updated to public
            updated_req = db.session.get(ItemRequest, req_id)
            assert updated_req.visibility == "circles"


class TestRequestDeletion:
    """Test deleting requests."""

    def test_delete_request_success(self, client, app, auth_user):
        """Test soft-deleting a request."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(f"/requests/{req_id}/delete", follow_redirects=True)

            assert response.status_code == 200
            assert b"Your request has been removed." in response.data

            deleted_req = db.session.get(ItemRequest, req_id)
            assert deleted_req.status == "deleted"

    def test_delete_other_users_request_forbidden(self, client, app, auth_user):
        """Test that deleting another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.post(f"/requests/{req.id}/delete")
            assert response.status_code == 403

    def test_delete_nonexistent_request_returns_404(self, client, app, auth_user):
        """Test deleting a nonexistent request returns 404."""
        import uuid

        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.post(f"/requests/{uuid.uuid4()}/delete")
            assert response.status_code == 404


class TestRequestFulfillment:
    """Test marking requests as fulfilled."""

    def test_fulfill_request_success(self, client, app, auth_user):
        """Test marking a request as fulfilled."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(f"/requests/{req_id}/fulfill", follow_redirects=True)

            assert response.status_code == 200
            assert b"fulfilled" in response.data.lower()

            fulfilled_req = db.session.get(ItemRequest, req_id)
            assert fulfilled_req.status == "fulfilled"
            assert fulfilled_req.fulfilled_at is not None

    def test_fulfill_other_users_request_forbidden(self, client, app, auth_user):
        """Test that fulfilling another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.post(f"/requests/{req.id}/fulfill")
            assert response.status_code == 403


class TestRequestDetail:
    """Test request detail page."""

    def test_detail_page_loads(self, client, app, auth_user):
        """Test that the detail page loads."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, title="My detailed request")
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/detail")
            assert response.status_code == 200
            assert b"My detailed request" in response.data

    def test_detail_deleted_request_returns_404(self, client, app, auth_user):
        """Test that viewing a deleted request returns 404."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, status="deleted")
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/detail")
            assert response.status_code == 404

    def test_detail_nonexistent_request_returns_404(self, client, app, auth_user):
        """Test viewing a nonexistent request returns 404."""
        import uuid

        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get(f"/requests/{uuid.uuid4()}/detail")
            assert response.status_code == 404

    def test_detail_shows_owner_actions(self, client, app, auth_user):
        """Test that detail page shows action buttons for the owner."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f"/requests/{req.id}/detail")
            assert response.status_code == 200
            assert b"Edit" in response.data
            assert b"Mark Fulfilled" in response.data

    def test_circles_only_detail_requires_shared_circle(self, client, app, auth_user):
        """Test that circles-only requests are hidden from users outside the owner's circles."""
        with app.app_context():
            viewer = auth_user()
            owner = UserFactory()
            req = ItemRequestFactory(user=owner, visibility="circles")
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/requests/{req.id}/detail")

            assert response.status_code == 403


class TestRequestConversations:
    """Test request-linked conversation flows."""

    def test_start_conversation_creates_request_message(self, client, app):
        """Posting to conversation route creates a request-linked message."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility="public")
            db.session.commit()

            login_user(client, helper.email)
            response = client.post(
                f"/requests/{item_request.id}/conversation",
                data={"body": "I have one you can borrow!"},
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"I have one you can borrow!" in response.data

            message = (
                Message.query.join(Conversation)
                .filter(
                    Conversation.context_type == "request",
                    Conversation.context_id == item_request.id,
                )
                .first()
            )
            assert message is not None
            assert message.conversation.context_type == "request"
            assert message.sender_id == helper.id
            assert message.recipient_id == requester.id

    def test_conversation_route_redirects_when_thread_exists(self, client, app):
        """Route should redirect to existing conversation instead of creating duplicate."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility="public")
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            existing_message = MessageFactory(
                sender=helper,
                recipient=requester,
                conversation=conversation,
                body="Existing request thread",
            )
            db.session.commit()

            login_user(client, helper.email)
            response = client.get(f"/requests/{item_request.id}/conversation")

            assert response.status_code == 302
            assert (
                f"/conversation/{existing_message.conversation_id}" in response.headers["Location"]
            )

    def test_messages_inbox_shows_request_title(self, client, app):
        """Request-linked conversations should show Re: title in inbox."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(
                user=requester, title="Need a melon baller", visibility="public"
            )
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            MessageFactory(
                sender=helper,
                recipient=requester,
                conversation=conversation,
                body="I can help with this.",
            )
            db.session.commit()

            login_user(client, requester.email)
            response = client.get("/messages")

            assert response.status_code == 200
            assert b"Re: Need a melon baller" in response.data

    def test_view_conversation_reply_preserves_request_context(self, client, app):
        """Replies in request threads should keep the request conversation context."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility="public")
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            first_message = MessageFactory(
                sender=helper,
                recipient=requester,
                conversation=conversation,
                body="Initial request message",
            )
            db.session.commit()

            login_user(client, requester.email)
            response = client.post(
                f"/conversation/{first_message.conversation_id}",
                data={"body": "Thanks, messaging you now!"},
                follow_redirects=True,
            )

            assert response.status_code == 200
            reply = Message.query.filter(
                Message.parent_id == first_message.id, Message.body == "Thanks, messaging you now!"
            ).first()
            assert reply is not None
            assert reply.conversation.context_type == "request"
            assert reply.conversation.context_id == item_request.id

    def test_view_conversation_pending_pickup_giveaway_shows_pending_pickup(self, client, app):
        """Pending-pickup giveaways should show Pending Pickup, not Borrowed, in conversation header."""
        with app.app_context():
            owner = UserFactory()
            claimant = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by=claimant,
                available=False,
            )
            first_message = MessageFactory(
                sender=owner,
                recipient=claimant,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Ready for pickup when you are.",
            )
            db.session.commit()

            login_user(client, claimant.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Pending Pickup" in response.data
            assert b"Borrowed" not in response.data
            assert b"You are the selected recipient for this giveaway." in response.data
            assert b"Mark Handoff Complete" not in response.data

    def test_view_conversation_claimed_giveaway_shows_rehomed(self, client, app):
        """Claimed giveaways should show Rehomed, not Borrowed, in conversation header."""
        with app.app_context():
            owner = UserFactory()
            claimant = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="claimed",
                claimed_by=claimant,
                available=False,
            )
            first_message = MessageFactory(
                sender=owner,
                recipient=claimant,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Thanks for taking it off my hands!",
            )
            db.session.commit()

            login_user(client, claimant.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Rehomed" in response.data
            assert b"Borrowed" not in response.data

    def test_view_conversation_owner_loan_request_uses_consolidated_summary(self, client, app):
        """Owner loan conversations should keep the request context in one summary card without a borrower row."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory(first_name="User1", last_name="Test")
            shared_circle = CircleFactory(name="Outdoor Adventures")
            shared_circle.members.extend([owner, requester])

            item = ItemFactory(
                owner=owner,
                name="Bread Maker",
                description="Automatic bread making machine, barely used",
            )
            loan = LoanRequestFactory(
                item=item,
                borrower=requester,
                status="pending",
                start_date=datetime(2026, 5, 9, tzinfo=UTC),
                end_date=datetime(2026, 5, 16, tzinfo=UTC),
            )
            first_message = MessageFactory(
                sender=requester,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="Could I borrow this next week?",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")
            content = response.get_data(as_text=True)

            assert response.status_code == 200
            assert "Conversation with" in content
            assert requester.full_name in content
            assert content.index(requester.full_name) < content.index("Circles in common:")
            assert shared_circle.name in content
            assert f'href="/item/{item.id}"' in content
            assert "Requested dates:" in content
            assert "Approve Request" in content
            assert "Deny Request" in content
            assert "Borrower:" not in content

    def test_view_conversation_pending_pickup_giveaway_owner_sees_handoff_actions(
        self, client, app
    ):
        """Owners should get the handoff-complete CTA in the recipient conversation."""
        with app.app_context():
            owner = UserFactory()
            claimant = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by=claimant,
                available=False,
            )
            first_message = MessageFactory(
                sender=owner,
                recipient=claimant,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Let me know when you are on your way.",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Giveaway Pickup" in response.data
            assert b"Mark Handoff Complete" in response.data
            assert b"Change Recipient" in response.data
            assert b"Release to Everyone" in response.data

    def test_view_conversation_unclaimed_giveaway_owner_sees_quick_select_actions(
        self, client, app
    ):
        """Owners should get the direct recipient-selection CTA in an interested user's conversation."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
            )
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status="active",
            )
            first_message = MessageFactory(
                sender=requester,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="I would love to pick this up.",
            )
            db.session.add(interest)
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Choose Recipient" in response.data
            assert b"Give Item to This User" in response.data
            assert b"View Interested Users" in response.data
            assert b"Mark Handoff Complete" not in response.data

    def test_view_conversation_unclaimed_giveaway_shows_shared_circle_links(self, client, app):
        """Owner giveaway conversations should show the circles shared with the requester."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            shared_circle = CircleFactory(name="Neighborhood Circle")
            requester_only_circle = CircleFactory(name="Requester Circle")

            shared_circle.members.extend([owner, requester])
            requester_only_circle.members.append(requester)

            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
            )
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status="active",
            )
            first_message = MessageFactory(
                sender=requester,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="I can pick this up after work.",
            )
            db.session.add(interest)
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Circles in common:" in response.data
            assert b"Neighborhood Circle" in response.data
            assert f"/circles/{shared_circle.id}".encode() in response.data
            assert b"Requester Circle" not in response.data

    def test_view_conversation_unclaimed_giveaway_shows_interested_count_guidance(
        self, client, app
    ):
        """Owner quick-select panel should call out when multiple users are interested."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            another_requester = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
            )
            db.session.add_all(
                [
                    GiveawayInterest(item_id=giveaway.id, user_id=requester.id, status="active"),
                    GiveawayInterest(
                        item_id=giveaway.id, user_id=another_requester.id, status="active"
                    ),
                ]
            )
            first_message = MessageFactory(
                sender=requester,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Happy to collect it this week.",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"2 people are interested in this giveaway." in response.data
            assert b"View Interested Users" in response.data

    def test_view_conversation_unclaimed_giveaway_recipient_does_not_see_quick_select_actions(
        self, client, app
    ):
        """Recipients should not see owner-only quick-select actions."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
            )
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status="active",
            )
            first_message = MessageFactory(
                sender=owner,
                recipient=requester,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Thanks for reaching out.",
            )
            db.session.add(interest)
            db.session.commit()

            login_user(client, requester.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Choose Recipient" not in response.data
            assert b"Give Item to This User" not in response.data

    def test_view_conversation_unclaimed_giveaway_hides_quick_select_when_user_not_interested(
        self, client, app
    ):
        """Owner should not get the quick-select CTA if the conversation partner is not in the pool."""
        with app.app_context():
            owner = UserFactory()
            chatter = UserFactory()
            giveaway = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
            )
            first_message = MessageFactory(
                sender=chatter,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=giveaway.id),
                body="Is this still available?",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/conversation/{first_message.conversation_id}")

            assert response.status_code == 200
            assert b"Choose Recipient" not in response.data
            assert b"Give Item to This User" not in response.data


class TestRequestNavigation:
    """Test top-level nav links relevant to requests and find."""

    def test_nav_links_for_authenticated_user(self, client, app, auth_user):
        """Test updated authenticated nav shows Home and Find but not Requests/Giveaways/List Item."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get("/")
            assert response.status_code == 200
            assert b"Home" in response.data
            assert b"Find" in response.data
            assert b"/find" in response.data
            assert b'href="/giveaways"' not in response.data
            assert b'href="/requests/"' not in response.data
            assert b'class="nav-link" href="/list-item"' not in response.data

    def test_nav_link_not_for_anonymous(self, client, app):
        """Test that Requests nav link is not shown to anonymous users."""
        response = client.get("/")
        assert response.status_code == 200
        # The navbar should not contain a Requests nav link for anonymous users
        # (the landing page mock feed uses the icon but NOT as a nav link)
        assert b'href="/requests/"' not in response.data


class TestRequestEmailNotifications:
    """Test email notifications for request-related messages."""

    def test_start_conversation_sends_email_notification(self, client, app):
        """Test that starting a conversation on a request sends an email notification to the requester."""
        with app.app_context():
            requester = UserFactory(email="requester@test.com")
            helper = UserFactory(email="helper@test.com")
            item_request = ItemRequestFactory(
                user=requester,
                title="Need a melon baller",
                visibility="public",
            )
            db.session.commit()

            login_user(client, helper.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                response = client.post(
                    f"/requests/{item_request.id}/conversation",
                    data={"body": "I have one you can borrow!"},
                    follow_redirects=True,
                )

                assert response.status_code == 200
                assert b"Your message has been sent." in response.data

                # Verify email was sent
                mock_send_email.assert_called_once()
                call_args = mock_send_email.call_args
                assert call_args[0][0] == requester.email  # to_email
                assert (
                    "Meutch - New Message about request: Need a melon baller" in call_args[0][1]
                )  # subject
                assert "I have one you can borrow!" in call_args[0][2]  # message body

    def test_reply_to_request_conversation_sends_email(self, client, app):
        """Test that replying in a request conversation thread sends email notification."""
        with app.app_context():
            requester = UserFactory(email="requester@test.com")
            helper = UserFactory(email="helper@test.com")
            item_request = ItemRequestFactory(
                user=requester,
                title="Need a hammer drill",
                visibility="public",
            )
            conversation = ConversationFactory(context_type="request", context_id=item_request.id)
            initial_message = MessageFactory(
                sender=helper,
                recipient=requester,
                conversation=conversation,
                body="I have one you can borrow!",
            )
            db.session.commit()

            login_user(client, requester.email)

            # Patch the email sending function
            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                response = client.post(
                    f"/conversation/{initial_message.conversation_id}",
                    data={"body": "Great! When can I pick it up?"},
                    follow_redirects=True,
                )

                assert response.status_code == 200

                # Verify email was sent to the helper
                mock_send_email.assert_called_once()
                call_args = mock_send_email.call_args
                assert call_args[0][0] == helper.email  # to_email (the other participant)
                assert (
                    "Meutch - New Message about request: Need a hammer drill" in call_args[0][1]
                )  # subject
                assert "Great! When can I pick it up?" in call_args[0][2]  # message body

    def test_request_message_email_includes_context(self, client, app):
        """Test that request message emails properly identify the request context."""
        with app.app_context():
            requester = UserFactory(email="requester@test.com", first_name="Alice")
            helper = UserFactory(email="helper@test.com", first_name="Bob")
            item_request = ItemRequestFactory(
                user=requester,
                title="Looking for a soldering iron",
                visibility="public",
            )
            db.session.commit()

            login_user(client, helper.email)

            with patch("app.utils.email.send_email") as mock_send_email:
                mock_send_email.return_value = True

                response = client.post(
                    f"/requests/{item_request.id}/conversation",
                    data={"body": "I have a soldering iron!"},
                    follow_redirects=True,
                )

                assert response.status_code == 200

                mock_send_email.assert_called_once()
                call_args = mock_send_email.call_args
                text_content = call_args[0][2]  # text_content argument

                # Verify the email includes request-specific context
                assert "Looking for a soldering iron" in text_content  # request title
                assert "Bob" in text_content  # helper's first name
                assert "I have a soldering iron!" in text_content  # message body
                assert (
                    "view_conversation" in call_args[0][3] or "conversation" in text_content
                )  # has link
