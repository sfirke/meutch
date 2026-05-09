from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func, or_

from app import db
from app.forms import ConfirmHandoffForm, EmptyForm, MessageForm, ReleaseToAllForm
from app.main import bp as main_bp
from app.models import GiveawayInterest, Item, ItemRequest, LoanRequest, Message, User
from app.utils.email import send_message_notification_email

from .helpers import _conversation_other_user_id


@main_bp.route("/messages")
@login_required
def messages():
    latest_messages_subquery = (
        db.session.query(
            func.least(Message.sender_id, Message.recipient_id).label("user1_id"),
            func.greatest(Message.sender_id, Message.recipient_id).label("user2_id"),
            Message.item_id,
            Message.request_id,
            Message.circle_id,
            func.max(Message.timestamp).label("latest_timestamp"),  # pylint: disable=not-callable
        )
        .filter(or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id))
        .group_by(
            func.least(Message.sender_id, Message.recipient_id),
            func.greatest(Message.sender_id, Message.recipient_id),
            Message.item_id,
            Message.request_id,
            Message.circle_id,
        )
        .subquery()
    )

    latest_conversations = (
        db.session.query(Message)
        .join(
            latest_messages_subquery,
            and_(
                func.least(Message.sender_id, Message.recipient_id)
                == latest_messages_subquery.c.user1_id,
                func.greatest(Message.sender_id, Message.recipient_id)
                == latest_messages_subquery.c.user2_id,
                or_(
                    and_(Message.item_id.is_(None), latest_messages_subquery.c.item_id.is_(None)),
                    Message.item_id == latest_messages_subquery.c.item_id,
                ),
                or_(
                    and_(
                        Message.request_id.is_(None),
                        latest_messages_subquery.c.request_id.is_(None),
                    ),
                    Message.request_id == latest_messages_subquery.c.request_id,
                ),
                or_(
                    and_(
                        Message.circle_id.is_(None),
                        latest_messages_subquery.c.circle_id.is_(None),
                    ),
                    Message.circle_id == latest_messages_subquery.c.circle_id,
                ),
                Message.timestamp == latest_messages_subquery.c.latest_timestamp,
            ),
        )
        .order_by(Message.timestamp.desc())
        .all()
    )

    conversation_summaries = []
    for convo in latest_conversations:
        if convo.sender_id == current_user.id:
            other_user = db.session.get(User, convo.recipient_id)
        else:
            other_user = db.session.get(User, convo.sender_id)

        if not convo.is_request_message:
            if convo.is_circle_message:
                target_filter = and_(
                    Message.circle_id == convo.circle_id,
                    Message.item_id.is_(None),
                    Message.request_id.is_(None),
                )
                item = None
                item_request = None
                circle = convo.circle
            else:
                target_filter = and_(
                    Message.item_id == convo.item_id,
                    Message.request_id.is_(None),
                    Message.circle_id.is_(None),
                )
                item = db.session.get(Item, convo.item_id)
                item_request = None
                circle = None
        else:
            target_filter = and_(
                Message.request_id == convo.request_id,
                Message.item_id.is_(None),
                Message.circle_id.is_(None),
            )
            item = None
            item_request = db.session.get(ItemRequest, convo.request_id)
            circle = None

        unread_count = Message.query.filter(
            target_filter,
            Message.recipient_id == current_user.id,
            Message.sender_id == other_user.id,
            Message.is_read.is_(False),
        ).count()

        conversation_summaries.append(
            {
                "conversation_id": f"{min(convo.sender_id, convo.recipient_id)}_{max(convo.sender_id, convo.recipient_id)}_{convo.item_id}_{convo.request_id}_{convo.circle_id}",
                "other_user": other_user,
                "item": item,
                "item_request": item_request,
                "circle": circle,
                "latest_message": convo,
                "unread_count": unread_count,
            }
        )

    return render_template("messaging/messages.html", conversations=conversation_summaries)


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

    if not message.is_request_message:
        if message.is_circle_message:
            target_filter = and_(
                Message.circle_id == message.circle_id,
                Message.item_id.is_(None),
                Message.request_id.is_(None),
            )
        else:
            target_filter = and_(
                Message.item_id == message.item_id,
                Message.request_id.is_(None),
                Message.circle_id.is_(None),
            )
    else:
        target_filter = and_(
            Message.request_id == message.request_id,
            Message.item_id.is_(None),
            Message.circle_id.is_(None),
        )

    thread_messages = (
        Message.query.filter(
            target_filter,
            or_(
                and_(
                    Message.sender_id == message.sender_id,
                    Message.recipient_id == message.recipient_id,
                ),
                and_(
                    Message.sender_id == message.recipient_id,
                    Message.recipient_id == message.sender_id,
                ),
            ),
        )
        .order_by(Message.timestamp)
        .all()
    )

    for msg in thread_messages:
        msg.other_user = msg.recipient if msg.sender_id == current_user.id else msg.sender

    unread_messages = Message.query.filter(
        target_filter,
        or_(
            and_(
                Message.sender_id == message.sender_id,
                Message.recipient_id == message.recipient_id,
            ),
            and_(
                Message.sender_id == message.recipient_id,
                Message.recipient_id == message.sender_id,
            ),
        ),
        Message.recipient_id == current_user.id,
        Message.is_read.is_(False),
        or_(
            Message.loan_request_id.is_(None),
            ~Message.loan_request.has(LoanRequest.status == "pending"),
        ),
    ).all()

    has_unread_messages = len(unread_messages) > 0

    for msg in unread_messages:
        msg.is_read = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

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

    form = MessageForm()
    if form.validate_on_submit():
        reply = Message(
            sender_id=current_user.id,
            recipient_id=other_user.id,
            item_id=message.item_id,
            request_id=message.request_id,
            circle_id=message.circle_id,
            body=form.body.data,
            is_read=False,
            parent_id=message.id,
        )
        db.session.add(reply)
        db.session.commit()

        try:
            send_message_notification_email(reply)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for reply message {reply.id}: {str(e)}"
            )

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
    )
