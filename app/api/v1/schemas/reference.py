"""Reference-data API schemas."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiSchema


class CategorySchema(ApiSchema):
    """Category reference data for read-side endpoints."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)


class TagSchema(ApiSchema):
    """Tag reference data for item reads and filters."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
