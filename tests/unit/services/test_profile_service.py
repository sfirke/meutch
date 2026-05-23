from unittest.mock import patch

from app import db
from app.models import User, UserWebLink
from app.services import profile_service
from tests.factories import UserFactory, UserWebLinkFactory


class TestProfileService:
    def test_update_profile_replaces_about_me_and_web_links(self, app):
        with app.app_context():
            user = UserFactory(about_me="Old bio")
            UserWebLinkFactory(user=user, platform_type="facebook", url="https://facebook.com/old")
            db.session.commit()

            result = profile_service.update_profile(
                user,
                about_me="New bio",
                links=[
                    {
                        "platform": "other",
                        "custom_name": "GitHub",
                        "url": "https://github.com/example",
                    },
                    {
                        "platform": "linkedin",
                        "custom_name": "",
                        "url": "https://linkedin.com/in/example",
                    },
                ],
            )

            links = (
                UserWebLink.query.filter_by(user_id=user.id)
                .order_by(UserWebLink.display_order)
                .all()
            )
            assert result.image_upload_failed is False
            assert user.about_me == "New bio"
            assert len(links) == 2
            assert links[0].platform_type == "other"
            assert links[0].platform_name == "GitHub"
            assert links[0].display_order == 1
            assert links[1].platform_type == "linkedin"
            assert links[1].display_order == 2

    def test_update_profile_skips_blank_link_slots(self, app):
        with app.app_context():
            user = UserFactory(about_me="Old bio")
            db.session.commit()

            result = profile_service.update_profile(
                user,
                about_me="New bio",
                links=[
                    {
                        "platform": None,
                        "custom_name": None,
                        "url": None,
                    },
                    {
                        "platform": "instagram",
                        "custom_name": "",
                        "url": "https://instagram.com/example",
                    },
                    {
                        "platform": "linkedin",
                        "custom_name": "",
                        "url": "   ",
                    },
                ],
            )

            links = (
                UserWebLink.query.filter_by(user_id=user.id)
                .order_by(UserWebLink.display_order)
                .all()
            )
            assert result.image_upload_failed is False
            assert user.about_me == "New bio"
            assert len(links) == 1
            assert links[0].platform_type == "instagram"
            assert links[0].display_order == 2

    def test_update_profile_replaces_existing_profile_image(self, app):
        with app.app_context():
            user = UserFactory(profile_image_url="https://example.com/old.jpg")
            db.session.commit()

            with patch("app.services.profile_service.delete_file") as mock_delete:
                with patch(
                    "app.services.profile_service.upload_profile_image",
                    return_value="https://example.com/new.jpg",
                ):
                    result = profile_service.update_profile(
                        user,
                        about_me=user.about_me,
                        links=[],
                        profile_image=object(),
                    )

            assert result.image_upload_failed is False
            assert user.profile_image_url == "https://example.com/new.jpg"
            mock_delete.assert_called_once_with("https://example.com/old.jpg")

    def test_update_profile_reports_failed_profile_image_upload(self, app):
        with app.app_context():
            user = UserFactory(profile_image_url=None)
            db.session.commit()

            with patch("app.services.profile_service.upload_profile_image", return_value=None):
                result = profile_service.update_profile(
                    user,
                    about_me=user.about_me,
                    links=[],
                    profile_image=object(),
                )

            assert result.image_upload_failed is True
            assert user.profile_image_url is None

    def test_update_digest_settings_returns_opt_out_state(self, app):
        with app.app_context():
            user = UserFactory(digest_frequency="weekly", vacation_mode=False)
            db.session.commit()

            opted_out = profile_service.update_digest_settings(
                user,
                vacation_mode=True,
                digest_frequency=User.DIGEST_FREQUENCY_NONE,
                digest_radius_miles=20,
                digest_include_giveaways=True,
                digest_include_requests=False,
                digest_include_circle_joins=True,
                digest_include_loans=False,
                digest_giveaways_include_public=True,
                digest_requests_include_public=False,
            )

            db.session.refresh(user)
            assert opted_out is True
            assert user.vacation_mode is True
            assert user.digest_frequency == User.DIGEST_FREQUENCY_NONE
            assert user.digest_radius_miles == 20
            assert user.digest_include_requests is False

    def test_toggle_vacation_mode_persists_state(self, app):
        with app.app_context():
            user = UserFactory(vacation_mode=False)
            db.session.commit()

            result = profile_service.toggle_vacation_mode(user, True)

            db.session.refresh(user)
            assert result is True
            assert user.vacation_mode is True
