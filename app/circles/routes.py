from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.circles import bp as circles_bp
from app.forms import (
    CircleCreateForm,
    CircleJoinRequestForm,
    CircleSearchForm,
    CircleUuidSearchForm,
    EmptyForm,
)
from app.forms_circles import CircleRegionalSettingsForm
from app.models import Circle, CircleJoinRequest, User, db
from app.services import circle_service
from app.services.exceptions import ServiceError
from app.utils.circle_members import build_circle_member_samples
from app.utils.circle_queries import (
    build_circle_recommendations,
    get_admin_circle_pending_counts,
    get_listed_circles,
    get_paginated_circle_members,
    get_pending_circle_join_request,
    get_sorted_user_circles,
    should_show_circle_members,
)
from app.utils.pagination import ListPagination

# Circles -----------------------------------------------------


@circles_bp.route("/", methods=["GET", "POST"])
@login_required
def manage_circles():
    circle_form = CircleCreateForm()
    search_form = CircleSearchForm()
    uuid_search_form = CircleUuidSearchForm()
    recommendation_form = EmptyForm()
    searched_circles = None
    browse_circles = None
    searched_circle_samples = {}
    browse_circle_samples = {}
    circle_recommendations = []
    featured_circle_recommendation = None
    secondary_circle_recommendations = []
    show_browse = False

    user_admin_circles = get_admin_circle_pending_counts(current_user.id)

    # Compute once — used for facepile visibility and template membership checks
    user_circle_ids = {circle.id for circle in current_user.circles}

    if request.method == "POST":
        if "create_circle" in request.form and circle_form.validate_on_submit():
            try:
                result = circle_service.create_circle(
                    current_user,
                    name=circle_form.name.data,
                    description=circle_form.description.data,
                    circle_type=circle_form.circle_type.data,
                    location_method=circle_form.location_method.data,
                    latitude=circle_form.latitude.data,
                    longitude=circle_form.longitude.data,
                    street=circle_form.street.data,
                    city=circle_form.city.data,
                    state=circle_form.state.data,
                    zip_code=circle_form.zip_code.data,
                    country=circle_form.country.data,
                )
            except ServiceError as exc:
                flash(str(exc), exc.flash_category)
            except Exception as exc:
                current_app.logger.error(f"Error creating circle: {str(exc)}")
                flash("There was an error creating the circle.", "danger")
            else:
                if circle_form.location_method.data == "skip":
                    flash(
                        "Circle created successfully! You can add a location later to help members find circles nearby.",
                        "success",
                    )
                elif result["geocoding_failed"]:
                    flash(
                        "Circle created successfully, but we couldn't determine the location from the address provided. "
                        "You can try entering coordinates directly, or update the location later.",
                        "warning",
                    )
                else:
                    flash("Circle created successfully!", "success")

                return redirect(url_for("circles.view_circle", circle_id=result["circle"].id))

        elif "search_circles" in request.form and search_form.validate_on_submit():
            # Handle Circle Search or Browse (open and closed circles, not secret)
            query = search_form.search_query.data.strip() if search_form.search_query.data else ""
            radius = search_form.radius.data

            searched_circles = get_listed_circles(current_user, search_query=query, radius=radius)
            if not query:
                show_browse = True
            searched_circle_samples = build_circle_member_samples(
                searched_circles, limit=5, user_circle_ids=user_circle_ids
            )

            if not searched_circles:
                if radius and current_user.is_geocoded:
                    if query:
                        flash(f'No circles found matching "{query}" within {radius} miles.', "info")
                    else:
                        flash(f"No circles found within {radius} miles.", "info")
                else:
                    if query:
                        flash(f'No circles found matching "{query}".', "info")
                    else:
                        flash("No circles available to browse.", "info")

        elif "find_by_uuid" in request.form and uuid_search_form.validate_on_submit():
            # Handle UUID Search for secret circles
            try:
                circle_uuid = uuid_search_form.circle_uuid.data.strip()
                found_circle = Circle.query.filter_by(id=circle_uuid).first()
                if found_circle:
                    searched_circles = [found_circle]
                    searched_circle_samples = build_circle_member_samples(
                        searched_circles, limit=5, user_circle_ids=user_circle_ids
                    )
                else:
                    flash("No circle found with that UUID.", "warning")
            except Exception:
                flash("Invalid UUID format.", "danger")

    # Fetch user's circles and sort by member count (descending)
    user_circles = get_sorted_user_circles(current_user)
    has_circles = len(user_circles) > 0

    # If no search was performed on GET request, show browse results (all listed circles)
    if request.method == "GET":
        selected_radius = search_form.radius.data or search_form.radius.default

        browse_circles = get_listed_circles(current_user, radius=selected_radius)
        browse_circle_samples = build_circle_member_samples(
            browse_circles, limit=5, user_circle_ids=user_circle_ids
        )

        show_browse = True

    if not has_circles:
        circle_recommendations = build_circle_recommendations(
            current_user,
            limit=4,
        )
        if circle_recommendations:
            featured_circle_recommendation = circle_recommendations[0]
            secondary_circle_recommendations = circle_recommendations[1:]

    return render_template(
        "circles/circles.html",
        circle_form=circle_form,
        search_form=search_form,
        recommendation_form=recommendation_form,
        uuid_search_form=uuid_search_form,
        user_circles=user_circles,
        user_admin_circles=user_admin_circles,
        searched_circles=searched_circles,
        browse_circles=browse_circles,
        searched_circle_samples=searched_circle_samples,
        browse_circle_samples=browse_circle_samples,
        show_circle_onboarding=not has_circles,
        needs_location_hint=not current_user.is_geocoded,
        featured_circle_recommendation=featured_circle_recommendation,
        secondary_circle_recommendations=secondary_circle_recommendations,
        show_browse=show_browse,
        user_circle_ids=user_circle_ids,
    )


