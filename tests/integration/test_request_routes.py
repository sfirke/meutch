"""Integration tests for requests routes."""
import pytest
from datetime import datetime, UTC, timedelta
from app import db
from app.models import ItemRequest, Circle, Message
from tests.factories import UserFactory, ItemRequestFactory, CircleFactory, MessageFactory
from conftest import login_user


class TestRequestsFeedAccess:
    """Test feed access and authentication."""

    def test_feed_requires_login(self, client, app):
        """Test that the feed requires authentication."""
        response = client.get('/requests/')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_feed_loads_for_authenticated_user(self, client, app, auth_user):
        """Test that the feed loads for authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'Community Requests' in response.data

    def test_feed_shows_no_circles_message(self, client, app, auth_user):
        """Test feed shows message when user has no circles and views circles scope."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/requests/?scope=circles')
            assert response.status_code == 200
            assert b'Join a circle to see requests' in response.data


class TestRequestsFeedFiltering:
    """Test feed filtering and visibility."""

    def test_feed_shows_circle_members_requests(self, client, app, auth_user):
        """Test that requests from circle members are visible."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            req = ItemRequestFactory(
                user=other_user,
                title='Need a screwdriver',
                visibility='circles',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/?scope=circles')
            assert response.status_code == 200
            assert b'Need a screwdriver' in response.data

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
                title='Hidden request',
                visibility='circles',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/?scope=circles')
            assert response.status_code == 200
            assert b'Hidden request' not in response.data

    def test_feed_shows_public_requests(self, client, app, auth_user):
        """Test that public requests are visible to any circle member."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            # Put each user in a circle (not shared)
            circle1 = CircleFactory()
            circle1.members.append(user)
            circle2 = CircleFactory()
            circle2.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Public screwdriver request',
                visibility='public',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/?scope=public&distance=')
            assert response.status_code == 200
            assert b'Public screwdriver request' in response.data

    def test_feed_hides_expired_requests(self, client, app, auth_user):
        """Test that expired requests are not shown in the feed."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Expired request',
                visibility='circles',
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'Expired request' not in response.data

    def test_feed_shows_recently_fulfilled_requests(self, client, app, auth_user):
        """Test that fulfilled requests within 7 days are shown."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Got my screwdriver',
                visibility='circles',
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=3),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/?scope=circles')
            assert response.status_code == 200
            assert b'Got my screwdriver' in response.data

    def test_feed_hides_old_fulfilled_requests(self, client, app, auth_user):
        """Test that fulfilled requests older than 7 days are hidden."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Old fulfilled request',
                visibility='circles',
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=8),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'Old fulfilled request' not in response.data

    def test_feed_hides_deleted_requests(self, client, app, auth_user):
        """Test that deleted requests are never shown."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Deleted request',
                visibility='circles',
                status='deleted',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'Deleted request' not in response.data

    def test_feed_hides_vacation_mode_users(self, client, app, auth_user):
        """Test that requests from vacation mode users are hidden."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory(vacation_mode=True)
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()

            ItemRequestFactory(
                user=other_user,
                title='Vacation request',
                visibility='circles',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'Vacation request' not in response.data

    def test_feed_own_requests_section(self, client, app, auth_user):
        """Test that user's own requests appear in My Requests section."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory()
            circle.members.append(user)
            db.session.commit()

            ItemRequestFactory(user=user, title='My own request')
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/')
            assert response.status_code == 200
            assert b'My own request' in response.data
            assert b'My Requests' in response.data

    def test_feed_public_distance_filter(self, client, app, auth_user):
        """Test distance filtering on public requests."""
        with app.app_context():
            user = auth_user()
            # auth_user has coordinates (40.7128, -74.0060) - NYC
            nearby_user = UserFactory(latitude=40.7300, longitude=-74.0000)  # Very close to NYC
            far_user = UserFactory(latitude=34.0522, longitude=-118.2437)    # Los Angeles

            circle = CircleFactory()
            circle.members.append(user)
            circle2 = CircleFactory()
            circle2.members.append(nearby_user)
            circle3 = CircleFactory()
            circle3.members.append(far_user)
            db.session.commit()

            ItemRequestFactory(user=nearby_user, title='Nearby request', visibility='public')
            ItemRequestFactory(user=far_user, title='Far away request', visibility='public')
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/requests/?scope=public&distance=5')
            assert response.status_code == 200
            assert b'Nearby request' in response.data
            assert b'Far away request' not in response.data


