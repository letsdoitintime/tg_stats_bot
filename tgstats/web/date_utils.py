"""Date and timezone utilities for web API.

This module provides utilities for parsing dates, handling timezones,
and transforming data for visualization.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def parse_period(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tz: ZoneInfo = ZoneInfo("UTC"),
) -> Tuple[datetime, datetime, int]:
    """
    Parse period parameters and return UTC start, end, and days count.

    Args:
        from_date: Start date in YYYY-MM-DD format (optional)
        to_date: End date in YYYY-MM-DD format (optional)
        tz: Timezone for interpreting dates

    Returns:
        Tuple of (start_utc, end_utc, days_count)

    Raises:
        HTTPException: If date format is invalid
    """
    if to_date:
        try:
            end_local = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
    else:
        # Default to end of today in local timezone
        now_local = datetime.now(tz)
        end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

    if from_date:
        try:
            start_local = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
    else:
        # Default to 30 days before end_local
        start_local = end_local - timedelta(days=30)
        start_local = start_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC
    # Note: We use timezone-naive datetimes here for database compatibility
    # PostgreSQL TIMESTAMP columns expect naive datetimes in UTC
    # The database layer handles timezone-aware storage with TIMESTAMP WITH TIMEZONE columns
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    days = (end_local.date() - start_local.date()).days + 1

    return start_utc, end_utc, days


def rotate_heatmap_rows(rows: List[Tuple], tz: ZoneInfo) -> List[List[int]]:
    """
    Rotate heatmap data from UTC to local timezone.

    Args:
        rows: Database rows with (hour_bucket, weekday_utc, hour_utc, msg_cnt)
        tz: Target timezone for rotation

    Returns:
        7x24 matrix of message counts (weekday x hour)
    """
    # Initialize 7x24 matrix (weekday x hour)
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    for row in rows:
        hour_bucket, weekday_utc, hour_utc, msg_cnt = row

        # Convert UTC hour_bucket to local time
        utc_dt = hour_bucket.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = utc_dt.astimezone(tz)

        local_weekday = local_dt.isoweekday() % 7  # Convert to 0=Monday, 6=Sunday
        local_hour = local_dt.hour

        matrix[local_weekday][local_hour] += msg_cnt

    return matrix


def convert_local_to_utc(local_date: datetime, tz: ZoneInfo) -> datetime:
    """
    Convert local datetime to UTC.

    Args:
        local_date: Datetime in local timezone
        tz: Source timezone

    Returns:
        Datetime in UTC (timezone-naive)
    """
    local_aware = local_date.replace(tzinfo=tz)
    return local_aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def convert_utc_to_local(utc_date: datetime, tz: ZoneInfo) -> datetime:
    """
    Convert UTC datetime to local timezone.

    Args:
        utc_date: Datetime in UTC
        tz: Target timezone

    Returns:
        Datetime in local timezone
    """
    utc_aware = utc_date.replace(tzinfo=ZoneInfo("UTC"))
    return utc_aware.astimezone(tz)
