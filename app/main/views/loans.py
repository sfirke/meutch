from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import EmptyForm, ExtendLoanForm, LoanRequestForm
from app.main import bp as main_bp
from app.models import Item, LoanRequest, Message
from app.utils.email import send_message_notification_email

from .helpers import _build_item_detail_url, _shares_circle_or_has_item_token_access


def _get_first_loan_conversation_message(loan):
    return (
        Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
    )


def _redirect_to_loan_conversation(loan):
    original_message = _get_first_loan_conversation_message(loan)
    if original_message:
        return redirect(url_for("main.view_conversation", message_id=original_message.id))
    return redirect(url_for("main.item_detail", item_id=loan.item_id))


@main_bp.route("/items/<uuid:item_id>/request", methods=["GET", "POST"])
@login_required
def request_item(item_id):
    item = db.get_or_404(Item, item_id)
    share_token = request.args.get("share_token", "").strip() or None

    if item.owner == current_user:
        flash("You cannot request your own items.", "warning")
        return redirect(_build_item_detail_url(item.id, share_token))

    if item.is_giveaway:
        flash("This item is being offered as a giveaway, not a loan.", "warning")
        return redirect(_build_item_detail_url(item.id, share_token))

    if not item.available:
        flash("This item is not currently available to borrow.", "warning")
        return redirect(_build_item_detail_url(item.id, share_token))

    if not _shares_circle_or_has_item_token_access(item, share_token):
        abort(403)

    existing_request = LoanRequest.query.filter_by(
        item_id=item.id,
        borrower_id=current_user.id,
        status="pending",
    ).first()

    if existing_request:
        flash("You already have a pending request for this item.", "info")
        return redirect(_build_item_detail_url(item.id, share_token))

    form = LoanRequestForm()
    if form.validate_on_submit():
        loan_request = LoanRequest(
            item_id=item.id,
            borrower_id=current_user.id,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status="pending",
        )
        db.session.add(loan_request)

        message = Message(
            sender_id=current_user.id,
            recipient_id=item.owner_id,
            item_id=item.id,
            body=form.message.data,
            loan_request=loan_request,
        )
        db.session.add(message)

        try:
            db.session.commit()

            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification for loan request message {message.id}: {str(e)}"
                )

            flash("Your loan request has been submitted.", "success")
            return redirect(url_for("main.view_conversation", message_id=message.id))
        except Exception:
            db.session.rollback()
            flash("An error occurred. Please try again.", "danger")

    return render_template("main/request_loan.html", form=form, item=item, share_token=share_token)


@main_bp.route("/loan/<uuid:loan_id>/<string:action>", methods=["POST"])
@login_required
def process_loan(loan_id, action):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("main.messages"))

    if action.lower() not in ["approve", "deny"]:
        flash("Invalid action.", "danger")
        return redirect(url_for("main.messages"))

    if loan.status != "pending":
        flash("This loan request has already been processed.", "warning")
        return redirect(url_for("main.messages"))

    if action.lower() == "approve":
        loan.status = "approved"
        loan.item.available = False
        message_body = f"The loan request for '{loan.item.name}' has been approved."
    else:
        loan.status = "denied"
        message_body = f"The loan request for '{loan.item.name}' has been denied."

    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body=message_body,
        loan_request_id=loan.id,
    )
    db.session.add(message)

    try:
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for loan decision message {message.id}: {str(e)}"
            )

        flash(f"Loan request has been {loan.status}.", "success")
    except Exception:
        db.session.rollback()
        flash("An error occurred processing the request.", "danger")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/cancel", methods=["POST"])
@login_required
def cancel_loan_request(loan_id):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    if loan.borrower_id != current_user.id:
        flash("You are not authorized to cancel this request.", "danger")
        return redirect(url_for("main.messages"))

    if loan.status != "pending":
        flash("This loan request cannot be canceled.", "warning")
        return redirect(url_for("main.messages"))

    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.item.owner_id,
        item_id=loan.item_id,
        body="Loan request has been canceled by the borrower.",
        loan_request_id=loan.id,
    )
    db.session.add(message)
    loan.status = "canceled"

    try:
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for loan cancellation message {message.id}: {str(e)}"
            )

        flash("Loan request has been canceled.", "success")
    except Exception:
        db.session.rollback()
        flash("An error occurred canceling the request.", "danger")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/complete", methods=["POST"])
