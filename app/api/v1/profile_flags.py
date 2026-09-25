"""Dump helpers that mark nested users whose profiles the API viewer may open."""

from marshmallow.experimental.context import Context

from app.api.v1.jwt_auth import current_user
from app.api.v1.schemas.users import VIEWABLE_USER_IDS_CONTEXT_KEY
from app.utils.profile_visibility import viewable_profile_user_ids


def dump_with_viewable_profiles(schema, obj, candidate_ids, *, many=None):
    """Dump obj with schema, marking profile_viewable for viewable candidate_ids."""
    candidates = {user_id for user_id in candidate_ids if user_id is not None}
    ids = viewable_profile_user_ids(current_user, candidates) if candidates else set()
    with Context({VIEWABLE_USER_IDS_CONTEXT_KEY: ids}):
        return schema.dump(obj, many=many)
