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
from app.models import GiveawayInterest, Item, ItemImage, LoanRequest, Message, Tag
from app.utils.email import send_message_notification_email
from app.utils.giveaway_visibility import (
    can_view_claimed_giveaway,
    get_unavailable_giveaway_suggestions,
)
from app.utils.item_share import ITEM_SHARE_TOKEN_MAX_AGE_DAYS, token_grants_item_access
from app.utils.storage import MAX_ITEM_IMAGE_COUNT, delete_item_images, upload_item_images

from .helpers import (
    _build_item_detail_url,
    _collect_item_image_uploads,
    _generated_item_share_link,
    _parse_json_string_list,
)


def _giveaway_conversion_blocker(item):
    active_loan = LoanRequest.query.filter_by(item_id=item.id, status="approved").first()
    if active_loan:
        return active_loan, "active"

    pending_loan = LoanRequest.query.filter_by(item_id=item.id, status="pending").first()
    if pending_loan:
        return pending_loan, "pending"

    return None, None


def _loan_conversion_blocker(item):
    if item.claim_status == "claimed":
        return "claimed"

    if item.claim_status == "pending_pickup":
        return "pending_pickup"

    active_interest = GiveawayInterest.query.filter(
        GiveawayInterest.item_id == item.id,
        GiveawayInterest.status.in_(["active", "selected"]),
    ).first()
    if active_interest:
        return "interested_users"

    return None


