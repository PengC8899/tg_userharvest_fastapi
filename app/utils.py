from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def parse_range_to_utc_window(range_key: str, tz: str) -> tuple[datetime, datetime]:
    tzinfo = ZoneInfo(tz)
    now_local = datetime.now(tzinfo)
    if range_key == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    elif range_key == "yesterday":
        end_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = end_local - timedelta(days=1)
    elif range_key == "3d":
        start_local = now_local - timedelta(days=3)
        end_local = now_local
    elif range_key == "7d":
        start_local = now_local - timedelta(days=7)
        end_local = now_local
    else:
        raise ValueError("Unsupported range key")
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc