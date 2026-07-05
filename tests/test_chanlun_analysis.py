from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.analysis import analyze_chanlun_signals, build_lower_timeframe_precision_entry, build_signal_point_payloads, build_signal_summary_fields, build_structure_state
from chanlun.models import Bi, BiDirection, Zhongshu
from chanlun.zhongshu import identify_zhongshu


def _zhongshu(zs_id: int, *, zs_low: float, zs_high: float, day: int) -> Zhongshu:
    start_ts = datetime(2026, 5, day, 10, 30)
    end_ts = datetime(2026, 5, day + 1, 14, 30)
    return Zhongshu(
        zs_id=zs_id,
        start_bi_id=zs_id * 10,
        end_bi_id=zs_id * 10 + 2,
        zs_low=zs_low,
        zs_high=zs_high,
        peak_low=zs_low - 0.5,
        peak_high=zs_high + 0.5,
        start_ts=start_ts,
        end_ts=end_ts,
        bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
    )


def _bi(bi_id: int, direction: BiDirection, *, high: float, low: float, day: int) -> Bi:
    start_ts = datetime(2026, 5, day, 10, 30)
    end_ts = datetime(2026, 5, day, 14, 30)
    return Bi(
        bi_id=bi_id,
        direction=direction,
        start_fx_id=bi_id,
        end_fx_id=bi_id + 1,
        start_ts=start_ts,
        end_ts=end_ts,
        high=high,
        low=low,
        norm_bar_range=(bi_id, bi_id + 1),
        is_confirmed=True,
    )


def test_build_structure_state_single_zhongshu_is_range_ongoing() -> None:
    state = build_structure_state([], [_zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)])

    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_two_non_overlapping_zhongshus_is_up_ongoing() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.2, day=4),
    ]

    state = build_structure_state([], zhongshus)

    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["zs_count_so_far"] == 2
    assert state["last_completed"] is None
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_single_zhongshu_extension_stays_range_ongoing() -> None:
    zhongshu = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    raw_bars = [SimpleNamespace(ts=datetime(2026, 5, 10, 14, 30))]

    state = build_structure_state(raw_bars, [zhongshu])

    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["current_ongoing"]["latest_ts"] == "2026-05-10T14:30:00"
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_three_non_overlapping_up_zhongshus_extend_same_trend() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4),
        _zhongshu(3, zs_low=12.4, zs_high=13.0, day=7),
    ]

    state = build_structure_state([], zhongshus)

    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 3
    assert state["last_completed"] is None
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_up_then_overlapping_return_becomes_new_range_ongoing() -> None:
    first = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    second = _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4)
    third = _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7)
    second.is_terminated = True
    second.exit_bi_id = 29
    zhongshus = [first, second, third]

    state = build_structure_state([], zhongshus)

    assert state["last_completed"] is not None
    assert state["last_completed"]["type"] == "up"
    assert state["last_completed"]["status"] == "completed"
    assert state["last_completed"]["zs_count"] == 2
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"


def test_build_structure_state_unterminated_trend_tail_overlap_stays_same_trend_ongoing() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4),
        _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7),
    ]

    state = build_structure_state([], zhongshus)

    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 3
    assert state["current_ongoing"]["confirmation_basis"] == "forming_next_same_level_zhongshu"
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_terminated_tail_may_still_be_higher_level_expansion() -> None:
    first = _zhongshu(1, zs_low=12.0, zs_high=13.0, day=1)
    second = _zhongshu(2, zs_low=10.5, zs_high=11.5, day=4)
    third = _zhongshu(3, zs_low=10.7, zs_high=11.4, day=7)
    second.is_terminated = True
    second.exit_bi_id = 29
    second.superseded_by_zs_id = third.zs_id
    second.is_reabsorbed_by_larger_expansion = True

    state = build_structure_state([], [first, second, third])

    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "down"
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_auto_detects_reabsorbed_tail_from_identified_zhongshus() -> None:
    first = _zhongshu(100, zs_low=105.0, zs_high=106.0, day=1)
    bis = [
        _bi(0, BiDirection.DOWN, high=110.0, low=98.0, day=1),
        _bi(1, BiDirection.UP, high=106.0, low=100.0, day=2),
        _bi(2, BiDirection.DOWN, high=104.0, low=101.0, day=3),
        _bi(3, BiDirection.UP, high=103.0, low=102.0, day=4),
        _bi(4, BiDirection.DOWN, high=102.0, low=96.0, day=5),
        _bi(5, BiDirection.UP, high=102.5, low=101.5, day=6),
        _bi(6, BiDirection.DOWN, high=102.3, low=101.8, day=7),
        _bi(7, BiDirection.UP, high=102.8, low=101.7, day=8),
        _bi(8, BiDirection.DOWN, high=102.1, low=95.0, day=9),
    ]

    zhongshus = [first, *identify_zhongshu(bis)]
    state = build_structure_state([], zhongshus)

    assert len(zhongshus) == 3
    assert zhongshus[1].is_reabsorbed_by_larger_expansion is True
    assert zhongshus[1].superseded_by_zs_id == zhongshus[2].zs_id
    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "down"
    assert state["relationship"]["kind"] == "undetermined"
    assert state["current_structure_status"] == "ongoing_same_type"


