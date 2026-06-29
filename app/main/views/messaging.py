from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import ConfirmHandoffForm, EmptyForm, MessageForm, ReleaseToAllForm
from app.main import bp as main_bp
from app.models import GiveawayInterest, Message, User
from app.services import message_service
from app.utils.messaging_queries import build_inbox_summaries

from .helpers import _conversation_other_user_id


@main_bp.route("/messages")
@login_required
def messages():
    return render_template(
        "messaging/messages.html",
        conversations=build_inbox_summaries(current_user.id),
    )


@main_bp.route("/message/<uuid:message_id>", methods=["GET", "POST"])
@login_required
def view_conversation(message_id):
    message = db.get_or_404(Message, message_id)

    other_user_id = _conversation_other_user_id(message, current_user.id)
    other_user = db.session.get(User, other_user_id)
    shared_circles = current_user.shared_circles_with(other_user)

    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        flash("You do not have permission to view this message.", "danger")
        return redirect(url_for("main.messages"))

    thread_state = message_service.get_conversation_thread_state(message, current_user.id)
    thread_messages = thread_state["thread_messages"]
    has_unread_messages = thread_state["has_unread_messages"]

    active_loan = None
    if not message.is_request_message:
        for msg in thread_messages:
            if msg.loan_request and msg.loan_request.status in ["pending", "approved"]:
                active_loan = msg.loan_request
                break

    giveaway_selection_item = None
    giveaway_selection_form = None
    giveaway_selection_interested_count = 0
    if (
        message.item
        and message.item.is_giveaway
        and message.item.claim_status in [None, "unclaimed"]
        and current_user.id == message.item.owner_id
    ):
        active_interest = GiveawayInterest.query.filter_by(
            item_id=message.item.id,
            user_id=other_user.id,
            status="active",
        ).first()
        if active_interest:
            giveaway_selection_item = message.item
            giveaway_selection_form = EmptyForm()
            giveaway_selection_interested_count = GiveawayInterest.query.filter_by(
                item_id=message.item.id,
                status="active",
            ).count()

    giveaway_handoff_item = None
    giveaway_handoff_form = None
    giveaway_release_form = None
    if (
        message.item
        and message.item.is_giveaway
        and message.item.claim_status == "pending_pickup"
        and message.item.claimed_by_id
        and {current_user.id, other_user.id} == {message.item.owner_id, message.item.claimed_by_id}
    ):
        giveaway_handoff_item = message.item
        if current_user.id == message.item.owner_id:
            giveaway_handoff_form = ConfirmHandoffForm()
            giveaway_release_form = ReleaseToAllForm()

    fulfillable_request = None
    request_fulfill_form = None
    if (
        message.is_request_message
        and message.request.user_id == current_user.id
        and message.request.status == "open"
        and not message.request.is_expired
    ):
        fulfillable_request = message.request
        request_fulfill_form = EmptyForm()

    form = MessageForm()
    if form.validate_on_submit():
        message_service.reply_to_message(message, current_user.id, form.body.data)

        flash("Your reply has been sent.", "success")
        return redirect(url_for("main.view_conversation", message_id=message_id))

    loan_action_form = EmptyForm()

    return render_template(
        "messaging/view_conversation.html",
        message=message,
        thread_messages=thread_messages,
        form=form,
        shared_circles=shared_circles,
        active_loan=active_loan,
        giveaway_selection_item=giveaway_selection_item,
        giveaway_selection_form=giveaway_selection_form,
        giveaway_selection_interested_count=giveaway_selection_interested_count,
        giveaway_handoff_item=giveaway_handoff_item,
        giveaway_handoff_form=giveaway_handoff_form,
        giveaway_release_form=giveaway_release_form,
        loan_action_form=loan_action_form,
        has_unread_messages=has_unread_messages,
        fulfillable_request=fulfillable_request,
        request_fulfill_form=request_fulfill_form,
    )
