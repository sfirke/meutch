import uuid

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import (
    ConfirmHandoffForm,
    DeleteItemForm,
    EmptyForm,
    ExpressInterestForm,
    ListItemForm,
    MessageForm,
    ReleaseToAllForm,
    WithdrawInterestForm,
)
from app.main import bp as main_bp
from app.models import GiveawayInterest, Item, Message
from app.services import item_service, message_service
from app.services.exceptions import AuthorizationError, ConflictError, InformationalError
from app.utils.giveaway_visibility import get_unavailable_giveaway_suggestions
from app.utils.item_share import ITEM_SHARE_TOKEN_MAX_AGE_DAYS
from app.utils.item_visibility import build_item_access_state
from app.utils.storage import MAX_ITEM_IMAGE_COUNT

from .helpers import (
    _build_item_detail_url,
    _collect_item_image_uploads,
    _generated_item_share_link,
    _parse_json_string_list,
)


def _ensure_item_creation_token(form):
    try:
        creation_token = uuid.UUID(str(form.creation_token.data))
    except (AttributeError, TypeError, ValueError):
        creation_token = uuid.uuid4()

    form.creation_token.data = str(creation_token)
    return creation_token


def _duplicate_item_creation_response(item, submit_and_create_another):
    from markupsafe import Markup, escape

    item_link = url_for("main.item_detail", item_id=item.id)
    message = Markup(
        'We already listed this item from your earlier submission: <a href="{}" class="alert-link">{}</a>.'
    ).format(item_link, escape(item.name))
    flash(message, "info")

    if submit_and_create_another:
        return redirect(url_for("main.list_item"))

    return redirect(url_for("main.index"))


@main_bp.route("/list-item", methods=["GET", "POST"])
@login_required
def list_item():
    form = ListItemForm()
    creation_token = _ensure_item_creation_token(form)

    if form.validate_on_submit():
        existing_item = item_service.get_item_by_creation_token(current_user.id, creation_token)
        if existing_item is not None:
            return _duplicate_item_creation_response(
                existing_item,
                form.submit_and_create_another.data,
            )

        uploaded_files, upload_errors = _collect_item_image_uploads(form.image.data)
        if upload_errors:
            for error in upload_errors:
                flash(error, "error")
            return render_template("main/list_item.html", form=form)

        if len(uploaded_files) > MAX_ITEM_IMAGE_COUNT:
            flash(f"You can upload a maximum of {MAX_ITEM_IMAGE_COUNT} images per item.", "error")
            return render_template("main/list_item.html", form=form)

        try:
            new_item = item_service.create_item(
                current_user,
                form.name.data,
                form.description.data,
                form.category.data,
                form.is_giveaway.data,
                form.giveaway_visibility.data,
                form.tags.data,
                uploaded_files,
                creation_token=creation_token,
            )
        except ValueError:
            flash(
                "Image upload failed. Please ensure you upload valid image files (JPG, PNG, GIF, etc.).",
                "error",
            )
            return render_template("main/list_item.html", form=form)
        except InformationalError:
            existing_item = item_service.get_item_by_creation_token(current_user.id, creation_token)
            if existing_item is not None:
                return _duplicate_item_creation_response(
                    existing_item,
                    form.submit_and_create_another.data,
                )

            current_app.logger.warning(
                "Duplicate item creation was reported for user %s without a matching creation token row.",
                current_user.id,
            )
            flash(
                "We could not confirm whether this item was already created. Please check your profile.",
                "warning",
            )
            return redirect(url_for("main.profile", tab="my-items"))
        except Exception as exc:
            current_app.logger.error(
                f"Failed to create item for user {current_user.id}: {str(exc)}"
            )
            flash("We could not save your item. Please try again.", "error")
            return render_template("main/list_item.html", form=form)

        from markupsafe import Markup, escape

        item_link = url_for("main.item_detail", item_id=new_item.id)
        message = Markup(
            'Item "<a href="{}" class="alert-link">{}</a>" has been listed successfully!'
        ).format(item_link, escape(new_item.name))

        if form.submit_and_create_another.data:
            flash(message, "success")
            return redirect(url_for("main.list_item"))

        flash(message, "success")
        return redirect(url_for("main.index"))

    return render_template("main/list_item.html", form=form)


