import io
from unittest.mock import patch

from flask import url_for
from sqlalchemy import text

from app.models import Circle, db
from conftest import login_user
from tests.factories import CircleFactory, UserFactory


def login_admin(client, user, circle):
    db.session.execute(
        text(f"""
        INSERT INTO circle_members (user_id, circle_id, joined_at, is_admin)
        VALUES ('{user.id}', '{circle.id}', NOW(), TRUE)
        ON CONFLICT DO NOTHING
        """)
    )
    db.session.commit()
    login_user(client, user.email)


@patch(
    "app.services.circle_service.upload_circle_image", return_value="https://example.com/circle.jpg"
)
def test_create_circle_with_image(mock_upload, client, app):
    with app.app_context():
        user = UserFactory()
        login_user(client, user.email)
        image_data = (io.BytesIO(b"fake image data"), "circle.jpg")
        response = client.post(
            url_for("circles.create_circle"),
            data={
                "name": "Circle With Image",
                "description": "A circle with an image",
                "circle_type": "open",
                "image": image_data,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        circle = Circle.query.filter_by(name="Circle With Image").first()
        assert circle is not None
        assert circle.image_url == "https://example.com/circle.jpg"
        assert b"has been created successfully" in response.data


@patch("app.services.circle_service.upload_circle_image", return_value=None)
def test_create_circle_with_invalid_image(mock_upload, client, app):
    with app.app_context():
        user = UserFactory()
        login_user(client, user.email)
        # Mock upload failure
        bad_image = (io.BytesIO(b"not an image"), "circle.jpg")
        response = client.post(
            url_for("circles.create_circle"),
            data={
                "name": "Bad Image Circle",
                "description": "Should fail",
                "circle_type": "open",
                "image": bad_image,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        circle = Circle.query.filter_by(name="Bad Image Circle").first()
        # Should not create the circle if image upload fails
        assert circle is None
        assert b"Image upload failed" in response.data


@patch("app.services.circle_service.is_valid_file_upload", return_value=True)
@patch(
    "app.services.circle_service.upload_circle_image",
    return_value="https://example.com/new-circle.jpg",
)
def test_edit_circle_image(mock_upload, mock_valid, client, app):
    with app.app_context():
        user = UserFactory()
        circle = CircleFactory(image_url=None)
        login_admin(client, user, circle)
        image_data = (io.BytesIO(b"new image data"), "circle2.jpg")
        response = client.post(
            url_for("circles.edit_circle", circle_id=circle.id),
            data={
                "name": circle.name,
                "description": circle.description,
                "circle_type": circle.circle_type,
                "image": image_data,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        db.session.refresh(circle)
        assert circle.image_url == "https://example.com/new-circle.jpg"
        assert b"Circle image updated." in response.data


@patch("app.services.circle_service.delete_file")
def test_remove_circle_image(mock_delete, client, app):
    with app.app_context():
        user = UserFactory()
        circle = CircleFactory(image_url="https://example.com/old.jpg")
        login_admin(client, user, circle)
        response = client.post(
            url_for("circles.edit_circle", circle_id=circle.id),
            data={
                "name": circle.name,
                "description": circle.description,
                "circle_type": circle.circle_type,
                "delete_image": True,
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        db.session.refresh(circle)
        assert circle.image_url is None
        assert b"Circle image has been removed." in response.data
        mock_delete.assert_called_once_with("https://example.com/old.jpg")


def test_circle_details_shows_regional_settings_only_to_site_admin(client, app):
    with app.app_context():
        site_admin = UserFactory(is_admin=True)
        regular_user = UserFactory()
        circle = CircleFactory(circle_type="open", latitude=42.2808, longitude=-83.7430)
        db.session.commit()

        login_user(client, site_admin.email)
        admin_response = client.get(url_for("circles.view_circle", circle_id=circle.id))
        assert b"This is a regional circle" in admin_response.data

        login_user(client, regular_user.email)
        regular_response = client.get(url_for("circles.view_circle", circle_id=circle.id))
        assert b"This is a regional circle" not in regular_response.data


def test_site_admin_can_update_regional_settings_from_circle_details(client, app):
    with app.app_context():
        site_admin = UserFactory(is_admin=True)
        circle = CircleFactory(circle_type="open", latitude=42.2808, longitude=-83.7430)
        db.session.commit()

        login_user(client, site_admin.email)
        response = client.post(
            url_for("circles.update_regional_circle_settings", circle_id=circle.id),
            data={
                "is_regional": "y",
                "regional_radius_miles": "25",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        db.session.refresh(circle)
        assert circle.is_regional is True
        assert circle.regional_radius_miles == 25
        assert b"Regional circle status enabled." in response.data


class TestPaginatedCircleMembers:
    """Tests for paginated member list on circle details page."""

    def test_pagination_controls_appear_with_many_members(self, client, app):
        """When a circle has >20 members, pagination controls should appear."""
        with app.app_context():
            circle = CircleFactory()
            members = [UserFactory() for _ in range(25)]
            circle.members.extend(members)
            db.session.commit()

            login_user(client, members[0].email)

            response = client.get(url_for("circles.view_circle", circle_id=circle.id))
            assert response.status_code == 200

            html = response.data.decode()
            assert "Members (25)" in html
            assert 'aria-label="Members pages"' in html
            assert '<li class="page-item active"><span class="page-link">1</span></li>' in html
            assert f'href="/circles/{circle.id}?page=2"' in html

    def test_page_two_shows_remaining_members(self, client, app):
        """Page 2 should show the 5 members that don't fit on page 1 (25 total, 20 per page)."""
        with app.app_context():
            circle = CircleFactory()
            members = [UserFactory() for _ in range(25)]
            circle.members.extend(members)
            db.session.commit()

            all_ids = {str(m.id) for m in members}
            login_user(client, members[0].email)

            # Collect member IDs visible on page 1
            resp1 = client.get(url_for("circles.view_circle", circle_id=circle.id, page=1))
            assert resp1.status_code == 200
            html1 = resp1.data.decode()
            page1_ids = {str(m.id) for m in members if str(m.id) in html1}

            # Collect member IDs visible on page 2
            resp2 = client.get(url_for("circles.view_circle", circle_id=circle.id, page=2))
            assert resp2.status_code == 200
            html2 = resp2.data.decode()
            page2_ids = {str(m.id) for m in members if str(m.id) in html2}

            # Page 2 should show exactly 5 members, all distinct from page 1
            assert len(page2_ids) == 5
            assert page1_ids.isdisjoint(page2_ids)
            assert page1_ids | page2_ids == all_ids
            assert '<li class="page-item active"><span class="page-link">2</span></li>' in html2

    def test_join_leave_button_above_members(self, client, app):
        """The Join/Leave button should appear before the members heading in HTML."""
        with app.app_context():
            circle = CircleFactory(circle_type="open")
            members = [UserFactory() for _ in range(6)]
            circle.members.extend(members)
            db.session.commit()

            login_user(client, members[0].email)

            response = client.get(url_for("circles.view_circle", circle_id=circle.id))
            html = response.data.decode()

            leave_pos = html.find("Leave Circle")
            members_heading_pos = html.find("Members (6)")
            assert leave_pos != -1, "Leave Circle button not found"
            assert members_heading_pos != -1, "Members heading not found"
            assert leave_pos < members_heading_pos, (
                f"Leave Circle button (at {leave_pos}) should appear before "
                f"Members heading (at {members_heading_pos})"
            )

    def test_non_member_sees_join_button_above_closed_message(self, client, app):
        """A non-member of a closed circle sees Join button above the closed message."""
        with app.app_context():
            circle = CircleFactory(circle_type="closed")
            member = UserFactory()
            circle.members.append(member)
            db.session.commit()

            non_member = UserFactory()
            db.session.commit()
            login_user(client, non_member.email)

            response = client.get(url_for("circles.view_circle", circle_id=circle.id))
            html = response.data.decode()

            join_pos = html.find("Send Join Request")
            closed_msg_pos = html.find("This is a closed circle")
            assert join_pos != -1, "Send Join Request button not found"
            assert closed_msg_pos != -1, "Closed circle message not found"
            assert join_pos < closed_msg_pos, (
                f"Send Join Request button (at {join_pos}) should appear before "
                f"closed circle message (at {closed_msg_pos})"
            )

    def test_member_count_displays_total(self, client, app):
        """The member count should show the correct total from pagination."""
        with app.app_context():
            circle = CircleFactory()
            members = [UserFactory() for _ in range(8)]
            circle.members.extend(members)
            db.session.commit()

            login_user(client, members[0].email)
            response = client.get(url_for("circles.view_circle", circle_id=circle.id))
            html = response.data.decode()

            assert "Members (8)" in html
