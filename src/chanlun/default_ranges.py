"""Default lookback windows for Chanlun structure chart generation."""

from __future__ import annotations

from datetime import datetime, timedelta


_LOOKBACK_DAYS = {
    "day": 1000,
    "60m": 300,
    "15m": 120,
}


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