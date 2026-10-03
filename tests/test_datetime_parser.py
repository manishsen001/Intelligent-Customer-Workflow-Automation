"""Tests for datetime parsing utilities."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.datetime_parser import (
    parse_relative_datetime,
    parse_relative_datetime_or_raise,
    format_datetime_for_user,
)


def test_parse_today_at():
    """Test parsing 'today at 5 PM'."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("today at 5 PM", reference)
    assert result is not None
    assert result == datetime(2025, 1, 15, 17, 0, 0)


def test_parse_tomorrow_at():
    """Test parsing 'tomorrow at 9 AM'."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("tomorrow at 9 AM", reference)
    assert result is not None
    assert result == datetime(2025, 1, 16, 9, 0, 0)


def test_parse_in_hours():
    """Test parsing 'in 2 hours'."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("in 2 hours", reference)
    assert result is not None
    assert result == datetime(2025, 1, 15, 12, 0, 0)


def test_parse_in_minutes():
    """Test parsing 'in 30 minutes'."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("in 30 minutes", reference)
    assert result is not None
    assert result == datetime(2025, 1, 15, 10, 30, 0)


def test_parse_next_weekday():
    """Test parsing 'next Monday at 10 AM'."""
    # Jan 15, 2025 is a Wednesday
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("next Monday at 10 AM", reference)
    assert result is not None
    # Next Monday is Jan 20, 2025
    assert result == datetime(2025, 1, 20, 10, 0, 0)


def test_parse_this_weekday():
    """Test parsing 'this Friday at 3 PM'."""
    # Jan 15, 2025 is a Wednesday
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("this Friday at 3 PM", reference)
    assert result is not None
    # This Friday is Jan 17, 2025
    assert result == datetime(2025, 1, 17, 15, 0, 0)


def test_parse_iso_format():
    """Test parsing ISO format datetime."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("2025-01-20T14:30:00", reference)
    assert result is not None
    assert result == datetime(2025, 1, 20, 14, 30, 0)


def test_parse_month_day():
    """Test parsing 'on January 15 at 2 PM'."""
    reference = datetime(2025, 1, 10, 10, 0, 0)
    result = parse_relative_datetime("on January 15 at 2 PM", reference)
    assert result is not None
    assert result == datetime(2025, 1, 15, 14, 0, 0)


def test_parse_month_day_past_year():
    """Test parsing month/day that already passed this year."""
    reference = datetime(2025, 12, 10, 10, 0, 0)
    result = parse_relative_datetime("on January 15 at 2 PM", reference)
    assert result is not None
    # Should be next year
    assert result == datetime(2026, 1, 15, 14, 0, 0)


def test_parse_invalid():
    """Test that invalid strings return None."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("not a valid date", reference)
    assert result is None


def test_parse_empty():
    """Test that empty string returns None."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("", reference)
    assert result is None


def test_parse_24_hour_format():
    """Test parsing 24-hour format like 'today at 17:00'."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime("today at 17:00", reference)
    assert result is not None
    assert result == datetime(2025, 1, 15, 17, 0, 0)


def test_parse_or_raise_valid():
    """Test parse_relative_datetime_or_raise with valid input."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    result = parse_relative_datetime_or_raise("tomorrow at 9 AM", reference)
    assert result == datetime(2025, 1, 16, 9, 0, 0)


def test_parse_or_raise_invalid():
    """Test parse_relative_datetime_or_raise raises ValueError for invalid input."""
    reference = datetime(2025, 1, 15, 10, 0, 0)
    try:
        parse_relative_datetime_or_raise("invalid date string", reference)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unable to parse datetime" in str(e)
        assert "tomorrow at 9 AM" in str(e) or "ISO format" in str(e)


def test_format_datetime_for_user():
    """Test formatting datetime for user display."""
    dt = datetime(2025, 1, 15, 14, 30, 0)
    result = format_datetime_for_user(dt)
    assert "January 15, 2025" in result
    assert "02:30 PM" in result


if __name__ == "__main__":
    test_parse_today_at()
    test_parse_tomorrow_at()
    test_parse_in_hours()
    test_parse_in_minutes()
    test_parse_next_weekday()
    test_parse_this_weekday()
    test_parse_iso_format()
    test_parse_month_day()
    test_parse_month_day_past_year()
    test_parse_invalid()
    test_parse_empty()
    test_parse_24_hour_format()
    test_parse_or_raise_valid()
    test_parse_or_raise_invalid()
    test_format_datetime_for_user()
    print("All datetime parser tests passed!")