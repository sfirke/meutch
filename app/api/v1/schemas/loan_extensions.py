"""Loan extension-request read schema shared by the loan and messaging schemas."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiDateTime, ApiSchema


class LoanExtensionRequestSchema(ApiSchema):
    """Borrower request to move a loan's due date, with the owner's decision state."""

    id = fields.UUID(required=True)
    status = fields.String(required=True)
    previous_end_date = fields.Date(required=True)
    proposed_end_date = fields.Date(required=True)
    message = fields.String(required=True)
    created_at = ApiDateTime(required=True)
    responded_at = ApiDateTime(allow_none=True)