@circles_bp.route("/<uuid:circle_id>", methods=["GET"])
@login_required
def view_circle(circle_id):
    circle = db.get_or_404(Circle, circle_id)
    is_member = current_user in circle.members

    # Create form instance for CSRF protection
    form = EmptyForm()  # Use this for all basic forms including cancel
    join_form = CircleJoinRequestForm() if circle.requires_join_approval and not is_member else None
    regional_form = None
    if current_user.is_admin:
        regional_form = CircleRegionalSettingsForm()
        regional_form.is_regional.data = circle.is_regional
        regional_form.regional_radius_miles.data = circle.regional_radius_miles

    # Check for pending request
    pending_request = get_pending_circle_join_request(circle_id, current_user.id)

    page = request.args.get("page", 1, type=int)
    if should_show_circle_members(circle, current_user):
        members_pagination = get_paginated_circle_members(circle_id, page=page, per_page=20)
    else:
        members_pagination = ListPagination(items=[], page=1, per_page=20)
    total_members = members_pagination.total

    # Check if current user is the last member
    is_last_member = is_member and total_members == 1

    return render_template(
        "circles/circle_details.html",
        circle=circle,
        is_member=is_member,
        is_last_member=is_last_member,
        form=form,
        join_form=join_form,
        regional_form=regional_form,
        members_pagination=members_pagination,
        total_members=total_members,
        pending_request=pending_request,
    )


@circles_bp.route("/<uuid:circle_id>/regional-settings", methods=["POST"])
@login_required
def update_regional_circle_settings(circle_id):
    circle = db.get_or_404(Circle, circle_id)
    form = CircleRegionalSettingsForm()

    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "danger")
        return redirect(url_for("circles.view_circle", circle_id=circle_id))

    try:
        circle_service.update_regional_circle_settings(
            circle,
            current_user,
            is_regional=form.is_regional.data,
            regional_radius_miles=form.regional_radius_miles.data,
        )
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(
            f"Error updating regional settings for circle {circle_id}: {str(exc)}"
        )
        flash("There was an error updating the regional circle settings.", "danger")
    else:
        if form.is_regional.data:
            flash("Regional circle status enabled.", "success")
        else:
            flash("Regional circle status removed.", "success")

    return redirect(url_for("circles.view_circle", circle_id=circle_id))