@login_required
def complete_loan(loan_id):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("main.messages"))

    if loan.status != "approved":
        flash("This loan is not currently active.", "warning")
        return redirect(url_for("main.messages"))

    loan.status = "completed"
    loan.item.available = True

    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The item has been marked as returned. Thank you for borrowing!",
        loan_request_id=loan.id,
    )
    db.session.add(message)

    try:
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for loan completion message {message.id}: {str(e)}"
            )

        flash("Loan has been marked as completed.", "success")
    except Exception:
        db.session.rollback()
        flash("An error occurred completing the loan.", "danger")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/owner_cancel", methods=["POST"])
@login_required
def owner_cancel_loan(loan_id):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("main.messages"))

    if loan.status != "approved":
        flash("Only approved loans can be canceled.", "warning")
        return redirect(url_for("main.view_conversation", message_id=loan.messages[0].id))

    loan.status = "canceled"
    loan.item.available = True

    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The loan has been canceled by the owner. The item is now available.",
        loan_request_id=loan.id,
    )
    db.session.add(message)

    try:
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(
                f"Failed to send email notification for owner loan cancellation message {message.id}: {str(e)}"
            )

        flash("Loan has been canceled.", "success")
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while canceling the loan.", "danger")
        current_app.logger.error(f"Error canceling loan {loan_id}: {e}")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/extend", methods=["GET", "POST"])
@login_required
def extend_loan(loan_id):
    """Allow item owner to extend the loan due date"""
    loan = db.get_or_404(LoanRequest, loan_id)

    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to extend this loan.", "danger")
        return redirect(url_for("main.messages"))

    if loan.status not in ["pending", "approved"]:
        flash("Only pending or approved loans can be extended.", "warning")
        return redirect(url_for("main.messages"))

    form = ExtendLoanForm(current_end_date=loan.end_date)

    if form.validate_on_submit():
        old_end_date = loan.end_date
        loan.end_date = form.new_end_date.data
        loan.due_soon_reminder_sent = None
        loan.due_date_reminder_sent = None
        loan.last_overdue_reminder_sent = None
        loan.overdue_reminder_count = 0
        is_extension = form.new_end_date.data > old_end_date

        if form.message.data and form.message.data.strip():
            if is_extension:
                message_body = f"The loan of '{loan.item.name}' has been extended until {form.new_end_date.data.strftime('%B %d, %Y')}.\n\nMessage from owner: {form.message.data}"
            else:
                message_body = f"The due date for '{loan.item.name}' has been updated to {form.new_end_date.data.strftime('%B %d, %Y')}.\n\nMessage from owner: {form.message.data}"
        else:
            if is_extension:
                message_body = f"Good news! The loan of '{loan.item.name}' has been extended. The new due date is {form.new_end_date.data.strftime('%B %d, %Y')} (previously {old_end_date.strftime('%B %d, %Y')})."
            else:
                message_body = f"The due date for '{loan.item.name}' has been updated. The new due date is {form.new_end_date.data.strftime('%B %d, %Y')} (previously {old_end_date.strftime('%B %d, %Y')})."

        message = Message(
            sender_id=current_user.id,
            recipient_id=loan.borrower_id,
            item_id=loan.item_id,
            body=message_body,
            loan_request_id=loan.id,
        )
        db.session.add(message)

        try:
            db.session.commit()

            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send email notification for loan extension message {message.id}: {str(e)}"
                )

            if is_extension:
                flash(
                    f"Loan has been extended until {form.new_end_date.data.strftime('%B %d, %Y')}.",
                    "success",
                )
            else:
                flash(
                    f"Loan due date has been updated to {form.new_end_date.data.strftime('%B %d, %Y')}.",
                    "success",
                )
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while updating the loan due date.", "danger")
            current_app.logger.error(f"Error updating loan due date {loan_id}: {e}")

        return redirect(url_for("main.profile", tab="my-activity"))

    return render_template("main/extend_loan.html", form=form, loan=loan)
