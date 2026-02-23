"""Integration tests for share link routes."""
from datetime import datetime, UTC, timedelta

import pytest
from app import db
from tests.factories import UserFactory, ItemFactory, CircleFactory, ItemRequestFactory
from conftest import login_user


class TestGiveawaySharePreview:
    """Tests for the giveaway share preview page."""

    def test_public_giveaway_preview_accessible(self, client, app):
        """Test that a public giveaway preview page loads for unauthenticated users."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert item.name.encode() in response.data

    def test_public_giveaway_preview_shows_description(self, client, app):
        """Test that the preview shows the item description."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed',
                description='A wonderful item to share'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'A wonderful item to share' in response.data

    def test_public_giveaway_preview_shows_owner_first_name(self, client, app):
        """Test that preview shows owner's first name."""
        with app.app_context():
            user = UserFactory(first_name='Alice')
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'Alice' in response.data

    def test_public_giveaway_preview_has_signup_link(self, client, app):
        """Test that preview has sign up and login CTAs."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'Sign Up' in response.data
            assert b'Log In' in response.data

    def test_public_giveaway_preview_has_og_meta(self, client, app):
        """Test that preview includes Open Graph meta tags."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed',
                name='Free Ladder'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'Free Ladder - Free Giveaway on Meutch' in response.data

    def test_public_giveaway_preview_uses_item_image_for_meta(self, client, app):
        """Test that preview metadata uses giveaway image when present."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                image_url='https://cdn.example.com/giveaway.jpg'
            )
            db.session.commit()

            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'https://cdn.example.com/giveaway.jpg' in response.data

    def test_public_giveaway_preview_uses_large_twitter_card_with_image(self, client, app):
        """Test that giveaway preview uses summary_large_image when image exists."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                image_url='https://cdn.example.com/giveaway-card.jpg'
            )
            db.session.commit()

            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'<meta name="twitter:card" content="summary_large_image">' in response.data

    def test_public_giveaway_preview_uses_summary_twitter_card_without_image(self, client, app):
        """Test that giveaway preview uses summary when no image exists."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                image_url=None
            )
            db.session.commit()

            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200
            assert b'<meta name="twitter:card" content="summary">' in response.data

    def test_non_public_giveaway_returns_404(self, client, app):
        """Test that a giveaway with default visibility returns 404."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='default', claim_status='unclaimed'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 404

    def test_non_giveaway_item_returns_404(self, client, app):
        """Test that a regular item (not giveaway) returns 404."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user, is_giveaway=False)
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 404

    def test_nonexistent_giveaway_returns_404(self, client, app):
        """Test that a non-existent item ID returns 404."""
        import uuid
        response = client.get(f'/share/giveaway/{uuid.uuid4()}')
        assert response.status_code == 404

    def test_claimed_giveaway_still_accessible(self, client, app):
        """Test that a claimed giveaway preview is still accessible."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(
                owner=user, is_giveaway=True,
                giveaway_visibility='public', claim_status='claimed'
            )
            db.session.commit()
            
            response = client.get(f'/share/giveaway/{item.id}')
            assert response.status_code == 200


