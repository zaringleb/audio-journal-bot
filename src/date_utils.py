from __future__ import annotations

"""Utility functions related to date handling for the audio-journal bot."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

__all__ = ["journal_date"]

# Default timezone and cutoff can be overridden if necessary
DEFAULT_TZ = ZoneInfo("Europe/London")
DEFAULT_CUTOFF = time(4, 0)  # 04:00


def journal_date(
    message_dt_utc: datetime,
    *,
    tz: ZoneInfo = DEFAULT_TZ,
    cutoff: time = DEFAULT_CUTOFF,
) -> datetime.date:
    """Return the *logical* journal date for a Telegram message.

    Parameters
    ----------
    message_dt_utc : datetime
        The original timestamp from Telegram, assumed to be in UTC (naive or tz-aware).
    tz : ZoneInfo, optional
        Target timezone (defaults to Europe/London).
    cutoff : datetime.time, optional
        Hour/minute before which entries are attributed to the previous day.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> journal_date(datetime(2025, 7, 21, 2, 30, tzinfo=timezone.utc))
    datetime.date(2025, 7, 20)
    """

    # Ensure we are working with an aware UTC datetime
    if message_dt_utc.tzinfo is None:
        message_dt_utc = message_dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    else:
        message_dt_utc = message_dt_utc.astimezone(ZoneInfo("UTC"))

    # Convert to local timezone
    local_dt = message_dt_utc.astimezone(tz)

    # If local time is before cutoff -> previous day
    if local_dt.time() < cutoff:
        local_dt -= timedelta(days=1)

    return local_dt.date()
