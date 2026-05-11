from datetime import UTC, datetime
from unittest.mock import patch

from app import db
from app.models import CircleJoinRequest, Message, circle_members
from app.services import circle_service
from tests.factories import CircleFactory, UserFactory


class TestCircleService:
    def test_join_circle_with_approval_creates_request_and_sends_email(self, app):
        with app.app_context():
            requester = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(circle_type="closed")
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with patch(
                "app.services.circle_service.send_circle_join_request_notification_email"
            ) as mock_email:
                join_request = circle_service.join_circle(
                    circle,
                    requester,
                    "Please let me in",
                )

            assert join_request.status == "pending"
            assert join_request.circle_id == circle.id
            mock_email.assert_called_once_with(join_request)

    def test_handle_join_request_approve_adds_member_and_message(self, app):
        with app.app_context():
            requester = UserFactory()
            admin = UserFactory()
            circle = CircleFactory(circle_type="closed")
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=requester.id,
                message="Please let me in",
                status="pending",
            )
            db.session.add(join_request)
            db.session.commit()

            with patch(
                "app.services.circle_service.send_circle_join_request_decision_email"
            ) as mock_email:
                handled_action = circle_service.handle_join_request(
                    circle,
                    join_request,
                    admin,
                    "approve",
                )

            membership = (
                db.session.query(circle_members)
                .filter_by(circle_id=circle.id, user_id=requester.id)
                .first()
            )
            decision_message = Message.query.filter_by(
                recipient_id=requester.id,
                circle_id=circle.id,
            ).one()
            assert handled_action == "approve"
            assert membership is not None
            assert join_request.status == "approved"
            assert "approved" in decision_message.body.lower()
            mock_email.assert_called_once_with(join_request)

    def test_toggle_admin_updates_membership_flag(self, app):
        with app.app_context():
            admin = UserFactory()
            member = UserFactory()
            circle = CircleFactory()
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.execute(
                circle_members.insert().values(
                    user_id=member.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=False,
                )
            )
            db.session.commit()

            is_admin = circle_service.toggle_admin(circle, member.id, admin, "add")
            membership = (
                db.session.query(circle_members)
                .filter_by(circle_id=circle.id, user_id=member.id)
                .first()
            )

            assert is_admin is True
            assert membership.is_admin is True
