# app/template_filters.py
"""Custom Jinja2 template filters for the Meutch application."""

import re

from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup, escape

# ---------------------------------------------------------------------------
# Pre-compiled URL regex for linkify filter (module level for performance).
# ReDoS-safe: uses [^\s<>...] (explicit char class) rather than .* to avoid
# catastrophic backtracking. No nested quantifiers.
# ---------------------------------------------------------------------------
_URL_RE = re.compile(
    # Protocol URLs: stop at whitespace, angle brackets, quotes, brackets,
    # guillemets, or HTML entities (except &amp; which is a real & in URLs).
    r"(https?://"
    r'(?:[^\s<>"\'\[\]«»&]'  # normal URL chars
    r"|&(?!lt;|gt;|quot;|#39;))+"  # allow &amp; but stop at other entities
    r")"
    r"|"
    # www. URLs (no protocol)
    r"(www\.[a-zA-Z0-9][-a-zA-Z0-9]*\."
    r"[a-zA-Z]{2,}"  # TLD
    r"(?::\d+)?"  # optional :port
    r'(?:/(?:[^\s<>"\'\[\]«»&]|&(?!lt;|gt;|quot;|#39;))*)?)',  # optional /path
    re.IGNORECASE,
)

# Set of trailing punctuation characters to trim from URL endings.
# ')' is excluded from this set — it is handled separately in _replace_url
# to preserve balanced parentheses (e.g. Wikipedia URLs).
_TRAILING_PUNCT_CHARS = frozenset(".,;:!?\"'»]")


def utc_timestamp(value, format="datetime"):
    """
    Convert a datetime object to a span element with data attributes for
    client-side timezone conversion.

    Usage in templates:
        {{ some_datetime|utc_timestamp }}
        {{ some_datetime|utc_timestamp('short-datetime') }}
        {{ some_datetime|utc_timestamp('date') }}

    Available formats:
        - datetime: "January 24, 2026 at 09:05 PM EST" (default)
        - short-datetime: "Jan 24, 09:05 PM EST"
        - date: "January 24, 2026"
        - short-date: "Jan 24, 2026"
        - time: "09:05 PM EST"
        - compact: "2026-01-24 21:05 EST"
        - message: "Jan 24, 21:05"

    Args:
        value: A datetime object (should be in UTC)
        format: The display format to use

    Returns:
        A Markup object containing a span with data attributes
    """
    if value is None:
        return ""

    # Convert to ISO format for JavaScript parsing
    # If the datetime is naive (no timezone), we assume it's UTC
    iso_timestamp = value.isoformat()

    # Fallback text in case JavaScript doesn't run
    # Use a simple format that works server-side
    try:
        if format in ("date", "short-date"):
            fallback = value.strftime("%B %d, %Y")
        elif format == "time":
            fallback = value.strftime("%I:%M %p UTC")
        elif format == "message":
            fallback = value.strftime("%b %d, %H:%M")
        elif format == "compact":
            fallback = value.strftime("%Y-%m-%d %H:%M UTC")
        elif format == "short-datetime":
            fallback = value.strftime("%b %d, %I:%M %p UTC")
        elif format == "timeago":
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            # If value is naive, assume UTC but make it aware for comparison
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            delta = now - value
            if delta.total_seconds() < 60:
                fallback = "just now"
            elif delta.total_seconds() < 3600:
                mins = int(delta.total_seconds() / 60)
                fallback = f"{mins} minute{'s' if mins > 1 else ''} ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                fallback = f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif delta.total_seconds() < 604800:
                days = int(delta.total_seconds() / 86400)
                fallback = f"{days} day{'s' if days > 1 else ''} ago"
            else:
                fallback = value.strftime("%b %d, %Y")
        else:
            fallback = value.strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception:
        fallback = str(value)

    return Markup(
        f'<span data-utc-timestamp="{iso_timestamp}" data-format="{format}">{fallback}</span>'
    )


def tojson_images(images):
    """Serialize a list of ItemImage objects to JSON for the multi-image upload component."""
    return Markup(htmlsafe_json_dumps([{"id": str(img.id), "url": img.url} for img in images]))


def linkify(text):
    """Convert plain text to safe HTML with clickable URLs and line breaks.

    HTML-escapes the input (XSS prevention), converts newlines to ``<br>``,
    and wraps http/https/www URLs in ``<a>`` tags with security attributes
    (``target="_blank" rel="noopener noreferrer"``).

    For ``www.`` URLs without a protocol, ``https://`` is prepended
    automatically.

    Returns a ``Markup`` object so Jinja2 does not re-escape the generated
    HTML.

    Args:
        text: Plain text string, or ``None`` / empty (returns ``''``).
    """
    if not text:
        return Markup("")

    text = str(text)

    # HTML-escape first — neutralises <a href=evil>good.com</a> style tricks.
    # strip() to get a plain str; Markup.replace() would escape the
    # replacement string, which we don't want when adding <br> / <a> tags.
    plain = str(escape(text))

    # Short-circuit: if no URL-like substrings, skip regex entirely
    if "http://" not in text and "https://" not in text and "www." not in text:
        return Markup(plain.replace("\n", "<br>"))

    # Replace newlines with <br>
    with_br = plain.replace("\n", "<br>")

    # Find and linkify URLs in the already-escaped text
    def _replace_url(match):
        raw_url = match.group(0)
        # Trim trailing punctuation that is unlikely to be part of the URL.
        # Preserve a trailing ')' if there is an unclosed '(' in the URL
        # (handles Wikipedia-style URLs like .../Cat_(animal) ).
        clean = raw_url
        while clean and clean[-1] in _TRAILING_PUNCT_CHARS:
            clean = clean[:-1]
        # Don't strip ')' if it closes a parenthesis inside the URL
        if clean and raw_url[len(clean) :].startswith(")") and "(" in clean:
            clean = clean + ")"
        trailing = raw_url[len(clean) :]

        href = clean
        if clean.lower().startswith("www."):
            href = "https://" + clean

        return (
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">' f"{clean}</a>{trailing}"
        )

    result = _URL_RE.sub(_replace_url, with_br)
    return Markup(result)


def register_filters(app):
    """Register all custom template filters with the Flask app."""
    app.jinja_env.filters["utc_timestamp"] = utc_timestamp
    app.jinja_env.filters["tojson_images"] = tojson_images
    app.jinja_env.filters["linkify"] = linkify
