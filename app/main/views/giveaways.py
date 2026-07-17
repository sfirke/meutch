from uuid import UUID

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import (
    ChangeRecipientForm,
    ConfirmHandoffForm,
    EmptyForm,
    MessageForm,
    ReleaseToAllForm,
    SelectRecipientForm,
    WithdrawInterestForm,
)
from app.main import bp as main_bp
from app.models import GiveawayInterest, Item, Message, User
from app.services import giveaway_service, message_service
from app.services.exceptions import ConflictError, ServiceError
from app.utils.messaging_queries import (
    find_context_conversation,
    get_conversation_other_user_id,
    get_or_create_conversation,
)


@main_bp.route("/item/<uuid:item_id>/withdraw-interest", methods=["POST"])
@login_required
def withdraw_interest(item_id):
    """Allow a user to withdraw their interest in a giveaway"""
    item = db.get_or_404(Item, item_id)
    form = WithdrawInterestForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        giveaway_service.withdraw_interest(item, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error withdrawing interest from giveaway {item_id}: {str(exc)}")
        flash("An error occurred. Please try again.", "danger")
    else:
        flash("Your interest has been withdrawn.", "success")

    return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/select-recipient", methods=["GET", "POST"])
@login_required
def select_recipient(item_id):
    """Owner views interested users and selects a recipient for a giveaway"""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status not in [None, "unclaimed", "pending_pickup"]:
        flash("This giveaway has already been claimed.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    first_form = SelectRecipientForm(selection_method="first")
    random_form = SelectRecipientForm(selection_method="random")
    manual_form = SelectRecipientForm(selection_method="manual")

    if request.method == "POST":
        selection_method = request.form.get("selection_method")

        if selection_method == "first" and first_form.validate_on_submit():
            form = first_form
        elif selection_method == "random" and random_form.validate_on_submit():
            form = random_form
        elif selection_method == "manual" and manual_form.validate_on_submit():
            form = manual_form
        else:
            flash("Invalid selection. Please try again.", "danger")
            return redirect(url_for("main.select_recipient", item_id=item.id))

        try:
            selected_interest = giveaway_service.select_recipient(
                item,
                current_user.id,
                selection_method,
                form.user_id.data if selection_method == "manual" else None,
            )
        except ConflictError as exc:
            flash(str(exc), exc.flash_category)
            if str(exc) == "No interested users found.":
                return redirect(url_for("main.item_detail", item_id=item.id))
            return redirect(url_for("main.select_recipient", item_id=item.id))
        except ServiceError as exc:
            flash(str(exc), exc.flash_category)
            return redirect(url_for("main.select_recipient", item_id=item.id))
        except Exception as exc:
            current_app.logger.error(
                f"Error selecting recipient for giveaway {item_id}: {str(exc)}"
            )
            flash("An error occurred. Please try again.", "danger")
            return redirect(url_for("main.select_recipient", item_id=item.id))
        else:
            flash(
                f"{selected_interest.user.full_name} has been selected! They will be notified.",
                "success",
            )
            return redirect(url_for("main.item_detail", item_id=item.id))

    is_reassignment = item.claim_status == "pending_pickup"
    interested_users, messaging_info = giveaway_service.get_giveaway_interest_messaging_info(
        item.id, current_user.id
    )

    if not interested_users:
        flash("No users have expressed interest in this giveaway yet.", "info")
        return redirect(url_for("main.item_detail", item_id=item.id))

    user_messaging_info = {}
    for interest in interested_users:
        info = messaging_info.get(interest.user_id, {})
        user_messaging_info[str(interest.user_id)] = {
            "has_conversation": info.get("has_conversation", False),
            "unread_count": info.get("unread_count", 0),
            "message_count": info.get("message_count", 0),
            "latest_message": info.get("latest_message"),
        }

    next_form = ChangeRecipientForm(selection_method="next")
    random_reassign_form = ChangeRecipientForm(selection_method="random")
    manual_reassign_form = ChangeRecipientForm(selection_method="manual")

    return render_template(
        "main/select_recipient.html",
        item=item,
        interested_users=interested_users,
        user_messaging_info=user_messaging_info,
        is_reassignment=is_reassignment,
        first_form=first_form,
        random_form=random_form,
        manual_form=manual_form,
        next_form=next_form,
        random_reassign_form=random_reassign_form,
        manual_reassign_form=manual_reassign_form,
    )


@main_bp.route("/item/<uuid:item_id>/give-to-user/<uuid:user_id>", methods=["POST"])
@login_required
def give_to_user(item_id, user_id):
    """Owner selects an interested user directly from their conversation."""
    item = db.get_or_404(Item, item_id)
    form = EmptyForm()

    conversation_message = None
    conversation_message_id = request.form.get("message_id")
    if conversation_message_id:
        try:
            conversation_message = db.session.get(Message, UUID(conversation_message_id))
        except (TypeError, ValueError):
            conversation_message = None

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        if conversation_message:
            return redirect(
                url_for(
                    "main.view_conversation",
                    conversation_id=conversation_message.conversation_id,
                )
            )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        if conversation_message:
            return redirect(
                url_for(
                    "main.view_conversation",
                    conversation_id=conversation_message.conversation_id,
                )
            )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status not in [None, "unclaimed"]:
        flash("This giveaway is no longer awaiting recipient selection.", "warning")
        if conversation_message:
            return redirect(
                url_for(
                    "main.view_conversation",
                    conversation_id=conversation_message.conversation_id,
                )
            )
        return redirect(url_for("main.item_detail", item_id=item.id))

    if (
        conversation_message is None
        or conversation_message.conversation.context_type != "item"
        or conversation_message.conversation.context_id != item.id
    ):
        flash("Invalid conversation context.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    other_user_id = get_conversation_other_user_id(conversation_message, current_user.id)
    if other_user_id != user_id:
        flash("This conversation does not match that interested user.", "danger")
        return redirect(
            url_for(
                "main.view_conversation",
                conversation_id=conversation_message.conversation_id,
            )
        )

    try:
        selected_interest = giveaway_service.select_recipient(
            item, current_user.id, "manual", user_id
        )
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(
            f"Error selecting giveaway recipient from conversation {conversation_message.id}: {str(exc)}"
        )
        flash("An error occurred. Please try again.", "danger")
    else:
        flash(
            f"{selected_interest.user.full_name} has been selected! They will be notified.",
            "success",
        )

    return redirect(
        url_for(
            "main.view_conversation",
            conversation_id=conversation_message.conversation_id,
        )
    )


@main_bp.route("/item/<uuid:item_id>/message-requester/<uuid:user_id>", methods=["GET", "POST"])
@login_required
def message_giveaway_requester(item_id, user_id):
    """Allow giveaway owner to initiate a message with an interested user"""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to message requesters for this item.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    target_user = db.get_or_404(User, user_id)
    interest = GiveawayInterest.query.filter_by(item_id=item.id, user_id=user_id).first()

    if not interest:
        flash("This user has not expressed interest in this giveaway.", "warning")
        return redirect(url_for("main.select_recipient", item_id=item.id))

    existing_conv = find_context_conversation("item", item.id, current_user.id, user_id)

    if existing_conv:
        return redirect(url_for("main.view_conversation", conversation_id=existing_conv.id))

    form = MessageForm()
    if form.validate_on_submit():
        try:
            conversation = get_or_create_conversation("item", item.id, current_user.id, user_id)
            message = message_service.create_message(
                current_user.id,
                user_id,
                form.body.data,
                conversation_id=conversation.id,
            )
            flash("Your message has been sent.", "success")
            return redirect(
                url_for("main.view_conversation", conversation_id=message.conversation_id)
            )
        except Exception as exc:
            current_app.logger.error(f"Error sending message for giveaway {item_id}: {str(exc)}")
            flash("An error occurred. Please try again.", "danger")

    shared_circles = current_user.shared_circles_with(target_user)

    return render_template(
        "main/message_requester.html",
        form=form,
        item=item,
        target_user=target_user,
        interest=interest,
        shared_circles=shared_circles,
    )


@main_bp.route("/item/<uuid:item_id>/change-recipient", methods=["POST"])
@login_required
def change_recipient(item_id):
    """Owner changes the recipient of a giveaway that's pending pickup."""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ChangeRecipientForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.select_recipient", item_id=item.id))

    try:
        selected_interest = giveaway_service.change_recipient(
            item,
            current_user.id,
            form.selection_method.data,
            form.user_id.data if form.selection_method.data == "manual" else None,
        )
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
        return redirect(url_for("main.select_recipient", item_id=item.id))
    except Exception as exc:
        current_app.logger.error(f"Error changing recipient for giveaway {item_id}: {str(exc)}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("main.select_recipient", item_id=item.id))
    else:
        flash(
            f"{selected_interest.user.full_name} has been selected! They will be notified.",
            "success",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/release-to-all", methods=["POST"])
@login_required
def release_to_all(item_id):
    """Owner releases a giveaway back to unclaimed status."""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ReleaseToAllForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        giveaway_service.release_to_all(item, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error releasing giveaway {item_id} to all: {str(exc)}")
        flash("An error occurred. Please try again.", "danger")
    else:
        flash(
            "The giveaway has been released and will reappear in the feed. All interested users remain in the pool.",
            "success",
        )

    return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/confirm-handoff", methods=["POST"])
@login_required
def confirm_handoff(item_id):
    """Owner confirms the handoff of a giveaway is complete."""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ConfirmHandoffForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        giveaway_service.confirm_handoff(item, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error confirming handoff for giveaway {item_id}: {str(exc)}")
        flash("An error occurred. Please try again.", "danger")
    else:
        recipient_name = item.claimed_by_name
        flash(
            f"Handoff complete! The giveaway has been successfully given to {recipient_name}.",
            "success",
        )

    return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/mark-given-away", methods=["POST"])
@login_required
def mark_given_away(item_id):
    """Owner marks a giveaway as handed off without recording a specific recipient.

    Use this for items given away outside the app (no in-app interest or messages).
    """
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status not in [None, "unclaimed"]:
        flash("This giveaway is no longer available.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        giveaway_service.mark_given_away(item, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error marking giveaway {item_id} as given away: {str(exc)}")
        flash("An error occurred. Please try again.", "danger")
    else:
        flash(
            "Your item has been marked as rehomed. Thanks for sharing with your community!",
            "success",
        )

    return redirect(url_for("main.item_detail", item_id=item.id))
