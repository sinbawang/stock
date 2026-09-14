"""港股分钟线幽灵价闸门测试。"""

from __future__ import annotations

import csv
from pathlib import Path

from chanlun.data.hk_phantom_gate import apply_hk_minute_phantom_gate, run_hk_phantom_gate


def _bar(ts: str, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    return {"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _day(ts: str, o: float, h: float, l: float, c: float) -> dict:
    return {"ts": ts, "open": o, "high": h, "low": l, "close": c}


def _gated_values(rows: list[dict], ts: str) -> dict:
    return next(row for row in rows if row["ts"] == ts)


def test_first_bar_stale_high_repaired_to_day_anchor() -> None:
    """03690 2026-09-11：首根 O=H=84.628/84.629（陈旧价）→ O/H 回锚日线 open。"""
    day_rows = [_day("2026-09-11", 74.0, 75.6, 73.4, 75.1)]
    rows = [_bar("2026-09-11 09:31", 84.628, 84.629, 73.4, 73.7)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="03690", timeframe="1m", day_rows=day_rows
    )

    bar = gated[0]
    assert bar["open"] == 74.0
    assert bar["high"] == 74.0
    assert bar["low"] == 73.4
    assert bar["close"] == 73.7
    fields = {(event.field, event.changed) for event in events}
    assert ("open", True) in fields
    assert ("high", True) in fields
    assert all(event.changed for event in events)


def test_first_bar_prev_close_open_repaired_and_low_carried() -> None:
    """00175 2026-09-04：首根 open=前收 17.22（<日线 low）→ open 回锚；低点随幽灵价被带走。"""
    day_rows = [_day("2026-09-04", 17.42, 17.66, 17.26, 17.28)]
    rows = [_bar("2026-09-04 09:31", 17.22, 17.56, 17.22, 17.5)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="00175", timeframe="1m", day_rows=day_rows
    )

    bar = gated[0]
    assert bar["open"] == 17.42
    assert bar["low"] == 17.42
    assert bar["high"] == 17.56
    reasons = {event.reason for event in events}
    assert "open_beyond_day_range" in reasons
    assert "carried_from_open" in reasons


def test_five_minute_boundary_rebuilt_from_one_minute_constituents() -> None:
    """5m 首根越界 high 优先用 1m 成分重聚合（03690 2026-09-11 → 74.3）。"""
    day_rows = [_day("2026-09-11", 74.0, 75.6, 73.4, 75.1)]
    one_min = [
        _bar("2026-09-11 09:31", 74.0, 74.0, 73.4, 73.7),
        _bar("2026-09-11 09:32", 73.7, 74.0, 73.6, 73.9),
        _bar("2026-09-11 09:33", 73.9, 74.3, 73.8, 74.1),
        _bar("2026-09-11 09:34", 74.1, 74.2, 74.0, 74.1),
        _bar("2026-09-11 09:35", 74.1, 74.2, 73.9, 73.9),
    ]
    rows = [_bar("2026-09-11 09:35", 84.628, 84.629, 73.4, 73.9)]

    gated, events = apply_hk_minute_phantom_gate(
        rows,
        symbol="03690",
        timeframe="5m",
        day_rows=day_rows,
        one_min_rows=one_min,
    )

    bar = gated[0]
    assert bar["open"] == 74.0
    assert bar["high"] == 74.3
    assert bar["low"] == 73.4
    high_event = next(event for event in events if event.field == "high")
    assert high_event.source == "from_1m"
    assert high_event.after == 74.3


def test_tail_low_phantom_repaired_from_one_minute() -> None:
    """00175 2026-09-04 尾根 low=16.45（越界 4.7%）→ 用 1m 成分重聚合为真实低点。"""
    day_rows = [_day("2026-09-04", 17.42, 17.66, 17.26, 17.28)]
    one_min = [
        _bar("2026-09-04 15:56", 17.35, 17.4, 17.26, 17.3),
        _bar("2026-09-04 15:57", 17.3, 17.34, 17.27, 17.31),
        _bar("2026-09-04 15:58", 17.31, 17.33, 17.28, 17.3),
        _bar("2026-09-04 15:59", 17.3, 17.32, 17.27, 17.3),
        _bar("2026-09-04 16:00", 17.3, 17.32, 17.28, 17.28),
    ]
    rows = [_bar("2026-09-04 16:00", 17.32, 17.33, 16.45, 17.28)]

    gated, events = apply_hk_minute_phantom_gate(
        rows,
        symbol="00175",
        timeframe="5m",
        day_rows=day_rows,
        one_min_rows=one_min,
    )

    bar = gated[0]
    assert bar["low"] == 17.26
    assert bar["close"] == 17.28
    low_event = next(event for event in events if event.field == "low")
    assert low_event.changed and low_event.source == "from_1m"
    assert low_event.position == "tail"


def test_tail_low_phantom_without_one_minute_uses_conservative_bound() -> None:
    day_rows = [_day("2026-09-04", 17.42, 17.66, 17.26, 17.28)]
    rows = [_bar("2026-09-04 16:00", 17.32, 17.33, 16.45, 17.28)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="00175", timeframe="5m", day_rows=day_rows
    )

    bar = gated[0]
    assert bar["low"] == 17.28
    assert bar["close"] == 17.28
    low_event = next(event for event in events if event.field == "low")
    assert low_event.source == "anchored"


def test_mid_phantom_repaired_conservatively() -> None:
    """09988 2026-07-23 11:10：盘中 high=118.062（+2.6%）→ 保守界 max(O, L, C)。"""
    day_rows = [_day("2026-07-23", 114.1, 115.1, 110.5, 114.9)]
    rows = [_bar("2026-07-23 11:10", 114.1, 118.062, 113.8, 114.0)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="09988", timeframe="5m", day_rows=day_rows
    )

    bar = gated[0]
    assert bar["high"] == 114.1
    high_event = next(event for event in events if event.field == "high")
    assert high_event.position == "mid"
    assert high_event.changed


def test_soft_violation_logged_but_not_changed() -> None:
    """轻微越界（<0.5%）只记录 soft，不改数据。"""
    day_rows = [_day("2026-09-04", 17.42, 17.66, 17.26, 17.28)]
    rows = [_bar("2026-09-04 11:00", 17.5, 17.58, 17.2, 17.5)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="00175", timeframe="1m", day_rows=day_rows
    )

    assert gated[0]["low"] == 17.2
    assert len(events) == 1
    assert events[0].changed is False
    assert events[0].reason == "beyond_day_range_soft"


def test_real_gap_day_first_bar_untouched() -> None:
    """真实跳空开盘：首根 open=日线 open，high 即日线 high，不应产生任何事件。"""
    day_rows = [_day("2026-09-08", 20.0, 21.0, 19.8, 20.5)]
    rows = [_bar("2026-09-08 09:31", 20.0, 21.0, 19.8, 20.4)]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="00175", timeframe="1m", day_rows=day_rows
    )

    assert events == []
    assert gated[0] == {"ts": "2026-09-08 09:31", "open": 20.0, "high": 21.0, "low": 19.8, "close": 20.4, "volume": 1000}


def test_gate_is_idempotent() -> None:
    day_rows = [_day("2026-09-11", 74.0, 75.6, 73.4, 75.1)]
    rows = [_bar("2026-09-11 09:31", 84.628, 84.629, 73.4, 73.7)]

    once, _ = apply_hk_minute_phantom_gate(
        rows, symbol="03690", timeframe="1m", day_rows=day_rows
    )
    twice, events = apply_hk_minute_phantom_gate(
        once, symbol="03690", timeframe="1m", day_rows=day_rows
    )

    assert events == []
    assert twice == once


def test_missing_day_anchor_keeps_rows_unchanged() -> None:
    rows = [_bar("2026-09-11 09:31", 84.628, 84.629, 73.4, 73.7)]
    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="03690", timeframe="1m", day_rows=[]
    )
    assert events == []
    assert gated == rows


