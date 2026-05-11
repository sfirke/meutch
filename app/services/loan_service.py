import logging

from app import db
from app.models import LoanRequest, Message
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.email import send_message_notification_email

logger = logging.getLogger(__name__)


def _send_notification_email(message, error_prefix):
    try:
        send_message_notification_email(message)
    except Exception as exc:  # pragma: no cover - route/service behavior is the same either way
        logger.error("%s: %s", error_prefix, exc)


def _commit_and_notify(message, error_prefix):
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    _send_notification_email(message, error_prefix)
    return message


def create_loan_request(item, borrower_id, start_date, end_date, message_body):
    if item.owner_id == borrower_id:
        raise ConflictError("You cannot request your own items.")

    if item.is_giveaway:
        raise ConflictError("This item is being offered as a giveaway, not a loan.")

    if not item.available:
        raise ConflictError("This item is not currently available to borrow.")

    existing_request = LoanRequest.query.filter_by(
        item_id=item.id,
        borrower_id=borrower_id,
        status="pending",
    ).first()
    if existing_request:
        raise InformationalError("You already have a pending request for this item.")

    loan_request = LoanRequest(
        item_id=item.id,
        borrower_id=borrower_id,
        start_date=start_date,
        end_date=end_date,
        status="pending",
    )
    message = Message(
        sender_id=borrower_id,
        recipient_id=item.owner_id,
        item_id=item.id,
        body=message_body,
        loan_request=loan_request,
    )
    db.session.add(loan_request)
    db.session.add(message)
    return _commit_and_notify(
        message,
        f"Failed to send email notification for loan request message {message.id}",
    )


def process_loan_decision(loan, owner_id, action):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    normalized_action = action.lower()
    if normalized_action not in {"approve", "deny"}:
        raise InvalidActionError("Invalid action.")

    if loan.status != "pending":
        raise ConflictError("This loan request has already been processed.")

    if normalized_action == "approve":
        loan.status = "approved"
        loan.item.available = False
        message_body = f"The loan request for '{loan.item.name}' has been approved."
    else:
        loan.status = "denied"
        message_body = f"The loan request for '{loan.item.name}' has been denied."

    message = Message(
        sender_id=owner_id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body=message_body,
        loan_request_id=loan.id,
    )
    db.session.add(message)
    return _commit_and_notify(
        message,
        f"Failed to send email notification for loan decision message {message.id}",
    )


def cancel_loan_request(loan, borrower_id):
    if loan.borrower_id != borrower_id:
        raise AuthorizationError("You are not authorized to cancel this request.")

    if loan.status != "pending":
        raise ConflictError("This loan request cannot be canceled.")

    loan.status = "canceled"
    message = Message(
        sender_id=borrower_id,
        recipient_id=loan.item.owner_id,
        item_id=loan.item_id,
        body="Loan request has been canceled by the borrower.",
        loan_request_id=loan.id,
    )
    db.session.add(message)
    return _commit_and_notify(
        message,
        f"Failed to send email notification for loan cancellation message {message.id}",
    )


def complete_loan(loan, owner_id):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    if loan.status != "approved":
        raise ConflictError("This loan is not currently active.")

    loan.status = "completed"
    loan.item.available = True

    message = Message(
        sender_id=owner_id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The item has been marked as returned. Thank you for borrowing!",
        loan_request_id=loan.id,
    )
    db.session.add(message)
    return _commit_and_notify(
        message,
        f"Failed to send email notification for loan completion message {message.id}",
    )


def owner_cancel_approved_loan(loan, owner_id):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    if loan.status != "approved":
        raise ConflictError("Only approved loans can be canceled.")

    loan.status = "canceled"
    loan.item.available = True

    message = Message(
        sender_id=owner_id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The loan has been canceled by the owner. The item is now available.",
        loan_request_id=loan.id,
    )
    db.session.add(message)
    return _commit_and_notify(
        message,
        f"Failed to send email notification for owner loan cancellation message {message.id}",
    )


def extend_loan(loan, owner_id, new_end_date, owner_message):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to extend this loan.")

    if loan.status not in ["pending", "approved"]:
        raise ConflictError("Only pending or approved loans can be extended.")

    old_end_date = loan.end_date
    loan.end_date = new_end_date
    loan.due_soon_reminder_sent = None
    loan.due_date_reminder_sent = None
    loan.last_overdue_reminder_sent = None
    loan.overdue_reminder_count = 0

    is_extension = new_end_date > old_end_date
    cleaned_message = owner_message.strip() if owner_message else ""
    if cleaned_message:
        if is_extension:
            message_body = (
                f"The loan of '{loan.item.name}' has been extended until "
                f"{new_end_date.strftime('%B %d, %Y')}.\n\n"
                f"Message from owner: {cleaned_message}"
            )
        else:
            message_body = (
                f"The due date for '{loan.item.name}' has been updated to "
                f"{new_end_date.strftime('%B %d, %Y')}.\n\n"
                f"Message from owner: {cleaned_message}"
            )
    elif is_extension:
        message_body = (
            f"Good news! The loan of '{loan.item.name}' has been extended. The new due date "
            f"is {new_end_date.strftime('%B %d, %Y')} (previously {old_end_date.strftime('%B %d, %Y')})."
        )
    else:
        message_body = (
            f"The due date for '{loan.item.name}' has been updated. The new due date is "
            f"{new_end_date.strftime('%B %d, %Y')} (previously {old_end_date.strftime('%B %d, %Y')})."
        )

    message = Message(
        sender_id=owner_id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body=message_body,
        loan_request_id=loan.id,
    )
    db.session.add(message)
    _commit_and_notify(
        message,
        f"Failed to send email notification for loan extension message {message.id}",
    )
    return is_extension