class TestRequestCreation:
    """Test creating new requests."""

    def test_new_page_loads(self, client, app, auth_user):
        """Test that the new request page loads."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/requests/new')
            assert response.status_code == 200
            assert b'Post a Request' in response.data

    def test_create_request_success(self, client, app, auth_user):
        """Test creating a request successfully."""
        with app.app_context():
            from datetime import date, timedelta
            user = auth_user()
            login_user(client, user.email)

            response = client.post('/requests/new', data={
                'title': 'Plastic googly eyes',
                'description': 'I need eight for a craft project',
                'expires_at': (date.today() + timedelta(days=30)).isoformat(),
                'seeking': 'either',
                'visibility': 'circles',
            }, follow_redirects=True)

            assert response.status_code == 200
            assert b'Your request has been posted!' in response.data

            req = ItemRequest.query.filter_by(title='Plastic googly eyes').first()
            assert req is not None
            assert req.user_id == user.id
            assert req.seeking == 'either'
            assert req.visibility == 'circles'
            assert req.status == 'open'

    def test_create_request_validation_error(self, client, app, auth_user):
        """Test creating a request with validation errors."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)

            response = client.post('/requests/new', data={
                'title': '',
                'expires_at': '',
                'seeking': 'either',
                'visibility': 'circles',
            })

            assert response.status_code == 200
            assert b'Post a Request' in response.data
            # No request should have been created
            assert ItemRequest.query.count() == 0

    def test_create_request_requires_login(self, client, app):
        """Test that creating a request requires authentication."""
        response = client.get('/requests/new')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']


