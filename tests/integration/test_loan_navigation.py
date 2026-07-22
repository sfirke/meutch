"""Integration tests for loan activity navigation links."""

from datetime import date, timedelta

from app import db
from conftest import login_user
from tests.factories import (
    CategoryFactory,
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    ItemImageFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)


class TestItemCardLoanButton:
    """Test loan button on item card when owner has active loan."""

    def test_item_card_shows_loan_button_when_item_has_active_loan(self, client, app, auth_user):
        """Owner's item card shows 'Loan' button linking to conversation when item is on loan."""
        with app.app_context():
            owner = auth_user()
            borrower = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=10),
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                body="Can I borrow this?",
                loan_request=loan,
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get("/profile?tab=my-items")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert f'href="/conversation/{msg.conversation_id}"' in content
            assert "View active loan" in content

    def test_item_card_hides_loan_button_when_no_active_loan(self, client, app, auth_user):
        """Owner's item card does not show 'Loan' button when item has no active loan."""
        with app.app_context():
            owner = auth_user()
            category = CategoryFactory()
            ItemFactory(owner=owner, category=category)
            db.session.commit()

            login_user(client, owner.email)
            response = client.get("/profile?tab=my-items")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "View active loan" not in content


class TestItemDetailLoanLink:
    """Test loan link on item detail page for owner."""

    def test_item_detail_shows_loan_link_for_owner_with_active_loan(self, client, app, auth_user):
        """Owner sees 'View Active Loan' button on item detail when item is on loan."""
        with app.app_context():
            owner = auth_user()
            borrower = UserFactory()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=10),
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                body="Can I borrow this?",
                loan_request=loan,
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "View Active Loan" in content
            assert f'href="/conversation/{msg.conversation_id}"' in content

    def test_item_detail_hides_loan_link_when_no_active_loan(self, client, app, auth_user):
        """Owner does not see 'View Active Loan' button when item has no active loan."""
        with app.app_context():
            owner = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=owner, category=category)
            db.session.commit()

            login_user(client, owner.email)
            response = client.get(f"/item/{item.id}")
            assert response.status_code == 200
            content = response.data.decode("utf-8")
            assert "View Active Loan" not in content


class TestMyActivityConversationLinks:
    """Test that My Activity tab links item names to conversations."""

    def test_borrowing_table_item_name_links_to_conversation(self, client, app, auth_user):
        """In borrowing table, item name and thumbnail link to item; View Loan button links to conversation."""
        with app.app_context():
            borrower = auth_user()
            owner = UserFactory()
            category = CategoryFactory()
            circle = CircleFactory()
            circle.members.append(borrower)
            circle.members.append(owner)
            item = ItemFactory(owner=owner, category=category)
            ItemImageFactory(item=item, url="https://example.com/img.jpg", position=0)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=10),
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="Can I borrow this?",
            )
            db.session.commit()

            login_user(client, borrower.email)
            response = client.get("/profile?tab=my-activity")
            assert response.status_code == 200
            content = response.data.decode("utf-8")

            # Both item name and thumbnail link to item detail
            assert f'href="/item/{item.id}"' in content
            # Dedicated View Loan button links to conversation
            assert f'href="/conversation/{msg.conversation_id}"' in content
            assert "View Loan" in content

    def test_lending_table_item_name_links_to_conversation(self, client, app, auth_user):
        """In lending table, item name and thumbnail link to item; View Loan button links to conversation."""
        with app.app_context():
            owner = auth_user()
            borrower = UserFactory()
            category = CategoryFactory()
            circle = CircleFactory()
            circle.members.append(owner)
            circle.members.append(borrower)
            item = ItemFactory(owner=owner, category=category)
            ItemImageFactory(item=item, url="https://example.com/img.jpg", position=0)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=10),
            )
            msg = MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="Can I borrow this?",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get("/profile?tab=my-activity")
            assert response.status_code == 200
            content = response.data.decode("utf-8")

            # Both item name and thumbnail link to item detail
            assert f'href="/item/{item.id}"' in content
            # Dedicated View Loan button links to conversation
            assert f'href="/conversation/{msg.conversation_id}"' in content
            assert "View Loan" in content

    def test_view_loan_links_to_current_active_loan_not_old_loan(self, client, app, auth_user):
        """When an item has been loaned multiple times, the View Loan button on the
        lending table links to the current active loan's conversation, not an old
        completed one."""
        with app.app_context():
            owner = auth_user()
            borrower1 = UserFactory()
            borrower2 = UserFactory()
            category = CategoryFactory()
            circle = CircleFactory()
            circle.members.append(owner)
            circle.members.append(borrower1)
            circle.members.append(borrower2)
            item = ItemFactory(owner=owner, category=category, available=False)

            # First loan: already completed
            loan1 = LoanRequestFactory(
                item=item,
                borrower=borrower1,
                status="approved",
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() - timedelta(days=10),
            )
            msg1 = MessageFactory(
                sender=borrower1,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan1,
                body="Can I borrow this? (first loan)",
            )
            loan1.status = "completed"

            # Second loan: currently active
            loan2 = LoanRequestFactory(
                item=item,
                borrower=borrower2,
                status="approved",
                start_date=date.today() - timedelta(days=5),
                end_date=date.today() + timedelta(days=10),
            )
            msg2 = MessageFactory(
                sender=borrower2,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan2,
                body="Can I borrow this? (second loan)",
            )
            db.session.commit()

            login_user(client, owner.email)
            response = client.get("/profile?tab=my-activity")
            assert response.status_code == 200
            content = response.data.decode("utf-8")

            # View Loan button must link to the current active loan's conversation
            assert f'href="/conversation/{msg2.conversation_id}"' in content
            # View Loan button must NOT link to the old completed loan's conversation
            assert f'href="/conversation/{msg1.conversation_id}"' not in content
            assert "View Loan" in content