def test_build_structure_state_range_then_non_overlapping_up_marks_previous_range_completed() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=10.4, zs_high=10.9, day=4),
        _zhongshu(3, zs_low=11.5, zs_high=12.2, day=7),
    ]

    state = build_structure_state([], zhongshus)

    assert state["last_completed"] is not None
    assert state["last_completed"]["type"] == "range"
    assert state["last_completed"]["status"] == "completed"
    assert state["last_completed"]["zs_count"] == 1
    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 2
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["current_structure_status"] == "completed_then_new_type"


def test_build_signal_summary_fields_preserves_catalog_slots() -> None:
    payload = build_signal_summary_fields(
        {
            "buy_points": ["buy_1"],
            "sell_points": [],
            "signal_points": [{"point": "buy1", "active": True, "time": "2026-05-01T10:30:00", "price": 10.2, "basis": "x"}],
            "signal_catalog": [
                {"point": "buy1", "active": True, "time": "2026-05-01T10:30:00", "price": 10.2, "basis": "x"},
                {"point": "buy2", "active": False, "time": None, "price": None, "basis": None},
                {"point": "buy3", "active": False, "time": None, "price": None, "basis": None},
                {"point": "sell1", "active": False, "time": None, "price": None, "basis": None},
                {"point": "sell2", "active": False, "time": None, "price": None, "basis": None},
                {"point": "sell3", "active": False, "time": None, "price": None, "basis": None},
            ],
            "structure_state": {"current_ongoing": {"type": "range"}},
            "divergence": {"trend": {"active": False}},
        }
    )

    assert payload["buy_points"] == ["buy1"]
    assert payload["signal_points"][0]["point"] == "buy1"
    assert len(payload["signal_catalog"]) == 6


def test_build_signal_point_payloads_include_related_structure() -> None:
    current_zs = _zhongshu(3, zs_low=10.0, zs_high=11.0, day=6)
    latest_down = _bi(21, BiDirection.DOWN, high=11.1, low=10.2, day=8)

    signal_points, signal_catalog = build_signal_point_payloads(
        buy_points=["buy_1"],
        sell_points=[],
        latest_confirmed_up=None,
        latest_up=None,
        latest_down=latest_down,
        current_zs=current_zs,
    )

    assert signal_points[0]["signal_bi_id"] == 21
    assert signal_points[0]["related_zs_id"] == 3
    assert signal_points[0]["related_bi_ids"] == current_zs.bi_ids
    assert signal_catalog[0]["related_zs_id"] == 3
    assert signal_catalog[1]["related_bi_ids"] == []


def test_analyze_chanlun_signals_flags_second_buy_after_buy1_rebound() -> None:
    current_zs = _zhongshu(4, zs_low=10.2, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=10),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=11),
        _bi(3, BiDirection.DOWN, high=11.0, low=10.0, day=12),
        _bi(4, BiDirection.UP, high=11.3, low=10.3, day=13),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 14, 10, 30),
            end_ts=datetime(2026, 5, 14, 14, 30),
            high=11.1,
            low=10.4,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_2" in signals["buy_points"]
    assert signals["signal_catalog"][1]["active"] is True
    assert signals["signal_catalog"][1]["basis"] == "buy1_pullback_confirmation"


def test_analyze_chanlun_signals_flags_second_sell_after_sell1_rebound() -> None:
    current_zs = _zhongshu(5, zs_low=10.2, zs_high=10.8, day=15)
    bis = [
        _bi(11, BiDirection.UP, high=10.6, low=10.1, day=15),
        _bi(12, BiDirection.DOWN, high=10.5, low=10.0, day=16),
        _bi(13, BiDirection.UP, high=11.0, low=10.2, day=17),
        _bi(14, BiDirection.DOWN, high=10.4, low=9.8, day=18),
        Bi(
            bi_id=15,
            direction=BiDirection.UP,
            start_fx_id=15,
            end_fx_id=16,
            start_ts=datetime(2026, 5, 19, 10, 30),
            end_ts=datetime(2026, 5, 19, 14, 30),
            high=10.7,
            low=10.0,
            norm_bar_range=(15, 16),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=2.0, dif=0.4),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.0, dif=0.2),
        SimpleNamespace(ts=bis[4].end_ts, macd=0.8, dif=0.1),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "sell_2" in signals["sell_points"]
    assert signals["signal_catalog"][4]["active"] is True
    assert signals["signal_catalog"][4]["basis"] == "sell1_rebound_confirmation"


