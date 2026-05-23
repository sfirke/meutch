from datetime import UTC, date, datetime
from unittest.mock import patch

from app import db
from app.models import LoanRequest, User, circle_members
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

    def test_delete_user_account_preserves_active_loan_items_and_clears_memberships(self, app):
        with app.app_context():
            deleting_user = UserFactory(
                email="delete-me@example.com",
                profile_image_url="https://example.com/profiles/user.jpg",
            )
            borrower = UserFactory()
            circle = CircleFactory()

            db.session.execute(
                circle_members.insert().values(
                    user_id=deleting_user.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )

            active_item = ItemFactory(owner=deleting_user, is_giveaway=False, available=True)
            LoanRequestFactory(
                item=active_item,
                borrower=borrower,
                status="approved",
                end_date=date.today(),
            )

            pending_item = ItemFactory(owner=deleting_user, is_giveaway=False, available=True)
            pending_request = LoanRequestFactory(
                item=pending_item,
                borrower=borrower,
                status="pending",
            )
            pending_request_id = pending_request.id
            db.session.commit()

            with patch("app.services.account_service.delete_file") as mock_delete_file:
                with patch("app.services.account_service.send_account_deletion_email"):
                    account_service.delete_user_account(deleting_user)

            db.session.refresh(active_item)
            deleted_user = db.session.get(User, deleting_user.id)

            assert active_item.owner_id == deleting_user.id
            assert active_item.available is False
            assert db.session.get(LoanRequest, pending_request_id) is None
            assert deleted_user.is_deleted is True
            assert deleted_user.email.startswith("deleted_")
            assert deleted_user.circles == []
            mock_delete_file.assert_called_once_with("https://example.com/profiles/user.jpg")
