"""Writing rows to the activity log.

Nothing in here may ever break the request that called it: the row is written on its
own connection, the whole body is wrapped in ``except Exception``, a
``statement_timeout`` bounds the write, and ``ACTIVITY_LOG_ENABLED`` turns it off
without a deploy.

Call ``log_event`` after the caller has committed. Writing on a separate connection
means an event can outlive a state change that later rolled back; the alternative
would silently lose the events worth having most, like a failed sign-in that writes
nothing else.
"""

import ipaddress
import json
import logging
import math
import re

from flask import current_app, g, has_request_context, request

from app import db
from app.models import ActivityLog
from app.utils.activity_events import CONTEXT_KEY_EXEMPTIONS, EVENT_TYPES

logger = logging.getLogger(__name__)

# Caps on `context`, so one bad call site cannot bloat the table.
MAX_CONTEXT_VALUE_LENGTH = 200
MAX_CONTEXT_BYTES = 2048

MAX_USER_AGENT_LENGTH = 400
MAX_REQUEST_ID_LENGTH = 64

STATEMENT_TIMEOUT = "2s"

# Key words that mean a value carries personal information. Keys are matched token by
# token rather than by substring, which is what lets "lat" reject `latitude` without
# also rejecting `violation` and `translation`.
DENIED_KEY_TOKENS = frozenset(
    {
        "address",
        "body",
        "city",
        "comment",
        "content",
        "coordinate",
        "coordinates",
        "coords",
        "description",
        "email",
        "lat",
        "latitude",
        "lng",
        "lon",
        "longitude",
        "message",
        "name",
        "note",
        "notes",
        "password",
        "phone",
        "postal",
        "secret",
        "street",
        "subject",
        "text",
        "title",
        "token",
        "zip",
        "zipcode",
    }
)

_KEY_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
# Split camelCase before lowercasing, so `emailAddress` is checked as `email` + `address`
# rather than slipping through as one unknown token. The second branch handles a run of
# capitals: `IPAddress` splits as `IP` + `Address`.
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# Means "work the actor out from the request", leaving actor=None free to mean "this
# event genuinely has no actor" -- the case for every sign-in attempt.
_RESOLVE_ACTOR = object()


def _key_tokens(key):
    return _KEY_TOKEN_PATTERN.findall(_CAMEL_CASE_BOUNDARY.sub("_", str(key)).lower())


def sanitize_context(event_type, context):
    """Return the subset of *context* that is safe to store.

    `context` holds scalars explaining *why* an event happened; anything identifying
    *who* or *what* belongs in the actor, subject and target columns instead.

    Offending keys are dropped and the row is still written. Never raises.
    """
    if not context:
        return None

    if not isinstance(context, dict):
        logger.warning("activity log context for %s was %s, not a dict", event_type, type(context))
        return None

    exempt_keys = CONTEXT_KEY_EXEMPTIONS.get(event_type, frozenset())
    sanitized = {}

    for key, value in context.items():
        if key not in exempt_keys and DENIED_KEY_TOKENS.intersection(_key_tokens(key)):
            logger.warning("dropped activity log context key %r on %s", key, event_type)
            continue

        # Scalars only: a nested dict or list is how a whole model's __dict__ or a raw
        # form payload ends up in the log by accident.
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            logger.warning(
                "dropped activity log context key %r on %s: %s is not a scalar",
                key,
                event_type,
                type(value),
            )
            continue

        # JSON has no NaN or Infinity, so Postgres would reject the whole row.
        if isinstance(value, float) and not math.isfinite(value):
            logger.warning(
                "dropped activity log context key %r on %s: %r is not finite",
                key,
                event_type,
                value,
            )
            continue

        if isinstance(value, str) and len(value) > MAX_CONTEXT_VALUE_LENGTH:
            value = value[:MAX_CONTEXT_VALUE_LENGTH]

        sanitized[key] = value

    if not sanitized:
        return None

    if len(json.dumps(sanitized, default=str).encode("utf-8")) > MAX_CONTEXT_BYTES:
        logger.warning("dropped oversized activity log context on %s", event_type)
        return None

    return sanitized


