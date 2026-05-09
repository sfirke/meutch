import random
from datetime import UTC, datetime
from uuid import UUID

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import (
    ChangeRecipientForm,
    ConfirmHandoffForm,
    EmptyForm,
    ExpressInterestForm,
    MessageForm,
    ReleaseToAllForm,
    SelectRecipientForm,
    WithdrawInterestForm,
)
from app.main import bp as main_bp
from app.models import GiveawayInterest, Item, Message, User
from app.utils.email import send_message_notification_email

from .helpers import _conversation_other_user_id


def _select_giveaway_recipient(item, selected_interest, sender_id):
    item.claim_status = "pending_pickup"
    item.claimed_by_id = selected_interest.user_id
    item.claimed_at = None
    item.available = False
    selected_interest.status = "selected"

    notification_message = Message(
        sender_id=sender_id,
        recipient_id=selected_interest.user_id,
        item_id=item.id,
        body=f"Good news! You've been selected for the giveaway '{item.name}'! Please coordinate pickup with the owner.",
    )
    db.session.add(notification_message)
    db.session.commit()

    try:
        send_message_notification_email(notification_message)
    except Exception as exc:
        current_app.logger.error(
            f"Failed to send email notification for giveaway selection: {str(exc)}"
        )

    return notification_message


@main_bp.route("/item/<uuid:item_id>/express-interest", methods=["POST"])
@login_required
def express_interest(item_id):
    """Allow a user to express interest in claiming a giveaway"""
    item = db.get_or_404(Item, item_id)
    form = ExpressInterestForm()

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status not in [None, "unclaimed"]:
        flash("This giveaway is no longer available.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.owner_id == current_user.id:
        flash("You cannot express interest in your own giveaway.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if form.validate_on_submit():
        message_text = form.message.data.strip() if form.message.data else None
        notification_body = message_text or f"Hi! I'm interested in your giveaway '{item.name}'."

        try:
            interest = GiveawayInterest(
                item_id=item.id,
                user_id=current_user.id,
                message=message_text,
                status="active",
            )
            db.session.add(interest)

            message = Message(
                sender_id=current_user.id,
                recipient_id=item.owner_id,
                item_id=item.id,
                body=notification_body,
            )
            db.session.add(message)

            db.session.commit()

            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification for giveaway interest message {message.id}: {str(e)}"
                )

            flash(
                "Your interest has been recorded! The owner will contact you if you are selected.",
                "success",
            )
        except IntegrityError:
            db.session.rollback()
            flash("You have already expressed interest in this giveaway.", "info")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error expressing interest in giveaway {item_id}: {str(e)}")
            flash("An error occurred. Please try again.", "danger")

    return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/withdraw-interest", methods=["POST"])
@login_required
def withdraw_interest(item_id):
    """Allow a user to withdraw their interest in a giveaway"""
    item = db.get_or_404(Item, item_id)
    form = WithdrawInterestForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    interest = GiveawayInterest.query.filter_by(item_id=item.id, user_id=current_user.id).first()

    if not interest:
        flash("You have not expressed interest in this giveaway.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        db.session.delete(interest)
        db.session.commit()
        flash("Your interest has been withdrawn.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error withdrawing interest from giveaway {item_id}: {str(e)}")
        flash("An error occurred. Please try again.", "danger")

    return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/select-recipient", methods=["GET", "POST"])
@login_required
def select_recipient(item_id):
    """Owner views interested users and selects a recipient for a giveaway"""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
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

        active_interests = (
            GiveawayInterest.query.filter_by(item_id=item.id, status="active")
            .order_by(GiveawayInterest.created_at)
            .all()
        )

        if not active_interests:
            flash("No interested users found.", "warning")
            return redirect(url_for("main.item_detail", item_id=item.id))

        selected_interest = None
        if selection_method == "first":
            selected_interest = active_interests[0]
        elif selection_method == "random":
            selected_interest = random.choice(active_interests)
        elif selection_method == "manual":
            manual_user_id = form.user_id.data
            selected_interest = GiveawayInterest.query.filter_by(
                item_id=item.id,
                user_id=manual_user_id,
                status="active",
            ).first()

        if not selected_interest:
            flash("Invalid selection. Please try again.", "danger")
            return redirect(url_for("main.select_recipient", item_id=item.id))

        try:
            _select_giveaway_recipient(item, selected_interest, current_user.id)
            flash(
                f"{selected_interest.user.full_name} has been selected! They will be notified.",
                "success",
            )
            return redirect(url_for("main.item_detail", item_id=item.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error selecting recipient for giveaway {item_id}: {str(e)}")
            flash("An error occurred. Please try again.", "danger")
            return redirect(url_for("main.select_recipient", item_id=item.id))

    is_reassignment = item.claim_status == "pending_pickup"
    interested_users = (
        GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.status.in_(["active", "selected"]),
        )
        .order_by(GiveawayInterest.created_at)
        .all()
    )

    if not interested_users:
        flash("No users have expressed interest in this giveaway yet.", "info")
        return redirect(url_for("main.item_detail", item_id=item.id))

    user_messaging_info = {}
    for interest in interested_users:
        conversation_messages = (
            Message.query.filter(
                Message.item_id == item.id,
                or_(
                    and_(
                        Message.sender_id == current_user.id,
                        Message.recipient_id == interest.user_id,
                    ),
                    and_(
                        Message.sender_id == interest.user_id,
                        Message.recipient_id == current_user.id,
                    ),
                ),
            )
            .order_by(Message.timestamp)
            .all()
        )

        latest_message = conversation_messages[-1] if conversation_messages else None
        user_messaging_info[str(interest.user_id)] = {
            "has_conversation": len(conversation_messages) > 0,
            "unread_count": sum(
                1
                for msg in conversation_messages
                if msg.recipient_id == current_user.id and not msg.is_read
            ),
            "message_count": len(conversation_messages),
            "latest_message": latest_message,
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
            return redirect(url_for("main.view_conversation", message_id=conversation_message.id))
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        if conversation_message:
            return redirect(url_for("main.view_conversation", message_id=conversation_message.id))
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        if conversation_message:
            return redirect(url_for("main.view_conversation", message_id=conversation_message.id))
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status not in [None, "unclaimed"]:
        flash("This giveaway is no longer awaiting recipient selection.", "warning")
        if conversation_message:
            return redirect(url_for("main.view_conversation", message_id=conversation_message.id))
        return redirect(url_for("main.item_detail", item_id=item.id))

    if conversation_message is None or conversation_message.item_id != item.id:
        flash("Invalid conversation context.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    other_user_id = _conversation_other_user_id(conversation_message, current_user.id)
    if other_user_id != user_id:
        flash("This conversation does not match that interested user.", "danger")
        return redirect(url_for("main.view_conversation", message_id=conversation_message.id))

    selected_interest = GiveawayInterest.query.filter_by(
        item_id=item.id,
        user_id=user_id,
        status="active",
    ).first()

    if not selected_interest:
        flash("This user is not currently in the interested-user pool.", "warning")
        return redirect(url_for("main.view_conversation", message_id=conversation_message.id))

    try:
        _select_giveaway_recipient(item, selected_interest, current_user.id)
        flash(
            f"{selected_interest.user.full_name} has been selected! They will be notified.",
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            f"Error selecting giveaway recipient from conversation {conversation_message.id}: {str(exc)}"
        )
        flash("An error occurred. Please try again.", "danger")

    return redirect(url_for("main.view_conversation", message_id=conversation_message.id))


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

    existing_message = Message.query.filter(
        Message.item_id == item.id,
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id),
        ),
    ).first()

    if existing_message:
        return redirect(url_for("main.view_conversation", message_id=existing_message.id))

    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            sender_id=current_user.id,
            recipient_id=user_id,
            item_id=item.id,
            body=form.body.data,
        )
        db.session.add(message)

        try:
            db.session.commit()

            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification for message {message.id}: {str(e)}"
                )

            flash("Your message has been sent.", "success")
            return redirect(url_for("main.view_conversation", message_id=message.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending message for giveaway {item_id}: {str(e)}")
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

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ChangeRecipientForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.select_recipient", item_id=item.id))

    selection_method = form.selection_method.data
    previous_claimed_by_id = item.claimed_by_id
    active_interests = (
        GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.status == "active",
            GiveawayInterest.user_id != previous_claimed_by_id,
        )
        .order_by(GiveawayInterest.created_at)
        .all()
    )

    if not active_interests:
        flash("No other interested users available to select.", "warning")
        return redirect(url_for("main.select_recipient", item_id=item.id))

    selected_interest = None
    if selection_method == "next":
        selected_interest = active_interests[0]
    elif selection_method == "random":
        selected_interest = random.choice(active_interests)
    elif selection_method == "manual":
        manual_user_id = form.user_id.data
        if str(manual_user_id) == str(previous_claimed_by_id):
            flash("That recipient is currently selected.", "warning")
            return redirect(url_for("main.select_recipient", item_id=item.id))
        selected_interest = GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.user_id == manual_user_id,
            GiveawayInterest.status == "active",
            GiveawayInterest.user_id != previous_claimed_by_id,
        ).first()

    if not selected_interest:
        flash("Invalid selection. Please try again.", "danger")
        return redirect(url_for("main.select_recipient", item_id=item.id))

    try:
        previous_interest = GiveawayInterest.query.filter_by(
            item_id=item.id, user_id=previous_claimed_by_id
        ).first()
        if previous_interest:
            previous_interest.status = "active"

        previous_recipient = db.session.get(User, previous_claimed_by_id)
        if previous_recipient:
            previous_notification = Message(
                sender_id=current_user.id,
                recipient_id=previous_recipient.id,
                item_id=item.id,
                body=f"The owner has selected a different recipient for the giveaway '{item.name}'. Your interest remains active and you may still be selected in the future.",
            )
            db.session.add(previous_notification)

        item.claimed_by_id = selected_interest.user_id
        selected_interest.status = "selected"

        notification_message = Message(
            sender_id=current_user.id,
            recipient_id=selected_interest.user_id,
            item_id=item.id,
            body=f"Good news! You've been selected for the giveaway '{item.name}'! Please coordinate pickup with the owner.",
        )
        db.session.add(notification_message)

        db.session.commit()

        try:
            send_message_notification_email(notification_message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for giveaway reassignment: {str(e)}"
            )

        if previous_recipient:
            try:
                send_message_notification_email(previous_notification)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification to previous recipient: {str(e)}"
                )

        flash(
            f"{selected_interest.user.full_name} has been selected! They will be notified.",
            "success",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing recipient for giveaway {item_id}: {str(e)}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("main.select_recipient", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/release-to-all", methods=["POST"])
@login_required
def release_to_all(item_id):
    """Owner releases a giveaway back to unclaimed status."""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ReleaseToAllForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        previous_recipient_id = item.claimed_by_id
        if previous_recipient_id:
            previous_interest = GiveawayInterest.query.filter_by(
                item_id=item.id, user_id=previous_recipient_id
            ).first()
            if previous_interest:
                previous_interest.status = "active"

            release_notification = Message(
                sender_id=current_user.id,
                recipient_id=previous_recipient_id,
                item_id=item.id,
                body=f"The owner has released the giveaway '{item.name}' back to everyone. Your interest remains active and you may still be selected.",
            )
            db.session.add(release_notification)

        item.claim_status = "unclaimed"
        item.claimed_by_id = None
        item.available = True

        db.session.commit()

        if previous_recipient_id:
            try:
                send_message_notification_email(release_notification)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification for giveaway release: {str(e)}"
                )

        flash(
            "The giveaway has been released and will reappear in the feed. All interested users remain in the pool.",
            "success",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error releasing giveaway {item_id} to all: {str(e)}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))


@main_bp.route("/item/<uuid:item_id>/confirm-handoff", methods=["POST"])
@login_required
def confirm_handoff(item_id):
    """Owner confirms the handoff of a giveaway is complete."""
    item = db.get_or_404(Item, item_id)

    if item.owner_id != current_user.id:
        flash("You do not have permission to manage this giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if not item.is_giveaway:
        flash("This item is not a giveaway.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    if item.claim_status != "pending_pickup":
        flash("This giveaway is not pending pickup.", "warning")
        return redirect(url_for("main.item_detail", item_id=item.id))

    form = ConfirmHandoffForm()

    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))

    try:
        item.claim_status = "claimed"
        item.claimed_at = datetime.now(UTC)
        item.available = False

        db.session.commit()

        recipient_name = item.claimed_by_name
        flash(
            f"Handoff complete! The giveaway has been successfully given to {recipient_name}.",
            "success",
        )
        return redirect(url_for("main.item_detail", item_id=item.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error confirming handoff for giveaway {item_id}: {str(e)}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("main.item_detail", item_id=item.id))
