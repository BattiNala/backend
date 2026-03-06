"""
date and time related utilities.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def utc_to_timezone(utc_datetime, timezone="Asia/Kathmandu"):
    """Convert UTC datetime to specified timezone."""
    if isinstance(utc_datetime, str):
        utc_datetime = datetime.fromisoformat(utc_datetime)

    utc_datetime = utc_datetime.replace(tzinfo=ZoneInfo("UTC"))
    return utc_datetime.astimezone(ZoneInfo(timezone))