@circles_bp.route("/join/<uuid:circle_id>", methods=["POST"])
@login_required
def join_circle(circle_id):
    circle = db.get_or_404(Circle, circle_id)
    form = CircleJoinRequestForm() if circle.requires_join_approval else EmptyForm()

    if circle.requires_join_approval:
        if form.validate_on_submit():
            try:
                circle_service.join_circle(circle, current_user, form.message.data)
            except ServiceError as exc:
                flash(str(exc), exc.flash_category)
            except Exception as exc:
                current_app.logger.error(
                    f"Error creating circle join request for {circle.id}: {str(exc)}"
                )
                flash("There was an error with your join request.", "danger")
            else:
                flash("Your request to join has been submitted.", "success")
                return redirect(url_for("circles.view_circle", circle_id=circle.id))
        else:
            flash("There was an error with your join request.", "danger")
            return redirect(url_for("circles.view_circle", circle_id=circle.id))
    else:
        try:
            circle_service.join_circle(circle, current_user)
        except ServiceError as exc:
            flash(str(exc), exc.flash_category)
        except Exception as exc:
            current_app.logger.error(f"Error joining open circle {circle.id}: {str(exc)}")
            flash("There was an error joining the circle.", "danger")
        else:
            flash("You have joined the circle successfully!", "success")
            return redirect(url_for("circles.view_circle", circle_id=circle.id))

    return redirect(url_for("circles.view_circle", circle_id=circle.id))


@circles_bp.route("/leave/<uuid:circle_id>", methods=["POST"])
@login_required
def leave_circle(circle_id):
    circle = db.get_or_404(Circle, circle_id)
    try:
        result = circle_service.leave_circle(circle, current_user)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
        return redirect(url_for("circles.view_circle", circle_id=circle_id))
    except Exception as exc:
        current_app.logger.error(f"Error leaving circle {circle_id}: {str(exc)}")
        flash("There was an error leaving the circle.", "danger")
        return redirect(url_for("circles.view_circle", circle_id=circle_id))

    if result["circle_deleted"]:
        flash("Circle has been deleted as it has no remaining members.", "info")
        return redirect(url_for("circles.manage_circles"))

    flash("You have left the circle.", "success")
    return redirect(url_for("circles.manage_circles"))


@circles_bp.route("/<uuid:circle_id>/request/<uuid:request_id>/<action>", methods=["POST"])
@login_required
def handle_join_request(circle_id, request_id, action):
    circle = db.get_or_404(Circle, circle_id)
    join_request = db.get_or_404(CircleJoinRequest, request_id)

    try:
        handled_action = circle_service.handle_join_request(
            circle, join_request, current_user, action
        )
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error handling circle join request {request_id}: {str(exc)}")
        flash("There was an error handling the join request.", "danger")
    else:
        if handled_action == "approve":
            flash("User has been approved to join the circle.", "success")
        else:
            flash("User request has been denied.", "info")

    return redirect(url_for("circles.view_circle", circle_id=circle_id))


@circles_bp.route("/<uuid:circle_id>/cancel-request", methods=["POST"])
@login_required
def cancel_join_request(circle_id):
    db.get_or_404(Circle, circle_id)

    try:
        if circle_service.cancel_join_request(circle_id, current_user.id):
            flash("Join request cancelled.", "info")
    except Exception:
        db.session.rollback()
        flash("Error cancelling request.", "danger")

    # Force a fresh query on redirect
    return redirect(url_for("circles.view_circle", circle_id=circle_id))


@circles_bp.route("/<uuid:circle_id>/admin/<uuid:user_id>/<action>", methods=["POST"])
@login_required
def toggle_admin(circle_id, user_id, action):
    circle = db.get_or_404(Circle, circle_id)

    try:
        is_admin = circle_service.toggle_admin(circle, user_id, current_user, action)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(
            f"Error updating admin status for user {user_id} in circle {circle_id}: {str(exc)}"
        )
        flash("There was an error updating admin status.", "danger")
    else:
        if is_admin:
            flash("Admin status granted to user.", "success")
        else:
            flash("Admin status removed from user.", "success")

    return redirect(url_for("circles.view_circle", circle_id=circle_id))


