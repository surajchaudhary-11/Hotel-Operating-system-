"""
HotelOS — Timezone Utilities
Guarantees timezone-accurate date boundaries across global cloud infrastructure (Render/AWS/GCP).
Stores all timestamps in UTC, but resolves business dates in the hotel's local timezone (e.g. Asia/Kolkata).
"""

from datetime import date, datetime, timezone
import zoneinfo

DEFAULT_HOTEL_TIMEZONE = "Asia/Kolkata"

def get_hotel_timezone(tz_name: str = None) -> zoneinfo.ZoneInfo:
    """Safely resolves ZoneInfo with fallback to Asia/Kolkata."""
    if not tz_name:
        return zoneinfo.ZoneInfo(DEFAULT_HOTEL_TIMEZONE)
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return zoneinfo.ZoneInfo(DEFAULT_HOTEL_TIMEZONE)

def get_hotel_now(tz_name: str = None) -> datetime:
    """Returns the current timezone-aware datetime in the hotel's local timezone."""
    tz = get_hotel_timezone(tz_name)
    return datetime.now(tz)

def get_hotel_today(tz_name: str = None) -> date:
    """
    Returns the current business date in the hotel's local timezone.
    Prevents date discrepancy between UTC cloud servers and IST Indian hotel operations.
    """
    return get_hotel_now(tz_name).date()
