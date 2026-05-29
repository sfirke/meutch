"""Integration tests for API circle reads and writes."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import patch

from app import db
from app.models import Circle, CircleJoinRequest, circle_members
from tests.factories import CircleFactory, CircleJoinRequestFactory, UserFactory

from .api_test_helpers import auth_headers, login_api_user


def _add_circle_membership(circle, user, *, is_admin=False, joined_at=None):
    db.session.execute(
        circle_members.insert().values(
            user_id=user.id,
            circle_id=circle.id,
            joined_at=joined_at or datetime.now(UTC),
            is_admin=is_admin,
        )
    )


def _get_circle_membership(circle_id, user_id):
    return db.session.query(circle_members).filter_by(circle_id=circle_id, user_id=user_id).first()


class TestApiCircles:
    """Exercise circle list, detail, and mutation behavior."""

    def test_circles_list_returns_membership_and_pending_request_metadata(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member_circle = CircleFactory(circle_type="open", name="Member Circle")
            pending_circle = CircleFactory(circle_type="closed", name="Pending Circle")
            CircleFactory(circle_type="secret", name="Secret Circle")

            member_circle.members.append(viewer)
            db.session.add(
                CircleJoinRequestFactory(circle=pending_circle, user=viewer, status="pending")
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)

        response = client.get(
            "/api/v1/circles?membership=discoverable&page=1&per_page=10",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        circles_by_name = {circle["name"]: circle for circle in payload["circles"]}

        assert payload["pagination"] == {
            "page": 1,
            "per_page": 10,
            "total": 2,
            "pages": 1,
            "has_next": False,
            "has_prev": False,
        }
        assert "Secret Circle" not in circles_by_name
        assert circles_by_name["Member Circle"]["is_member"] is True
        assert circles_by_name["Pending Circle"]["has_pending_join_request"] is True

    def test_circle_detail_hides_members_for_closed_circle_non_member(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member = UserFactory()
            circle = CircleFactory(circle_type="closed")
            circle.members.append(member)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            circle_id = circle.id

        response = client.get(
            f"/api/v1/circles/{circle_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json()["circle"]["can_view_members"] is False
        assert response.get_json()["circle"]["members"] == []

    def test_circle_detail_returns_404_for_secret_circle_non_member(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            member = UserFactory()
            circle = CircleFactory(circle_type="secret")
            circle.members.append(member)
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            circle_id = circle.id

        response = client.get(
            f"/api/v1/circles/{circle_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404

    def test_circle_detail_includes_regional_fields(self, client, app):
        with app.app_context():
            viewer = UserFactory(email_confirmed=True)
            circle = CircleFactory(
                circle_type="open",
                latitude=42.2808,
                longitude=-83.7430,
                is_regional=True,
                regional_radius_miles=25,
            )
            db.session.commit()
            access_token = login_api_user(client, viewer.email)
            circle_id = circle.id

        response = client.get(
            f"/api/v1/circles/{circle_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        payload = response.get_json()["circle"]
        assert payload["is_regional"] is True
        assert payload["regional_radius_miles"] == 25

    def test_circles_list_requires_authentication(self, client, app):
        response = client.get("/api/v1/circles")

        assert response.status_code == 401

    def test_circle_create_returns_circle_payload_and_creator_admin_membership(self, client, app):
        with app.app_context():
            creator = UserFactory(email_confirmed=True)
            access_token = login_api_user(client, creator.email)
            creator_id = creator.id

        with patch(
            "app.services.circle_service.upload_circle_image",
            return_value="https://cdn.example.com/circle.png",
        ):
            response = client.post(
                "/api/v1/circles",
                data={
                    "name": "Tool Library Crew",
                    "description": "Shared tools for the block.",
                    "circle_type": "open",
                    "location_method": "skip",
                    "image": (BytesIO(b"circle-image"), "circle.png"),
                },
                headers=auth_headers(access_token),
            )

        assert response.status_code == 201
        payload = response.get_json()

        assert payload["geocoding_failed"] is False
        assert payload["image_removed"] is False
        assert payload["image_updated"] is True
        assert payload["circle"]["name"] == "Tool Library Crew"
        assert payload["circle"]["is_member"] is True
        assert payload["circle"]["is_admin"] is True
        assert payload["circle"]["member_count"] == 1
        assert payload["circle"]["can_view_members"] is True
        assert payload["circle"]["image_url"] == "https://cdn.example.com/circle.png"

        with app.app_context():
            circle = Circle.query.filter_by(name="Tool Library Crew").one()
            membership = _get_circle_membership(circle.id, creator_id)
            assert membership is not None
            assert membership.is_admin is True

    def test_circle_update_returns_geocoding_and_image_flags(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            circle = CircleFactory(
                name="Repair Neighbors",
                image_url="https://cdn.example.com/original.png",
            )
            _add_circle_membership(circle, admin, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id

        with (
            patch("app.services.circle_service.geocode_address", return_value=None),
            patch("app.services.circle_service.delete_file") as mock_delete_file,
        ):
            response = client.patch(
                f"/api/v1/circles/{circle_id}",
                data={
                    "name": "Repair Neighbors Updated",
                    "description": "Updated description.",
                    "circle_type": "closed",
                    "location_method": "address",
                    "street": "123 Main St",
                    "city": "Portland",
                    "state": "OR",
                    "zip_code": "97201",
                    "country": "USA",
                    "delete_image": "true",
                },
                headers=auth_headers(access_token),
            )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["geocoding_failed"] is True
        assert payload["image_removed"] is True
        assert payload["image_updated"] is False
        assert payload["circle"]["name"] == "Repair Neighbors Updated"
        assert payload["circle"]["circle_type"] == "closed"
        mock_delete_file.assert_called_once_with("https://cdn.example.com/original.png")

    def test_circle_name_conflict_returns_409(self, client, app):
        with app.app_context():
            creator = UserFactory(email_confirmed=True)
            CircleFactory(name="Neighborhood Tools")
            db.session.commit()
            access_token = login_api_user(client, creator.email)

        response = client.post(
            "/api/v1/circles",
            json={
                "name": "neighborhood tools",
                "description": "A duplicate name.",
                "circle_type": "open",
                "location_method": "skip",
            },
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_open_circle_join_adds_member_immediately(self, client, app):
        with app.app_context():
            admin = UserFactory()
            joiner = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, admin, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, joiner.email)
            circle_id = circle.id
            joiner_id = joiner.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/join",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "membership_status": "member",
            "join_request": None,
        }

        with app.app_context():
            membership = _get_circle_membership(circle_id, joiner_id)
            assert membership is not None
            assert membership.is_admin is False

    def test_closed_and_secret_circles_create_pending_join_requests(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            access_token = login_api_user(client, requester.email)
            requester_id = requester.id
            circle_ids = []
            for circle_type in ("closed", "secret"):
                admin = UserFactory()
                circle = CircleFactory(circle_type=circle_type)
                _add_circle_membership(circle, admin, is_admin=True)
                circle_ids.append(circle.id)
            db.session.commit()

        for circle_id in circle_ids:
            response = client.post(
                f"/api/v1/circles/{circle_id}/join",
                json={"message": "Please let me join."},
                headers=auth_headers(access_token),
            )

            assert response.status_code == 200
            payload = response.get_json()
            assert payload["membership_status"] == "pending"
            assert payload["join_request"]["status"] == "pending"

            with app.app_context():
                join_request = CircleJoinRequest.query.filter_by(
                    circle_id=circle_id,
                    user_id=requester_id,
                    status="pending",
                ).one()
                assert join_request.message == "Please let me join."

    def test_user_cannot_join_circle_twice(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            admin = UserFactory()
            circle = CircleFactory(circle_type="closed")
            _add_circle_membership(circle, admin, is_admin=True)
            db.session.add(
                CircleJoinRequest(
                    circle_id=circle.id,
                    user_id=requester.id,
                    message="First request",
                    status="pending",
                )
            )
            db.session.commit()
            access_token = login_api_user(client, requester.email)
            circle_id = circle.id
            requester_id = requester.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/join",
            json={"message": "Second try"},
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "BAD_REQUEST"

        with app.app_context():
            pending_requests = CircleJoinRequest.query.filter_by(
                circle_id=circle_id,
                user_id=requester_id,
                status="pending",
            ).all()
            assert len(pending_requests) == 1

    def test_cancel_join_request_returns_canceled_true(self, client, app):
        with app.app_context():
            requester = UserFactory(email_confirmed=True)
            admin = UserFactory()
            circle = CircleFactory(circle_type="closed")
            _add_circle_membership(circle, admin, is_admin=True)
            join_request = CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
            db.session.commit()
            access_token = login_api_user(client, requester.email)
            circle_id = circle.id
            request_id = join_request.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/cancel-request",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"canceled": True}

        with app.app_context():
            assert db.session.get(CircleJoinRequest, request_id) is None

    def test_admin_can_approve_join_request(self, client, app):
        with app.app_context():
            requester = UserFactory()
            admin = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="closed")
            _add_circle_membership(circle, admin, is_admin=True)
            join_request = CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            request_id = join_request.id
            requester_id = requester.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/join-requests/{request_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "action": "approve",
            "join_request": {
                "id": str(request_id),
                "status": "approved",
            },
        }

        with app.app_context():
            membership = _get_circle_membership(circle_id, requester_id)
            join_request = db.session.get(CircleJoinRequest, request_id)
            assert membership is not None
            assert join_request.status == "approved"

    def test_admin_can_reject_join_request(self, client, app):
        with app.app_context():
            requester = UserFactory()
            admin = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="closed")
            _add_circle_membership(circle, admin, is_admin=True)
            join_request = CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            request_id = join_request.id
            requester_id = requester.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/join-requests/{request_id}/reject",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "action": "reject",
            "join_request": {
                "id": str(request_id),
                "status": "rejected",
            },
        }

        with app.app_context():
            membership = _get_circle_membership(circle_id, requester_id)
            join_request = db.session.get(CircleJoinRequest, request_id)
            assert membership is None
            assert join_request.status == "rejected"

    def test_non_admin_cannot_approve_or_reject_join_requests(self, client, app):
        with app.app_context():
            requester = UserFactory()
            admin = UserFactory()
            member = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="closed")
            _add_circle_membership(circle, admin, is_admin=True)
            _add_circle_membership(circle, member, is_admin=False)
            join_request = CircleJoinRequestFactory(circle=circle, user=requester, status="pending")
            db.session.commit()
            access_token = login_api_user(client, member.email)
            circle_id = circle.id
            request_id = join_request.id

        approve_response = client.post(
            f"/api/v1/circles/{circle_id}/join-requests/{request_id}/approve",
            headers=auth_headers(access_token),
        )
        reject_response = client.post(
            f"/api/v1/circles/{circle_id}/join-requests/{request_id}/reject",
            headers=auth_headers(access_token),
        )

        assert approve_response.status_code == 403
        assert reject_response.status_code == 403

        with app.app_context():
            join_request = db.session.get(CircleJoinRequest, request_id)
            assert join_request.status == "pending"

    def test_leave_circle_promotes_earliest_remaining_member(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            earliest_member = UserFactory()
            later_member = UserFactory()
            circle = CircleFactory(circle_type="open")
            now = datetime.now(UTC)
            _add_circle_membership(circle, admin, is_admin=True, joined_at=now - timedelta(days=3))
            _add_circle_membership(
                circle,
                earliest_member,
                is_admin=False,
                joined_at=now - timedelta(days=2),
            )
            _add_circle_membership(
                circle,
                later_member,
                is_admin=False,
                joined_at=now - timedelta(days=1),
            )
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            admin_id = admin.id
            earliest_member_id = earliest_member.id
            later_member_id = later_member.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/leave",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"circle_deleted": False}

        with app.app_context():
            assert _get_circle_membership(circle_id, admin_id) is None
            assert _get_circle_membership(circle_id, earliest_member_id).is_admin is True
            assert _get_circle_membership(circle_id, later_member_id).is_admin is False

    def test_leave_circle_deletes_last_member_circle(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, user, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)
            circle_id = circle.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/leave",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"circle_deleted": True}

        with app.app_context():
            assert db.session.get(Circle, circle_id) is None

    def test_leave_regional_circle_returns_invalid_action(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            circle = CircleFactory(
                circle_type="open",
                latitude=42.2808,
                longitude=-83.7430,
                is_regional=True,
                regional_radius_miles=25,
            )
            _add_circle_membership(circle, user, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, user.email)
            circle_id = circle.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/leave",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_ACTION"

        with app.app_context():
            assert db.session.get(Circle, circle_id) is not None

    def test_remove_member_rejects_self_removal(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, admin, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            admin_id = admin.id

        response = client.delete(
            f"/api/v1/circles/{circle_id}/members/{admin_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_ACTION"

    def test_demoting_last_admin_is_blocked(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, admin, is_admin=True)
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            admin_id = admin.id

        response = client.delete(
            f"/api/v1/circles/{circle_id}/admins/{admin_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "CONFLICT"

    def test_promote_and_demote_admin_endpoints_update_membership_state(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            member = UserFactory()
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, admin, is_admin=True)
            _add_circle_membership(circle, member, is_admin=False)
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_id = circle.id
            member_id = member.id

        promote_response = client.post(
            f"/api/v1/circles/{circle_id}/admins/{member_id}",
            headers=auth_headers(access_token),
        )
        demote_response = client.delete(
            f"/api/v1/circles/{circle_id}/admins/{member_id}",
            headers=auth_headers(access_token),
        )

        assert promote_response.status_code == 200
        assert promote_response.get_json() == {
            "user_id": str(member_id),
            "is_admin": True,
        }
        assert demote_response.status_code == 200
        assert demote_response.get_json() == {
            "user_id": str(member_id),
            "is_admin": False,
        }

        with app.app_context():
            membership = _get_circle_membership(circle_id, member_id)
            assert membership.is_admin is False

    def test_cancel_join_request_with_no_pending_request_returns_canceled_false(self, client, app):
        with app.app_context():
            user = UserFactory(email_confirmed=True)
            circle = CircleFactory(circle_type="closed")
            db.session.commit()
            access_token = login_api_user(client, user.email)
            circle_id = circle.id

        response = client.post(
            f"/api/v1/circles/{circle_id}/cancel-request",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 200
        assert response.get_json() == {"canceled": False}

    def test_non_admin_cannot_remove_member(self, client, app):
        with app.app_context():
            admin = UserFactory()
            member = UserFactory(email_confirmed=True)
            target = UserFactory()
            circle = CircleFactory(circle_type="open")
            _add_circle_membership(circle, admin, is_admin=True)
            _add_circle_membership(circle, member, is_admin=False)
            _add_circle_membership(circle, target, is_admin=False)
            db.session.commit()
            access_token = login_api_user(client, member.email)
            circle_id = circle.id
            target_id = target.id

        response = client.delete(
            f"/api/v1/circles/{circle_id}/members/{target_id}",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 403
        with app.app_context():
            assert _get_circle_membership(circle_id, target_id) is not None

    def test_join_request_action_with_wrong_circle_returns_404(self, client, app):
        with app.app_context():
            admin = UserFactory(email_confirmed=True)
            requester = UserFactory()
            circle_a = CircleFactory(circle_type="closed")
            circle_b = CircleFactory(circle_type="closed")
            _add_circle_membership(circle_a, admin, is_admin=True)
            _add_circle_membership(circle_b, admin, is_admin=True)
            join_request_b = CircleJoinRequestFactory(
                circle=circle_b, user=requester, status="pending"
            )
            db.session.commit()
            access_token = login_api_user(client, admin.email)
            circle_a_id = circle_a.id
            request_b_id = join_request_b.id

        response = client.post(
            f"/api/v1/circles/{circle_a_id}/join-requests/{request_b_id}/approve",
            headers=auth_headers(access_token),
        )

        assert response.status_code == 404
