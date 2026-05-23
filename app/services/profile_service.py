from dataclasses import dataclass

from app import db
from app.models import User, UserWebLink
from app.utils.storage import delete_file, upload_profile_image


@dataclass
class ProfileUpdateResult:
    image_upload_failed: bool


def update_profile(user, *, about_me, links, profile_image=None, delete_image=False):
    image_upload_failed = False

    if delete_image and user.profile_image_url:
        delete_file(user.profile_image_url)
        user.profile_image_url = None

    if profile_image:
        if user.profile_image_url:
            delete_file(user.profile_image_url)

        image_url = upload_profile_image(profile_image)
        if image_url:
            user.profile_image_url = image_url
        else:
            image_upload_failed = True

    user.about_me = about_me
    UserWebLink.query.filter_by(user_id=user.id).delete()

    for display_order, link in enumerate(links, start=1):
        platform = link["platform"]
        url = link["url"]
        custom_name = link["custom_name"]
        if not url or not url.strip():
            continue
        web_link = UserWebLink(
            user_id=user.id,
            platform_type=platform,
            platform_name=custom_name.strip() if custom_name else None,
            url=url.strip(),
            display_order=display_order,
        )
        db.session.add(web_link)

    db.session.commit()
    return ProfileUpdateResult(image_upload_failed=image_upload_failed)


def update_digest_settings(
    user,
    *,
    vacation_mode=None,
    digest_frequency,
    digest_radius_miles,
    digest_include_giveaways,
    digest_include_requests,
    digest_include_circle_joins,
    digest_include_loans,
    digest_giveaways_include_public,
    digest_requests_include_public,
):
    if vacation_mode is not None:
        user.vacation_mode = vacation_mode

    user.digest_frequency = digest_frequency
    user.digest_radius_miles = digest_radius_miles
    user.digest_include_giveaways = digest_include_giveaways
    user.digest_include_requests = digest_include_requests
    user.digest_include_circle_joins = digest_include_circle_joins
    user.digest_include_loans = digest_include_loans
    user.digest_giveaways_include_public = digest_giveaways_include_public
    user.digest_requests_include_public = digest_requests_include_public

    db.session.commit()
    return user.digest_frequency == User.DIGEST_FREQUENCY_NONE


def set_digest_frequency(user, frequency):
    if user.digest_frequency != frequency:
        user.digest_frequency = frequency
        db.session.commit()


def unsubscribe_from_digest(user):
    if user.digest_frequency != User.DIGEST_FREQUENCY_NONE:
        user.digest_frequency = User.DIGEST_FREQUENCY_NONE
        db.session.commit()


def toggle_vacation_mode(user, enabled):
    user.vacation_mode = enabled
    db.session.commit()
    return user.vacation_mode