def test_analyze_chanlun_signals_exports_current_zhongshu_exit_time() -> None:
    current_zs = _zhongshu(6, zs_low=10.2, zs_high=10.8, day=20)
    current_zs.exit_bi_id = 42
    current_zs.is_terminated = True
    bis = [
        _bi(41, BiDirection.UP, high=10.9, low=10.3, day=20),
        _bi(42, BiDirection.DOWN, high=10.7, low=10.0, day=21),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], [])

    assert signals["current_zs_exit_bi"] is bis[1]
    assert signals["current_zs_exit_time"] == "2026-05-21T14:30:00"


def test_build_lower_timeframe_precision_entry_requires_higher_context_and_time_alignment() -> None:
    higher_signals = {
        "buy_points": ["buy_1"],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {
                "point": "buy1",
                "active": True,
                "time": "2026-05-10T14:30:00",
                "price": 10.2,
                "basis": "bottom_divergence_near_zs_low",
            }
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [
            {"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"},
            {"point": "buy1", "active": True, "time": "2026-05-10T14:10:00", "price": 10.1, "basis": "bottom_divergence_near_zs_low"},
            {"point": "buy3", "active": True, "time": "2026-05-10T15:00:00", "price": 10.3, "basis": "leave_zs_then_pullback_holds_upper_edge"},
            {"point": "sell1", "active": True, "time": "2026-05-10T15:10:00", "price": 10.4, "basis": "top_divergence_near_zs_high"},
        ],
        "signal_catalog": [
            {"point": "buy1", "active": True, "time": "2026-05-10T14:10:00", "price": 10.1, "basis": "bottom_divergence_near_zs_low"},
            {"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"},
            {"point": "buy3", "active": True, "time": "2026-05-10T15:00:00", "price": 10.3, "basis": "leave_zs_then_pullback_holds_upper_edge"},
            {"point": "sell1", "active": True, "time": "2026-05-10T15:10:00", "price": 10.4, "basis": "top_divergence_near_zs_high"},
        ],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": True, "direction": "down", "time": "2026-05-10T14:50:00"}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "actionable"
    assert entry["nested_from"]["side"] == "buy"
    assert entry["nested_from"]["window_start_time"] == "2026-05-10T14:00:00"
    assert entry["nested_from"]["window_end_time"] == "2026-05-10T14:30:00"
    assert entry["nested_from"]["window_basis"] == "current_zs_anchor_cap"
    assert entry["window_basis_label"] == "中枢到锚点窗口"
    assert entry["window_basis_description"] == "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    assert entry["nested_from"]["window_basis_label"] == "中枢到锚点窗口"
    assert entry["nested_from"]["window_basis_description"] == "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    assert entry["nested_from"]["anchor_time"] == "2026-05-10T14:30:00"
    assert entry["nested_from"]["related_zs_id"] == 9
    assert entry["nested_from"]["exit_bi_id"] == 33
    assert entry["nested_from"]["zs_is_terminated"] is False
    assert [item["point"] for item in entry["signal_points"]] == ["buy2", "buy1"]
    assert entry["buy_points"] == ["buy2", "buy1"]
    assert entry["sell_points"] == []
    assert "窗口依据：上级别离开笔尚未单独解析" in entry["note"]


def test_build_lower_timeframe_precision_entry_stays_standby_without_higher_context() -> None:
    entry = build_lower_timeframe_precision_entry(
        {"buy_points": [], "sell_points": [], "divergence": {"trend": {"active": False}, "range": {"active": False}}},
        {
            "buy_points": ["buy_2"],
            "sell_points": [],
            "signal_points": [{"point": "buy2", "active": True, "time": "2026-05-10T15:00:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
            "signal_catalog": [{"point": "buy2", "active": True, "time": "2026-05-10T15:00:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
            "structure_state": {"current_ongoing": {"type": "down"}},
            "divergence": {"trend": {"active": True, "direction": "down", "time": "2026-05-10T14:50:00"}, "range": {"active": False}},
        },
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "standby"
    assert entry["signal_points"] == []
    assert entry["nested_from"] is None


def test_build_lower_timeframe_precision_entry_ignores_divergence_outside_higher_window() -> None:
    entry = build_lower_timeframe_precision_entry(
        {
            "buy_points": ["buy_1"],
            "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0)),
            "signal_points": [
                {
                    "point": "buy1",
                    "active": True,
                    "time": "2026-05-10T14:30:00",
                    "price": 10.2,
                    "basis": "bottom_divergence_near_zs_low",
                }
            ],
            "divergence": {"trend": {"active": False}, "range": {"active": False}},
        },
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "down"}},
            "divergence": {"trend": {"active": True, "direction": "down", "time": "2026-05-10T13:50:00"}, "range": {"active": False}},
        },
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert "趋势背驰" not in entry["note"]
    assert "窗口依据：上级别离开笔尚未单独解析" in entry["note"]


def test_build_lower_timeframe_precision_entry_reports_divergence_inside_higher_window() -> None:
    entry = build_lower_timeframe_precision_entry(
        {
            "buy_points": ["buy_1"],
            "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0)),
            "signal_points": [
                {
                    "point": "buy1",
                    "active": True,
                    "time": "2026-05-10T14:30:00",
                    "price": 10.2,
                    "basis": "bottom_divergence_near_zs_low",
                }
            ],
            "divergence": {"trend": {"active": False}, "range": {"active": False}},
        },
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "down"}},
            "divergence": {"trend": {"active": True, "direction": "down", "time": "2026-05-10T14:20:00"}, "range": {"active": False}},
        },
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert "趋势背驰" in entry["note"]
    assert "窗口依据：上级别离开笔尚未单独解析" in entry["note"]


def test_build_lower_timeframe_precision_entry_falls_back_to_anchor_window_without_current_zs() -> None:
    entry = build_lower_timeframe_precision_entry(
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "divergence": {"trend": {"active": True, "direction": "down", "time": "2026-05-10T14:30:00"}, "range": {"active": False}},
        },
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "down"}},
            "divergence": {"trend": {"active": False}, "range": {"active": False}},
        },
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert entry["nested_from"]["window_basis"] == "higher_signal_anchor"
    assert entry["window_basis_label"] == "锚点跟踪窗口"
    assert entry["window_basis_description"] == "窗口依据：上级别尚无可用中枢边界，当前先按触发锚点向后跟踪区间套窗口。"
    assert entry["nested_from"]["window_start_time"] == "2026-05-10T14:30:00"
    assert entry["nested_from"]["window_end_time"] is None
    assert entry["nested_from"]["related_zs_id"] is None
    assert entry["nested_from"]["exit_bi_id"] is None
    assert entry["nested_from"]["zs_is_terminated"] is False
    assert "窗口依据：上级别尚无可用中枢边界" in entry["note"]


