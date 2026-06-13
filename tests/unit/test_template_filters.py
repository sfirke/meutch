# tests/unit/test_template_filters.py
"""Unit tests for custom Jinja2 template filters."""

from datetime import datetime
from types import SimpleNamespace

from markupsafe import Markup

from app.template_filters import linkify, tojson_images, utc_timestamp


class TestUtcTimestampFilter:
    """Tests for the utc_timestamp Jinja filter."""

    def test_utc_timestamp_returns_span_with_data_attributes(self):
        """Test that the filter returns a span element with proper data attributes."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt))

        # Check for proper span structure
        assert result.startswith('<span data-utc-timestamp="')
        assert 'data-format="datetime"' in result
        assert result.endswith("</span>")

        # Verify ISO timestamp format
        assert "2026-01-24T21:05:00" in result

    def test_utc_timestamp_datetime_format(self):
        """Test the datetime format fallback text."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "datetime"))

        # Check for complete datetime format: "January 24, 2026 at 09:05 PM UTC"
        assert "January 24, 2026 at 09:05 PM UTC" in result
        assert 'data-format="datetime"' in result
        assert 'data-utc-timestamp="2026-01-24T21:05:00"' in result

    def test_utc_timestamp_date_format(self):
        """Test the date-only format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "date"))

        # Should only show date, no time or "at"
        assert "January 24, 2026" in result
        assert " at " not in result
        assert "PM" not in result
        assert 'data-format="date"' in result

    def test_utc_timestamp_short_date_format(self):
        """Test the short date format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "short-date"))

        # Server-side fallback is the same as date format (full month name)
        assert "January 24, 2026" in result
        assert 'data-format="short-date"' in result

    def test_utc_timestamp_short_datetime_format(self):
        """Test the short datetime format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "short-datetime"))

        # Check for abbreviated format: "Jan 24, 09:05 PM UTC"
        assert "Jan 24, 09:05 PM UTC" in result
        assert 'data-format="short-datetime"' in result

    def test_utc_timestamp_message_format(self):
        """Test the message format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "message"))

        # Message format is "Jan 24, 21:05" (abbreviated month, 24-hour time, no timezone shown)
        assert "Jan 24, 21:05" in result
        assert "UTC" not in result  # No timezone in fallback for message format
        assert 'data-format="message"' in result

    def test_utc_timestamp_compact_format(self):
        """Test the compact format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "compact"))

        # Compact format is "2026-01-24 21:05 UTC"
        assert "2026-01-24 21:05 UTC" in result
        assert 'data-format="compact"' in result

    def test_utc_timestamp_time_format(self):
        """Test the time-only format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, "time"))

        # Time format is "09:05 PM UTC"
        assert "09:05 PM UTC" in result
        # Date should not be in the displayed text (but will be in data attribute)
        fallback = result.split(">")[1].split("<")[0]
        assert "2026" not in fallback
        assert 'data-format="time"' in result

    def test_utc_timestamp_none_value(self):
        """Test handling of None value."""
        result = utc_timestamp(None)
        assert result == ""

    def test_utc_timestamp_preserves_iso_format(self):
        """Test that the ISO format is preserved for JavaScript parsing."""
        dt = datetime(2026, 6, 15, 14, 30, 45)
        result = str(utc_timestamp(dt))

        # Verify complete ISO timestamp with seconds
        assert 'data-utc-timestamp="2026-06-15T14:30:45"' in result

    def test_utc_timestamp_returns_markup(self):
        """Test that the filter returns a Markup object (safe HTML)."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = utc_timestamp(dt)

        # Should return Markup object, not string
        assert isinstance(result, Markup)

    def test_utc_timestamp_midnight(self):
        """Test handling of midnight (00:00)."""
        dt = datetime(2026, 1, 24, 0, 0, 0)
        result = str(utc_timestamp(dt, "datetime"))

        # Should show 12:00 AM
        assert "12:00 AM UTC" in result

    def test_utc_timestamp_noon(self):
        """Test handling of noon (12:00)."""
        dt = datetime(2026, 1, 24, 12, 0, 0)
        result = str(utc_timestamp(dt, "datetime"))

        # Should show 12:00 PM
        assert "12:00 PM UTC" in result

    def test_utc_timestamp_single_digit_minute(self):
        """Test that single-digit minutes are zero-padded."""
        dt = datetime(2026, 1, 24, 15, 5, 0)
        result = str(utc_timestamp(dt, "datetime"))

        # Should show 03:05 PM, not 03:5 PM
        assert "03:05 PM UTC" in result

    def test_utc_timestamp_with_microseconds(self):
        """Test that microseconds are handled (but not displayed)."""
        dt = datetime(2026, 1, 24, 15, 30, 45, 123456)
        result = str(utc_timestamp(dt))

        # ISO format should include microseconds
        assert "2026-01-24T15:30:45.123456" in result

        # But fallback display shouldn't show them
        fallback = result.split(">")[1].split("<")[0]
        assert ".123456" not in fallback


class TestToJsonImagesFilter:
    """Tests for the existing-image JSON serializer used by the upload widget."""

    def test_tojson_images_escapes_html_sensitive_characters(self):
        image = SimpleNamespace(id="img-1", url="https://cdn.example.com/o'reilly?<script>.jpg")

        result = tojson_images([image])

        assert isinstance(result, Markup)
        assert "\\u0027" in str(result)
        assert "\\u003cscript\\u003e" in str(result)


class TestLinkifyFilter:
    """Tests for the linkify Jinja filter (URL detection + HTML escaping + newlines)."""

    # ── basic behaviour ──────────────────────────────────────────────────

    def test_none_returns_empty(self):
        assert str(linkify(None)) == ""

    def test_empty_string_returns_empty(self):
        assert str(linkify("")) == ""

    def test_plain_text_unchanged_except_newlines(self):
        result = str(linkify("Hello world"))
        assert result == "Hello world"

    def test_newlines_become_br(self):
        result = str(linkify("Line one\nLine two\nLine three"))
        assert result == "Line one<br>Line two<br>Line three"

    def test_returns_markup(self):
        assert isinstance(linkify("hello"), Markup)

    # ── URL linkification ────────────────────────────────────────────────

    def test_https_url(self):
        result = str(linkify("Visit https://example.com for info"))
        assert '<a href="https://example.com"' in result
        assert 'target="_blank"' in result
        assert 'rel="noopener noreferrer"' in result
        assert ">https://example.com</a>" in result

    def test_http_url(self):
        result = str(linkify("See http://example.org now"))
        assert '<a href="http://example.org"' in result

    def test_www_url_prepends_https(self):
        result = str(linkify("Go to www.example.com today"))
        assert '<a href="https://www.example.com"' in result
        assert ">www.example.com</a>" in result

    def test_multiple_urls(self):
        result = str(linkify("A: https://a.com and B: https://b.org"))
        assert result.count("<a href=") == 2

    def test_url_with_path(self):
        result = str(linkify("https://example.com/path/to/page"))
        assert 'href="https://example.com/path/to/page"' in result

    def test_url_with_query_string(self):
        result = str(linkify("https://example.com?foo=bar&baz=qux"))
        # After escape(), & becomes &amp; — valid HTML in href attributes
        assert "foo=bar" in result
        assert "baz=qux" in result

    def test_url_with_fragment(self):
        result = str(linkify("https://example.com/page#section"))
        assert 'href="https://example.com/page#section"' in result

    def test_url_with_port(self):
        result = str(linkify("https://example.com:8080/path"))
        assert 'href="https://example.com:8080/path"' in result

    def test_www_url_with_port(self):
        result = str(linkify("Visit www.example.com:3000/app"))
        assert 'href="https://www.example.com:3000/app"' in result

    # ── trailing punctuation ─────────────────────────────────────────────

    def test_trailing_period_not_included(self):
        result = str(linkify("See https://example.com."))
        assert ">https://example.com</a>." in result

    def test_trailing_comma_not_included(self):
        result = str(linkify("Visit https://example.com, please"))
        assert ">https://example.com</a>," in result

    def test_trailing_colon_not_included(self):
        result = str(linkify("URL: https://example.com: see it"))
        # Colon after URL should be excluded; port colon preserved
        assert ">https://example.com</a>:" in result

    def test_internal_punctuation_preserved(self):
        result = str(linkify("https://en.wikipedia.org/wiki/Cat_(animal)"))
        assert 'href="https://en.wikipedia.org/wiki/Cat_(animal)"' in result

    # ── XSS / HTML safety ────────────────────────────────────────────────

    def test_script_tag_escaped(self):
        result = str(linkify('<script>alert("xss")</script>'))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "alert" in result  # the text content is preserved (escaped)

    def test_fake_link_tag_neutralised(self):
        # The exact scenario from the threat model:
        # <a href=MALICIOUS_LINK>www.goodurl.com</a>
        result = str(linkify("<a href=http://evil.com>www.goodurl.com</a>"))
        # The <a> and </a> tags must be escaped (HTML entities)
        assert "&lt;a href=" in result
        assert "&lt;/a&gt;" in result
        # The inner URL http://evil.com is linkified (it's a real URL inside
        # the escaped tag soup — user typed it, we linkify it).
        assert 'href="http://evil.com"' in result
        # www.goodurl.com is also linkified
        assert 'href="https://www.goodurl.com"' in result

    def test_html_entities_in_input_are_doubled(self):
        # If user types &amp; it should become &amp;amp; (safe)
        result = str(linkify("Price: $5 &amp; up"))
        assert "&amp;amp;" in result

    # ── edge cases ───────────────────────────────────────────────────────

    def test_url_with_amp_in_query_string_after_escape(self):
        result = str(linkify("https://example.com?a=1&b=2"))
        assert 'href="https://example.com?a=1' in result
        # &b=2 after escape becomes &amp;b=2 which is fine in href
        assert "b=2" in result

    def test_text_around_url(self):
        result = str(linkify("Before https://example.com after"))
        assert "Before " in result
        assert '<a href="https://example.com"' in result
        assert " after" in result

    def test_url_at_start_of_text(self):
        result = str(linkify("https://example.com is great"))
        assert result.startswith('<a href="https://example.com"')

    def test_url_at_end_of_text(self):
        result = str(linkify("Check out https://example.com"))
        assert result.endswith("</a>")

    # ── ReDoS safety ─────────────────────────────────────────────────────

    def test_long_punctuation_string_no_backtracking(self):
        # 10 000 exclamation marks — must not cause catastrophic backtracking
        long_text = "!" * 10000
        result = str(linkify(long_text))
        assert len(result) == 10000  # escaped result same length (no & in '!')

    def test_long_text_with_urls_no_backtracking(self):
        # Alternating pattern that could trigger backtracking in naive regexes
        long_text = "a" * 5000 + " https://example.com " + "b" * 5000
        result = str(linkify(long_text))
        assert '<a href="https://example.com"' in result

    # ── false positives ──────────────────────────────────────────────────

    def test_phone_number_not_linkified(self):
        result = str(linkify("Call 555-1234 for info"))
        assert "<a href=" not in result

    def test_email_not_linkified(self):
        result = str(linkify("Contact user@example.com for help"))
        # Email addresses should not be linkified (not in scope)
        assert "<a href=" not in result

    # ── short-circuit fast path ──────────────────────────────────────────

    def test_fast_path_when_no_url_substrings(self):
        # Text without http/https/www should skip regex entirely
        result = str(linkify("Just some plain text\nwith newlines"))
        assert "Just some plain text<br>with newlines" == result
        assert "<a href=" not in result
