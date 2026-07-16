from unittest.mock import patch

import pytest

from app.models import GiveawayInterest, Message
from app.services import giveaway_service
from app.services.exceptions import AuthorizationError, ConflictError, InvalidActionError
from tests.factories import (
    ConversationFactory,
    GiveawayInterestFactory,
    ItemFactory,
    MessageFactory,
    UserFactory,
)


class TestGiveawayService:
    def test_express_interest_creates_interest_and_notification_message(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                interest = giveaway_service.express_interest(
                    item, requester.id, "I can pick this up"
                )

            notification = Message.query.one()
            assert interest.user_id == requester.id
            assert interest.status == "active"
            assert notification.recipient_id == owner.id
            mock_email.assert_called_once_with(notification)

    def test_express_interest_without_notification_creates_interest_only(self, app):
        """send_notification=False persists interest without sending a message or email."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                interest = giveaway_service.express_interest(
                    item, requester.id, "Just messaging", send_notification=False
                )

            assert interest.user_id == requester.id
            assert interest.status == "active"
            assert interest.message == "Just messaging"
            assert Message.query.count() == 0
            mock_email.assert_not_called()

    def test_express_interest_reactivates_stale_interest(self, app):
        """Calling express_interest on an existing non-active interest re-activates it."""
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )
            existing = GiveawayInterestFactory(item=item, user=requester, status="selected")

            interest = giveaway_service.express_interest(
                item, requester.id, "Trying again!", send_notification=False
            )

            assert interest.id == existing.id
            assert interest.status == "active"
            assert interest.message == "Trying again!"
            assert (
                GiveawayInterest.query.filter_by(item_id=item.id, user_id=requester.id).count() == 1
            )

    def test_select_recipient_random_updates_item_and_selected_interest(self, app):
        with app.app_context():
            owner = UserFactory()
            first_user = UserFactory()
            second_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )
            first_interest = GiveawayInterestFactory(item=item, user=first_user, status="active")
            second_interest = GiveawayInterestFactory(item=item, user=second_user, status="active")

            with patch("app.services.giveaway_service.random.choice", return_value=second_interest):
                with patch(
                    "app.services.message_service.send_message_notification_email"
                ) as mock_email:
                    selected_interest = giveaway_service.select_recipient(item, owner.id, "random")

            notification = Message.query.one()
            assert selected_interest.id == second_interest.id
            assert item.claim_status == "pending_pickup"
            assert item.claimed_by_id == second_user.id
            assert item.available is False
            assert first_interest.status == "active"
            assert second_interest.status == "selected"
            mock_email.assert_called_once_with(notification)

    def test_change_recipient_reactivates_previous_interest_and_notifies_both_users(self, app):
        with app.app_context():
            owner = UserFactory()
            previous_user = UserFactory()
            next_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by_id=previous_user.id,
                available=False,
                giveaway_visibility="default",
            )
            previous_interest = GiveawayInterestFactory(
                item=item,
                user=previous_user,
                status="selected",
            )
            next_interest = GiveawayInterestFactory(item=item, user=next_user, status="active")

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                selected_interest = giveaway_service.change_recipient(item, owner.id, "next")

            messages = Message.query.order_by(Message.timestamp.asc()).all()
            assert selected_interest.id == next_interest.id
            assert item.claimed_by_id == next_user.id
            assert previous_interest.status == "active"
            assert next_interest.status == "selected"
            assert len(messages) == 2
            assert {message.recipient_id for message in messages} == {
                previous_user.id,
                next_user.id,
            }
            assert mock_email.call_count == 2

    def test_express_interest_raises_conflict_for_non_giveaway_item(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)

            with pytest.raises(InvalidActionError, match="not a giveaway"):
                giveaway_service.express_interest(item, requester.id, "I want this")

    def test_express_interest_raises_conflict_when_already_claimed(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="claimed",
                available=False,
                giveaway_visibility="default",
            )

            with pytest.raises(ConflictError, match="no longer available"):
                giveaway_service.express_interest(item, requester.id, "I want this")

    def test_express_interest_raises_conflict_when_owner_expresses_interest(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with pytest.raises(ConflictError, match="cannot express interest in your own"):
                giveaway_service.express_interest(item, owner.id, "I want this")

    def test_withdraw_interest_raises_conflict_when_interest_not_found(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with pytest.raises(ConflictError, match="not expressed interest"):
                giveaway_service.withdraw_interest(item, requester.id)

    def test_withdraw_interest_raises_invalid_action_for_non_giveaway(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False, available=True)

            with pytest.raises(InvalidActionError, match="not a giveaway"):
                giveaway_service.withdraw_interest(item, requester.id)

    def test_select_recipient_raises_auth_error_for_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            other = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )
            GiveawayInterestFactory(item=item, user=requester, status="active")

            with pytest.raises(AuthorizationError):
                giveaway_service.select_recipient(item, other.id, "first")

    def test_select_recipient_raises_conflict_when_no_interested_users(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with pytest.raises(ConflictError, match="No interested users"):
                giveaway_service.select_recipient(item, owner.id, "first")

    def test_change_recipient_raises_auth_error_for_non_owner(self, app):
        with app.app_context():
            owner = UserFactory()
            other = UserFactory()
            prev_user = UserFactory()
            next_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by_id=prev_user.id,
                available=False,
                giveaway_visibility="default",
            )
            GiveawayInterestFactory(item=item, user=next_user, status="active")

            with pytest.raises(AuthorizationError):
                giveaway_service.change_recipient(item, other.id, "next")

    def test_change_recipient_raises_conflict_when_not_pending_pickup(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="unclaimed",
                available=True,
                giveaway_visibility="default",
            )

            with pytest.raises(ConflictError, match="not pending pickup"):
                giveaway_service.change_recipient(item, owner.id, "next")

    def test_release_to_all_reactivates_selected_interest_and_notifies_previous_recipient(
        self, app
    ):
        with app.app_context():
            owner = UserFactory()
            previous_recipient = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by=previous_recipient,
                available=False,
                giveaway_visibility="default",
            )
            previous_interest = GiveawayInterestFactory(
                item=item,
                user=previous_recipient,
                status="selected",
            )

            with patch(
                "app.services.message_service.send_message_notification_email"
            ) as mock_email:
                giveaway_service.release_to_all(item, owner.id)

            notification = Message.query.one()
            assert item.claim_status == "unclaimed"
            assert item.claimed_by_id is None
            assert item.available is True
            assert previous_interest.status == "active"
            assert notification.recipient_id == previous_recipient.id
            mock_email.assert_called_once_with(notification)

    def test_confirm_handoff_marks_item_claimed(self, app):
        with app.app_context():
            owner = UserFactory()
            recipient = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                claim_status="pending_pickup",
                claimed_by=recipient,
                available=False,
                giveaway_visibility="default",
            )
            selected_interest = GiveawayInterestFactory(
                item=item,
                user=recipient,
                status="selected",
            )

            giveaway_service.confirm_handoff(item, owner.id)

            assert item.claim_status == "claimed"
            assert item.claimed_by_id == recipient.id
            assert item.available is False
            assert item.claimed_at is not None
            assert selected_interest.status == "selected"

    # --- get_giveaway_interest_messaging_info ---

    def test_get_messaging_info_returns_conversation_metadata_per_user(self, app):
        with app.app_context():
            owner = UserFactory()
            user_a = UserFactory()
            user_b = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
            )
            GiveawayInterestFactory(item=item, user=user_a, status="active")
            GiveawayInterestFactory(item=item, user=user_b, status="active")
            conversation = ConversationFactory(context_type="item", context_id=item.id)
            msg_from_a = MessageFactory(
                conversation=conversation,
                sender=user_a,
                recipient=owner,
                is_read=True,
            )
            msg_from_b = MessageFactory(
                conversation=conversation,
                sender=user_b,
                recipient=owner,
                is_read=False,
            )

            interests, messaging_info = giveaway_service.get_giveaway_interest_messaging_info(
                item.id, owner.id
            )

            assert len(interests) == 2
            assert {i.user_id for i in interests} == {user_a.id, user_b.id}
            assert messaging_info[user_a.id] == {
                "conversation_message_id": msg_from_a.id,
                "unread_count": 0,
                "message_count": 1,
                "has_conversation": True,
                "latest_message": msg_from_a,
            }
            assert messaging_info[user_b.id] == {
                "conversation_message_id": msg_from_b.id,
                "unread_count": 1,
                "message_count": 1,
                "has_conversation": True,
                "latest_message": msg_from_b,
            }

    def test_get_messaging_info_handles_users_with_no_conversation(self, app):
        with app.app_context():
            owner = UserFactory()
            silent_user = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
            )
            GiveawayInterestFactory(item=item, user=silent_user, status="active")

            interests, messaging_info = giveaway_service.get_giveaway_interest_messaging_info(
                item.id, owner.id
            )

            assert len(interests) == 1
            assert interests[0].user_id == silent_user.id
            assert messaging_info[silent_user.id] == {
                "conversation_message_id": None,
                "unread_count": 0,
                "message_count": 0,
                "has_conversation": False,
                "latest_message": None,
            }

    def test_get_messaging_info_returns_empty_dict_when_no_interests(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
            )

            interests, messaging_info = giveaway_service.get_giveaway_interest_messaging_info(
                item.id, owner.id
            )

            assert interests == []
            assert messaging_info == {}

    # --- get_giveaway_interest_state ---

    def test_get_interest_state_returns_viewer_status_and_owner_count(self, app):
        with app.app_context():
            owner = UserFactory()
            requester = UserFactory()
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="default",
            )
            GiveawayInterestFactory(item=item, user=requester, status="active")

            owner_state = giveaway_service.get_giveaway_interest_state(item, owner.id)
            assert owner_state["viewer_interest_status"] is None
            assert owner_state["interested_count"] == 1

            requester_state = giveaway_service.get_giveaway_interest_state(item, requester.id)
            assert requester_state["viewer_interest_status"] == "active"
            assert requester_state["interested_count"] is None

    def test_get_interest_state_returns_none_for_non_giveaway(self, app):
        with app.app_context():
            owner = UserFactory()
            item = ItemFactory(owner=owner, is_giveaway=False)

            state = giveaway_service.get_giveaway_interest_state(item, owner.id)

            assert state == {
                "viewer_interest_status": None,
                "interested_count": None,
            }
