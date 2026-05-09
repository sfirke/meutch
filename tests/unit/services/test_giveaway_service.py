from unittest.mock import patch

from app.models import Message
from app.services import giveaway_service
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
