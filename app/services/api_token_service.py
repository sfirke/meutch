"""JWT session management for API authentication."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from app import db
from app.models import ApiTokenBlocklist, ApiTokenFamily, User
from app.services import auth_service
from app.services.exceptions import AuthenticationError, AuthorizationError, ConflictError

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

REVOKE_REASON_LOGOUT = "logout"
REVOKE_REASON_ROTATED = "refresh_rotated"
REVOKE_REASON_REUSED = "refresh_reused"


@dataclass
class TokenBundle:
    """Issued API tokens for a single authenticated session."""

    user: User
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


def _timestamp_to_utc(timestamp):
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _parse_family_id(token_payload):
    family_id = token_payload.get("family_id")
    if not family_id:
        return None

    try:
        return UUID(family_id)
    except ValueError:
        return None


def _get_token_family(token_payload):
    family_id = _parse_family_id(token_payload)
    if family_id is None:
        return None

    return db.session.get(ApiTokenFamily, family_id)


def _get_user_id(token_payload):
    try:
        return UUID(token_payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("The supplied token is invalid.") from exc


def _add_blocklist_entry(token_payload, *, reason):
    existing_entry = ApiTokenBlocklist.query.filter_by(jti=token_payload["jti"]).first()
    if existing_entry is not None:
        return existing_entry

    family_id = _parse_family_id(token_payload)
    blocked_token = ApiTokenBlocklist(
        jti=token_payload["jti"],
        user_id=_get_user_id(token_payload),
        family_id=family_id,
        token_type=token_payload["type"],
        expires_at=_timestamp_to_utc(token_payload["exp"]),
        reason=reason,
    )
    db.session.add(blocked_token)
    return blocked_token


def _build_tokens_for_family(user, family_id):
    claims = {"family_id": str(family_id)}
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)
    access_token_payload = decode_token(access_token)
    refresh_token_payload = decode_token(refresh_token)
    return access_token, refresh_token, access_token_payload, refresh_token_payload


def issue_token_bundle(user):
    """Create a new JWT session for a confirmed user."""
    family_id = uuid.uuid4()
    access_token, refresh_token, access_payload, refresh_payload = _build_tokens_for_family(
        user, family_id
    )

    token_family = ApiTokenFamily(
        id=family_id,
        user_id=user.id,
        current_refresh_jti=refresh_payload["jti"],
        current_refresh_expires_at=_timestamp_to_utc(refresh_payload["exp"]),
    )
    db.session.add(token_family)
    db.session.commit()

    return TokenBundle(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=_timestamp_to_utc(access_payload["exp"]),
        refresh_token_expires_at=_timestamp_to_utc(refresh_payload["exp"]),
    )


def issue_login_tokens(email, password):
    """Authenticate API credentials and start a JWT session."""
    authentication_result = auth_service.authenticate_user(email, password)

    if authentication_result.status == auth_service.LOGIN_STATUS_INVALID_CREDENTIALS:
        raise AuthenticationError("Invalid email or password.")

    if authentication_result.status == auth_service.LOGIN_STATUS_UNCONFIRMED:
        raise AuthorizationError("Please confirm your email address before logging in.")

    return issue_token_bundle(authentication_result.user)


def rotate_refresh_token(user, refresh_token_payload):
    """Rotate a refresh token and issue a fresh access/refresh pair."""
    token_family = _get_token_family(refresh_token_payload)
    if token_family is None or token_family.revoked_at is not None:
        raise AuthenticationError("The supplied token is invalid.")

    _add_blocklist_entry(refresh_token_payload, reason=REVOKE_REASON_ROTATED)
    access_token, refresh_token, access_payload, new_refresh_payload = _build_tokens_for_family(
        user, token_family.id
    )
    token_family.current_refresh_jti = new_refresh_payload["jti"]
    token_family.current_refresh_expires_at = _timestamp_to_utc(new_refresh_payload["exp"])
    db.session.commit()

    return TokenBundle(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=_timestamp_to_utc(access_payload["exp"]),
        refresh_token_expires_at=_timestamp_to_utc(new_refresh_payload["exp"]),
    )


def revoke_token_family(token_payload, *, reason=REVOKE_REASON_LOGOUT):
    """Revoke the current token and its session family."""
    token_family = _get_token_family(token_payload)
    if token_family is not None:
        token_family.revoke(reason)

    _add_blocklist_entry(token_payload, reason=reason)
    db.session.commit()


def is_token_revoked(token_payload):
    """Return True when a JWT should no longer be honored."""
    blocked_token = ApiTokenBlocklist.query.filter_by(jti=token_payload["jti"]).first()
    token_family = _get_token_family(token_payload)

    if blocked_token is not None:
        if token_payload["type"] == TOKEN_TYPE_REFRESH and token_family is not None:
            token_family.revoke(REVOKE_REASON_REUSED)
            db.session.commit()
        return True

    if token_family is None:
        return True

    if token_family.revoked_at is not None:
        return True

    if (
        token_payload["type"] == TOKEN_TYPE_REFRESH
        and token_payload["jti"] != token_family.current_refresh_jti
    ):
        token_family.revoke(REVOKE_REASON_REUSED)
        db.session.commit()
        return True

    return False


def register_api_user(**user_data):
    """Register a new API user while preserving web-auth workflow behavior."""
    existing_user = User.query.filter(
        db.func.lower(User.email) == db.func.lower(user_data["email"])
    ).first()
    if existing_user is not None:
        raise ConflictError("This email is already registered.")

    return auth_service.register_user(**user_data)
