from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import ConfirmHandoffForm, EmptyForm, MessageForm, ReleaseToAllForm
from app.main import bp as main_bp
from app.models import Conversation, ConversationParticipant, GiveawayInterest, Message
from app.services import message_service
from app.utils.messaging_queries import build_inbox_summaries


@main_bp.route("/messages")
@login_required
def messages():
    return render_template(
        "messaging/messages.html",
        conversations=build_inbox_summaries(current_user.id),
    )


@main_bp.route("/conversation/<uuid:conversation_id>", methods=["GET", "POST"])
@login_required
def view_conversation(conversation_id):
    conversation = db.get_or_404(Conversation, conversation_id)

    # Verify the viewer is a participant
    viewer_participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation.id, user_id=current_user.id
    ).first()
    if not viewer_participant:
        flash("You do not have permission to view this conversation.", "danger")
        return redirect(url_for("main.messages"))

    other_participant = conversation.other_participant(current_user.id)

    if not other_participant:
        flash("This conversation is missing a participant.", "danger")
        return redirect(url_for("main.messages"))

    other_user = other_participant.user
    shared_circles = current_user.shared_circles_with(other_user)

    # Get the latest message in this conversation for thread state loading
    latest_message = (
        Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.timestamp.desc())
        .first()
    )
    if latest_message is None:
        flash("This conversation has no messages.", "danger")
        return redirect(url_for("main.messages"))

    if (
        latest_message.recipient_id != current_user.id
        and latest_message.sender_id != current_user.id
    ):
        flash("You do not have permission to view this conversation.", "danger")
        return redirect(url_for("main.messages"))

    thread_state = message_service.get_conversation_thread_state(latest_message, current_user.id)
    thread_messages = thread_state["thread_messages"]
    has_unread_messages = thread_state["has_unread_messages"]

    active_loan = None
    if conversation.context_type == "item":
        for msg in thread_messages:
            if msg.loan_request and msg.loan_request.status in ["pending", "approved"]:
                active_loan = msg.loan_request
                break

    item = conversation.item
    giveaway_selection_item = None
    giveaway_selection_form = None
    giveaway_selection_interested_count = 0
    if (
        item
        and item.is_giveaway
        and item.claim_status in [None, "unclaimed"]
        and current_user.id == item.owner_id
    ):
        active_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=other_user.id,
            status="active",
        ).first()
        if active_interest:
            giveaway_selection_item = item
            giveaway_selection_form = EmptyForm()
            giveaway_selection_interested_count = GiveawayInterest.query.filter_by(
                item_id=item.id,
                status="active",
            ).count()

    giveaway_handoff_item = None
    giveaway_handoff_form = None
    giveaway_release_form = None
    if (
        item
        and item.is_giveaway
        and item.claim_status == "pending_pickup"
        and item.claimed_by_id
        and {current_user.id, other_user.id} == {item.owner_id, item.claimed_by_id}
    ):
        giveaway_handoff_item = item
        if current_user.id == item.owner_id:
            giveaway_handoff_form = ConfirmHandoffForm()
            giveaway_release_form = ReleaseToAllForm()

    fulfillable_request = None
    request_fulfill_form = None
    if conversation.context_type == "request":
        req = conversation.request
        if req and req.user_id == current_user.id and req.status == "open" and not req.is_expired:
            fulfillable_request = req
            request_fulfill_form = EmptyForm()

    form = MessageForm()
    if form.validate_on_submit():
        message_service.reply_to_message(latest_message, current_user.id, form.body.data)
        flash("Your reply has been sent.", "success")
        return redirect(url_for("main.view_conversation", conversation_id=conversation_id))

    loan_action_form = EmptyForm()

    return render_template(
        "messaging/view_conversation.html",
        message=latest_message,
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
