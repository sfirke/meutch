from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import EmptyForm, ExtendLoanForm, LoanRequestForm
from app.main import bp as main_bp
from app.models import Item, LoanRequest, Message
from app.services import loan_service
from app.services.exceptions import ServiceError

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
        try:
            message = loan_service.create_loan_request(
                item,
                current_user.id,
                form.start_date.data,
                form.end_date.data,
                form.message.data,
            )
        except ServiceError as exc:
            flash(str(exc), exc.flash_category)
        except Exception as exc:
            current_app.logger.error(f"Error creating loan request for item {item_id}: {str(exc)}")
            flash("An error occurred. Please try again.", "danger")
        else:
            flash("Your loan request has been submitted.", "success")
            return redirect(url_for("main.view_conversation", message_id=message.id))

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

    try:
        loan_service.process_loan_decision(loan, current_user.id, action)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error processing loan {loan_id}: {str(exc)}")
        flash("An error occurred processing the request.", "danger")
    else:
        flash(f"Loan request has been {loan.status}.", "success")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/cancel", methods=["POST"])
@login_required
def cancel_loan_request(loan_id):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    try:
        loan_service.cancel_loan_request(loan, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error canceling loan request {loan_id}: {str(exc)}")
        flash("An error occurred canceling the request.", "danger")
    else:
        flash("Loan request has been canceled.", "success")

    return _redirect_to_loan_conversation(loan)


@main_bp.route("/loan/<uuid:loan_id>/complete", methods=["POST"])
@login_required
def complete_loan(loan_id):
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("main.messages"))

    loan = db.get_or_404(LoanRequest, loan_id)

    try:
        loan_service.complete_loan(loan, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        current_app.logger.error(f"Error completing loan {loan_id}: {str(exc)}")
        flash("An error occurred completing the loan.", "danger")
    else:
        flash("Loan has been marked as completed.", "success")

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

    try:
        loan_service.owner_cancel_approved_loan(loan, current_user.id)
    except ServiceError as exc:
        flash(str(exc), exc.flash_category)
    except Exception as exc:
        flash("An error occurred while canceling the loan.", "danger")
        current_app.logger.error(f"Error canceling loan {loan_id}: {str(exc)}")
    else:
        flash("Loan has been canceled.", "success")

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
        try:
            extend_result = loan_service.extend_loan(
                loan,
                current_user.id,
                form.new_end_date.data,
                form.message.data,
            )
        except ServiceError as exc:
            flash(str(exc), exc.flash_category)
        except Exception as exc:
            flash("An error occurred while updating the loan due date.", "danger")
            current_app.logger.error(f"Error updating loan due date {loan_id}: {str(exc)}")
        else:
            if extend_result.is_extension:
                flash(
                    f"Loan has been extended until {form.new_end_date.data.strftime('%B %d, %Y')}.",
                    "success",
                )
            else:
                flash(
                    f"Loan due date has been updated to {form.new_end_date.data.strftime('%B %d, %Y')}.",
                    "success",
                )

        return redirect(url_for("main.profile", tab="my-activity"))

    return render_template("main/extend_loan.html", form=form, loan=loan)
