"""Integration tests for loan extension functionality."""

from datetime import date, timedelta

from flask import url_for

from app import db
from app.models import Message
from conftest import login_user
from tests.factories import (
    CircleFactory,
    ItemFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestLoanExtension:
    """Test loan extension route and message generation."""

    def test_extend_loan_with_later_date_says_extended(self, app, client):
        """Test that extending a loan with a later date says 'extended' in message."""
        with app.app_context():
            # Create owner and borrower
            owner = UserFactory()
            borrower = UserFactory()

            # Create item and loan
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status="approved",
            )
            db.session.commit()

            # Login as owner
            login_user(client, owner.email)

            # Extend loan to a later date
            new_end_date = date.today() + timedelta(days=10)
            response = client.post(
                url_for("main.extend_loan", loan_id=loan.id),
                data={"new_end_date": new_end_date.strftime("%Y-%m-%d"), "message": ""},
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Check that flash message says "extended"
            assert b"extended" in response.data

            # Check that the notification message to borrower says "extended"
            message = (
                Message.query.filter_by(
                    sender_id=owner.id, recipient_id=borrower.id, item_id=item.id
                )
                .order_by(Message.timestamp.desc())
                .first()
            )

            assert message is not None
            assert "extended" in message.body.lower()
            assert "good news" in message.body.lower()

    def test_extend_loan_with_earlier_date_says_updated(self, app, client):
        """Test that changing a loan to an earlier date says 'updated' not 'extended'."""
        with app.app_context():
            # Create owner and borrower
            owner = UserFactory()
            borrower = UserFactory()

            # Create item and loan with due date far in future
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=10)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status="approved",
            )
            db.session.commit()

            # Login as owner
            login_user(client, owner.email)

            # Change loan to an earlier date
            new_end_date = date.today() + timedelta(days=5)
            response = client.post(
                url_for("main.extend_loan", loan_id=loan.id),
                data={"new_end_date": new_end_date.strftime("%Y-%m-%d"), "message": ""},
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Check that flash message says "updated" not "extended"
            assert b"Loan due date has been updated to" in response.data
            assert b"Loan has been extended until" not in response.data

            # Check that the notification message to borrower says "updated" not "extended"
            message = (
                Message.query.filter_by(
                    sender_id=owner.id, recipient_id=borrower.id, item_id=item.id
                )
                .order_by(Message.timestamp.desc())
                .first()
            )

            assert message is not None
            assert "has been updated" in message.body.lower()
            assert "has been extended" not in message.body.lower()
            # Should not have "good news" for earlier date
            assert "good news" not in message.body.lower()

    def test_extend_loan_with_custom_message_and_later_date(self, app, client):
        """Test loan extension with custom message and later date."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=5)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status="approved",
            )
            db.session.commit()

            # Login as owner
            login_user(client, owner.email)

            # Extend with custom message
            new_end_date = date.today() + timedelta(days=10)
            custom_msg = "You can keep it longer, no rush!"
            response = client.post(
                url_for("main.extend_loan", loan_id=loan.id),
                data={"new_end_date": new_end_date.strftime("%Y-%m-%d"), "message": custom_msg},
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Check message contains "extended" and custom message
            message = (
                Message.query.filter_by(
                    sender_id=owner.id, recipient_id=borrower.id, item_id=item.id
                )
                .order_by(Message.timestamp.desc())
                .first()
            )

            assert message is not None
            assert "extended" in message.body.lower()
            assert custom_msg in message.body

    def test_extend_loan_with_custom_message_and_earlier_date(self, app, client):
        """Test loan update with custom message and earlier date."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            current_end_date = date.today() + timedelta(days=10)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=current_end_date,
                status="approved",
            )
            db.session.commit()

            # Login as owner
            login_user(client, owner.email)

            # Update to earlier date with custom message
            new_end_date = date.today() + timedelta(days=5)
            custom_msg = "Need the item back sooner, sorry!"
            response = client.post(
                url_for("main.extend_loan", loan_id=loan.id),
                data={"new_end_date": new_end_date.strftime("%Y-%m-%d"), "message": custom_msg},
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Check message contains "updated" (not "extended") and custom message
            message = (
                Message.query.filter_by(
                    sender_id=owner.id, recipient_id=borrower.id, item_id=item.id
                )
                .order_by(Message.timestamp.desc())
                .first()
            )

            assert message is not None
            assert "has been updated" in message.body.lower()
            assert "has been extended" not in message.body.lower()
            assert custom_msg in message.body

    def test_owner_does_not_see_extend_button_for_pending_loan(self, app, client):
        """Owners should not see the 'Extend Loan Period' button when viewing a conversation
        with a pending loan request — only Approve and Deny."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=7),
                status="pending",
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                item=item,
                body="Can I borrow this?",
                is_read=False,
            )
            msg.loan_request = loan
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(url_for("main.view_conversation", message_id=msg.id))

            assert response.status_code == 200
            assert b"Approve Request" in response.data
            assert b"Deny Request" in response.data
            assert b"Extend Loan Period" not in response.data

    def test_pending_loan_conversation_shows_shared_circle_links(self, app, client):
        """Pending loan conversations should show the circles both users share."""
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory()
            shared_circle = CircleFactory(name="Tool Library Circle")
            owner_only_circle = CircleFactory(name="Owner Circle")

            shared_circle.members.extend([owner, borrower])
            owner_only_circle.members.append(owner)

            item = ItemFactory(owner=owner)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=7),
                status="pending",
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                item=item,
                body="Could I borrow this next week?",
                is_read=False,
            )
            msg.loan_request = loan
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(url_for("main.view_conversation", message_id=msg.id))

            assert response.status_code == 200
            assert b"Circles in common:" in response.data
            assert b"Tool Library Circle" in response.data
            assert f"/circles/{shared_circle.id}".encode() in response.data
            assert b"Owner Circle" not in response.data