def test_build_lower_timeframe_precision_entry_prefers_exit_bi_time_as_window_end() -> None:
    entry = build_lower_timeframe_precision_entry(
        {
            "buy_points": ["buy_1"],
            "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=True),
            "current_zs_exit_time": "2026-05-10T14:20:00",
            "signal_points": [
                {
                    "point": "buy1",
                    "active": True,
                    "time": "2026-05-10T14:30:00",
                    "price": 10.2,
                    "basis": "bottom_divergence_near_zs_low",
                }
            ],
            "divergence": {"trend": {"active": False}, "range": {"active": False}},
        },
        {
            "buy_points": ["buy_2"],
            "sell_points": [],
            "signal_points": [
                {"point": "buy1", "active": True, "time": "2026-05-10T14:10:00", "price": 10.1, "basis": "bottom_divergence_near_zs_low"},
                {"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"},
            ],
            "signal_catalog": [
                {"point": "buy1", "active": True, "time": "2026-05-10T14:10:00", "price": 10.1, "basis": "bottom_divergence_near_zs_low"},
                {"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"},
            ],
            "structure_state": {"current_ongoing": {"type": "down"}},
            "divergence": {"trend": {"active": False}, "range": {"active": False}},
        },
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["nested_from"]["window_start_time"] == "2026-05-10T14:00:00"
    assert entry["nested_from"]["window_end_time"] == "2026-05-10T14:20:00"
    assert entry["nested_from"]["window_basis"] == "current_zs_exit_bi"
    assert entry["window_basis_label"] == "离开笔窗口"
    assert entry["window_basis_description"] == "窗口依据：上级别已确认离开笔，当前按中枢结束至离开笔完成时间收缩区间套窗口。"
    assert [item["point"] for item in entry["signal_points"]] == ["buy1"]
    assert "窗口依据：上级别已确认离开笔" in entry["note"]