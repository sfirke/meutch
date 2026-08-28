# app/template_filters.py
"""Custom Jinja2 template filters for the Meutch application."""

import re

from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup, escape


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


def truncate(value, length=30):
    """Truncate a string to the given length, appending '…' if truncated.

    Usage in templates:
        {{ some_text|truncate }}
        {{ some_text|truncate(60) }}

    Args:
        value: The string to truncate.
        length: Maximum number of characters before truncation (default 30).

    Returns:
        The truncated string with '…' appended if it exceeded the limit.
    """
    if value is None:
        return ""
    if len(value) <= length:
        return value
    return value[:length] + "…"


# Only http(s) URLs become links. Restricting the scheme here is what keeps
# `javascript:` and `data:` URIs out of the href we generate.
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Punctuation that usually belongs to the sentence rather than the URL, e.g.
# "see it here: https://meutch.com/item/abc." — the period is not part of the link.
_TRAILING_PUNCTUATION = ".,;:!?'\"]}"


def _trim_trailing_punctuation(url):
    """Return *url* with sentence punctuation stripped from its end."""
    while url and (url[-1] in _TRAILING_PUNCTUATION or url[-1] == ")"):
        # A closing paren is kept when the URL opened one, so Wikipedia-style
        # links such as .../Foo_(bar) survive intact.
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    return url


def linkify(value, br=True):
    """Render user-supplied plain text as HTML with clickable http(s) links.

    The text is escaped first and the anchors are built afterwards, so a message
    body can never inject markup: everything the user typed is escaped, and the
    only HTML in the result is the anchors (and line breaks) this function adds.

    Usage in templates:
        {{ message.body|linkify }}

    Args:
        value: The plain text to render.
        br: When True, newlines become <br> tags. Pass False where the
            surrounding markup already preserves newlines (for example a
            `white-space: pre-line` block in an email).

    Returns:
        A Markup object safe to render unescaped.
    """
    if value is None:
        return Markup("")

    text = str(value)
    chunks = []
    cursor = 0
    for match in _URL_PATTERN.finditer(text):
        url = _trim_trailing_punctuation(match.group(0))
        if not url:
            continue
        chunks.append(str(escape(text[cursor : match.start()])))
        safe_url = str(escape(url))
        chunks.append(
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer nofollow">{safe_url}</a>'
        )
        cursor = match.start() + len(url)
    chunks.append(str(escape(text[cursor:])))

    html = "".join(chunks)
    if br:
        # Newlines only survive in the escaped text chunks; URLs cannot contain
        # whitespace, so this never touches the anchors built above.
        html = html.replace("\n", "<br>")
    return Markup(html)


def register_filters(app):
    """Register all custom template filters with the Flask app."""
    app.jinja_env.filters["utc_timestamp"] = utc_timestamp
    app.jinja_env.filters["tojson_images"] = tojson_images
    app.jinja_env.filters["truncate"] = truncate
    app.jinja_env.filters["linkify"] = linkify