class TestRequestSharePreview:
    """Tests for the request share preview page."""

    def test_public_request_preview_accessible(self, client, app):
        """Test that a public request preview loads for unauthenticated users."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user, visibility='public',
                title='Need a wheelbarrow'
            )
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'Need a wheelbarrow' in response.data

    def test_public_request_preview_shows_description(self, client, app):
        """Test that the preview shows the request description."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user, visibility='public',
                description='For a weekend garden project'
            )
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'For a weekend garden project' in response.data

    def test_public_request_preview_shows_author_name(self, client, app):
        """Test that preview shows requester's first name."""
        with app.app_context():
            user = UserFactory(first_name='Bob')
            req = ItemRequestFactory(user=user, visibility='public')
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'Bob' in response.data

    def test_public_request_preview_has_cta(self, client, app):
        """Test that preview has sign up and login CTAs."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(user=user, visibility='public')
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'Sign Up' in response.data
            assert b'Log In' in response.data

    def test_public_request_preview_has_og_meta(self, client, app):
        """Test that preview includes Open Graph meta tags."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user, visibility='public',
                title='Need a drill'
            )
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'Need a drill - Request on Meutch' in response.data

    def test_public_request_preview_uses_requester_image_for_meta(self, client, app):
        """Test that preview metadata uses requester image when present."""
        with app.app_context():
            user = UserFactory(profile_image_url='https://cdn.example.com/requester.jpg')
            req = ItemRequestFactory(
                user=user,
                visibility='public',
                title='Need a pressure washer'
            )
            db.session.commit()

            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'https://cdn.example.com/requester.jpg' in response.data

    def test_public_request_preview_uses_summary_twitter_card(self, client, app):
        """Test that request preview keeps summary twitter card."""
        with app.app_context():
            user = UserFactory(profile_image_url='https://cdn.example.com/requester.jpg')
            req = ItemRequestFactory(
                user=user,
                visibility='public',
                title='Need a folding table'
            )
            db.session.commit()

            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'<meta name="twitter:card" content="summary">' in response.data

    def test_circles_only_request_returns_404(self, client, app):
        """Test that a circles-only request returns 404."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(user=user, visibility='circles')
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 404

    def test_deleted_request_returns_404(self, client, app):
        """Test that a deleted request returns 404."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user, visibility='public', status='deleted'
            )
            db.session.commit()
            
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 404

    def test_nonexistent_request_returns_404(self, client, app):
        """Test that a non-existent request ID returns 404."""
        import uuid
        response = client.get(f'/share/request/{uuid.uuid4()}')
        assert response.status_code == 404

    def test_fulfilled_request_older_than_7_days_shows_fallback(self, client, app):
        """Test that old fulfilled requests show fulfilled fallback content and feed CTA."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user,
                visibility='public',
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=8),
            )
            db.session.commit()

            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert b'This request has already been fulfilled.' in response.data
            assert b'Browse current community requests in the requests feed.' in response.data
            assert b'/auth/register' in response.data
            assert b'/auth/login' in response.data
            assert (b'next=%2Frequests%2F' in response.data) or (b'next=/requests/' in response.data)

    def test_fulfilled_request_within_7_days_still_accessible_with_feed_next(self, client, app):
        """Test that recent fulfilled request is visible but points auth CTA to feed."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user,
                visibility='public',
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=2),
            )
            db.session.commit()

            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            assert req.title.encode() in response.data
            assert b'This request has already been fulfilled.' not in response.data
            assert b'/auth/register' in response.data
            assert b'/auth/login' in response.data
            assert (b'next=%2Frequests%2F' in response.data) or (b'next=/requests/' in response.data)

    def test_open_request_uses_request_detail_for_auth_next(self, client, app):
        """Test that open requests preserve request-detail next links."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(user=user, visibility='public', status='open')
            db.session.commit()

            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 200
            encoded_next = f'%2Frequests%2F{req.id}%2Fdetail'.encode()
            raw_next = f'/requests/{req.id}/detail'.encode()
            assert b'/auth/register' in response.data
            assert b'/auth/login' in response.data
            assert (b'next=' + encoded_next in response.data) or (b'next=' + raw_next in response.data)

    def test_authenticated_user_old_fulfilled_share_link_redirects_to_feed(self, client, app):
        """Test authenticated users are redirected to requests feed for old fulfilled shared requests."""
        with app.app_context():
            user = UserFactory()
            req = ItemRequestFactory(
                user=user,
                visibility='public',
                status='fulfilled',
                fulfilled_at=datetime.now(UTC) - timedelta(days=8),
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get(f'/share/request/{req.id}')
            assert response.status_code == 302
            assert response.headers['Location'].endswith('/requests/')


class TestCircleSharePreview:
    """Tests for the circle share preview page."""

    def test_public_circle_preview_accessible(self, client, app):
        """Test that a public circle preview loads for unauthenticated users."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public', name='Board Gamers Club'
            )
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'Board Gamers Club' in response.data

    def test_private_circle_preview_accessible(self, client, app):
        """Test that a private circle preview loads for unauthenticated users."""
        with app.app_context():
            circle = CircleFactory(
                visibility='private', name='Work Friends'
            )
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'Work Friends' in response.data

    def test_unlisted_circle_returns_404(self, client, app):
        """Test that an unlisted circle returns 404."""
        with app.app_context():
            circle = CircleFactory(visibility='unlisted')
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 404

    def test_public_circle_shows_member_avatars(self, client, app):
        """Test that a public circle shows member avatars."""
        with app.app_context():
            circle = CircleFactory(visibility='public')
            user1 = UserFactory(first_name='Member1')
            user2 = UserFactory(first_name='Member2')
            circle.members.append(user1)
            circle.members.append(user2)
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'share-member-avatar' in response.data
            assert b'2 members' in response.data

    def test_private_circle_hides_member_avatars(self, client, app):
        """Test that a private circle does NOT show member avatars."""
        with app.app_context():
            circle = CircleFactory(visibility='private')
            user1 = UserFactory()
            circle.members.append(user1)
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'share-member-avatar' not in response.data
            assert b'private circle' in response.data.lower()

    def test_circle_preview_shows_description(self, client, app):
        """Test that the preview shows the circle description."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public',
                description='A circle for board game lovers'
            )
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'A circle for board game lovers' in response.data

    def test_circle_preview_has_cta(self, client, app):
        """Test that preview has sign up and login CTAs."""
        with app.app_context():
            circle = CircleFactory(visibility='public')
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'Sign Up' in response.data
            assert b'Log In' in response.data

    def test_circle_preview_has_og_meta(self, client, app):
        """Test that preview includes Open Graph meta tags."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public', name='Neighbors Circle'
            )
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'Neighbors Circle - Circle on Meutch' in response.data

    def test_circle_preview_uses_circle_image_for_meta(self, client, app):
        """Test that preview metadata uses circle image when present."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public',
                image_url='https://cdn.example.com/circle.jpg'
            )
            db.session.commit()

            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'https://cdn.example.com/circle.jpg' in response.data

    def test_circle_preview_uses_large_twitter_card_with_image(self, client, app):
        """Test that circle preview uses summary_large_image when image exists."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public',
                image_url='https://cdn.example.com/circle-card.jpg'
            )
            db.session.commit()

            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'<meta name="twitter:card" content="summary_large_image">' in response.data

    def test_circle_preview_uses_summary_twitter_card_without_image(self, client, app):
        """Test that circle preview uses summary when no image exists."""
        with app.app_context():
            circle = CircleFactory(
                visibility='public',
                image_url=None
            )
            db.session.commit()

            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'<meta name="twitter:card" content="summary">' in response.data

    def test_nonexistent_circle_returns_404(self, client, app):
        """Test that a non-existent circle ID returns 404."""
        import uuid
        response = client.get(f'/share/circle/{uuid.uuid4()}')
        assert response.status_code == 404

    def test_circle_member_count_shown(self, client, app):
        """Test that member count is displayed correctly."""
        with app.app_context():
            circle = CircleFactory(visibility='public')
            for _ in range(5):
                user = UserFactory()
                circle.members.append(user)
            db.session.commit()
            
            response = client.get(f'/share/circle/{circle.id}')
            assert response.status_code == 200
            assert b'5 members' in response.data