@circles_bp.route("/create-circle", methods=["GET", "POST"])
@login_required
def create_circle():
    form = CircleCreateForm()
    if form.validate_on_submit():
        try:
            result = circle_service.create_circle(
                current_user,
                name=form.name.data,
                description=form.description.data,
                circle_type=form.circle_type.data,
                image_file=form.image.data,
                location_method=form.location_method.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
                street=form.street.data,
                city=form.city.data,
                state=form.state.data,
                zip_code=form.zip_code.data,
                country=form.country.data,
            )
        except ServiceError as exc:
            if str(exc) == "A circle with this name already exists.":
                flash(
                    "A circle with that name already exists. Please choose a different name.",
                    "danger",
                )
            else:
                flash(str(exc), exc.flash_category)
            return render_template("circles/create_circle.html", form=form)
        except Exception as exc:
            current_app.logger.error(f"Error creating circle: {str(exc)}")
            flash("There was an error creating the circle.", "danger")
            return render_template("circles/create_circle.html", form=form)

        flash(f'Circle "{result["circle"].name}" has been created successfully!', "success")
        return redirect(url_for("circles.view_circle", circle_id=result["circle"].id))
    return render_template("circles/create_circle.html", form=form)


@circles_bp.route("/<uuid:circle_id>/remove/<uuid:user_id>", methods=["POST"])
@login_required
def remove_member(circle_id, user_id):
    circle = db.get_or_404(Circle, circle_id)
    user_to_remove = db.get_or_404(User, user_id)
    try:
        circle_service.remove_member(circle, user_to_remove, current_user)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
        return redirect(url_for("circles.view_circle", circle_id=circle_id))
    except Exception as exc:
        current_app.logger.error(
            f"Error removing user {user_id} from circle {circle_id}: {str(exc)}"
        )
        flash("There was an error removing the member.", "danger")
        return redirect(url_for("circles.view_circle", circle_id=circle_id))

    flash(
        f"{user_to_remove.first_name} {user_to_remove.last_name} has been removed from the circle.",
        "success",
    )
    return redirect(url_for("circles.view_circle", circle_id=circle_id))


@circles_bp.route("/<uuid:circle_id>/edit", methods=["GET", "POST"])
@login_required
def edit_circle(circle_id):
    circle = db.get_or_404(Circle, circle_id)
    if not circle.is_admin(current_user):
        flash("Only circle admins can edit circle details.", "danger")
        return redirect(url_for("circles.view_circle", circle_id=circle.id))

    from app.forms import CircleCreateForm

    form = CircleCreateForm(obj=circle)
    # Remove submit label confusion
    form.submit.label.text = "Update Circle"

    if request.method == "GET":
        form.image.data = None
        form.delete_image.data = False
        # Populate location fields with existing data
        if circle.is_geocoded:
            form.latitude.data = circle.latitude
            form.longitude.data = circle.longitude
            form.location_method.data = (
                "skip"  # Default to skip, user can change if they want to update
            )

    if form.validate_on_submit():
        try:
            result = circle_service.update_circle(
                circle,
                current_user,
                name=form.name.data,
                description=form.description.data,
                circle_type=form.circle_type.data,
                image_file=form.image.data,
                delete_image=form.delete_image.data,
                location_method=form.location_method.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
                street=form.street.data,
                city=form.city.data,
                state=form.state.data,
                zip_code=form.zip_code.data,
                country=form.country.data,
            )
        except ServiceError as exc:
            flash(str(exc), exc.flash_category)
            return render_template("circles/edit_circle.html", form=form, circle=circle)
        except Exception as exc:
            current_app.logger.error(f"Error updating circle {circle_id}: {str(exc)}")
            flash("There was an error updating the circle.", "danger")
            return render_template("circles/edit_circle.html", form=form, circle=circle)

        if result["image_removed"]:
            flash("Circle image has been removed.", "success")
        if result["image_updated"]:
            flash("Circle image updated.", "success")

        # Provide appropriate feedback based on location update
        if result["geocoding_failed"]:
            flash(
                "Circle updated, but we couldn't determine the location from the address provided. "
                "You can try entering coordinates directly.",
                "warning",
            )
        else:
            flash("Circle updated successfully.", "success")

        return redirect(url_for("circles.view_circle", circle_id=circle.id))

    return render_template("circles/edit_circle.html", form=form, circle=circle)
