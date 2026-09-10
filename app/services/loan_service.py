import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import LoanExtensionRequest, LoanRequest, Message
from app.services import message_service
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.messaging_queries import get_or_create_conversation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoanExtendResult:
    """Result payload for loan due-date mutations."""

    message: Message
    is_extension: bool


@dataclass(frozen=True)
class LoanExtensionDecisionResult:
    """Result payload for a borrower extension request decision."""

    message: Message
    approved: bool


def _reset_loan_reminders(loan):
    """Clear reminder bookkeeping after the due date moves."""
    loan.due_soon_reminder_sent = None
    loan.due_date_reminder_sent = None
    loan.last_overdue_reminder_sent = None
    loan.overdue_reminder_count = 0


def _ensure_item_is_lendable(item):
    if item.is_giveaway:
        raise ConflictError("This item is being offered as a giveaway, not a loan.")


def _ensure_item_conversation(item, user1_id, user2_id):
    """Get or create the item conversation between two users."""
    return get_or_create_conversation("item", item.id, user1_id, user2_id)


def create_loan_request(item, borrower_id, start_date, end_date, message_body):
    if item.owner_id == borrower_id:
        raise ConflictError("You cannot request your own items.")

    _ensure_item_is_lendable(item)

    if not item.available:
        raise ConflictError("This item is not currently available to borrow.")

    existing_request = LoanRequest.query.filter_by(
        item_id=item.id,
        borrower_id=borrower_id,
        status="pending",
    ).first()
    if existing_request:
        raise InformationalError("You already have a pending request for this item.")

    conversation = _ensure_item_conversation(item, borrower_id, item.owner_id)
    loan_request = LoanRequest(
        item_id=item.id,
        borrower_id=borrower_id,
        start_date=start_date,
        end_date=end_date,
        status="pending",
    )
    db.session.add(loan_request)
    db.session.flush()  # get loan_request.id for the FK on Message

    return message_service.create_message(
        borrower_id,
        item.owner_id,
        message_body,
        conversation_id=conversation.id,
        loan_request_id=loan_request.id,
    )


def process_loan_decision(loan, owner_id, action):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    _ensure_item_is_lendable(loan.item)

    normalized_action = action.lower()
    if normalized_action not in {"approve", "deny"}:
        raise InvalidActionError("Invalid action.")

    if loan.status != "pending":
        raise ConflictError("This loan request has already been processed.")

    conversation = _ensure_item_conversation(loan.item, owner_id, loan.borrower_id)

    if normalized_action == "approve":
        loan.status = "approved"
        loan.item.available = False
        message_body = f"The loan request for '{loan.item.name}' has been approved."
    else:
        loan.status = "denied"
        message_body = f"The loan request for '{loan.item.name}' has been denied."

    return message_service.create_message(
        owner_id,
        loan.borrower_id,
        message_body,
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )


def cancel_loan_request(loan, borrower_id):
    if loan.borrower_id != borrower_id:
        raise AuthorizationError("You are not authorized to cancel this request.")

    _ensure_item_is_lendable(loan.item)

    if loan.status != "pending":
        raise ConflictError("This loan request cannot be canceled.")

    conversation = _ensure_item_conversation(loan.item, borrower_id, loan.item.owner_id)
    loan.status = "canceled"

    return message_service.create_message(
        borrower_id,
        loan.item.owner_id,
        "Loan request has been canceled by the borrower.",
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )


def complete_loan(loan, owner_id):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    _ensure_item_is_lendable(loan.item)

    if loan.status != "approved":
        raise ConflictError("This loan is not currently active.")

    conversation = _ensure_item_conversation(loan.item, owner_id, loan.borrower_id)
    loan.status = "completed"
    loan.item.available = True

    return message_service.create_message(
        owner_id,
        loan.borrower_id,
        "The item has been marked as returned. Thank you for borrowing!",
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )


def owner_cancel_approved_loan(loan, owner_id):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to perform this action.")

    _ensure_item_is_lendable(loan.item)

    if loan.status != "approved":
        raise ConflictError("Only approved loans can be canceled.")

    conversation = _ensure_item_conversation(loan.item, owner_id, loan.borrower_id)
    loan.status = "canceled"
    loan.item.available = True

    return message_service.create_message(
        owner_id,
        loan.borrower_id,
        "The loan has been canceled by the owner. The item is now available.",
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )


