"""Integration tests for API loan endpoints."""

from datetime import UTC, date, datetime, timedelta

from app import db
from tests.factories import (
    CircleFactory,
    ConversationFactory,
    ItemFactory,
    LoanExtensionRequestFactory,
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


def _approved_loan(owner, borrower, *, end_offset=3):
    return LoanRequestFactory(
        item=ItemFactory(owner=owner, available=False),
        borrower=borrower,
        status="approved",
        start_date=date.today() - timedelta(days=2),
        end_date=date.today() + timedelta(days=end_offset),
    )


def _extension_payload(*, proposed_offset=10, message="Could I keep it a bit longer?"):
    return {
        "proposed_end_date": (date.today() + timedelta(days=proposed_offset)).isoformat(),
        "message": message,
    }


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
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
                body="Could I borrow this for the weekend?",
            )
            latest_message = MessageFactory(
                sender=owner,
                recipient=borrower,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
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
            "pending_extension_request": None,
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
                conversation=ConversationFactory(context_type="item", context_id=item.id),
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
                conversation=ConversationFactory(context_type="item", context_id=item.id),
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
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=approve_loan,
            )
            MessageFactory(
                sender=deny_borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=other_item.id),
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
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=pending_loan,
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=other_item.id),
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
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=approved_loan,
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=other_item.id),
                loan_request=pending_loan,
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
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=approved_loan,
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=other_item.id),
                loan_request=pending_loan,
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
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan,
            )
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

    def test_me_loans_pending_returns_borrowers_pending_requests(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            item = ItemFactory(owner=owner, available=True)
            pending_loan = LoanRequestFactory(
                item=item,
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=3),
                end_date=date.today() + timedelta(days=10),
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=pending_loan,
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            pending_loan_id = str(pending_loan.id)

        response = client.get(
            "/api/v1/me/loans?role=borrowing&status=pending",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["pagination"]["total"] == 1
        assert payload["loans"][0]["id"] == pending_loan_id
        assert payload["loans"][0]["status"] == "pending"
        assert payload["loans"][0]["due_state"] is None
        assert payload["loans"][0]["days_until_due"] is None
        assert payload["loans"][0]["days_overdue"] is None

    def test_me_loans_all_returns_approved_and_pending(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            active_item = ItemFactory(owner=owner, available=False)
            pending_item = ItemFactory(owner=owner, available=True)
            approved_loan = LoanRequestFactory(
                item=active_item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=5),
            )
            pending_loan = LoanRequestFactory(
                item=pending_item,
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=7),
                end_date=date.today() + timedelta(days=14),
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=active_item.id),
                loan_request=approved_loan,
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=pending_item.id),
                loan_request=pending_loan,
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)

        response = client.get(
            "/api/v1/me/loans?role=borrowing&status=all",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        statuses = {loan["status"] for loan in payload["loans"]}
        assert payload["pagination"]["total"] == 2
        assert statuses == {"approved", "pending"}

    def test_me_loans_active_default_excludes_pending(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            active_item = ItemFactory(owner=owner, available=False)
            pending_item = ItemFactory(owner=owner, available=True)
            approved_loan = LoanRequestFactory(
                item=active_item,
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=5),
            )
            pending_loan = LoanRequestFactory(
                item=pending_item,
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=7),
                end_date=date.today() + timedelta(days=14),
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=active_item.id),
                loan_request=approved_loan,
            )
            MessageFactory(
                sender=borrower,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=pending_item.id),
                loan_request=pending_loan,
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)

        default_response = client.get(
            "/api/v1/me/loans?role=borrowing",
            headers=auth_headers(access_token),
        )

        assert default_response.status_code == 200
        payload = default_response.get_json()
        assert payload["pagination"]["total"] == 1
        assert payload["loans"][0]["status"] == "approved"

    def test_me_loans_pending_lending_shows_owner_inbox(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower_a = UserFactory()
            borrower_b = UserFactory()
            item = ItemFactory(owner=owner, available=True)
            other_item = ItemFactory(owner=owner, available=True)
            loan_a = LoanRequestFactory(item=item, borrower=borrower_a, status="pending")
            loan_b = LoanRequestFactory(item=other_item, borrower=borrower_b, status="pending")
            MessageFactory(
                sender=borrower_a,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=item.id),
                loan_request=loan_a,
            )
            MessageFactory(
                sender=borrower_b,
                recipient=owner,
                conversation=ConversationFactory(context_type="item", context_id=other_item.id),
                loan_request=loan_b,
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)

        response = client.get(
            "/api/v1/me/loans?role=lending&status=pending",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["pagination"]["total"] == 2
        assert all(loan["status"] == "pending" for loan in payload["loans"])

    def test_me_loans_all_lists_pending_before_approved(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            approved_loan = LoanRequestFactory(
                item=ItemFactory(owner=owner, available=False),
                borrower=borrower,
                status="approved",
                start_date=date.today() - timedelta(days=3),
                end_date=date.today() + timedelta(days=1),
            )
            pending_late = LoanRequestFactory(
                item=ItemFactory(owner=owner),
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=20),
            )
            pending_early = LoanRequestFactory(
                item=ItemFactory(owner=owner),
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=2),
                end_date=date.today() + timedelta(days=10),
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            expected_ids = [str(pending_early.id), str(pending_late.id), str(approved_loan.id)]

        response = client.get(
            "/api/v1/me/loans?role=borrowing&status=all",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert [loan["id"] for loan in response.get_json()["loans"]] == expected_ids

    def test_me_loans_reports_owner_profile_viewable_per_user(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            circle_owner = UserFactory()
            unviewable_owner = UserFactory()
            _share_circle(borrower, circle_owner)
            LoanRequestFactory(
                item=ItemFactory(owner=circle_owner, available=False),
                borrower=borrower,
                status="approved",
            )
            LoanRequestFactory(
                item=ItemFactory(owner=unviewable_owner, available=False),
                borrower=borrower,
                status="approved",
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            circle_owner_id = str(circle_owner.id)

        response = client.get(
            "/api/v1/me/loans?role=borrowing",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        flags = {
            loan["owner"]["id"]: loan["owner"]["profile_viewable"]
            for loan in response.get_json()["loans"]
        }
        assert len(flags) == 2
        assert flags.pop(circle_owner_id) is True
        assert list(flags.values()) == [False]

    def test_me_loans_lending_reports_borrower_profile_viewable_per_user(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            circle_borrower = UserFactory()
            unviewable_borrower = UserFactory()
            _share_circle(owner, circle_borrower)
            for borrower in (circle_borrower, unviewable_borrower):
                LoanRequestFactory(
                    item=ItemFactory(owner=owner, available=False),
                    borrower=borrower,
                    status="approved",
                )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            circle_borrower_id = str(circle_borrower.id)

        response = client.get(
            "/api/v1/me/loans?role=lending&status=all",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        flags = {
            loan["borrower"]["id"]: loan["borrower"]["profile_viewable"]
            for loan in response.get_json()["loans"]
        }
        assert len(flags) == 2
        assert flags.pop(circle_borrower_id) is True
        assert list(flags.values()) == [False]

    def test_me_loans_lending_all_lists_pending_before_approved(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            approved_loan = LoanRequestFactory(
                item=ItemFactory(owner=owner, available=False),
                borrower=UserFactory(),
                status="approved",
                start_date=date.today() - timedelta(days=3),
                end_date=date.today() + timedelta(days=1),
            )
            pending_loan = LoanRequestFactory(
                item=ItemFactory(owner=owner),
                borrower=UserFactory(),
                status="pending",
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=20),
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            expected_ids = [str(pending_loan.id), str(approved_loan.id)]

        response = client.get(
            "/api/v1/me/loans?role=lending&status=all",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert [loan["id"] for loan in response.get_json()["loans"]] == expected_ids

    def test_loan_detail_marks_counterpart_profile_viewable_with_shared_circle(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            loan = LoanRequestFactory(
                item=ItemFactory(owner=owner, available=False),
                borrower=borrower,
                status="approved",
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id = loan.id

        response = client.get(f"/api/v1/loans/{loan_id}", headers=auth_headers(access_token))

        assert response.status_code == 200
        assert response.get_json()["loan"]["borrower"]["profile_viewable"] is True

    def test_create_loan_request_rejects_past_start_date(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            item = ItemFactory(owner=owner, available=True)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            item_id = item.id

        response = client.post(
            f"/api/v1/items/{item_id}/loan-requests",
            json=_loan_request_payload(start_offset=-1),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 422
        assert response.get_json()["error"]["details"] == {
            "start_date": ["Start date cannot be in the past."]
        }


class TestApiLoanExtensionRequests:
    """Exercise borrower extension requests and the owner's decision."""

    def test_borrower_creates_extension_request(self, client, app):
        with app.app_context():
            owner = UserFactory()
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            loan = _approved_loan(owner, borrower)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id
            current_end_date = loan.end_date.isoformat()
            borrower_id = str(borrower.id)

        payload_in = _extension_payload()
        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=payload_in,
            headers=auth_headers(access_token),
        )

        assert response.status_code == 201
        payload = response.get_json()
        pending = payload["loan"]["pending_extension_request"]
        assert payload["loan"]["id"] == str(loan_id)
        assert payload["loan"]["end_date"] == current_end_date
        assert pending["status"] == "pending"
        assert pending["previous_end_date"] == current_end_date
        assert pending["proposed_end_date"] == payload_in["proposed_end_date"]
        assert pending["message"] == payload_in["message"]
        assert pending["responded_at"] is None
        assert payload["message"]["sender"]["id"] == borrower_id
        assert payload["message"]["loan_extension_request"]["id"] == pending["id"]
        assert payload["loan"]["latest_conversation_message_id"] == payload["message"]["id"]
        assert payload["loan"]["owner"]["profile_viewable"] is True

    def test_owner_cannot_create_extension_request(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory())
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_extension_request_requires_approved_loan(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = LoanRequestFactory(
                item=ItemFactory(owner=UserFactory()),
                borrower=borrower,
                status="pending",
                start_date=date.today() + timedelta(days=1),
                end_date=date.today() + timedelta(days=5),
            )
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_duplicate_pending_extension_request_is_rejected(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = _approved_loan(UserFactory(), borrower)
            LoanExtensionRequestFactory(loan_request=loan)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert (
            response.get_json()["error"]["message"]
            == "You already have a pending extension request for this loan."
        )

    def test_extension_request_must_move_due_date_later(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = _approved_loan(UserFactory(), borrower, end_offset=5)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(proposed_offset=5),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert (
            response.get_json()["error"]["message"]
            == "Proposed due date must be after the current due date."
        )

    def test_extension_request_rejects_past_proposed_date(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = _approved_loan(UserFactory(), borrower)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(proposed_offset=-1),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 422
        assert response.get_json()["error"]["details"] == {
            "proposed_end_date": ["Proposed due date cannot be in the past."]
        }

    def test_extension_request_rejects_short_message(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = _approved_loan(UserFactory(), borrower)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            loan_id = loan.id

        response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(message="Too short"),
            headers=auth_headers(access_token),
        )

        assert response.status_code == 422
        assert list(response.get_json()["error"]["details"]) == ["message"]

    def test_owner_approves_extension_request(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory())
            extension = LoanExtensionRequestFactory(loan_request=loan)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            extension_id = extension.id
            proposed_end_date = extension.proposed_end_date.isoformat()

        response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["loan"]["end_date"] == proposed_end_date
        assert payload["loan"]["pending_extension_request"] is None
        assert payload["message"]["loan_extension_request"] is None

        with app.app_context():
            refreshed = db.session.get(type(extension), extension_id)
            assert refreshed.status == "approved"
            assert refreshed.responded_at is not None

    def test_borrower_cannot_approve_extension_request(self, client, app):
        with app.app_context():
            borrower = UserFactory(email_confirmed=True)
            loan = _approved_loan(UserFactory(), borrower)
            extension = LoanExtensionRequestFactory(loan_request=loan)
            db.session.commit()
            access_token = login_api_user(client, borrower.email)
            extension_id = extension.id

        response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "FORBIDDEN"

    def test_answered_extension_request_cannot_be_approved(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory())
            extension = LoanExtensionRequestFactory(
                loan_request=loan,
                status="denied",
                responded_at=datetime.now(UTC),
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            extension_id = extension.id

        response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_approve_after_owner_extends_past_proposed_date_conflicts(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory(), end_offset=3)
            extension = LoanExtensionRequestFactory(
                loan_request=loan,
                proposed_end_date=date.today() + timedelta(days=10),
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id = loan.id
            extension_id = extension.id
            owner_end_date = (date.today() + timedelta(days=14)).isoformat()

        extend_response = client.post(
            f"/api/v1/loans/{loan_id}/extend",
            json={"new_end_date": owner_end_date, "message": "Keep it two weeks."},
            headers=auth_headers(access_token),
        )
        approve_response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/approve",
            headers=auth_headers(access_token),
        )

        assert extend_response.status_code == 200
        assert approve_response.status_code == 409
        with app.app_context():
            refreshed_loan = db.session.get(type(loan), loan_id)
            assert refreshed_loan.end_date.isoformat() == owner_end_date

    def test_approving_stale_extension_request_conflicts(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory(), end_offset=10)
            extension = LoanExtensionRequestFactory(
                loan_request=loan,
                previous_end_date=date.today() + timedelta(days=3),
                proposed_end_date=date.today() + timedelta(days=7),
            )
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            loan_id = loan.id
            extension_id = extension.id

        response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["message"].startswith(
            "The proposed due date is no longer later than the current due date."
        )
        with app.app_context():
            refreshed_loan = db.session.get(type(loan), loan_id)
            assert refreshed_loan.end_date == date.today() + timedelta(days=10)
            assert db.session.get(type(extension), extension_id).status == "pending"

    def test_owner_denies_extension_request(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            loan = _approved_loan(owner, UserFactory())
            extension = LoanExtensionRequestFactory(loan_request=loan)
            db.session.commit()
            access_token = login_api_user(client, owner.email)
            extension_id = extension.id
            current_end_date = loan.end_date.isoformat()

        response = client.post(
            f"/api/v1/loan-extension-requests/{extension_id}/deny",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["loan"]["end_date"] == current_end_date
        assert payload["loan"]["pending_extension_request"] is None
        with app.app_context():
            assert db.session.get(type(extension), extension_id).status == "denied"

    def test_pending_extension_request_appears_on_loan_reads_but_not_item_detail(self, client, app):
        with app.app_context():
            owner = UserFactory(email_confirmed=True)
            borrower = UserFactory(email_confirmed=True)
            _share_circle(owner, borrower)
            loan = _approved_loan(owner, borrower)
            db.session.commit()
            owner_token = login_api_user(client, owner.email)
            borrower_token = login_api_user(client, borrower.email)
            loan_id = loan.id
            item_id = loan.item_id

        create_response = client.post(
            f"/api/v1/loans/{loan_id}/extension-requests",
            json=_extension_payload(),
            headers=auth_headers(borrower_token),
        )
        assert create_response.status_code == 201
        created = create_response.get_json()
        extension_id = created["loan"]["pending_extension_request"]["id"]
        request_message_id = created["message"]["id"]

        list_response = client.get(
            "/api/v1/me/loans?role=lending&status=active",
            headers=auth_headers(owner_token),
        )
        detail_response = client.get(f"/api/v1/loans/{loan_id}", headers=auth_headers(owner_token))
        thread_response = client.get(
            f"/api/v1/messages/{request_message_id}",
            headers=auth_headers(owner_token),
        )
        item_response = client.get(f"/api/v1/items/{item_id}", headers=auth_headers(owner_token))

        assert list_response.status_code == 200
        [listed] = list_response.get_json()["loans"]
        assert listed["pending_extension_request"]["id"] == extension_id

        assert detail_response.status_code == 200
        assert detail_response.get_json()["loan"]["pending_extension_request"]["id"] == (
            extension_id
        )

        assert thread_response.status_code == 200
        thread = thread_response.get_json()
        assert thread["active_loan"]["id"] == str(loan_id)
        assert thread["active_loan"]["pending_extension_request"]["id"] == extension_id
        request_messages = [m for m in thread["messages"] if m["id"] == request_message_id]
        assert request_messages[0]["loan_extension_request"]["id"] == extension_id

        assert item_response.status_code == 200
        current_loan = item_response.get_json()["item"]["current_loan"]
        assert current_loan["id"] == str(loan_id)
        assert "pending_extension_request" not in current_loan