@main_bp.route("/item/<uuid:item_id>", methods=["GET", "POST"])
@login_required
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    share_token = request.values.get("share_token", "").strip() or None
    access_state = build_item_access_state(item, current_user, share_token=share_token)
    has_token_access = access_state["has_token_access"]
    shares_circle_with_owner = access_state["shares_circle_with_owner"]

    if not access_state["can_view"]:
        if access_state["claimed_unavailable"]:
            suggestions = get_unavailable_giveaway_suggestions(
                current_user, exclude_item_id=item.id
            )
            return render_template("main/item_unavailable.html", suggestions=suggestions)
        abort(403)

    form = MessageForm()
    express_interest_form = ExpressInterestForm()
    withdraw_interest_form = WithdrawInterestForm()

    if form.validate_on_submit():
        message_service.create_message(
            current_user.id,
            item.owner.id,
            form.body.data,
            item_id=item.id,
        )

        flash("Your message has been sent.", "success")
        return redirect(_build_item_detail_url(item.id, share_token))

    messages = (
        Message.query.filter_by(item_id=item.id, recipient_id=current_user.id)
        .order_by(Message.timestamp.desc())
        .all()
    )

    user_interest = None
    if item.is_giveaway:
        user_interest = GiveawayInterest.query.filter_by(
            item_id=item.id, user_id=current_user.id
        ).first()

    interested_count = 0
    if item.is_giveaway and item.owner_id == current_user.id:
        interested_count = GiveawayInterest.query.filter_by(
            item_id=item.id, status="active"
        ).count()

    delete_form = DeleteItemForm()
    generate_share_link_form = EmptyForm()
    release_to_all_form = ReleaseToAllForm()
    confirm_handoff_form = ConfirmHandoffForm()
    return render_template(
        "main/item_detail.html",
        item=item,
        form=form,
        messages=messages,
        delete_form=delete_form,
        user_interest=user_interest,
        interested_count=interested_count,
        express_interest_form=express_interest_form,
        withdraw_interest_form=withdraw_interest_form,
        share_token=share_token,
        has_token_access=has_token_access,
        shares_circle_with_owner=shares_circle_with_owner,
        item_share_valid_days=ITEM_SHARE_TOKEN_MAX_AGE_DAYS,
        generated_share_url=_generated_item_share_link(item.id),
        generate_share_link_form=generate_share_link_form,
        release_to_all_form=release_to_all_form,
        confirm_handoff_form=confirm_handoff_form,
    )


@main_bp.route("/item/<uuid:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.owner != current_user:
        flash("You do not have permission to edit this item.", "danger")
        return redirect(url_for("main.profile"))

    form = ListItemForm(obj=item)
    form.submit.label.text = "Save"

    if request.method == "GET":
        form.is_giveaway.data = item.is_giveaway
        form.giveaway_visibility.data = item.giveaway_visibility
        form.category.data = str(item.category_id)
        form.tags.data = ", ".join([tag.name for tag in item.tags])

    if form.validate_on_submit():
        try:
            delete_entries = _parse_json_string_list(form.delete_images.data, "Photo removal")
            order_entries = _parse_json_string_list(form.image_order.data, "Photo order")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("main/edit_item.html", form=form, item=item)

        new_files, upload_errors = _collect_item_image_uploads(form.image.data)
        if upload_errors:
            for error in upload_errors:
                flash(error, "error")
            return render_template("main/edit_item.html", form=form, item=item)

        existing_images = list(item.images)
        existing_image_ids = {str(img.id) for img in existing_images}
        delete_ids = {entry for entry in delete_entries if entry in existing_image_ids}
        surviving_images = [img for img in existing_images if str(img.id) not in delete_ids]

        if len(surviving_images) + len(new_files) > MAX_ITEM_IMAGE_COUNT:
            flash(
                f"Maximum {MAX_ITEM_IMAGE_COUNT} images per item. Please remove some images first.",
                "warning",
            )
            return render_template("main/edit_item.html", form=form, item=item)

        try:
            item_service.update_item(
                item,
                form.name.data,
                form.description.data,
                form.category.data,
                form.is_giveaway.data,
                form.giveaway_visibility.data,
                form.tags.data,
                new_files,
                delete_entries,
                order_entries,
            )
        except ConflictError as exc:
            form.is_giveaway.errors.append(str(exc))
            return render_template("main/edit_item.html", form=form, item=item)
        except ValueError:
            flash("Some image uploads failed. Please try again.", "warning")
            return render_template("main/edit_item.html", form=form, item=item)
        except Exception as exc:
            current_app.logger.error(f"Failed to update item {item.id}: {str(exc)}")
            flash("We could not save your item changes. Please try again.", "error")
            return render_template("main/edit_item.html", form=form, item=item)

        flash("Item has been updated.", "success")
        return redirect(url_for("main.item_detail", item_id=item.id))

    return render_template("main/edit_item.html", form=form, item=item)


@main_bp.route("/item/<uuid:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)

    blocker_type, blocking_loan = item_service.get_item_delete_blocker(item)
    if blocker_type == "active_loan":
        flash(
            "This item is currently out on loan. Mark it returned or cancel the loan before deleting the item.",
            "warning",
        )
        if blocking_loan.messages:
            return redirect(
                url_for("main.view_conversation", message_id=blocking_loan.messages[0].id)
            )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if blocker_type == "pending_pickup":
        flash(
            "This giveaway is still pending pickup. Mark the handoff complete or release it instead of deleting the item.",
            "warning",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if blocker_type == "claimed":
        flash(
            "You cannot delete a giveaway that has been claimed and handed off. This is a completed transaction.",
            "danger",
        )
        return redirect(url_for("main.profile"))

    try:
        item_service.delete_item(item, current_user)
        flash("Item deleted successfully.", "success")
    except AuthorizationError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error deleting item {item_id}: {str(exc)}")
        flash("An error occurred while deleting the item.", "danger")

    return redirect(url_for("main.profile"))
