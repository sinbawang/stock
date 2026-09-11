from __future__ import annotations

from datetime import datetime, timedelta

from chanlun.data.local_bar_store import MergeStats, apply_retention_limit, detect_incremental_discontinuity, infer_incremental_start, merge_rows, tail_rows, upsert_local_rows


def test_infer_incremental_start_for_day_and_intraday() -> None:
    assert infer_incremental_start("2026-07-01", "day", overlap_bars=10) == "2026-06-21"
    assert infer_incremental_start("2026-07-01 10:00", "5m", overlap_bars=6) == "2026-07-01 09:30"


def test_detect_incremental_discontinuity_flags_forward_gap() -> None:
    """RS4：远端增量最早一根晚于本地缓存末根 -> 跳空 / 停牌不连续，需回退全量。"""
    local = [
        {"ts": "2026-07-01 09:30"},
        {"ts": "2026-07-01 10:00"},
    ]
    # 远端最早 10:30 > 本地末根 10:00 -> 两段之间存在空洞
    gap_remote = [{"ts": "2026-07-01 10:30"}, {"ts": "2026-07-01 10:45"}]
    assert detect_incremental_discontinuity(local, gap_remote) is True


def test_detect_incremental_discontinuity_allows_overlapping_or_gapfilling_window() -> None:
    """RS4 反例：远端回抓覆盖 / 填补本地末尾（最早一根不晚于本地末根）-> 连续，不回退。"""
    local = [
        {"ts": "2026-07-01 09:30"},
        {"ts": "2026-07-01 09:45"},
        {"ts": "2026-07-01 10:00"},
    ]
    # 远端 09:55 填补缺口 + 10:05 新增，最早 09:55 <= 本地末根 10:00 -> 连续
    healthy_remote = [{"ts": "2026-07-01 09:55"}, {"ts": "2026-07-01 10:05"}]
    assert detect_incremental_discontinuity(local, healthy_remote) is False
    # 空缓存 / 空远端一律视为连续（无可比较基准）
    assert detect_incremental_discontinuity([], healthy_remote) is False
    assert detect_incremental_discontinuity(local, []) is False



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


def test_apply_retention_limit_trims_supported_timeframes() -> None:
    base = datetime(2026, 7, 1, 9, 30)
    rows = [{"ts": (base + timedelta(minutes=idx)).strftime("%Y-%m-%d %H:%M")} for idx in range(5000)]

    trimmed = apply_retention_limit(rows, "1m")

    assert len(trimmed) == 4500
    assert trimmed[0]["ts"] == "2026-07-01 17:50"


def test_upsert_local_rows_applies_retention_limit(tmp_path) -> None:
    first_base = datetime(2026, 7, 1, 9, 30)
    second_base = datetime(2026, 7, 3, 9, 30)
    first_batch = [
        {
            "ts": (first_base + timedelta(minutes=idx)).strftime("%Y-%m-%d %H:%M"),
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": idx,
        }
        for idx in range(3000)
    ]
    second_batch = [
        {
            "ts": (second_base + timedelta(minutes=idx)).strftime("%Y-%m-%d %H:%M"),
            "open": 2.0,
            "high": 2.0,
            "low": 2.0,
            "close": 2.0,
            "volume": idx,
        }
        for idx in range(2000)
    ]

    upsert_local_rows("03690", "HK", "1m", first_batch, root=tmp_path)
    merged_rows, stats, _store_path = upsert_local_rows("03690", "HK", "1m", second_batch, root=tmp_path)

    assert len(merged_rows) == 4500
    assert stats.total == 4500
    assert merged_rows[0]["ts"] == "2026-07-01 15:50"
    assert merged_rows[-1]["ts"] == "2026-07-04 18:49"
