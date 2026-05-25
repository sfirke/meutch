"""Loan read and write endpoints for API v1."""

from flask_jwt_extended import jwt_required
from sqlalchemy.orm import selectinload

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.loans import (
    LoanActivitySummarySchema,
    LoanDetailResponseSchema,
    LoanExtendResponseSchema,
    LoanExtendSchema,
    LoanMutationResponseSchema,
    LoanRequestCreateSchema,
)
from app.api.v1.schemas.query import LoanListQuerySchema
from app.models import Item, LoanRequest
from app.services import loan_service
from app.services.exceptions import AuthorizationError
from app.utils.item_visibility import build_item_access_state

LOAN_LIST_QUERY_SCHEMA = LoanListQuerySchema()
LOAN_ACTIVITY_SUMMARY_SCHEMA = LoanActivitySummarySchema(many=True)
LOAN_DETAIL_RESPONSE_SCHEMA = LoanDetailResponseSchema()
LOAN_MUTATION_RESPONSE_SCHEMA = LoanMutationResponseSchema()
LOAN_EXTEND_RESPONSE_SCHEMA = LoanExtendResponseSchema()
LOAN_REQUEST_CREATE_SCHEMA = LoanRequestCreateSchema()
LOAN_EXTEND_SCHEMA = LoanExtendSchema()


def _base_loan_query():
    return LoanRequest.query.options(
        selectinload(LoanRequest.borrower),
        selectinload(LoanRequest.item).selectinload(Item.owner),
        selectinload(LoanRequest.item).selectinload(Item.images),
        selectinload(LoanRequest.messages),
    )


def _annotate_latest_conversation_message_id(loan):
    latest_message = None
    if loan.messages:
        latest_message = max(loan.messages, key=lambda message: message.timestamp)

    loan.api_latest_conversation_message_id = latest_message.id if latest_message else None
    return loan


def _serialize_loan_detail(loan):
    return LOAN_DETAIL_RESPONSE_SCHEMA.dump(
        {"loan": _annotate_latest_conversation_message_id(loan)}
    )


def _serialize_loan_mutation(loan, message):
    loan.api_latest_conversation_message_id = message.id
    return LOAN_MUTATION_RESPONSE_SCHEMA.dump({"loan": loan, "message": message})


def _ensure_loan_participant(loan):
    if current_user.id not in {loan.borrower_id, loan.item.owner_id}:
        raise AuthorizationError("You are not allowed to view this loan.")


def _ensure_item_is_requestable(item):
    access_state = build_item_access_state(item, current_user)
    if not access_state["can_view"]:
        raise AuthorizationError("You are not allowed to request this item.")


@bp.get("/me/loans")
@jwt_required()
def list_my_loans():
    """Return paginated active borrowing or lending entries for the authenticated user."""
    query_data = load_query_data(LOAN_LIST_QUERY_SCHEMA)
    loans_query = _base_loan_query().join(Item).filter(LoanRequest.status == "approved")

    if query_data["role"] == "borrowing":
        loans_query = loans_query.filter(LoanRequest.borrower_id == current_user.id)
    else:
        loans_query = loans_query.filter(Item.owner_id == current_user.id)

    pagination = loans_query.order_by(LoanRequest.end_date.asc()).paginate(
        page=query_data["page"],
        per_page=query_data["per_page"],
        error_out=False,
    )

    for loan in pagination.items:
        _annotate_latest_conversation_message_id(loan)

    return build_collection_response(
        "loans",
        LOAN_ACTIVITY_SUMMARY_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )


@bp.get("/loans/<uuid:loan_id>")
@jwt_required()
def get_loan(loan_id):
    """Return loan details for the borrower or the item owner."""
    loan = _base_loan_query().filter(LoanRequest.id == loan_id).first_or_404()
    _ensure_loan_participant(loan)
    return _serialize_loan_detail(loan)


@bp.post("/items/<uuid:item_id>/loan-requests")
@jwt_required()
def create_loan_request(item_id):
    """Create a pending loan request for an item the user can access."""
    item = db.get_or_404(Item, item_id)
    _ensure_item_is_requestable(item)
    data = load_request_data(LOAN_REQUEST_CREATE_SCHEMA)
    message = loan_service.create_loan_request(
        item,
        current_user.id,
        data["start_date"],
        data["end_date"],
        data["message"],
    )
    return _serialize_loan_mutation(message.loan_request, message), 201


@bp.post("/loans/<uuid:loan_id>/approve")
@jwt_required()
def approve_loan(loan_id):
    """Approve a pending loan request as the item owner."""
    loan = db.get_or_404(LoanRequest, loan_id)
    message = loan_service.process_loan_decision(loan, current_user.id, "approve")
    return _serialize_loan_mutation(loan, message)


@bp.post("/loans/<uuid:loan_id>/deny")
@jwt_required()
def deny_loan(loan_id):
    """Deny a pending loan request as the item owner."""
    loan = db.get_or_404(LoanRequest, loan_id)
    message = loan_service.process_loan_decision(loan, current_user.id, "deny")
    return _serialize_loan_mutation(loan, message)


@bp.post("/loans/<uuid:loan_id>/cancel")
@jwt_required()
def cancel_loan(loan_id):
    """Cancel a pending loan request as the borrower."""
    loan = db.get_or_404(LoanRequest, loan_id)
    message = loan_service.cancel_loan_request(loan, current_user.id)
    return _serialize_loan_mutation(loan, message)


@bp.post("/loans/<uuid:loan_id>/owner-cancel")
@jwt_required()
def owner_cancel_loan(loan_id):
    """Cancel an approved loan as the item owner."""
    loan = db.get_or_404(LoanRequest, loan_id)
    message = loan_service.owner_cancel_approved_loan(loan, current_user.id)
    return _serialize_loan_mutation(loan, message)


@bp.post("/loans/<uuid:loan_id>/complete")
@jwt_required()
def complete_loan(loan_id):
    """Mark an approved loan complete as the item owner."""
    loan = db.get_or_404(LoanRequest, loan_id)
    message = loan_service.complete_loan(loan, current_user.id)
    return _serialize_loan_mutation(loan, message)


@bp.post("/loans/<uuid:loan_id>/extend")
@jwt_required()
def extend_loan(loan_id):
    """Update the due date for a pending or approved loan as the item owner."""
    loan = db.get_or_404(LoanRequest, loan_id)
    data = load_request_data(LOAN_EXTEND_SCHEMA)
    extend_result = loan_service.extend_loan(
        loan,
        current_user.id,
        data["new_end_date"],
        data["message"],
    )
    loan.api_latest_conversation_message_id = extend_result.message.id
    return LOAN_EXTEND_RESPONSE_SCHEMA.dump(
        {
            "loan": loan,
            "message": extend_result.message,
            "is_extension": extend_result.is_extension,
        }
    )
