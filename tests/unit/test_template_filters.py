# tests/unit/test_template_filters.py
"""Unit tests for custom Jinja2 template filters."""

import pytest
from datetime import datetime
from app.template_filters import utc_timestamp


class TestUtcTimestampFilter:
    """Tests for the utc_timestamp Jinja filter."""
    
    def test_utc_timestamp_returns_span_with_data_attributes(self):
        """Test that the filter returns a span element with proper data attributes."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt))
        
        assert '<span data-utc-timestamp="' in result
        assert 'data-format="datetime"' in result
        assert '2026-01-24T21:05:00' in result
    
    def test_utc_timestamp_datetime_format(self):
        """Test the datetime format fallback text."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'datetime'))
        
        assert 'January 24, 2026' in result
        assert 'UTC' in result
        assert 'data-format="datetime"' in result
    
    def test_utc_timestamp_date_format(self):
        """Test the date-only format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'date'))
        
        assert 'January 24, 2026' in result
        assert 'data-format="date"' in result
    
    def test_utc_timestamp_short_date_format(self):
        """Test the short date format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'short-date'))
        
        # Server-side fallback is the same as date format
        assert '2026' in result
        assert 'data-format="short-date"' in result
    
    def test_utc_timestamp_short_datetime_format(self):
        """Test the short datetime format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'short-datetime'))
        
        assert 'Jan' in result
        assert 'UTC' in result
        assert 'data-format="short-datetime"' in result
    
    def test_utc_timestamp_message_format(self):
        """Test the message format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'message'))
        
        assert 'Jan' in result
        assert 'data-format="message"' in result
    
    def test_utc_timestamp_compact_format(self):
        """Test the compact format."""
        dt = datetime(2026, 1, 24, 21, 5, 0)
        result = str(utc_timestamp(dt, 'compact'))
        
        assert '2026-01-24' in result
        assert 'UTC' in result
        assert 'data-format="compact"' in result
    
    def test_utc_timestamp_none_value(self):
        """Test handling of None value."""
        result = utc_timestamp(None)
        assert result == ''
    
    def test_utc_timestamp_preserves_iso_format(self):
        """Test that the ISO format is preserved for JavaScript parsing."""
        dt = datetime(2026, 6, 15, 14, 30, 45)
        result = str(utc_timestamp(dt))
        
        assert '2026-06-15T14:30:45' in result
