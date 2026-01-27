# tests/unit/test_template_filters.py
"""Unit tests for custom Jinja2 template filters."""

import pytest
from datetime import datetime
from markupsafe import Markup
from app.template_filters import utc_timestamp


class TestUtcTimestampFilter:
    """Tests for the utc_timestamp Jinja filter."""
    
    def test_utc_timestamp_returns_span_with_data_attributes(self):
        """Test that the filter returns a span element with proper data attributes."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt))
        
        # Check for proper span structure
        assert result.startswith('<span data-utc-timestamp="')
        assert 'data-format="datetime"' in result
        assert result.endswith('</span>')
        
        # Verify ISO timestamp format
        assert '2026-01-24T21:05:00' in result
    
    def test_utc_timestamp_datetime_format(self):
        """Test the datetime format fallback text."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'datetime'))
        
        # Check for complete datetime format: "January 24, 2026 at 09:05 PM UTC"
        assert 'January 24, 2026 at 09:05 PM UTC' in result
        assert 'data-format="datetime"' in result
        assert 'data-utc-timestamp="2026-01-24T21:05:00"' in result
    
    def test_utc_timestamp_date_format(self):
        """Test the date-only format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'date'))
        
        # Should only show date, no time or "at"
        assert 'January 24, 2026' in result
        assert ' at ' not in result
        assert 'PM' not in result
        assert 'data-format="date"' in result
    
    def test_utc_timestamp_short_date_format(self):
        """Test the short date format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'short-date'))
        
        # Server-side fallback is the same as date format (full month name)
        assert 'January 24, 2026' in result
        assert 'data-format="short-date"' in result
    
    def test_utc_timestamp_short_datetime_format(self):
        """Test the short datetime format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'short-datetime'))
        
        # Check for abbreviated format: "Jan 24, 09:05 PM UTC"
        assert 'Jan 24, 09:05 PM UTC' in result
        assert 'data-format="short-datetime"' in result
    
    def test_utc_timestamp_message_format(self):
        """Test the message format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'message'))
        
        # Message format is "Jan 24, 21:05" (abbreviated month, 24-hour time, no timezone shown)
        assert 'Jan 24, 21:05' in result
        assert 'UTC' not in result  # No timezone in fallback for message format
        assert 'data-format="message"' in result
    
    def test_utc_timestamp_compact_format(self):
        """Test the compact format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'compact'))
        
        # Compact format is "2026-01-24 21:05 UTC"
        assert '2026-01-24 21:05 UTC' in result
        assert 'data-format="compact"' in result
    
    def test_utc_timestamp_time_format(self):
        """Test the time-only format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'time'))
        
        # Time format is "09:05 PM UTC"
        assert '09:05 PM UTC' in result
        # Date should not be in the displayed text (but will be in data attribute)
        fallback = result.split('>')[1].split('<')[0]
        assert '2026' not in fallback
        assert 'data-format="time"' in result
    
    def test_utc_timestamp_none_value(self):
        """Test handling of None value."""
        result = utc_timestamp(None)
        assert result == ''
    
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
        result = str(utc_timestamp(dt, 'datetime'))
        
        # Should show 12:00 AM
        assert '12:00 AM UTC' in result
    
    def test_utc_timestamp_noon(self):
        """Test handling of noon (12:00)."""
        dt = datetime(2026, 1, 24, 12, 0, 0)
        result = str(utc_timestamp(dt, 'datetime'))
        
        # Should show 12:00 PM
        assert '12:00 PM UTC' in result
    
    def test_utc_timestamp_single_digit_minute(self):
        """Test that single-digit minutes are zero-padded."""
        dt = datetime(2026, 1, 24, 15, 5, 0)
        result = str(utc_timestamp(dt, 'datetime'))
        
        # Should show 03:05 PM, not 03:5 PM
        assert '03:05 PM UTC' in result
    
    def test_utc_timestamp_with_microseconds(self):
        """Test that microseconds are handled (but not displayed)."""
        dt = datetime(2026, 1, 24, 15, 30, 45, 123456)
        result = str(utc_timestamp(dt))
        
        # ISO format should include microseconds
        assert '2026-01-24T15:30:45.123456' in result
        
        # But fallback display shouldn't show them
        fallback = result.split('>')[1].split('<')[0]
        assert '.123456' not in fallback