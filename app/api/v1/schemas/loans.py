"""Loan read and write schemas for API v1."""

from datetime import date

from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import ApiDateTime, ApiSchema
from app.api.v1.schemas.messaging import MessageSummarySchema
from app.api.v1.schemas.users import UserSummarySchema

_USER_SUMMARY_SCHEMA = UserSummarySchema()


class LoanActivityItemSchema(ApiSchema):
    """Item context included in loan activity reads."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    available = fields.Boolean(required=True)
    image_url = fields.Method("get_image_url", allow_none=True)

    def get_image_url(self, item):
        if not item.images:
            return None

        return item.images[0].url


class LoanActivitySummarySchema(ApiSchema):
    """Compact loan representation for activity lists."""

    id = fields.UUID(required=True)
    status = fields.String(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    item = fields.Nested(LoanActivityItemSchema(), required=True)
    owner = fields.Method("get_owner")
    borrower = fields.Nested(UserSummarySchema(), allow_none=True)
    latest_conversation_message_id = fields.Method(
        "get_latest_conversation_message_id",
        allow_none=True,
    )
    due_state = fields.Method("get_due_state")
    days_until_due = fields.Method("get_days_until_due")
    days_overdue = fields.Method("get_days_overdue")

    def get_latest_conversation_message_id(self, loan):
        return loan.api_latest_conversation_message_id

    def get_due_state(self, loan):
        return loan.due_state

    def get_days_until_due(self, loan):
        if loan.status != "approved":
            return None
        days = loan.days_until_due()
        return max(days, 0) if not loan.is_overdue() else None

    def get_days_overdue(self, loan):
        if loan.status != "approved":
            return None
        return loan.days_overdue()

    def get_owner(self, loan):
        return _USER_SUMMARY_SCHEMA.dump(loan.item.owner)


class LoanDetailSchema(LoanActivitySummarySchema):
    """Expanded loan representation for detail and mutation responses."""

    created_at = ApiDateTime(required=True)


class LoanDetailResponseSchema(ApiSchema):
    """Wrapper for loan detail reads."""

    loan = fields.Nested(LoanDetailSchema(), required=True)


class LoanMutationResponseSchema(ApiSchema):
    """Wrapper for loan mutations that emit a follow-up message."""

    loan = fields.Nested(LoanDetailSchema(), required=True)
    message = fields.Nested(MessageSummarySchema(), required=True)


class LoanExtendResponseSchema(LoanMutationResponseSchema):
    """Wrapper for loan due-date mutations."""

    is_extension = fields.Boolean(required=True)


class LoanRequestCreateSchema(ApiSchema):
    """Write payload for creating a loan request on an item."""

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    message = fields.String(required=True, validate=validate.Length(min=10, max=1000))

    @validates_schema
    def validate_date_order(self, data, **kwargs):
        if data["end_date"] < data["start_date"]:
            raise ValidationError({"end_date": ["End date must be on or after the start date."]})


class LoanExtendSchema(ApiSchema):
    """Write payload for updating a loan due date."""

    new_end_date = fields.Date(required=True)
    message = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=1000),
    )

    @validates_schema
    def validate_new_end_date(self, data, **kwargs):
        if "new_end_date" in data and data["new_end_date"] < date.today():
            raise ValidationError({"new_end_date": ["New end date cannot be in the past."]})
