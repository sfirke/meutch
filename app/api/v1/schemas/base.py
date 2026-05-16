"""Shared Marshmallow schema primitives for the API."""

from marshmallow import Schema, fields


class ApiSchema(Schema):
    """Base schema for API response serialization."""


class ApiDateTime(fields.DateTime):
    """Datetime field that always emits ISO 8601 strings."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("format", "iso")
        super().__init__(*args, **kwargs)
