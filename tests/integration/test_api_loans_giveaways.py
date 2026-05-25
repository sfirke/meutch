"""Integration tests for API loan endpoints."""

from datetime import UTC, date, datetime, timedelta

from app import db
from tests.factories import (
    CircleFactory,
    ItemFactory,
    LoanRequestFactory,
    MessageFactory,
    UserFactory,
)

from .api_test_helpers import auth_headers, login_api_user


def _loan_request_payload(*, start_offset=1, end_offset=7, message="Could I borrow this?"):
    return {
        "start_date": (date.today() + timedelta(days=start_offset)).isoformat(),
        "end_date": (date.today() + timedelta(days=end_offset)).isoformat(),
        "message": message,
    }


def _share_circle(*users):
    circle = CircleFactory()
    circle.members.extend(users)
    return circle


class TestApiLoans:
    """Exercise loan activity reads and loan mutation behavior."""

    def test_me_loans_borrowing_returns_authenticated_users_active_entries(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            owner = UserFactory()
            other_owner = UserFactory()

            item = ItemFactory(owner=owner, available=False, name="Borrowed tent")
            other_item = ItemFactory(owner=other_owner, available=False, name="Other ladder")
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=2),
                end_date=date.today() + timedelta(days=2),
            )
            LoanRequestFactory(
                item=other_item,
                borrower=UserFactory(),
                status="approved",
                start_date=date.today() - timedelta(days=2),
                end_date=date.today() + timedelta(days=10),
            )
            first_message = MessageFactory(
                sender=borrower,
                recipient=owner,
                item=item,
                loan_request=loan,
                body="Could I borrow this for the weekend?",
            )
            latest_message = MessageFactory(
                sender=owner,
                recipient=borrower,
                item=item,
                loan_request=loan,
                body="Yes, that works.",
            )
            first_message.timestamp = datetime.now(UTC) - timedelta(minutes=2)
            latest_message.timestamp = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = str(loan.id)
            owner_id = str(owner.id)
            borrower_id = str(borrower.id)
            item_id = str(item.id)
            latest_message_id = str(latest_message.id)

        response = client.get(
            "/api/v1/me/loans?role=borrowing&page=1&per_page=10",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["pagination"]["total"] == 1
        assert payload["loans"][0] == {
            "id": loan_id,
            "status": "approved",
            "start_date": (date.today() - timedelta(days=2)).isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "item": {
                "id": item_id,
                "name": "Borrowed tent",
                "available": False,
                "image_url": None,
            },
            "owner": payload["loans"][0]["owner"],
            "borrower": payload["loans"][0]["borrower"],
            "latest_conversation_message_id": latest_message_id,
            "due_state": "due_soon",
            "days_until_due": 2,
            "days_overdue": 0,
        }
        assert payload["loans"][0]["owner"]["id"] == owner_id
        assert payload["loans"][0]["borrower"]["id"] == borrower_id

    def test_me_loans_lending_returns_authenticated_users_active_entries(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False, name="Loaned drill")
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=5),
            )
            message = MessageFactory(
                sender=borrower,
                recipient=owner,
                item=item,
                loan_request=loan,
                body="Thanks again.",
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            borrower_id = str(borrower.id)
            message_id = str(message.id)

        response = client.get(
            "/api/v1/me/loans?role=lending&page=1&per_page=10",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["pagination"]["total"] == 1
        assert payload["loans"][0]["borrower"]["id"] == borrower_id
        assert payload["loans"][0]["latest_conversation_message_id"] == message_id
        assert payload["loans"][0]["item"]["name"] == "Loaned drill"

    def test_loan_detail_is_visible_only_to_owner_or_borrower(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory(email_confirmed=True)
            outsider = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=4),
            )
            anchor_message = MessageFactory(
                sender=borrower,
                recipient=owner,
                item=item,
                loan_request=loan,
            )
            db.session.commit()
            owner_token = login_api_user(client, owner.email)
            borrower_token = login_api_user(client, borrower.email)
            outsider_token = login_api_user(client, outsider.email)
            loan_id = loan.id
            anchor_message_id = str(anchor_message.id)

        owner_response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers=auth_headers(owner_token),
        )
        borrower_response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers=auth_headers(borrower_token),
        )
        outsider_response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers=auth_headers(outsider_token),
        )

        assert owner_response.status_code == 200
        assert borrower_response.status_code == 200
        assert (
            owner_response.get_json()["loan"]["latest_conversation_message_id"] == anchor_message_id
        )
        assert outsider_response.status_code == 403
        assert outsider_response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_create_loan_request_returns_loan_and_message(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            item = ItemFactory(owner=owner, available=True)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id
            owner_id = str(owner.id)
            borrower_id = str(borrower.id)

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(message="Could I borrow this next Tuesday?"),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["loan"]["status"] == "pending"
        assert payload["message"]["sender"]["id"] == borrower_id
        assert payload["message"]["recipient"]["id"] == owner_id

    def test_borrower_cannot_request_their_own_item(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_borrower_cannot_request_giveaway_item_as_loan(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            item = ItemFactory(
                owner=owner,
                is_giveaway=True,
                giveaway_visibility="public",
                claim_status="unclaimed",
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_borrower_cannot_request_unavailable_item(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            item = ItemFactory(owner=owner, available=False)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_duplicate_pending_loan_requests_are_rejected(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            item = ItemFactory(owner=owner, available=True)
            LoanRequestFactory(item=item, borrower=borrower, status="pending")
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(message="Checking again"),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_owner_can_approve_or_deny_pending_requests(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            deny_borrower = UserFactory()
            item = ItemFactory(owner=owner, available=True)
            other_item = ItemFactory(owner=owner, available=True)
            approve_loan = LoanRequestFactory(item=item, borrower=borrower, status="pending")
            deny_loan = LoanRequestFactory(
                item=other_item,
                borrower=deny_borrower,
                status="pending",
            )
            MessageFactory(sender=borrower, recipient=owner, item=item, loan_request=approve_loan)
            MessageFactory(
                sender=deny_borrower,
                recipient=owner,
                item=other_item,
                loan_request=deny_loan,
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            approve_loan_id = approve_loan.id
            deny_loan_id = deny_loan.id

        approve_response = client.post(
            f"/api/v1/loans/{approve_loan_id}/approve",
            headers=auth_headers(access_token),
        )
        deny_response = client.post(
            f"/api/v1/loans/{deny_loan_id}/deny",
            headers=auth_headers(access_token),
        )

        assert approve_response.status_code == 200
        assert deny_response.status_code == 200
        assert approve_response.get_json()["loan"]["status"] == "approved"
        assert approve_response.get_json()["loan"]["item"]["available"] is False
        assert deny_response.get_json()["loan"]["status"] == "denied"
        assert deny_response.get_json()["loan"]["item"]["available"] is True

    def test_borrower_can_cancel_only_pending_request(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            item = ItemFactory(owner=owner, available=True)
            other_item = ItemFactory(owner=owner, available=False)
            pending_loan = LoanRequestFactory(item=item, borrower=borrower, status="pending")
            approved_loan = LoanRequestFactory(
                item=other_item,
                borrower=borrower,
                status="approved",
            )
            MessageFactory(sender=borrower, recipient=owner, item=item, loan_request=pending_loan)
            MessageFactory(
                sender=borrower,
                recipient=owner,
                item=other_item,
                loan_request=approved_loan,
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            pending_loan_id = pending_loan.id
            approved_loan_id = approved_loan.id

        cancel_response = client.post(
            f"/api/v1/loans/{pending_loan_id}/cancel",
            headers=auth_headers(access_token),
        )
        invalid_response = client.post(
            f"/api/v1/loans/{approved_loan_id}/cancel",
            headers=auth_headers(access_token),
        )

        assert cancel_response.status_code == 200
        assert cancel_response.get_json()["loan"]["status"] == "canceled"
        assert invalid_response.status_code == 409

    def test_owner_can_cancel_only_approved_loan(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False)
            other_item = ItemFactory(owner=owner, available=True)
            approved_loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")
            pending_loan = LoanRequestFactory(item=other_item, borrower=borrower, status="pending")
            MessageFactory(sender=borrower, recipient=owner, item=item, loan_request=approved_loan)
            MessageFactory(
                sender=borrower, recipient=owner, item=other_item, loan_request=pending_loan
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            approved_loan_id = approved_loan.id
            pending_loan_id = pending_loan.id

        cancel_response = client.post(
            f"/api/v1/loans/{approved_loan_id}/owner-cancel",
            headers=auth_headers(access_token),
        )
        invalid_response = client.post(
            f"/api/v1/loans/{pending_loan_id}/owner-cancel",
            headers=auth_headers(access_token),
        )

        assert cancel_response.status_code == 200
        assert cancel_response.get_json()["loan"]["status"] == "canceled"
        assert cancel_response.get_json()["loan"]["item"]["available"] is True
        assert invalid_response.status_code == 409

    def test_complete_requires_approved_loan_and_restores_item_availability(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False)
            other_item = ItemFactory(owner=owner, available=True)
            approved_loan = LoanRequestFactory(item=item, borrower=borrower, status="approved")
            pending_loan = LoanRequestFactory(item=other_item, borrower=borrower, status="pending")
            MessageFactory(sender=borrower, recipient=owner, item=item, loan_request=approved_loan)
            MessageFactory(
                sender=borrower, recipient=owner, item=other_item, loan_request=pending_loan
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            approved_loan_id = approved_loan.id
            pending_loan_id = pending_loan.id

        complete_response = client.post(
            f"/api/v1/loans/{approved_loan_id}/complete",
            headers=auth_headers(access_token),
        )
        invalid_response = client.post(
            f"/api/v1/loans/{pending_loan_id}/complete",
            headers=auth_headers(access_token),
        )

        assert complete_response.status_code == 200
        assert complete_response.get_json()["loan"]["status"] == "completed"
        assert complete_response.get_json()["loan"]["item"]["available"] is True
        assert invalid_response.status_code == 409

    def test_extend_updates_due_date_and_resets_reminders(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory()
            item = ItemFactory(owner=owner, available=False)
            loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=3),
                end_date=date.today() + timedelta(days=2),
            )
            loan.due_soon_reminder_sent = datetime.now(UTC) - timedelta(days=1)
            loan.due_date_reminder_sent = datetime.now(UTC) - timedelta(days=1)
            loan.last_overdue_reminder_sent = datetime.now(UTC) - timedelta(days=1)
            loan.overdue_reminder_count = 4
            MessageFactory(sender=borrower, recipient=owner, item=item, loan_request=loan)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id = loan.id
            new_end_date = (date.today() + timedelta(days=7)).isoformat()

        response = client.post(
            f"/api/v1/loans/{loan_id}/extend",
            json={
                "new_end_date": new_end_date,
                "message": "Take a little more time with it.",
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["loan"]["end_date"] == new_end_date
        assert payload["is_extension"] is True
        assert payload["message"]["body"].endswith("Take a little more time with it.")

        with app.app_context():
            db.session.expire_all()
            refreshed_loan = db.session.get(type(loan), loan_id)
            assert refreshed_loan.due_soon_reminder_sent is None
            assert refreshed_loan.due_date_reminder_sent is None
            assert refreshed_loan.last_overdue_reminder_sent is None
            assert refreshed_loan.overdue_reminder_count == 0
