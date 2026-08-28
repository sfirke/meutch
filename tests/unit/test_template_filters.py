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
    """Tests for the linkify filter used to render message bodies."""

    def test_linkifies_an_http_url(self):
        result = str(linkify("You can see it here: https://meutch.com/item/abc"))

        assert (
            '<a href="https://meutch.com/item/abc" target="_blank" '
            'rel="noopener noreferrer nofollow">https://meutch.com/item/abc</a>'
        ) in result

    def test_escapes_html_in_the_surrounding_text(self):
        """A message body is plain text; markup in it must never be rendered."""
        result = str(linkify("<script>alert(1)</script> hello"))

        assert "<script>" not in result
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result

    def test_escapes_html_that_looks_like_an_anchor(self):
        result = str(linkify('<a href="https://evil.example.com">click</a>'))

        # The only anchor in the output is the one linkify builds for the URL.
        assert result.count("<a href=") == 1
        assert 'rel="noopener noreferrer nofollow"' in result
        assert "&lt;a href=" in result

    def test_does_not_linkify_javascript_uris(self):
        result = str(linkify("javascript:alert(1)"))

        assert "<a" not in result
        assert result == "javascript:alert(1)"

    def test_does_not_linkify_data_uris(self):
        result = str(linkify("data:text/html;base64,PHNjcmlwdD4="))

        assert "<a" not in result

    def test_converts_newlines_to_breaks_by_default(self):
        result = str(linkify("first\nsecond"))

        assert result == "first<br>second"

    def test_br_false_leaves_newlines_alone(self):
        """Email bodies sit in a `white-space: pre-line` block that already breaks lines."""
        result = str(linkify("first\nsecond", br=False))

        assert result == "first\nsecond"

    def test_trailing_sentence_punctuation_is_not_part_of_the_link(self):
        result = str(linkify("See https://meutch.com/item/abc."))

        assert 'href="https://meutch.com/item/abc"' in result
        assert result.endswith("</a>.")

    def test_balanced_parentheses_are_kept_in_the_link(self):
        result = str(linkify("https://example.com/wiki/Foo_(bar)"))

        assert 'href="https://example.com/wiki/Foo_(bar)"' in result

    def test_unbalanced_closing_paren_is_dropped(self):
        result = str(linkify("(see https://meutch.com/item/abc)"))

        assert 'href="https://meutch.com/item/abc"' in result
        assert result.endswith("</a>)")

    def test_ampersands_in_query_strings_are_escaped(self):
        result = str(linkify("https://meutch.com/items?a=1&b=2"))

        assert 'href="https://meutch.com/items?a=1&amp;b=2"' in result

    def test_quotes_cannot_break_out_of_the_href_attribute(self):
        result = str(linkify('https://meutch.com/a"onmouseover="alert(1)'))

        assert 'onmouseover="alert(1)' not in result

    def test_linkifies_several_urls_in_one_body(self):
        result = str(linkify("https://a.example.com and https://b.example.com"))

        assert result.count("<a href=") == 2

    def test_linkifies_a_scheme_less_www_url(self):
        """People type "www.example.com" far more often than they type the scheme."""
        result = str(linkify("Found it at www.example.com/dp/B012345"))

        assert (
            '<a href="https://www.example.com/dp/B012345" target="_blank" '
            'rel="noopener noreferrer nofollow">www.example.com/dp/B012345</a>'
        ) in result

    def test_www_url_with_a_multi_label_domain_is_matched_whole(self):
        result = str(linkify("www.example.co.uk/dp/B012345"))

        assert 'href="https://www.example.co.uk/dp/B012345"' in result
        assert ">www.example.co.uk/dp/B012345</a>" in result

    def test_www_without_a_tld_is_not_a_link(self):
        assert "<a" not in str(linkify("www.example"))

    def test_bare_hostname_without_www_is_not_a_link(self):
        """Only an explicit scheme or a www. prefix signals intent to link."""
        assert "<a" not in str(linkify("Ask me about example.com sometime"))

    def test_trailing_ellipsis_is_not_part_of_the_link(self):
        """`truncate` appends an ellipsis; it must not end up inside the href."""
        result = str(linkify("See https://meutch.com/item/abc…"))

        assert 'href="https://meutch.com/item/abc"' in result
        assert result.endswith("</a>…")

    def test_shorten_drops_the_scheme_from_the_link_text(self):
        result = str(linkify("https://example.com/shop", shorten=40))

        assert 'href="https://example.com/shop"' in result
        assert ">example.com/shop</a>" in result

    def test_shorten_leaves_the_href_whole(self):
        """Only the visible text is shortened; the link still goes to the real URL."""
        url = "https://www.example.com/Some-Long-Product-Name/dp/B08XYZ123?ref=sr_1_3"
        result = str(linkify(url, shorten=40))

        assert f'href="{url}"' in result
        assert "…</a>" in result

    def test_shorten_keeps_the_host_whole(self):
        """The host is how a reader judges a link, so it is the last thing elided."""
        result = str(
            linkify("https://www.example.com/a/very/long/path/that/keeps/going", shorten=40)
        )

        assert ">www.example.com/" in result

    def test_shorten_falls_back_when_the_host_alone_is_too_long(self):
        host = "a-really-long-hostname-that-alone-exceeds.example.com"
        result = str(linkify(f"https://{host}/x", shorten=40))

        text = result.split(">")[-2].replace("</a", "")
        assert len(text) == 40
        assert text.endswith("…")

    def test_shorten_adds_a_title_with_the_full_url_when_text_is_cut(self):
        url = "https://www.example.com/Some-Long-Product-Name/dp/B08XYZ123?ref=sr_1_3"
        result = str(linkify(url, shorten=40))

        assert f'title="{url}"' in result

    def test_shorten_adds_no_title_when_only_the_scheme_was_dropped(self):
        """A tooltip repeating a URL the reader can already read is just noise."""
        result = str(linkify("https://example.com/shop", shorten=40))

        assert "title=" not in result

    def test_shorten_unset_leaves_the_full_url_as_link_text(self):
        result = str(linkify("https://example.com/dp/B0123?a=1&b=2"))

        assert ">https://example.com/dp/B0123?a=1&amp;b=2</a>" in result
        assert "title=" not in result

    def test_returns_markup(self):
        assert isinstance(linkify("hello"), Markup)

    def test_none_renders_as_empty_markup(self):
        assert str(linkify(None)) == ""
