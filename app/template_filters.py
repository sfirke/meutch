# app/template_filters.py
"""Custom Jinja2 template filters for the Meutch application."""

from markupsafe import Markup


def utc_timestamp(value, format='datetime'):
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
        return ''
    
    # Convert to ISO format for JavaScript parsing
    # If the datetime is naive (no timezone), we assume it's UTC
    iso_timestamp = value.isoformat()
    
    # Fallback text in case JavaScript doesn't run
    # Use a simple format that works server-side
    try:
        if format in ('date', 'short-date'):
            fallback = value.strftime('%B %d, %Y')
        elif format == 'time':
            fallback = value.strftime('%I:%M %p UTC')
        elif format == 'message':
            fallback = value.strftime('%b %d, %H:%M')
        elif format == 'compact':
            fallback = value.strftime('%Y-%m-%d %H:%M UTC')
        elif format == 'short-datetime':
            fallback = value.strftime('%b %d, %I:%M %p UTC')
        else:
            fallback = value.strftime('%B %d, %Y at %I:%M %p UTC')
    except Exception:
        fallback = str(value)
    
    return Markup(
        f'<span data-utc-timestamp="{iso_timestamp}" data-format="{format}">{fallback}</span>'
    )


def register_filters(app):
    """Register all custom template filters with the Flask app."""
    app.jinja_env.filters['utc_timestamp'] = utc_timestamp
