from datetime import UTC, datetime, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import or_

from app import db
from app.forms import (
    ConfirmHandoffForm,
    DeleteAccountForm,
    DeleteItemForm,
    DigestSettingsForm,
    EditProfileForm,
    EmptyForm,
    UpdateLocationForm,
    VacationModeForm,
)
from app.main import bp as main_bp
from app.models import Item, ItemRequest, User, UserWebLink
from app.services import account_service, location_service, profile_service
from app.utils.digest_tokens import verify_digest_manage_token


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = EditProfileForm()
    digest_form = DigestSettingsForm()
    if form.validate_on_submit():
        links = []
        for index in range(1, 6):
            links.append(
                {
                    "platform": getattr(form, f"link_{index}_platform").data,
                    "custom_name": getattr(form, f"link_{index}_custom_name").data,
                    "url": getattr(form, f"link_{index}_url").data,
                    "display_order": index,
                }
            )

        profile_result = profile_service.update_profile(
            current_user,
            about_me=form.about_me.data,
            links=links,
            profile_image=form.profile_image.data,
            delete_image=form.delete_image.data,
        )
        if profile_result.image_upload_failed:
            flash(
                "Profile image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.).",
                "warning",
            )

        flash("Your profile has been updated.", "success")
        return redirect(url_for("main.profile", tab="about-me"))
    elif request.method == "GET":
        form.about_me.data = current_user.about_me

        existing_links = (
            UserWebLink.query.filter_by(user_id=current_user.id)
            .order_by(UserWebLink.display_order)
            .all()
        )
        for link in existing_links:
            if 1 <= link.display_order <= 5:
                platform_field = getattr(form, f"link_{link.display_order}_platform")
                custom_name_field = getattr(form, f"link_{link.display_order}_custom_name")
                url_field = getattr(form, f"link_{link.display_order}_url")

                platform_field.data = link.platform_type
                custom_name_field.data = link.platform_name or ""
                url_field.data = link.url

    page = request.args.get("page", 1, type=int)
    giveaway_page = request.args.get("giveaway_page", 1, type=int)
    past_giveaway_page = request.args.get("past_giveaway_page", 1, type=int)
    search_query = request.args.get("search", "").strip()
    per_page = 12

    my_items_search_filter = None
    if search_query:
        my_items_search_filter = or_(
            Item.name.ilike(f"%{search_query}%"),
            Item.description.ilike(f"%{search_query}%"),
        )

    active_giveaways_query = Item.query.filter_by(
        owner_id=current_user.id, is_giveaway=True
    ).filter(
        or_(
            Item.claim_status == "unclaimed",
            Item.claim_status == "pending_pickup",
            Item.claim_status.is_(None),
        )
    )
    if my_items_search_filter is not None:
        active_giveaways_query = active_giveaways_query.filter(my_items_search_filter)
    active_giveaways_pagination = active_giveaways_query.order_by(Item.created_at.desc()).paginate(
        page=giveaway_page,
        per_page=per_page,
        error_out=False,
    )

    ninety_days_ago = datetime.now(UTC) - timedelta(days=90)
    past_giveaways_query = Item.query.filter_by(owner_id=current_user.id, is_giveaway=True).filter(
        Item.claim_status == "claimed",
        Item.claimed_at >= ninety_days_ago,
    )
    if my_items_search_filter is not None:
        past_giveaways_query = past_giveaways_query.filter(my_items_search_filter)
    past_giveaways_pagination = past_giveaways_query.order_by(Item.claimed_at.desc()).paginate(
        page=past_giveaway_page,
        per_page=per_page,
        error_out=False,
    )

    items_query = Item.query.filter_by(owner_id=current_user.id, is_giveaway=False)
    if my_items_search_filter is not None:
        items_query = items_query.filter(my_items_search_filter)
    items_pagination = items_query.order_by(Item.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    user_items = items_pagination.items

    delete_forms = {
        item.id: DeleteItemForm() for item in active_giveaways_pagination.items + user_items
    }
    confirm_handoff_forms = {
        item.id: ConfirmHandoffForm()
        for item in active_giveaways_pagination.items
        if item.claim_status == "pending_pickup"
    }

    borrowing = current_user.get_active_loans_as_borrower()
    lending = current_user.get_active_loans_as_owner()

    active_requests_page = request.args.get("active_requests_page", 1, type=int)
    active_requests = (
        ItemRequest.query.filter(
            ItemRequest.user_id == current_user.id,
            ItemRequest.status == "open",
            ItemRequest.expires_at > datetime.now(UTC),
        )
        .order_by(ItemRequest.created_at.desc())
        .paginate(page=active_requests_page, per_page=12, error_out=False)
    )

    past_requests_page = request.args.get("past_requests_page", 1, type=int)
    ninety_days_ago_requests = datetime.now(UTC) - timedelta(days=90)
    past_requests = (
        ItemRequest.query.filter(
            ItemRequest.user_id == current_user.id,
            ItemRequest.status == "fulfilled",
            ItemRequest.fulfilled_at >= ninety_days_ago_requests,
        )
        .order_by(ItemRequest.fulfilled_at.desc())
        .paginate(page=past_requests_page, per_page=12, error_out=False)
    )

    vacation_form = VacationModeForm()
    vacation_form.vacation_mode.data = current_user.vacation_mode

    digest_form.digest_frequency.data = current_user.digest_frequency
    digest_form.digest_radius_miles.data = current_user.digest_radius_miles
    digest_form.digest_include_giveaways.data = current_user.digest_include_giveaways
    digest_form.digest_include_requests.data = current_user.digest_include_requests
    digest_form.digest_include_circle_joins.data = current_user.digest_include_circle_joins
    digest_form.digest_include_loans.data = current_user.digest_include_loans
    digest_form.digest_giveaways_include_public.data = current_user.digest_giveaways_include_public
    digest_form.digest_requests_include_public.data = current_user.digest_requests_include_public

    active_tab = request.args.get("tab", "my-items")
    show_edit = request.method == "POST" and form.errors
    if show_edit:
        active_tab = "about-me"

    fulfill_form = EmptyForm()
    delete_form = EmptyForm()
    return render_template(
        "main/profile.html",
        form=form,
        user=current_user,
        items=user_items,
        active_giveaways=active_giveaways_pagination.items,
        past_giveaways=past_giveaways_pagination.items,
        delete_forms=delete_forms,
        confirm_handoff_forms=confirm_handoff_forms,
        borrowing=borrowing,
        lending=lending,
        pagination=items_pagination,
        active_giveaways_pagination=active_giveaways_pagination,
        past_giveaways_pagination=past_giveaways_pagination,
        vacation_form=vacation_form,
        digest_form=digest_form,
        active_tab=active_tab,
        search_query=search_query,
        show_edit=show_edit,
        active_requests=active_requests,
        past_requests=past_requests,
        fulfill_form=fulfill_form,
        delete_form=delete_form,
    )


@main_bp.route("/profile/digest-settings", methods=["POST"])
@login_required
def update_digest_settings():
    """Update digest settings for the current user."""
    form = DigestSettingsForm()

    if not form.validate_on_submit():
        flash(
            "Unable to save digest settings. Please check your selections and try again.",
            "warning",
        )
        return redirect(url_for("main.profile", tab="settings"))

    digest_opted_out = profile_service.update_digest_settings(
        current_user,
        digest_frequency=form.digest_frequency.data,
        digest_radius_miles=form.digest_radius_miles.data,
        digest_include_giveaways=form.digest_include_giveaways.data,
        digest_include_requests=form.digest_include_requests.data,
        digest_include_circle_joins=form.digest_include_circle_joins.data,
        digest_include_loans=form.digest_include_loans.data,
        digest_giveaways_include_public=form.digest_giveaways_include_public.data,
        digest_requests_include_public=form.digest_requests_include_public.data,
    )

    if digest_opted_out:
        flash(
            "You turned off digest emails. Please consider staying subscribed to keep up with activity in your circles.",
            "warning",
        )
    else:
        flash("Digest settings updated.", "success")

    return redirect(url_for("main.profile", tab="settings"))


@main_bp.route("/digest/manage/<token>")
def digest_manage(token):
    """Anonymous digest management page via signed token."""
    user, token_error = verify_digest_manage_token(token)

    if token_error:
        status_code = 410 if token_error == "expired" else 400
        return render_template(
            "main/digest_manage.html",
            token_valid=False,
            token_error=token_error,
            unsubscribed=False,
            user=None,
            token=token,
        ), status_code

    return render_template(
        "main/digest_manage.html",
        token_valid=True,
        token_error=None,
        unsubscribed=False,
        frequency_updated=None,
        user=user,
        token=token,
    )


@main_bp.route("/digest/frequency/<token>/<frequency>")
def digest_set_frequency(token, frequency):
    """One-click anonymous digest frequency update for daily/weekly options."""
    user, token_error = verify_digest_manage_token(token)

    if token_error:
        status_code = 410 if token_error == "expired" else 400
        return render_template(
            "main/digest_manage.html",
            token_valid=False,
            token_error=token_error,
            unsubscribed=False,
            frequency_updated=None,
            user=None,
            token=token,
        ), status_code

    allowed_frequencies = {
        User.DIGEST_FREQUENCY_DAILY,
        User.DIGEST_FREQUENCY_WEEKLY,
    }
    if frequency not in allowed_frequencies:
        return render_template(
            "main/digest_manage.html",
            token_valid=True,
            token_error="invalid-frequency",
            unsubscribed=False,
            frequency_updated=None,
            user=user,
            token=token,
        ), 400

    profile_service.set_digest_frequency(user, frequency)

    return render_template(
        "main/digest_manage.html",
        token_valid=True,
        token_error=None,
        unsubscribed=False,
        frequency_updated=frequency,
        user=user,
        token=token,
    )


@main_bp.route("/digest/unsubscribe/<token>")
def digest_unsubscribe(token):
    """One-click anonymous unsubscribe for digest emails."""
    user, token_error = verify_digest_manage_token(token)

    if token_error:
        status_code = 410 if token_error == "expired" else 400
        return render_template(
            "main/digest_manage.html",
            token_valid=False,
            token_error=token_error,
            unsubscribed=False,
            frequency_updated=None,
            user=None,
            token=token,
        ), status_code

    profile_service.unsubscribe_from_digest(user)

    return render_template(
        "main/digest_manage.html",
        token_valid=True,
        token_error=None,
        unsubscribed=True,
        frequency_updated=None,
        user=user,
        token=token,
    )


@main_bp.route("/update-location", methods=["GET", "POST"])
@login_required
def update_location():
    """Allow users to update their location coordinates"""
    form = UpdateLocationForm()

    if form.validate_on_submit():
        location_result = location_service.update_user_location(
            current_user,
            location_method=form.location_method.data,
            street=form.street.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            country=form.country.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
        )
        if location_result == location_service.LOCATION_UPDATE_STATUS_RATE_LIMITED:
            flash(
                "You can only update your location once per day. Please try again tomorrow.",
                "warning",
            )
            return redirect(url_for("main.profile"))

        if location_result == location_service.LOCATION_UPDATE_STATUS_REMOVED:
            flash("Your location has been removed successfully.", "success")
            return redirect(url_for("main.profile"))

        if location_result == location_service.LOCATION_UPDATE_STATUS_SUCCESS:
            flash("Your location has been updated successfully!", "success")
            return redirect(url_for("main.profile"))

        if location_result == location_service.LOCATION_UPDATE_STATUS_GEOCODING_FAILED:
            flash(
                "We couldn't determine your location from that address. You can try entering coordinates directly using the second option below.",
                "warning",
            )
        elif location_result == location_service.LOCATION_UPDATE_STATUS_GEOCODING_ERROR:
            flash(
                "There was an error determining your location from that address. You can try entering coordinates directly using the second option below.",
                "warning",
            )
        elif location_result == location_service.LOCATION_UPDATE_STATUS_UNEXPECTED_ERROR:
            flash(
                "There was an error determining your location. You can try entering coordinates directly using the second option below.",
                "error",
            )

    return render_template("main/update_location.html", form=form)


@main_bp.route("/user/<uuid:user_id>")
@login_required
def user_profile(user_id):
    if current_user.is_admin or current_user.id == user_id:
        user = db.get_or_404(User, user_id)
    else:
        target_user = db.session.get(User, user_id)
        if not target_user or not current_user.shares_circle_with(target_user):
            flash("You can only view profiles of users in your circles.", "warning")
            return redirect(url_for("main.index"))
        user = target_user

    can_view_items = current_user.is_admin or current_user.id == user.id

    items = []
    items_pagination = None
    delete_forms = {}
    confirm_handoff_forms = {}

    if can_view_items:
        page = request.args.get("page", 1, type=int)
        per_page = 12
        items_pagination = (
            Item.query.filter_by(owner_id=user.id)
            .order_by(Item.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        items = items_pagination.items

        if current_user.id == user.id:
            delete_forms = {
                item.id: DeleteItemForm()
                for item in items
                if not (item.is_giveaway and item.claim_status == "claimed")
            }
            confirm_handoff_forms = {
                item.id: ConfirmHandoffForm()
                for item in items
                if item.is_giveaway and item.claim_status == "pending_pickup"
            }

    shared_circles = []
    if current_user.id != user.id:
        shared_circles = current_user.shared_circles_with(user)

    return render_template(
        "main/user_profile.html",
        user=user,
        items=items,
        pagination=items_pagination,
        delete_forms=delete_forms,
        confirm_handoff_forms=confirm_handoff_forms,
        can_view_items=can_view_items,
        shared_circles=shared_circles,
    )


@main_bp.route("/delete_account", methods=["GET", "POST"])
@login_required
def delete_account():
    """Handle user account deletion with confirmation"""
    form = DeleteAccountForm()
    loans_summary = current_user.get_outstanding_loans_summary()

    if form.validate_on_submit():
        try:
            account_service.delete_user_account(current_user)
            logout_user()
            flash("Your account has been successfully deleted.", "info")
            return redirect(url_for("main.index"))
        except Exception:
            db.session.rollback()
            flash(
                "An error occurred while deleting your account. Please try again or contact support.",
                "danger",
            )
            return redirect(url_for("main.delete_account"))

    return render_template("main/delete_account.html", form=form, loans_summary=loans_summary)


@main_bp.route("/toggle-vacation-mode", methods=["POST"])
@login_required
def toggle_vacation_mode():
    """Toggle vacation mode for the current user."""
    form = VacationModeForm()

    if form.validate_on_submit():
        try:
            vacation_mode_enabled = profile_service.toggle_vacation_mode(
                current_user,
                form.vacation_mode.data,
            )
            if vacation_mode_enabled:
                flash(
                    "Vacation mode enabled. Your items are now hidden from other users.",
                    "success",
                )
            else:
                flash(
                    "Vacation mode disabled. Your items are now visible to other users.",
                    "success",
                )
        except Exception:
            db.session.rollback()
            flash("An error occurred while updating vacation mode. Please try again.", "danger")

    return redirect(url_for("main.profile"))
