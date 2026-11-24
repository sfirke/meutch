"""Announcement schemas for API v1."""

from marshmallow import fields

from app.api.v1.schemas.base import ApiSchema


class AnnouncementSchema(ApiSchema):
    """A site-wide announcement, as the web banner shows it."""

    id = fields.UUID(required=True)
    message = fields.String(required=True)
    link_url = fields.String(allow_none=True)
    link_text = fields.String(allow_none=True)
    level = fields.String(required=True)
    dismissible = fields.Boolean(required=True)


class CurrentAnnouncementResponseSchema(ApiSchema):
    """The announcement to show the caller, or null when there is none."""

    announcement = fields.Nested(AnnouncementSchema, allow_none=True, required=True)


class AnnouncementDismissResponseSchema(ApiSchema):
    """Response after dismissing an announcement."""

    dismissed = fields.Boolean(required=True)
