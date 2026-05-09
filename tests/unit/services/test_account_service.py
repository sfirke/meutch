from datetime import UTC, datetime
from unittest.mock import patch

from app import db
from app.models import LoanRequest, circle_members
from app.services import account_service
from tests.factories import CircleFactory, ItemFactory, LoanRequestFactory, UserFactory


class TestAccountService:
    def test_delete_user_account_soft_deletes_and_updates_pending_loans(self, app):
        with app.app_context():
            user = UserFactory(email="delete-me@example.com")
            other_owner = UserFactory()
            other_borrower = UserFactory()

            borrowed_item = ItemFactory(owner=other_owner, is_giveaway=False)
            owned_item = ItemFactory(owner=user, is_giveaway=False)

            outgoing_request = LoanRequestFactory(
                item=borrowed_item,
                borrower=user,
                status="pending",
            )
            incoming_request = LoanRequestFactory(
                item=owned_item,
                borrower=other_borrower,
                status="pending",
            )

            with patch("app.services.account_service.send_account_deletion_email") as mock_email:
                account_service.delete_user_account(user)

            db.session.refresh(outgoing_request)
            db.session.refresh(user)
            assert outgoing_request.status == "canceled"
            assert db.session.get(LoanRequest, incoming_request.id) is None
            assert user.is_deleted is True
            assert user.deleted_at is not None
            assert user.email.startswith("deleted_")
            mock_email.assert_called_once()

    def test_delete_user_account_promotes_next_circle_admin(self, app):
        with app.app_context():
            deleting_user = UserFactory()
            next_member = UserFactory()
            circle = CircleFactory()

            db.session.execute(
                circle_members.insert().values(
                    user_id=deleting_user.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.execute(
                circle_members.insert().values(
                    user_id=next_member.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=False,
                )
            )
            db.session.commit()

            with patch("app.services.account_service.send_account_deletion_email"):
                account_service.delete_user_account(deleting_user)

            promoted_assoc = (
                db.session.query(circle_members)
                .filter_by(circle_id=circle.id, user_id=next_member.id)
                .first()
            )
            assert promoted_assoc is not None
            assert promoted_assoc.is_admin is True
