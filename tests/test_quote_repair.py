"""非正 OHLC 修复测试（港股分钟线 open=0 占位 bar）。"""

from __future__ import annotations

from datetime import datetime

from chanlun.data.cleaner import clean_bars
from chanlun.data.quote_repair import repair_nonpositive_quotes
from chanlun.models import Bar


def test_repair_nonpositive_open_uses_close() -> None:
    rows = [
        {"ts": "2026-11-02 13:59", "open": 2.94, "high": 2.94, "low": 2.94, "close": 2.94, "volume": 1000},
        {"ts": "2026-11-02 14:00", "open": 0.0, "high": 2.94, "low": 2.94, "close": 2.94, "volume": 0},
    ]

    repaired, repairs = repair_nonpositive_quotes(rows)

    assert repaired[1]["open"] == 2.94
    assert repaired[1]["high"] == 2.94
    assert repaired[1]["low"] == 2.94
    assert repaired[1]["close"] == 2.94
    assert repaired[1]["volume"] == 0
    assert len(repairs) == 1
    assert repairs[0][1].field == "open"
    assert repairs[0][1].reason == "nonpositive_open_filled_close"


def test_repair_nonpositive_open_falls_back_to_previous_close() -> None:
    rows = [
        {"ts": "2026-11-02 13:59", "open": 2.94, "high": 2.94, "low": 2.94, "close": 2.94, "volume": 1000},
        {"ts": "2026-11-02 14:00", "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0},
    ]

    repaired, _ = repair_nonpositive_quotes(rows)

    assert repaired[1]["close"] == 2.94
    assert repaired[1]["open"] == 2.94
    assert repaired[1]["high"] == 2.94
    assert repaired[1]["low"] == 2.94


def test_repair_is_idempotent() -> None:
    rows = [
        {"ts": "2026-11-02 14:00", "open": 0.0, "high": 2.94, "low": 2.94, "close": 2.94, "volume": 0}
    ]

    once, _ = repair_nonpositive_quotes(rows)
    twice, repairs = repair_nonpositive_quotes(once)

    assert twice == once
    assert repairs == []


def test_clean_bars_repairs_zero_open() -> None:
    bars = [
        Bar(datetime(2026, 11, 2, 13, 59), open=2.94, high=2.94, low=2.94, close=2.94, volume=1000),
        Bar(datetime(2026, 11, 2, 14, 0), open=0.0, high=2.94, low=2.94, close=2.94, volume=0),
    ]

    cleaned = clean_bars(bars)

    assert len(cleaned) == 2
    assert cleaned[1].open == 2.94
    # 原始对象不被就地修改
    assert bars[1].open == 0.0
