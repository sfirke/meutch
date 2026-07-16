from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import ConfirmHandoffForm, EmptyForm, MessageForm, ReleaseToAllForm
from app.main import bp as main_bp
from app.models import Conversation, ConversationParticipant, GiveawayInterest, Message
from app.services import message_service
from app.utils.messaging_queries import (
    build_inbox_summaries,
    filter_by_archive_status,
    sort_conversation_summaries,
)
from app.utils.pagination import ListPagination


@main_bp.route("/messages")
@login_required
def messages():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort = request.args.get("sort", "newest")
    status = request.args.get("status", "inbox")

    summaries = build_inbox_summaries(current_user.id, include_archived=True)
    summaries = filter_by_archive_status(summaries, status)
    summaries = sort_conversation_summaries(summaries, sort)

    pagination = ListPagination(items=summaries, page=page, per_page=per_page)

    return render_template(
        "messaging/messages.html",
        conversations=pagination.items,
        pagination=pagination,
        current_sort=sort,
        current_status=status,
    )


@main_bp.route("/messages/bulk-archive", methods=["POST"])
@login_required
def bulk_archive():
    conversation_ids = _parse_bulk_ids()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    if conversation_ids:
        message_service.bulk_archive(current_user.id, conversation_ids)
        flash(f"{len(conversation_ids)} conversation(s) archived.", "success")
    return redirect(
        url_for("main.messages", page=page, sort=sort, status=request.args.get("status", "inbox"))
    )


@main_bp.route("/messages/bulk-unarchive", methods=["POST"])
@login_required
def bulk_unarchive():
    conversation_ids = _parse_bulk_ids()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    if conversation_ids:
        message_service.bulk_unarchive(current_user.id, conversation_ids)
        flash(f"{len(conversation_ids)} conversation(s) moved to inbox.", "success")
    return redirect(
        url_for("main.messages", page=page, sort=sort, status=request.args.get("status", "inbox"))
    )


@main_bp.route("/messages/bulk-mark-read", methods=["POST"])
@login_required
def bulk_mark_read():
    conversation_ids = _parse_bulk_ids()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    if conversation_ids:
        message_service.bulk_mark_read(current_user.id, conversation_ids)
        flash(f"{len(conversation_ids)} conversation(s) marked as read.", "success")
    return redirect(
        url_for("main.messages", page=page, sort=sort, status=request.args.get("status", "inbox"))
    )


@main_bp.route("/messages/bulk-mark-unread", methods=["POST"])
@login_required
def bulk_mark_unread():
    conversation_ids = _parse_bulk_ids()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    if conversation_ids:
        message_service.bulk_mark_unread(current_user.id, conversation_ids)
        flash(f"{len(conversation_ids)} conversation(s) marked as unread.", "success")
    return redirect(
        url_for("main.messages", page=page, sort=sort, status=request.args.get("status", "inbox"))
    )


@main_bp.route("/messages/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    status = request.args.get("status", "inbox")
    message_service.mark_all_read_in_view(current_user.id, status=status)
    view_label = "inbox" if status == "inbox" else "archived"
    flash(f"Entire {view_label} marked as read.", "success")
    return redirect(url_for("main.messages", page=page, sort=sort, status=status))


def _parse_bulk_ids():
    """Extract conversation IDs from POST body (JSON or form)."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
        ids_raw = data.get("conversation_ids", [])
    else:
        ids_raw = request.form.get("conversation_ids", "")
        if ids_raw:
            ids_raw = ids_raw.split(",")
        else:
            ids_raw = []
    return [cid.strip() for cid in ids_raw if cid.strip()]


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
    giveaway_selection_direct = False
    if (
        item
        and item.is_giveaway
        and item.claim_status in [None, "unclaimed"]
        and current_user.id == item.owner_id
    ):
        giveaway_selection_item = item
        giveaway_selection_form = EmptyForm()
        # Count formal interests for display (may be zero if they only messaged)
        giveaway_selection_interested_count = GiveawayInterest.query.filter_by(
            item_id=item.id,
            status="active",
        ).count()
        # Check whether the other user has a formal interest record.
        # Since the "I Want This!" button was removed, express_interest()
        # is now called automatically when someone messages about a giveaway
        # (see message_service.py). That means every new conversation will
        # have an active GiveawayInterest record, making this distinction
        # vestigial in practice.
        #
        # TODO: Remove giveaway_selection_direct and the template branch for
        #       it once there are no pre-existing conversations where a user
        #       messaged about a giveaway before this auto-interest logic was
        #       deployed (i.e. no legacy items in this state).
        active_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=other_user.id,
            status="active",
        ).first()
        giveaway_selection_direct = not active_interest

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
        giveaway_selection_direct=giveaway_selection_direct,
        giveaway_handoff_item=giveaway_handoff_item,
        giveaway_handoff_form=giveaway_handoff_form,
        giveaway_release_form=giveaway_release_form,
        loan_action_form=loan_action_form,
        has_unread_messages=has_unread_messages,
        fulfillable_request=fulfillable_request,
        request_fulfill_form=request_fulfill_form,
        viewer_participant=viewer_participant,
        conversation=conversation,
    )


@main_bp.route("/conversation/<uuid:conversation_id>/archive", methods=["POST"])
@login_required
def archive_conversation(conversation_id):
    conversation = db.get_or_404(Conversation, conversation_id)
    _require_participant(conversation, current_user.id)
    message_service.archive_conversation(current_user.id, conversation_id)
    flash("Conversation archived.", "success")
    return redirect(url_for("main.messages"))


@main_bp.route("/conversation/<uuid:conversation_id>/unarchive", methods=["POST"])
@login_required
def unarchive_conversation(conversation_id):
    conversation = db.get_or_404(Conversation, conversation_id)
    _require_participant(conversation, current_user.id)
    message_service.unarchive_conversation(current_user.id, conversation_id)
    flash("Conversation unarchived.", "success")
    return redirect(url_for("main.messages", status="archived"))


def _require_participant(conversation, user_id):
    """Abort 404 if the user is not a participant in the conversation."""
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation.id, user_id=user_id
    ).first()
    if not participant:
        abort(404)