class TestShareButtonVisibility:
    """Tests for share button visibility on detail pages."""

    def test_share_button_shown_on_public_giveaway(self, client, app, auth_user):
        """Test that share button appears on public giveaway detail page."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            item = ItemFactory(
                owner=other_user, is_giveaway=True,
                giveaway_visibility='public', claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 200
            assert b'share-btn' in response.data
            assert b'/share/giveaway/' in response.data

    def test_share_button_not_shown_on_default_giveaway(self, client, app, auth_user):
        """Test that share button does NOT appear on default-visibility giveaway."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            item = ItemFactory(
                owner=other_user, is_giveaway=True,
                giveaway_visibility='default', claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 200
            assert b'/share/giveaway/' not in response.data

    def test_share_button_shown_on_public_request(self, client, app, auth_user):
        """Test that share button appears on public request detail page."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            req = ItemRequestFactory(
                user=other_user, visibility='public',
                title='Need something'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/detail')
            assert response.status_code == 200
            assert b'share-btn' in response.data
            assert b'/share/request/' in response.data

    def test_share_button_not_shown_on_circles_request(self, client, app, auth_user):
        """Test that share button does NOT appear on circles-only request."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(other_user)
            req = ItemRequestFactory(
                user=other_user, visibility='circles',
                title='Private need'
            )
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/requests/{req.id}/detail')
            assert response.status_code == 200
            assert b'/share/request/' not in response.data

    def test_share_button_shown_on_public_circle(self, client, app, auth_user):
        """Test that share button appears on public circle detail page."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory(visibility='public')
            circle.members.append(user)
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/circles/{circle.id}')
            assert response.status_code == 200
            assert b'share-btn' in response.data
            assert b'/share/circle/' in response.data

    def test_share_button_shown_on_private_circle(self, client, app, auth_user):
        """Test that share button appears on private circle detail page."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory(visibility='private', requires_approval=True)
            circle.members.append(user)
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/circles/{circle.id}')
            assert response.status_code == 200
            assert b'share-btn' in response.data

    def test_share_button_not_shown_on_unlisted_circle(self, client, app, auth_user):
        """Test that share button does NOT appear on unlisted circle."""
        with app.app_context():
            user = auth_user()
            circle = CircleFactory(visibility='unlisted', requires_approval=True)
            circle.members.append(user)
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get(f'/circles/{circle.id}')
            assert response.status_code == 200
            assert b'/share/circle/' not in response.data


class TestRegisterNextParam:
    """Test that the register route preserves the next parameter."""

    def test_register_preserves_next_param(self, client, app):
        """Test that after registration, redirect to login includes next param."""
        with app.app_context():
            response = client.post('/auth/register?next=/circles/some-id', data={
                'email': 'newuser@example.com',
                'password': 'testpassword123',
                'confirm_password': 'testpassword123',
                'first_name': 'New',
                'last_name': 'User',
                'location_method': 'skip'
            })
            # Should redirect to login with next param preserved
            assert response.status_code == 302
            location = response.headers['Location']
            assert '/auth/login' in location
            # Check both url-encoded and raw forms of the next parameter in the Location header
            assert ('next=%2Fcircles%2Fsome-id' in location) or ('next=/circles/some-id' in location)
