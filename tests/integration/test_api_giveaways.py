"""Integration tests for API giveaway reads and writes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app import db
from app.models import GiveawayInterest
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    GiveawayInterestFactory,
    ItemFactory,
    MessageFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


class TestApiGiveawayInterestReads:
    """Exercise owner-only giveaway-interest management reads."""

    def test_owner_interest_read_returns_interest_state_and_conversation_metadata(
        self, client, app
    ):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            active_user = UserFactory()
            selected_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
                claimed_by=selected_user,
                available=False,
            )
            active_interest = GiveawayInterestFactory(
                item=item,
                user=active_user,
                message="I can pick this up tomorrow.",
                status="active",
            )
            selected_interest = GiveawayInterestFactory(
                item=item,
                user=selected_user,
                message="Happy to coordinate pickup.",
                status="selected",
            )
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            first_message = MessageFactory(
                sender=active_user,
                recipient=owner,
                conversation=conversation,
                body="Still available?",
                is_read=False,
            )
            latest_message = MessageFactory(
                sender=owner,
                recipient=active_user,
                conversation=conversation,
                body="Yes, it is.",
                is_read=True,
            )
            first_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
            latest_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = str(item.id)
            active_interest_id = str(active_interest.id)
            selected_interest_id = str(selected_interest.id)
            selected_user_id = str(selected_user.id)
            latest_message_id = str(latest_message.id)

        response = client.get(
            f"/api/v1/items/{item_id}/giveaway-interests",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["item"] == {
            "id": item_id,
            "claim_status": "pending_pickup",
            "claimed_by": selected_user_id,
            "interested_count": 2,
        }
        assert payload["actions"] == {
            "select_recipient": False,
            "change_recipient": True,
            "release_to_all": True,
            "confirm_handoff": True,
        }
        assert [interest["id"] for interest in payload["interests"]] == [
            active_interest_id,
            selected_interest_id,
        ]
        assert payload["interests"][0]["conversation_message_id"] == latest_message_id
        assert payload["interests"][0]["message_count"] == 2
        assert payload["interests"][0]["unread_count"] == 1
        assert payload["interests"][1]["conversation_message_id"] is None
        assert payload["interests"][1]["message_count"] == 0
        assert payload["interests"][1]["unread_count"] == 0

    def test_non_owner_cannot_read_interest_management_state(self, client, app):
        with app.app_context():
            owner = UserFactory()
            viewer = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            item_id = item.id

        response = client.get(
            f"/api/v1/items/{item_id}/giveaway-interests",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"


class TestApiGiveawayInterestMutations:
    """Exercise giveaway-interest create and withdraw endpoints."""

    def test_withdraw_interest_removes_existing_interest(self, client, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            GiveawayInterestFactory(item=item, user=requester, status="active")
            db.session.commit()
            access_token = login_api_user(client, requester.email)
            item_id = item.id
            requester_id = requester.id

        response = client.delete(
            f"/api/v1/items/{item_id}/interest",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["withdrawn"] is True
        assert payload["item"]["viewer_interest_status"] is None

        with app.app_context():
            assert (
                GiveawayInterest.query.filter_by(item_id=item_id, user_id=requester_id).count() == 0
            )


class TestApiGiveawayRecipientMutations:
    """Exercise owner-side giveaway recipient actions."""

    def test_select_recipient_first_chooses_earliest_interest_and_updates_item(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            first_user = UserFactory()
            second_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            first_interest = GiveawayInterestFactory(item=item, user=first_user, status="active")
            second_interest = GiveawayInterestFactory(item=item, user=second_user, status="active")
            first_interest.created_at = datetime.now(UTC) - timedelta(minutes=2)
            second_interest.created_at = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            first_user_id = str(first_user.id)

        response = client.post(
            f"/api/v1/items/{item_id}/recipient/select",
            headers=auth_headers(access_token),
            json={"selection_method": "first"},
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["selected_interest"]["user"]["id"] == first_user_id
        assert payload["item"]["claim_status"] == "pending_pickup"
        assert payload["item"]["claimed_by"]["id"] == first_user_id

        with app.app_context():
            db.session.expire_all()
            item = db.session.get(type(item), item_id)
            assert item.available is False

    def test_select_recipient_random_uses_service_selection(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            first_user = UserFactory()
            second_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            GiveawayInterestFactory(item=item, user=first_user, status="active")
            GiveawayInterestFactory(item=item, user=second_user, status="active")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            second_user_id = str(second_user.id)

        with patch(
            "app.services.giveaway_service.random.choice",
            side_effect=lambda interests: interests[-1],
        ):
            response = client.post(
                f"/api/v1/items/{item_id}/recipient/select",
                headers=auth_headers(access_token),
                json={"selection_method": "random"},
            )

        assert response.status_code == 200
        assert response.get_json()["selected_interest"]["user"]["id"] == second_user_id

    def test_select_recipient_manual_selects_requested_user(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            first_user = UserFactory()
            second_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="unclaimed",
            )
            GiveawayInterestFactory(item=item, user=first_user, status="active")
            GiveawayInterestFactory(item=item, user=second_user, status="active")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            second_user_id = str(second_user.id)

        response = client.post(
            f"/api/v1/items/{item_id}/recipient/select",
            headers=auth_headers(access_token),
            json={"selection_method": "manual", "user_id": second_user_id},
        )

        assert response.status_code == 200
        assert response.get_json()["selected_interest"]["user"]["id"] == second_user_id

    def test_change_recipient_reactivates_previous_interest_and_selects_new_user(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            previous_user = UserFactory()
            next_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
                claimed_by=previous_user,
                available=False,
            )
            previous_interest = GiveawayInterestFactory(
                item=item,
                user=previous_user,
                status="selected",
            )
            next_interest = GiveawayInterestFactory(item=item, user=next_user, status="active")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            next_user_id = str(next_user.id)
            previous_interest_id = previous_interest.id
            next_interest_id = next_interest.id

        response = client.post(
            f"/api/v1/items/{item_id}/recipient/change",
            headers=auth_headers(access_token),
            json={"selection_method": "next"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["selected_interest"]["user"]["id"] == next_user_id
        assert payload["item"]["claimed_by"]["id"] == next_user_id

        with app.app_context():
            db.session.expire_all()
            refreshed_previous = db.session.get(GiveawayInterest, previous_interest_id)
            refreshed_next = db.session.get(GiveawayInterest, next_interest_id)
            assert refreshed_previous.status == "active"
            assert refreshed_next.status == "selected"

    def test_release_to_all_reopens_item_and_keeps_interest_pool_active(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            selected_user = UserFactory()
            other_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
                claimed_by=selected_user,
                available=False,
            )
            selected_interest = GiveawayInterestFactory(
                item=item,
                user=selected_user,
                status="selected",
            )
            GiveawayInterestFactory(item=item, user=other_user, status="active")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id
            selected_interest_id = selected_interest.id

        response = client.post(
            f"/api/v1/items/{item_id}/release-to-all",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["item"]["claim_status"] == "unclaimed"
        assert payload["item"]["claimed_by"] is None

        with app.app_context():
            db.session.expire_all()
            refreshed_item = db.session.get(type(item), item_id)
            refreshed_interest = db.session.get(GiveawayInterest, selected_interest_id)
            assert refreshed_item.available is True
            assert refreshed_interest.status == "active"

    def test_confirm_handoff_marks_giveaway_claimed(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            recipient = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
                claim_status="pending_pickup",
                claimed_by=recipient,
                available=False,
            )
            GiveawayInterestFactory(item=item, user=recipient, status="selected")
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/confirm-handoff",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json()["item"]["claim_status"] == "claimed"

        with app.app_context():
            db.session.expire_all()
            refreshed_item = db.session.get(type(item), item_id)
            assert refreshed_item.available is False
            assert refreshed_item.claimed_at is not None
