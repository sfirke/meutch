from unittest.mock import patch

import pytest

from app.models import Message
from app.services import giveaway_service
from app.services.exceptions import AuthorizationError, ConflictError, InvalidActionError
from tests.factories import GiveawayInterestFactory, ItemFactory, UserFactory


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
                "app.services.giveaway_service.send_message_notification_email"
            ) as mock_email:
                interest = giveaway_service.express_interest(
                    item, requester.id, "I can pick this up"
                )

            notification = Message.query.one()
            assert interest.user_id == requester.id
            assert interest.status == "active"
            assert notification.recipient_id == owner.id
            mock_email.assert_called_once_with(notification)

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
                    "app.services.giveaway_service.send_message_notification_email"
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
                "app.services.giveaway_service.send_message_notification_email"
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
                "app.services.giveaway_service.send_message_notification_email"
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
