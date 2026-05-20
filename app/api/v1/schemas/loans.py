"""Loan write schemas for API v1."""

from marshmallow import ValidationError, fields, validate, validates_schema

from app.api.v1.schemas.base import ApiSchema


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
