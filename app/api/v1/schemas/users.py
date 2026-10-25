"""User-focused API schemas."""

from collections.abc import Mapping

from marshmallow import fields
from marshmallow.experimental.context import Context

from app.api.v1.schemas.base import ApiSchema

VIEWABLE_USER_IDS_CONTEXT_KEY = "viewable_user_ids"


def _normalize_user_id(value):
    return str(value).lower() if value is not None else None


class UserSummaryFieldsSchema(ApiSchema):
    """Shared public user fields."""

    id = fields.UUID(required=True)
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    full_name = fields.String(required=True)
    profile_image_url = fields.String(allow_none=True)


class UserSummarySchema(UserSummaryFieldsSchema):
    """Minimal user shape for nested read-side resources."""

    profile_viewable = fields.Method("get_profile_viewable", dump_only=True)

    def get_profile_viewable(self, obj):
        """True only when the request context marks this user's profile as viewable."""
        viewable_ids = Context.get(default={}).get(VIEWABLE_USER_IDS_CONTEXT_KEY, ())
        if not viewable_ids:
            return False

        user_id = obj.get("id") if isinstance(obj, Mapping) else getattr(obj, "id", None)
        user_id = _normalize_user_id(user_id)
        if user_id is None:
            return False

        return user_id in {_normalize_user_id(viewable_id) for viewable_id in viewable_ids}


class UserIdentitySchema(UserSummaryFieldsSchema):
    """Authenticated user identity exposed by auth endpoints."""

    email = fields.Email(required=True)
    email_confirmed = fields.Boolean(required=True)