@main_bp.route("/list-item", methods=["GET", "POST"])
@login_required
def list_item():
    form = ListItemForm()
    if form.validate_on_submit():
        uploaded_files, upload_errors = _collect_item_image_uploads(form.image.data)
        if upload_errors:
            for error in upload_errors:
                flash(error, "error")
            return render_template("main/list_item.html", form=form)

        if len(uploaded_files) > MAX_ITEM_IMAGE_COUNT:
            flash(f"You can upload a maximum of {MAX_ITEM_IMAGE_COUNT} images per item.", "error")
            return render_template("main/list_item.html", form=form)

        image_urls = []
        if uploaded_files:
            try:
                image_urls = upload_item_images(uploaded_files)
            except ValueError:
                flash(
                    "Image upload failed. Please ensure you upload valid image files (JPG, PNG, GIF, etc.).",
                    "error",
                )
                return render_template("main/list_item.html", form=form)

        new_item = Item(
            name=form.name.data.strip(),
            description=form.description.data.strip(),
            owner=current_user,
            category_id=form.category.data,
            is_giveaway=form.is_giveaway.data,
            giveaway_visibility=form.giveaway_visibility.data if form.is_giveaway.data else None,
            claim_status="unclaimed" if form.is_giveaway.data else None,
        )

        db.session.add(new_item)

        for position, url in enumerate(image_urls):
            db.session.add(ItemImage(item=new_item, url=url, position=position))

        tag_input = form.tags.data.strip() if form.tags.data else ""
        if tag_input:
            tag_names = [tag.strip().lower() for tag in tag_input.split(",") if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                new_item.tags.append(tag)

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if image_urls:
                delete_item_images(image_urls)
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
    has_token_access = False
    shares_circle_with_owner = False

    if not item.is_giveaway and item.owner_id != current_user.id:
        has_token_access = token_grants_item_access(share_token, item)
        shares_circle_with_owner = current_user.shares_circle_with(item.owner)
        is_active_borrower = (
            LoanRequest.query.filter_by(
                item_id=item.id,
                borrower_id=current_user.id,
                status="approved",
            ).first()
            is not None
        )
        if not shares_circle_with_owner and not has_token_access and not is_active_borrower:
            abort(403)

    if item.is_giveaway and item.claim_status == "claimed":
        if not can_view_claimed_giveaway(item, current_user):
            suggestions = get_unavailable_giveaway_suggestions(
                current_user, exclude_item_id=item.id
            )
            return render_template("main/item_unavailable.html", suggestions=suggestions)

    form = MessageForm()
    express_interest_form = ExpressInterestForm()
    withdraw_interest_form = WithdrawInterestForm()

    if form.validate_on_submit():
        message = Message(
            sender_id=current_user.id,
            recipient_id=item.owner.id,
            item_id=item.id,
            body=form.body.data,
        )
        db.session.add(message)
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for message {message.id}: {str(e)}"
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
        if form.is_giveaway.data:
            blocking_loan, blocking_loan_type = _giveaway_conversion_blocker(item)
            if blocking_loan:
                if blocking_loan_type == "active":
                    form.is_giveaway.errors.append(
                        "This item has an active loan. Mark it returned or cancel the loan before converting it to a giveaway."
                    )
                else:
                    form.is_giveaway.errors.append(
                        "This item has a pending loan request. Resolve the request before converting it to a giveaway."
                    )
                return render_template("main/edit_item.html", form=form, item=item)
        elif item.is_giveaway:
            conversion_blocker = _loan_conversion_blocker(item)
            if conversion_blocker == "interested_users":
                form.is_giveaway.errors.append(
                    "This giveaway already has interested users. It cannot be converted back into a loan item."
                )
                return render_template("main/edit_item.html", form=form, item=item)
            if conversion_blocker == "pending_pickup":
                form.is_giveaway.errors.append(
                    "This giveaway is pending pickup. Complete the handoff or release it back to everyone before converting it to a loan item."
                )
                return render_template("main/edit_item.html", form=form, item=item)
            if conversion_blocker == "claimed":
                form.is_giveaway.errors.append(
                    "This giveaway has already been handed off. Completed giveaways cannot be converted back into loan items."
                )
                return render_template("main/edit_item.html", form=form, item=item)

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

        new_urls = []
        if new_files:
            try:
                new_urls = upload_item_images(new_files)
            except ValueError:
                flash("Some image uploads failed. Please try again.", "warning")
                return render_template("main/edit_item.html", form=form, item=item)

        item.name = form.name.data
        item.description = form.description.data
        item.category_id = form.category.data
        item.is_giveaway = form.is_giveaway.data
        item.giveaway_visibility = form.giveaway_visibility.data if form.is_giveaway.data else None
        if form.is_giveaway.data and not item.claim_status:
            item.claim_status = "unclaimed"
        elif not form.is_giveaway.data:
            item.claim_status = None

        tag_input = form.tags.data.strip() if form.tags.data else ""
        item.tags.clear()
        if tag_input:
            tag_names = [tag.strip().lower() for tag in tag_input.split(",") if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                item.tags.append(tag)

        removed_urls = []
        for img in existing_images:
            if str(img.id) in delete_ids:
                removed_urls.append(img.url)
                db.session.delete(img)

        existing_by_id = {str(img.id): img for img in surviving_images}
        ordered_entries = []
        ordered_existing_ids = set()
        new_url_iter = iter(new_urls)

        for entry_id in order_entries:
            if entry_id.startswith("new-"):
                url = next(new_url_iter, None)
                if url is not None:
                    ordered_entries.append(("new", url))
                continue

            image = existing_by_id.get(entry_id)
            if image is not None and entry_id not in ordered_existing_ids:
                ordered_entries.append(("existing", image))
                ordered_existing_ids.add(entry_id)

        for image in surviving_images:
            image_id = str(image.id)
            if image_id not in ordered_existing_ids:
                ordered_entries.append(("existing", image))

        for url in new_url_iter:
            ordered_entries.append(("new", url))

        for position, (entry_type, entry_value) in enumerate(ordered_entries):
            if entry_type == "existing":
                entry_value.position = position
            else:
                db.session.add(ItemImage(item=item, url=entry_value, position=position))

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if new_urls:
                delete_item_images(new_urls)
            current_app.logger.error(f"Failed to update item {item.id}: {str(exc)}")
            flash("We could not save your item changes. Please try again.", "error")
            return render_template("main/edit_item.html", form=form, item=item)

        if removed_urls:
            delete_item_images(removed_urls)
        flash("Item has been updated.", "success")
        return redirect(url_for("main.item_detail", item_id=item.id))

    return render_template("main/edit_item.html", form=form, item=item)


@main_bp.route("/item/<uuid:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)

    if item.owner != current_user:
        flash("You can only delete your own items.", "danger")
        return redirect(url_for("main.profile"))

    active_loan = LoanRequest.query.filter_by(item_id=item.id, status="approved").first()
    if active_loan:
        flash(
            "This item is currently out on loan. Mark it returned or cancel the loan before deleting the item.",
            "warning",
        )
        if active_loan.messages:
            return redirect(
                url_for("main.view_conversation", message_id=active_loan.messages[0].id)
            )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.is_giveaway and item.claim_status == "pending_pickup":
        flash(
            "This giveaway is still pending pickup. Mark the handoff complete or release it instead of deleting the item.",
            "warning",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.is_giveaway and item.claim_status == "claimed":
        flash(
            "You cannot delete a giveaway that has been claimed and handed off. This is a completed transaction.",
            "danger",
        )
        return redirect(url_for("main.profile"))

    try:
        Message.query.filter(Message.item_id == item_id).delete()
        LoanRequest.query.filter_by(item_id=item_id).delete()
        GiveawayInterest.query.filter_by(item_id=item_id).delete()
        item.tags.clear()

        image_urls = [img.url for img in item.images]
        db.session.delete(item)
        db.session.commit()

        if image_urls:
            delete_item_images(image_urls)

        flash("Item deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting item {item_id}: {str(e)}")
        flash("An error occurred while deleting the item.", "danger")

    return redirect(url_for("main.profile"))
