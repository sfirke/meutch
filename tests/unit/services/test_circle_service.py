from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app import db
from app.models import CircleJoinRequest, Message, circle_members
from app.services import circle_service
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from tests.factories import CircleFactory, UserFactory


class TestCircleService:
    def test_create_circle_with_address_uses_structured_geocoding(self, app):
        with app.app_context():
            creator = UserFactory()
            db.session.commit()

            with patch(
                "app.services.circle_service.geocode_address",
                return_value=(49.2570773, -123.0787301),
            ) as mock_geocode:
                result = circle_service.create_circle(
                    creator,
                    name="Vancouver Homes",
                    description="",
                    circle_type="open",
                    location_method="address",
                    street="1255 E 15th Avenue",
                    city="Vancouver",
                    state="BC",
                    zip_code="V5T 2S7",
                    country="Canada",
                )

            assert result["geocoding_failed"] is False
            assert result["circle"].latitude == 49.2570773
            assert result["circle"].longitude == -123.0787301
            mock_geocode.assert_called_once_with(
                street="1255 E 15th Avenue",
                city="Vancouver",
                state="BC",
                zip_code="V5T 2S7",
                country="Canada",
            )

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

    def test_join_circle_rejects_duplicate_pending_request(self, app):
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
            db.session.add(
                CircleJoinRequest(
                    circle_id=circle.id,
                    user_id=requester.id,
                    message="Please let me in",
                    status="pending",
                )
            )
            db.session.commit()

            with pytest.raises(InformationalError, match="pending join request"):
                circle_service.join_circle(circle, requester, "Trying again")

    def test_update_regional_circle_settings_enables_regional_circle_for_site_admin(self, app):
        with app.app_context():
            site_admin = UserFactory(is_admin=True)
            circle = CircleFactory(circle_type="open", latitude=42.2808, longitude=-83.7430)
            db.session.commit()

            updated_circle = circle_service.update_regional_circle_settings(
                circle,
                site_admin,
                is_regional=True,
                regional_radius_miles=25,
            )

            assert updated_circle.is_regional is True
            assert updated_circle.regional_radius_miles == 25

    def test_update_regional_circle_settings_rejects_non_site_admin(self, app):
        with app.app_context():
            circle_admin = UserFactory()
            circle = CircleFactory(circle_type="open", latitude=42.2808, longitude=-83.7430)
            db.session.commit()

            with pytest.raises(AuthorizationError, match="site admins"):
                circle_service.update_regional_circle_settings(
                    circle,
                    circle_admin,
                    is_regional=True,
                    regional_radius_miles=25,
                )

    def test_update_regional_circle_settings_rejects_non_public_circle(self, app):
        with app.app_context():
            site_admin = UserFactory(is_admin=True)
            circle = CircleFactory(circle_type="closed", latitude=42.2808, longitude=-83.7430)
            db.session.commit()

            with pytest.raises(InvalidActionError, match="public circles"):
                circle_service.update_regional_circle_settings(
                    circle,
                    site_admin,
                    is_regional=True,
                    regional_radius_miles=25,
                )

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

    def test_toggle_admin_rejects_self_demoting_last_admin(self, app):
        with app.app_context():
            admin = UserFactory()
            circle = CircleFactory()
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with pytest.raises(ConflictError, match="last admin"):
                circle_service.toggle_admin(circle, admin.id, admin, "remove")

    def test_leave_circle_promotes_earliest_remaining_member(self, app):
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

            result = circle_service.leave_circle(circle, admin)
            membership = (
                db.session.query(circle_members)
                .filter_by(circle_id=circle.id, user_id=member.id)
                .first()
            )

            assert result == {"circle_deleted": False}
            assert membership.is_admin is True

    def test_leave_circle_deletes_last_member_circle_and_image(self, app):
        with app.app_context():
            user = UserFactory()
            circle = CircleFactory(image_url="https://example.com/circle.jpg")
            db.session.execute(
                circle_members.insert().values(
                    user_id=user.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with patch("app.services.circle_service.delete_file") as mock_delete_file:
                result = circle_service.leave_circle(circle, user)

            assert result == {"circle_deleted": True}
            assert db.session.get(type(circle), circle.id) is None
            mock_delete_file.assert_called_once_with("https://example.com/circle.jpg")

    def test_leave_circle_blocks_deleting_regional_circle(self, app):
        with app.app_context():
            user = UserFactory()
            circle = CircleFactory(
                circle_type="open",
                latitude=42.2808,
                longitude=-83.7430,
                is_regional=True,
                regional_radius_miles=25,
            )
            db.session.execute(
                circle_members.insert().values(
                    user_id=user.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with pytest.raises(
                InvalidActionError,
                match="Remove the regional circle status from this circle before making this change.",
            ):
                circle_service.leave_circle(circle, user)

    def test_update_circle_blocks_visibility_change_for_regional_circle(self, app):
        with app.app_context():
            admin = UserFactory()
            circle = CircleFactory(
                circle_type="open",
                latitude=42.2808,
                longitude=-83.7430,
                is_regional=True,
                regional_radius_miles=25,
            )
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with pytest.raises(
                InvalidActionError,
                match="Remove the regional circle status from this circle before making this change.",
            ):
                circle_service.update_circle(
                    circle,
                    admin,
                    name=circle.name,
                    description=circle.description,
                    circle_type="closed",
                    location_method="skip",
                )

    def test_remove_member_rejects_self_removal(self, app):
        with app.app_context():
            admin = UserFactory()
            circle = CircleFactory()
            db.session.execute(
                circle_members.insert().values(
                    user_id=admin.id,
                    circle_id=circle.id,
                    joined_at=datetime.now(UTC),
                    is_admin=True,
                )
            )
            db.session.commit()

            with pytest.raises(InvalidActionError, match="leave circle button"):
                circle_service.remove_member(circle, admin, admin)