def _coerce_user_id(value):
    """Accept either a User (or anything with an id) or a bare id."""
    if value is None:
        return None
    return getattr(value, "id", value)


def _resolve_actor_id():
    """Work out who is acting, preferring the session over the token.

    ``flask_jwt_extended.get_current_user()`` raises ``RuntimeError`` outside a
    ``@jwt_required`` view, so it has to be guarded.
    """
    if not has_request_context():
        return None

    try:
        from flask_login import current_user

        if current_user is not None and current_user.is_authenticated:
            return current_user.id
    except Exception:  # pragma: no cover - defensive, login manager not initialized
        pass

    try:
        from flask_jwt_extended import get_current_user

        jwt_user = get_current_user()
        if jwt_user is not None:
            return jwt_user.id
    except Exception:
        pass

    return None


def _detect_source():
    if not has_request_context():
        return ActivityLog.SOURCE_CLI

    from app.api.v1.errors import is_api_request_path

    if is_api_request_path(request.path):
        return ActivityLog.SOURCE_API

    return ActivityLog.SOURCE_WEB


def _client_ip():
    """Return the caller's address, or None if it is missing or unparseable.

    The value comes from a header, so it is validated before it reaches an ``INET``
    column: an unparseable string would raise ``DataError`` and lose the event.
    """
    if not has_request_context():
        return None

    raw_address = request.remote_addr
    if not raw_address:
        return None

    try:
        return str(ipaddress.ip_address(raw_address))
    except ValueError:
        logger.warning("activity log could not parse remote address %r", raw_address)
        return None


def _user_agent():
    if not has_request_context():
        return None

    raw_user_agent = request.headers.get("User-Agent")
    if not raw_user_agent:
        return None

    return raw_user_agent[:MAX_USER_AGENT_LENGTH]


def _request_id():
    """Reuse the API's per-request id when there is one."""
    if not has_request_context():
        return None

    request_id = getattr(g, "api_request_id", None)
    if not request_id:
        return None

    return str(request_id)[:MAX_REQUEST_ID_LENGTH]


def log_event(
    event_type,
    *,
    actor=_RESOLVE_ACTOR,
    subject=None,
    target_type=None,
    target_id=None,
    context=None,
):
    """Record one activity-log row. Never raises.

    Args:
        event_type: a constant from ``app.utils.activity_events``.
        actor: the User who did it. Omit to resolve it from the request; pass None
            explicitly for an event where nobody has been authenticated.
        subject: the User the event is *about*, when that differs from the actor.
        target_type, target_id: the non-user object the event is about, if any.
        context: flat scalars explaining why the event happened. See
            ``sanitize_context`` for what is allowed through.
    """
    try:
        if not current_app.config.get("ACTIVITY_LOG_ENABLED", True):
            return

        if event_type not in EVENT_TYPES:
            # Still write it -- an unlabeled row beats a lost event.
            logger.warning("unregistered activity log event type %r", event_type)

        actor_user_id = _resolve_actor_id() if actor is _RESOLVE_ACTOR else _coerce_user_id(actor)

        values = {
            "event_type": event_type,
            "source": _detect_source(),
            "actor_user_id": actor_user_id,
            "subject_user_id": _coerce_user_id(subject),
            "target_type": target_type,
            "target_id": target_id,
            "ip_address": _client_ip(),
            "user_agent": _user_agent(),
            "request_id": _request_id(),
            "context": sanitize_context(event_type, context),
        }

        # Our own connection, committed here and now. Going through db.session would
        # defer the INSERT to the caller's next flush, where a bad value would abort the
        # caller's commit somewhere no try/except around this call could catch it.
        with db.engine.connect() as connection:
            connection.execute(db.text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
            connection.execute(ActivityLog.__table__.insert().values(**values))
            connection.commit()
    except Exception:
        # WARNING, not ERROR: a dropped audit row is worth noticing but nothing the user
        # asked for has failed.
        logger.warning("failed to write activity log event %r", event_type, exc_info=True)
