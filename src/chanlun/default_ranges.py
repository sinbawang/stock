"""Default lookback windows for Chanlun structure chart generation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta


_LOOKBACK_DAYS = {
    "day": 1000,
    "60m": 300,
    "15m": 120,
}

_DAY_BAR_TO_CALENDAR_DAYS = 1.6
_INTRADAY_BASE_BAR_TARGET = 600


def default_day_start_for_bar_target(day_bars: int, now: datetime | None = None) -> str:
    """Approximate a calendar start date that usually covers the requested daily bar count."""
    if day_bars <= 0:
        raise ValueError(f"day_bars must be positive, got {day_bars}")

    anchor = now or datetime.now()
    lookback_days = max(_LOOKBACK_DAYS["day"], math.ceil(day_bars * _DAY_BAR_TO_CALENDAR_DAYS))
    start = anchor - timedelta(days=lookback_days)
    return start.strftime("%Y-%m-%d")


def default_intraday_start_for_bar_target(
    timeframe: str,
    bar_count: int,
    now: datetime | None = None,
) -> str:
    """Approximate an intraday start time that usually covers the requested bar count."""
    normalized = timeframe.strip().lower()
    if normalized not in {"60m", "15m"}:
        raise ValueError(f"Unsupported intraday timeframe: {timeframe}")
    if bar_count <= 0:
        raise ValueError(f"bar_count must be positive, got {bar_count}")

    anchor = now or datetime.now()
    base_days = _LOOKBACK_DAYS[normalized]
    scale = max(1.0, bar_count / _INTRADAY_BASE_BAR_TARGET)
    lookback_days = math.ceil(base_days * scale)
    start = anchor - timedelta(days=lookback_days)
    return start.strftime("%Y-%m-%d 09:30")


def default_structure_start(timeframe: str, now: datetime | None = None) -> str:
    """Return a conservative dynamic default start time for structure charts.

    Chart pipelines fetch by time window rather than exact bar count. These
    calendar lookbacks are chosen so the default day/60m/15m windows typically
    cover at least about 600 K-lines across A-share and HK sessions.
    """
    normalized = timeframe.strip().lower()
    if normalized not in _LOOKBACK_DAYS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    anchor = now or datetime.now()
    start = anchor - timedelta(days=_LOOKBACK_DAYS[normalized])
    if normalized == "day":
        return start.strftime("%Y-%m-%d")
    return start.strftime("%Y-%m-%d 09:30")