def test_day_without_bar_is_skipped() -> None:
    """窗口里早于锚定日线的日期不参与（无日线锚）。"""
    day_rows = [_day("2026-09-11", 74.0, 75.6, 73.4, 75.1)]
    rows = [
        _bar("2026-09-10 09:31", 999.0, 999.0, 998.0, 998.5),
        _bar("2026-09-11 09:31", 84.628, 84.629, 73.4, 73.7),
    ]

    gated, events = apply_hk_minute_phantom_gate(
        rows, symbol="03690", timeframe="1m", day_rows=day_rows
    )

    assert gated[0]["open"] == 999.0
    assert gated[1]["open"] == 74.0
    assert all(event.ts.startswith("2026-09-11") for event in events)


def test_run_hk_phantom_gate_reads_store_anchor_and_one_minute(tmp_path: Path) -> None:
    """端到端（tmp store）：日线锚 + 1m 成分从仓库读取，5m 越界 high 聚合修复。"""
    store = tmp_path / "store"
    sym_dir = store / "HK" / "03690"
    sym_dir.mkdir(parents=True)

    def write(name: str, rows: list[dict]) -> None:
        with (sym_dir / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["ts", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerows(rows)

    write("day.csv", [_day("2026-09-11", 74.0, 75.6, 73.4, 75.1)])
    write(
        "1m.csv",
        [
            _bar("2026-09-11 09:31", 74.0, 74.0, 73.4, 73.7),
            _bar("2026-09-11 09:32", 73.7, 74.0, 73.6, 73.9),
            _bar("2026-09-11 09:33", 73.9, 74.3, 73.8, 74.1),
            _bar("2026-09-11 09:34", 74.1, 74.2, 74.0, 74.1),
            _bar("2026-09-11 09:35", 74.1, 74.2, 73.9, 73.9),
        ],
    )

    rows = [_bar("2026-09-11 09:35", 84.628, 84.629, 73.4, 73.9)]
    gated, summary = run_hk_phantom_gate(
        "03690", "5m", rows, store_root=store
    )

    assert summary["applied"] is True
    assert summary["repaired"] >= 2
    assert gated[0]["open"] == 74.0
    assert gated[0]["high"] == 74.3


def test_run_hk_phantom_gate_skips_without_day_anchor(tmp_path: Path) -> None:
    rows = [_bar("2026-09-11 09:31", 84.628, 84.629, 73.4, 73.7)]
    gated, summary = run_hk_phantom_gate("03690", "1m", rows, store_root=tmp_path)
    assert summary["applied"] is False
    assert summary["skipped"] == "no_day_anchor"
    assert gated == rows
