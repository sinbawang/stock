from __future__ import annotations

from chanlun.data.local_bar_store import MergeStats, infer_incremental_start, merge_rows, tail_rows


def test_infer_incremental_start_for_day_and_intraday() -> None:
    assert infer_incremental_start("2026-07-01", "day", overlap_bars=10) == "2026-06-21"
    assert infer_incremental_start("2026-07-01 10:00", "5m", overlap_bars=6) == "2026-07-01 09:30"


def test_merge_rows_deduplicates_and_prefers_new_values() -> None:
    existing = [
        {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 10},
        {"ts": "2026-07-01 09:35", "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2, "volume": 11},
    ]
    new_rows = [
        {"ts": "2026-07-01 09:35", "open": 1.15, "high": 1.35, "low": 1.05, "close": 1.25, "volume": 12},
        {"ts": "2026-07-01 09:40", "open": 1.2, "high": 1.4, "low": 1.1, "close": 1.3, "volume": 13},
    ]

    merged, stats = merge_rows(existing, new_rows)

    assert isinstance(stats, MergeStats)
    assert stats.added == 1
    assert stats.updated == 1
    assert stats.total == 3
    assert merged[-1]["ts"] == "2026-07-01 09:40"
    assert merged[1]["close"] == 1.25


def test_tail_rows_returns_last_n_rows() -> None:
    rows = [{"ts": f"2026-07-01 09:{idx:02d}"} for idx in range(10)]
    assert len(tail_rows(rows, 3)) == 3
    assert tail_rows(rows, 3)[0]["ts"] == "2026-07-01 09:07"