def extend_loan(loan, owner_id, new_end_date, owner_message):
    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to extend this loan.")

    _ensure_item_is_lendable(loan.item)

    if loan.status not in ["pending", "approved"]:
        raise ConflictError("Only pending or approved loans can be extended.")

    old_end_date = loan.end_date
    loan.end_date = new_end_date
    _reset_loan_reminders(loan)

    # A pending borrower request that asked for this much time or less is now
    # satisfied.  Leaving it pending would block the borrower from asking again
    # while its Approve button fails as stale.
    pending_request = loan.pending_extension_request
    if pending_request and pending_request.proposed_end_date <= new_end_date:
        pending_request.status = "approved"
        pending_request.responded_at = datetime.now(UTC)

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

    conversation = _ensure_item_conversation(loan.item, owner_id, loan.borrower_id)

    message = message_service.create_message(
        owner_id,
        loan.borrower_id,
        message_body,
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )
    return LoanExtendResult(message=message, is_extension=is_extension)


def request_extension(loan, borrower_id, proposed_end_date, borrower_message):
    if loan.borrower_id != borrower_id:
        raise AuthorizationError("You are not authorized to request an extension for this loan.")

    if loan.status != "approved":
        raise ConflictError("Only approved loans can have extension requests.")

    if loan.has_pending_extension:
        raise ConflictError("You already have a pending extension request for this loan.")

    if proposed_end_date <= loan.end_date:
        raise ConflictError("Proposed due date must be after the current due date.")

    cleaned_message = borrower_message.strip() if borrower_message else ""

    # get_or_create_conversation commits when it has to create the thread, so
    # settle that before the extension row is added.  Otherwise a pending row
    # could be committed on its own and the message that follows it lost.
    owner_id = loan.item.owner_id
    conversation = _ensure_item_conversation(loan.item, borrower_id, owner_id)

    db.session.add(
        LoanExtensionRequest(
            loan_request_id=loan.id,
            proposed_end_date=proposed_end_date,
            message=cleaned_message,
            status="pending",
        )
    )

    # The has_pending_extension check above can be passed by two simultaneous
    # submissions, so let the partial unique index settle the race before any
    # message is created.  The loser gets the same answer as the early check.
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError("You already have a pending extension request for this loan.")

    message_body = (
        f"Extension requested for '{loan.item.name}'.\n"
        f"Current due date: {loan.end_date.strftime('%B %d, %Y')}\n"
        f"Proposed new due date: {proposed_end_date.strftime('%B %d, %Y')}"
    )
    if cleaned_message:
        message_body += f"\n\nMessage from borrower: {cleaned_message}"

    return message_service.create_message(
        borrower_id,
        owner_id,
        message_body,
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )


def process_extension_request(extension_request, owner_id, action):
    loan = extension_request.loan_request

    if loan.item.owner_id != owner_id:
        raise AuthorizationError("You are not authorized to process this extension request.")

    if action not in ["approve", "deny"]:
        raise InvalidActionError("Invalid action.")

    if loan.status != "approved":
        raise ConflictError("Only active loans can be extended.")

    if extension_request.status != "pending":
        raise ConflictError("This extension request has already been processed.")

    approving = action == "approve"

    # The due date can move between the request and the decision - the owner may
    # have used "Extend Loan Period" in the meantime - and approving a stale
    # request would pull the due date back in.
    if approving and extension_request.proposed_end_date <= loan.end_date:
        raise ConflictError(
            "The proposed due date is no longer later than the current due date. "
            "Ask the borrower to send a new request."
        )

    extension_request.status = "approved" if approving else "denied"
    extension_request.responded_at = datetime.now(UTC)

    if approving:
        old_end_date = loan.end_date
        loan.end_date = extension_request.proposed_end_date
        _reset_loan_reminders(loan)
        message_body = (
            f"Your extension request for '{loan.item.name}' has been approved. "
            f"The due date has been updated from {old_end_date.strftime('%B %d, %Y')} "
            f"to {loan.end_date.strftime('%B %d, %Y')}."
        )
    else:
        message_body = (
            f"Your extension request for '{loan.item.name}' was denied. "
            f"The current due date remains {loan.end_date.strftime('%B %d, %Y')}."
        )

    conversation = _ensure_item_conversation(loan.item, owner_id, loan.borrower_id)

    message = message_service.create_message(
        owner_id,
        loan.borrower_id,
        message_body,
        conversation_id=conversation.id,
        loan_request_id=loan.id,
    )
    return LoanExtensionDecisionResult(message=message, approved=approving)