class TestRequestEditing:
    """Test editing requests."""

    def test_edit_page_loads(self, client, app, auth_user):
        """Test that the edit page loads for the owner."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/edit')
            assert response.status_code == 200
            assert b'Edit Request' in response.data

    def test_edit_request_success(self, client, app, auth_user):
        """Test successfully editing a request."""
        with app.app_context():
            from datetime import date, timedelta
            user = auth_user()
            req = ItemRequestFactory(user=user, title='Old title')
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(f'/requests/{req_id}/edit', data={
                'title': 'New title',
                'description': 'Updated description',
                'expires_at': (date.today() + timedelta(days=60)).isoformat(),
                'seeking': 'loan',
                'visibility': 'public',
            }, follow_redirects=True)

            assert response.status_code == 200
            assert b'Your request has been updated.' in response.data

            updated_req = db.session.get(ItemRequest, req_id)
            assert updated_req.title == 'New title'
            assert updated_req.seeking == 'loan'
            assert updated_req.visibility == 'public'

    def test_edit_other_users_request_forbidden(self, client, app, auth_user):
        """Test that editing another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/edit')
            assert response.status_code == 403

    def test_edit_deleted_request_returns_404(self, client, app, auth_user):
        """Test that editing a deleted request returns 404."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, status='deleted')
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/edit')
            assert response.status_code == 404


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
            response = client.post(f'/requests/{req_id}/delete', follow_redirects=True)

            assert response.status_code == 200
            assert b'Your request has been removed.' in response.data

            deleted_req = db.session.get(ItemRequest, req_id)
            assert deleted_req.status == 'deleted'

    def test_delete_other_users_request_forbidden(self, client, app, auth_user):
        """Test that deleting another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.post(f'/requests/{req.id}/delete')
            assert response.status_code == 403

    def test_delete_nonexistent_request_returns_404(self, client, app, auth_user):
        """Test deleting a nonexistent request returns 404."""
        import uuid
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.post(f'/requests/{uuid.uuid4()}/delete')
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
            response = client.post(f'/requests/{req_id}/fulfill', follow_redirects=True)

            assert response.status_code == 200
            assert b'fulfilled' in response.data.lower()

            fulfilled_req = db.session.get(ItemRequest, req_id)
            assert fulfilled_req.status == 'fulfilled'
            assert fulfilled_req.fulfilled_at is not None

    def test_fulfill_other_users_request_forbidden(self, client, app, auth_user):
        """Test that fulfilling another user's request returns 403."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            req = ItemRequestFactory(user=other_user)
            db.session.commit()

            login_user(client, user.email)
            response = client.post(f'/requests/{req.id}/fulfill')
            assert response.status_code == 403

    def test_reopen_fulfilled_request(self, client, app, auth_user):
        """Test reopening a fulfilled request."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(
                user=user,
                status='fulfilled',
                fulfilled_at=datetime.now(UTC),
            )
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(f'/requests/{req_id}/reopen', follow_redirects=True)

            assert response.status_code == 200
            assert b'reopened' in response.data.lower()

            reopened = db.session.get(ItemRequest, req_id)
            assert reopened.status == 'open'
            assert reopened.fulfilled_at is None

    def test_reopen_open_request_rejected(self, client, app, auth_user):
        """Test that reopening an already-open request is rejected."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, status='open')
            db.session.commit()
            req_id = req.id

            login_user(client, user.email)
            response = client.post(f'/requests/{req_id}/reopen', follow_redirects=True)

            assert response.status_code == 200
            # Should not change status — still open
            same_req = db.session.get(ItemRequest, req_id)
            assert same_req.status == 'open'


class TestRequestDetail:
    """Test request detail page."""

    def test_detail_page_loads(self, client, app, auth_user):
        """Test that the detail page loads."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, title='My detailed request')
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/detail')
            assert response.status_code == 200
            assert b'My detailed request' in response.data

    def test_detail_deleted_request_returns_404(self, client, app, auth_user):
        """Test that viewing a deleted request returns 404."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user, status='deleted')
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/detail')
            assert response.status_code == 404

    def test_detail_nonexistent_request_returns_404(self, client, app, auth_user):
        """Test viewing a nonexistent request returns 404."""
        import uuid
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get(f'/requests/{uuid.uuid4()}/detail')
            assert response.status_code == 404

    def test_detail_shows_owner_actions(self, client, app, auth_user):
        """Test that detail page shows action buttons for the owner."""
        with app.app_context():
            user = auth_user()
            req = ItemRequestFactory(user=user)
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/detail')
            assert response.status_code == 200
            assert b'Edit' in response.data
            assert b'Mark Fulfilled' in response.data


class TestRequestConversations:
    """Test request-linked conversation flows."""

    def test_start_conversation_creates_request_message(self, client, app):
        """Posting to conversation route creates a request-linked message."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility='public')
            db.session.commit()

            login_user(client, helper.email)
            response = client.post(
                f'/requests/{item_request.id}/conversation',
                data={'body': 'I have one you can borrow!'},
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b'I have one you can borrow!' in response.data

            message = Message.query.filter_by(request_id=item_request.id).first()
            assert message is not None
            assert message.item_id is None
            assert message.sender_id == helper.id
            assert message.recipient_id == requester.id

    def test_conversation_route_redirects_when_thread_exists(self, client, app):
        """Route should redirect to existing conversation instead of creating duplicate."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility='public')
            existing_message = MessageFactory(
                sender=helper,
                recipient=requester,
                item=None,
                request=item_request,
                body='Existing request thread',
            )
            db.session.commit()

            login_user(client, helper.email)
            response = client.get(f'/requests/{item_request.id}/conversation')

            assert response.status_code == 302
            assert f'/message/{existing_message.id}' in response.headers['Location']

    def test_messages_inbox_shows_request_title(self, client, app):
        """Request-linked conversations should show Re: title in inbox."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, title='Need a melon baller', visibility='public')
            MessageFactory(
                sender=helper,
                recipient=requester,
                item=None,
                request=item_request,
                body='I can help with this.',
            )
            db.session.commit()

            login_user(client, requester.email)
            response = client.get('/messages')

            assert response.status_code == 200
            assert b'Re: Need a melon baller' in response.data

    def test_view_conversation_reply_preserves_request_context(self, client, app):
        """Replies in request threads should keep request_id and null item_id."""
        with app.app_context():
            requester = UserFactory()
            helper = UserFactory()
            item_request = ItemRequestFactory(user=requester, visibility='public')
            first_message = MessageFactory(
                sender=helper,
                recipient=requester,
                item=None,
                request=item_request,
                body='Initial request message',
            )
            db.session.commit()

            login_user(client, requester.email)
            response = client.post(
                f'/message/{first_message.id}',
                data={'body': 'Thanks, messaging you now!'},
                follow_redirects=True,
            )

            assert response.status_code == 200
            reply = Message.query.filter(
                Message.parent_id == first_message.id,
                Message.body == 'Thanks, messaging you now!'
            ).first()
            assert reply is not None
            assert reply.request_id == item_request.id
            assert reply.item_id is None


class TestRequestNavigation:
    """Test that the Requests nav link is present."""

    def test_nav_link_for_authenticated_user(self, client, app, auth_user):
        """Test that Requests nav link is visible to authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/')
            assert response.status_code == 200
            assert b'Requests' in response.data
            assert b'/requests/' in response.data

    def test_nav_link_not_for_anonymous(self, client, app):
        """Test that Requests nav link is not shown to anonymous users."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'hand-holding-heart' not in response.data
