"""Natural language datetime parsing utilities."""

import re
from datetime import datetime, timedelta
from typing import Optional


def parse_relative_datetime(text: str, reference: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse natural language relative datetime expressions to a datetime object.
    
    Supported patterns:
    - "today at 5 PM" / "today at 17:00"
    - "tomorrow at 9 AM" / "tomorrow at 09:00"
    - "next Monday at 10 AM"
    - "in 2 hours" / "in 30 minutes" / "in 1 day"
    - "2 hours from now"
    - "this Friday at 3 PM"
    - "on January 15 at 2 PM"
    
    Args:
        text: Natural language datetime expression
        reference: Reference datetime (defaults to now)
        
    Returns:
        Parsed datetime object or None if unable to parse
    """
    if reference is None:
        reference = datetime.now()
    
    text = text.strip().lower()
    
    # Pattern: "in X hours/minutes/days/weeks"
    in_pattern = r'^in\s+(\d+)\s*(hour|hr|h|minute|min|m|day|d|week|w)s?\s*$'
    match = re.match(in_pattern, text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ('hour', 'hr', 'h'):
            return reference + timedelta(hours=amount)
        elif unit in ('minute', 'min', 'm'):
            return reference + timedelta(minutes=amount)
        elif unit in ('day', 'd'):
            return reference + timedelta(days=amount)
        elif unit in ('week', 'w'):
            return reference + timedelta(weeks=amount)
    
    # Pattern: "X hours/minutes/days from now"
    from_now_pattern = r'^(\d+)\s*(hour|hr|h|minute|min|m|day|d|week|w)s?\s+from\s+now\s*$'
    match = re.match(from_now_pattern, text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ('hour', 'hr', 'h'):
            return reference + timedelta(hours=amount)
        elif unit in ('minute', 'min', 'm'):
            return reference + timedelta(minutes=amount)
        elif unit in ('day', 'd'):
            return reference + timedelta(days=amount)
        elif unit in ('week', 'w'):
            return reference + timedelta(weeks=amount)
    
    # Pattern: "today at HH:MM" or "today at H AM/PM"
    today_pattern = r'^today\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$'
    match = re.match(today_pattern, text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        return reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Pattern: "tomorrow at HH:MM" or "tomorrow at H AM/PM"
    tomorrow_pattern = r'^tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$'
    match = re.match(tomorrow_pattern, text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        tomorrow = reference + timedelta(days=1)
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Pattern: "next <weekday> at HH:MM" or "next <weekday> at H AM/PM"
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for i, day in enumerate(weekdays):
        pattern = rf'^next\s+{day}\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?\s*$'
        match = re.match(pattern, text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3)
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            # Find next occurrence of this weekday
            days_ahead = (i - reference.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week, not today
            target_date = reference + timedelta(days=days_ahead)
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Pattern: "this <weekday> at HH:MM"
    for i, day in enumerate(weekdays):
        pattern = rf'^this\s+{day}\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?\s*$'
        match = re.match(pattern, text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3)
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            days_ahead = (i - reference.weekday() + 7) % 7
            target_date = reference + timedelta(days=days_ahead)
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Pattern: "on Month DD at HH:MM" or "Month DD at HH:MM"
    months = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]
    month_pattern = r'^(?:on\s+)?(' + '|'.join(months) + r')\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$'
    match = re.match(month_pattern, text)
    if match:
        month_name = match.group(1)
        day = int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4)) if match.group(4) else 0
        ampm = match.group(5)
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        month = months.index(month_name) + 1
        year = reference.year
        # If the date has already passed this year, assume next year
        try:
            target = datetime(year, month, day, hour, minute)
            if target < reference:
                target = datetime(year + 1, month, day, hour, minute)
            return target
        except ValueError:
            return None
    
    # Try to parse as ISO format directly
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    
    return None


def parse_relative_datetime_or_raise(text: str, reference: Optional[datetime] = None) -> datetime:
    """
    Parse natural language datetime or raise ValueError with descriptive message.
    
    Args:
        text: Natural language datetime expression
        reference: Reference datetime (defaults to now)
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If unable to parse with descriptive error message
    """
    result = parse_relative_datetime(text, reference)
    if result is None:
        raise ValueError(
            f"Unable to parse datetime from: '{text}'. "
            f"Supported formats: 'today at 5 PM', 'tomorrow at 9 AM', "
            f"'next Monday at 10 AM', 'in 2 hours', 'in 30 minutes', "
            f"'on January 15 at 2 PM', or ISO format (YYYY-MM-DDTHH:MM:SS)"
        )
    return result


def format_datetime_for_user(dt: datetime) -> str:
    """Format datetime for user-friendly display."""
    return dt.strftime("%A, %B %d, %Y at %I:%M %p")