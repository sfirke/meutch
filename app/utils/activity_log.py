"""Writing rows to the activity log.

``app/utils/`` is where side-effecting infrastructure lives (``email.py``,
``storage.py``, ``geocoding.py``), and keeping the writer here rather than under
``app/services/`` keeps the dependency direction clean: services call this, this
never calls a service.

**Nothing in here may ever break the request that called it.** A caller records an
event as a side effect of an action the user actually asked for, so four layers stand
between a logging failure and that action:

* the row is written on its own short-lived connection, so a failed INSERT aborts
  only itself and never poisons the caller's transaction;
* the whole body sits inside ``except Exception`` -- including actor resolution and
  address parsing, which can raise outside an application context;
* ``statement_timeout`` bounds the write, so a lock held by someone else costs a
  couple of seconds rather than the whole request;
* ``ACTIVITY_LOG_ENABLED`` turns the whole thing off from configuration, with no
  code deploy.

**Call ``log_event`` after the caller has committed.** Writing on a separate
connection means an event can outlive a state change that later rolled back, and a
convention is the mitigation. It is the right trade: under an ambient-session model
the events worth having most -- a failed sign-in against an address that matches no
account, which writes nothing else -- would silently vanish with the rollback.
"""

import ipaddress
import json
import logging
import re

from flask import current_app, g, has_request_context, request

from app import db
from app.models import ActivityLog
from app.utils.activity_events import CONTEXT_KEY_EXEMPTIONS, EVENT_TYPES

logger = logging.getLogger(__name__)

# Bounds on `context`. A value longer than this is a body or a blob rather than an
# explanation, and the whole payload is capped so one bad call site cannot bloat the
# table.
MAX_CONTEXT_VALUE_LENGTH = 200
MAX_CONTEXT_BYTES = 2048

MAX_USER_AGENT_LENGTH = 400
MAX_REQUEST_ID_LENGTH = 64

# How long the audit write is allowed to wait. The write happens after the caller has
# committed, so it should never contend with anything -- this is the backstop for the
# case where it does.
STATEMENT_TIMEOUT = "2s"

# Key words that mean a value carries personal information. Keys are split on
# non-alphanumeric boundaries and matched token by token, so `first_name`,
# `email_address`, `reset_token` and `message_body` are all rejected while
# `user_agent`, `attempt_count` and `retry_after_minutes` pass. Matching whole tokens
# rather than substrings is what lets "lat" reject `latitude` without also rejecting
# `violation` and `translation`.
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

# Sentinel for "work the actor out from the request", so that passing actor=None can
# mean "this event genuinely has no actor" -- which is the case for every sign-in
# attempt, where nobody has proved who they are yet.
_RESOLVE_ACTOR = object()


def _key_tokens(key):
    return _KEY_TOKEN_PATTERN.findall(str(key).lower())


def sanitize_context(event_type, context):
    """Return the subset of *context* that is safe to store.

    The rule in one sentence: `context` holds scalars explaining *why* an event
    happened, and anything identifying *who* or *what* belongs in the actor, subject
    and target columns instead.

    Offending keys are dropped and the row is still written. This never raises: a
    privacy guard that turns a careless dict into a 500 is worse than the dict.
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

        # Scalars only. A nested dict or a list is how a whole model's __dict__ or a
        # raw form payload ends up in the log by accident.
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            logger.warning(
                "dropped activity log context key %r on %s: %s is not a scalar",
                key,
                event_type,
                type(value),
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

    ``flask_login``'s ``current_user`` is safe to touch on an API request -- it just
    reports an anonymous user -- but ``flask_jwt_extended.get_current_user()`` raises
    ``RuntimeError`` outside a ``@jwt_required`` view, so it has to be guarded.
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

    The value ultimately comes from a header, so it is validated before it reaches an
    ``INET`` column -- an unparseable string would otherwise raise ``DataError`` and
    lose the event.
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
            # Still write it. Losing an event because someone forgot to register its
            # name is a worse outcome than an unlabeled row.
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

        # A connection of our own, checked out from the pool and committed here and
        # now. Adding this to db.session instead would defer the INSERT into the
        # caller's next flush, where a bad value would abort the caller's commit at a
        # point no try/except around this call could catch.
        with db.engine.connect() as connection:
            connection.execute(db.text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
            connection.execute(ActivityLog.__table__.insert().values(**values))
            connection.commit()
    except Exception:
        # WARNING rather than ERROR: a dropped audit row is worth noticing but is not
        # a failure of anything the user asked for.
        logger.warning("failed to write activity log event %r", event_type, exc_info=True)


# --- Read helpers -----------------------------------------------------------------

# Substring ladder from a User-Agent string to a browser family, most specific first
# (every Chromium browser also says "Chrome", and Chrome and Safari both say
# "Safari"). This is deliberately crude: the full string is kept in the column and
# shown on hover, and this is only the scannable summary. Werkzeug's own UA parsing
# was removed in 2.x, so request.user_agent.browser is always None here.
_USER_AGENT_FAMILIES = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
    ("curl/", "curl"),
    ("python-requests", "python-requests"),
    ("okhttp", "okhttp"),
    ("Dart/", "Dart"),
)


def user_agent_family(raw_user_agent):
    """Return a short browser or client name for a raw User-Agent string."""
    if not raw_user_agent:
        return None

    for marker, family in _USER_AGENT_FAMILIES:
        if marker in raw_user_agent:
            return family

    return "Other"


def oldest_entry_at():
    """Return the timestamp of the oldest surviving row, or None if the log is empty.

    Used by the admin page to notice that the prune job is not running. Cheap: an
    index-only scan of the first entry in ``ix_activity_log_occurred_at_id``.
    """
    return db.session.query(db.func.min(ActivityLog.occurred_at)).scalar()
