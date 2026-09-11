"""缠论分析层综合测试。spec_id: SPEC.CHANLUN.THEORY / SPEC.CHANLUN.RULE / SPEC.TREND_DIVERGENCE.CORE / SPEC.BUY_SELL.CORE。"""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.analysis import _build_zs_monitor_state, analyze_chanlun_signals, build_lower_timeframe_precision_entry, build_precision_window_display, build_signal_point_payloads, build_signal_summary_fields, build_structure_state, compute_segment_strengths, derive_signal_lifecycle_transitions, replay_confirmed_signal_lifecycle, to_lifecycle_frame
from chanlun.models import Bi, BiDirection, Segment, Zhongshu
from chanlun.zhongshu import identify_zhongshu


PROBE_SPEC = importlib.util.spec_from_file_location(
    "probe_intraday_prebreak_sample",
    ROOT / "build" / "probe_intraday_prebreak_sample.py",
)
if PROBE_SPEC is None or PROBE_SPEC.loader is None:
    raise RuntimeError("failed to load probe_intraday_prebreak_sample.py for tests")
probe_module = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(probe_module)


def _zhongshu(zs_id: int, *, zs_low: float, zs_high: float, day: int) -> Zhongshu:
    start_ts = datetime(2026, 5, day, 10, 30)
    end_ts = datetime(2026, 5, day + 1, 14, 30)
    return Zhongshu(
        zs_id=zs_id,
        start_bi_id=zs_id * 10,
        end_bi_id=zs_id * 10 + 2,
        zs_low=zs_low,
        zs_high=zs_high,
        peak_low=zs_low - 0.05,
        peak_high=zs_high + 0.05,
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


def _segment(segment_id: int, direction: BiDirection, *, high: float, low: float, start_day: int) -> Segment:
    start_ts = datetime(2026, 5, start_day, 10, 30)
    end_ts = datetime(2026, 5, start_day + 1, 14, 30)
    return Segment(
        segment_id=segment_id,
        direction=direction,
        start_bi_id=segment_id * 10,
        end_bi_id=segment_id * 10 + 2,
        start_ts=start_ts,
        end_ts=end_ts,
        start_price=low if direction == BiDirection.DOWN else high,
        end_price=high if direction == BiDirection.DOWN else low,
        high=high,
        low=low,
        norm_bar_range=(segment_id * 10, segment_id * 10 + 2),
        bi_ids=[segment_id * 10, segment_id * 10 + 1, segment_id * 10 + 2],
        is_confirmed=True,
    )


def _segment_zhongshu(zs_id: int, *, entering_segment_id: int, exit_segment_id: int, zs_low: float, zs_high: float) -> Zhongshu:
    start_ts = datetime(2026, 5, 1, 10, 30)
    end_ts = datetime(2026, 5, 2, 14, 30)
    return Zhongshu(
        zs_id=zs_id,
        start_bi_id=zs_id * 10,
        end_bi_id=zs_id * 10 + 2,
        zs_low=zs_low,
        zs_high=zs_high,
        peak_low=zs_low - 0.05,
        peak_high=zs_high + 0.05,
        start_ts=start_ts,
        end_ts=end_ts,
        bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
        structure_level="segment",
        entering_bi_id=entering_segment_id,
        exit_bi_id=exit_segment_id,
    )


def test_build_structure_state_single_zhongshu_is_range_ongoing() -> None:
    state = build_structure_state([], [_zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)])

    assert state["last_completed"] is None
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["current_structure_status"] == "ongoing_same_type"
    assert state["consumption_level"] == "pending"


def test_build_structure_state_without_same_level_zhongshu_is_auxiliary_only() -> None:
    state = build_structure_state([], [])

    assert state["current_ongoing"]["confirmation_basis"] == "no_same_level_zhongshu"
    assert state["consumption_level"] == "auxiliary"


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
    assert state["relationship"]["transition_state"] == "candidate_new_type"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"
    assert state["consumption_level"] == "pending"


def test_build_structure_state_type_chain_matches_last_completed_and_ongoing() -> None:
    first = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    second = _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4)
    third = _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7)
    second.is_terminated = True
    second.exit_bi_id = 29

    state = build_structure_state([], [first, second, third])

    assert state["type_chain"] == [
        {"type": "up", "status": "completed", "zs_count": 2, "start_zs_id": 1, "end_zs_id": 2, "start_ts": "2026-05-01T10:30:00", "end_ts": "2026-05-05T14:30:00"},
        {"type": "range", "status": "ongoing", "zs_count": 1, "start_zs_id": 3, "end_zs_id": 3, "start_ts": "2026-05-07T10:30:00", "end_ts": None},
    ]


def test_build_structure_state_type_chain_single_and_empty() -> None:
    empty_state = build_structure_state([], [])
    assert empty_state["type_chain"] == []

    single_state = build_structure_state([], [_zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)])
    assert single_state["type_chain"] == [
        {"type": "range", "status": "ongoing", "zs_count": 1, "start_zs_id": 1, "end_zs_id": 1, "start_ts": "2026-05-01T10:30:00", "end_ts": None},
    ]


def test_build_structure_state_type_chain_folds_multiple_completed_runs() -> None:
    """TD1 严格同级别分解：全部检出中枢都参与分解（扩张重吸收标记被忽略）。

    relations = [up, up, down, down, range, up]，唯一切分为 up（zs1..zs3）→
    down（zs4..zs5）→ up（zs6..zs7 ongoing）三个走势类型块；last_completed 指向
    最近的 completed 块（down）。
    """
    up1 = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    up2 = _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4)
    up2.is_terminated = True
    # 旧扩张重吸收标记：严格同级别分解不再据此裁剪，中枢仍参与走势类型分解。
    sep1 = _zhongshu(3, zs_low=12.5, zs_high=13.0, day=7)
    sep1.superseded_by_zs_id = 4
    sep1.is_reabsorbed_by_larger_expansion = True
    down1 = _zhongshu(4, zs_low=9.0, zs_high=9.4, day=10)
    down2 = _zhongshu(5, zs_low=8.5, zs_high=8.8, day=13)
    down2.is_terminated = True
    sep2 = _zhongshu(6, zs_low=8.2, zs_high=8.6, day=16)
    sep2.superseded_by_zs_id = 7
    sep2.is_reabsorbed_by_larger_expansion = True
    rng = _zhongshu(7, zs_low=10.0, zs_high=10.5, day=19)

    state = build_structure_state([], [up1, up2, sep1, down1, down2, sep2, rng])

    assert state["type_chain"] == [
        {"type": "up", "status": "completed", "zs_count": 3, "start_zs_id": 1, "end_zs_id": 3, "start_ts": "2026-05-01T10:30:00", "end_ts": "2026-05-08T14:30:00"},
        {"type": "down", "status": "completed", "zs_count": 2, "start_zs_id": 4, "end_zs_id": 5, "start_ts": "2026-05-10T10:30:00", "end_ts": "2026-05-14T14:30:00"},
        {"type": "up", "status": "ongoing", "zs_count": 2, "start_zs_id": 6, "end_zs_id": 7, "start_ts": "2026-05-16T10:30:00", "end_ts": None},
    ]
    assert state["last_completed"]["type"] == "down"
    assert state["last_completed"]["zs_count"] == 2
    assert state["last_completed"]["status"] == "completed"
    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["confirmation_basis"] == "forming_next_same_level_zhongshu"
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["relationship"]["transition_state"] == "ongoing_new_type"


def test_build_structure_state_type_chain_enumerates_in_run_type_switches() -> None:
    """Stage 2：单 run 内多段类型切换（up→range→up）应完整展开进 type_chain 前缀。

    relations = [up, range, range, up, up, up]；ongoing 为末尾 up 段（zs4..zs7），
    completed 前缀应包含 up（zs1..zs2）与 range（zs2..zs3）两段。
    """
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4),
        _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7),
        _zhongshu(4, zs_low=11.6, zs_high=12.2, day=10),
        _zhongshu(5, zs_low=12.5, zs_high=13.0, day=13),
        _zhongshu(6, zs_low=13.2, zs_high=13.7, day=16),
        _zhongshu(7, zs_low=13.9, zs_high=14.4, day=19),
    ]

    state = build_structure_state([], zhongshus)

    assert state["type_chain"] == [
        {"type": "up", "status": "completed", "zs_count": 2, "start_zs_id": 1, "end_zs_id": 2, "start_ts": "2026-05-01T10:30:00", "end_ts": "2026-05-05T14:30:00"},
        {"type": "range", "status": "completed", "zs_count": 1, "start_zs_id": 3, "end_zs_id": 3, "start_ts": "2026-05-07T10:30:00", "end_ts": "2026-05-08T14:30:00"},
        {"type": "up", "status": "ongoing", "zs_count": 4, "start_zs_id": 4, "end_zs_id": 7, "start_ts": "2026-05-10T10:30:00", "end_ts": None},
    ]
    assert state["last_completed"]["type"] == "range"
    assert state["last_completed"]["start_zs_id"] == 3
    assert state["last_completed"]["end_zs_id"] == 3


def test_build_structure_state_decomposition_selector_unique() -> None:
    """single_confirmed 时不产生选择器替代方案。"""
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4),
        _zhongshu(3, zs_low=12.4, zs_high=13.0, day=7),
    ]

    state = build_structure_state([], zhongshus)

    selector = state["decomposition_selector"]
    assert selector["mode"] == "single_confirmed"
    assert selector["alternatives"] == []
    assert selector["selected"] is None


def test_build_structure_state_decomposition_selector_candidate_new_type() -> None:
    """candidate_new_type 是「确认待定」而非「多解」：同级别分解具唯一性，无替代方案。"""
    zs1 = _zhongshu(1, zs_low=10.0, zs_high=12.0, day=1)
    sep = _zhongshu(2, zs_low=12.2, zs_high=12.5, day=4)
    sep.superseded_by_zs_id = 3
    sep.is_reabsorbed_by_larger_expansion = True
    zs2 = _zhongshu(3, zs_low=10.5, zs_high=11.8, day=7)

    state = build_structure_state([], [zs1, sep, zs2])

    assert state["relationship"]["transition_state"] == "candidate_new_type"
    selector = state["decomposition_selector"]
    assert selector["mode"] == "dual_interpretation_pending"
    assert selector["alternatives"] == []
    assert selector["selected"] is None
    assert "新类型候选" in selector["selection_reason"]


def test_build_structure_state_decomposition_selector_single_zhongshu_pending() -> None:
    """单中枢（无前段）的 dual_interpretation_pending 亦无多解可选。"""
    state = build_structure_state([], [_zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)])

    selector = state["decomposition_selector"]
    assert selector["mode"] == "dual_interpretation_pending"
    assert selector["alternatives"] == []
    assert selector["selected"] is None
    assert "确认待定" in selector["selection_reason"]


def test_analyze_chanlun_signals_marks_single_zhongshu_as_dual_interpretation_pending() -> None:
    raw_bars = [SimpleNamespace(ts=datetime(2026, 5, 2, 14, 30), close=10.2)]

    signals = analyze_chanlun_signals(
        raw_bars,
        [],
        [_zhongshu(1, zs_low=10.0, zs_high=10.4, day=1)],
        [],
    )

    assert signals["same_level_decomposition_mode"] == "dual_interpretation_pending"


def test_build_signal_summary_fields_keeps_missing_consumption_level_as_none() -> None:
    summary = build_signal_summary_fields({
        "buy_points": [],
        "sell_points": [],
        "signal_points": [],
        "signal_catalog": [],
        "same_level_consumption_level": None,
    })

    assert summary["same_level_consumption_level"] is None
    assert summary["same_level_consumption_level_label"] is None
    assert summary["same_level_consumption_level_note"] is None


def test_build_structure_state_unterminated_trend_tail_overlap_stays_same_trend_ongoing() -> None:
    """严格同级别分解：上涨趋势后出现重叠中枢，则趋势完成、重叠中枢另起一个盘整。

    zs1->zs2 同向不重叠=上涨趋势（已完成）；zs3 与 zs2 重叠→ 新盘整（ongoing），
    不再归为同趋势延伸（§8.2：重叠中枢=独立盘整）。
    """
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4),
        _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7),
    ]

    state = build_structure_state([], zhongshus)

    assert state["last_completed"]["type"] == "up"
    assert state["last_completed"]["zs_count"] == 2
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["status"] == "ongoing"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["relationship"]["transition_state"] == "candidate_new_type"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"


def test_build_structure_state_terminated_tail_may_still_be_higher_level_expansion() -> None:
    """严格同级别分解：扩张重吸收标记被忽略，中枢仍参与分解。

    first->second 同向下跌不重叠=下跌趋势（已完成）；second 虽标 reabsorbed，
    但不再被裁剪；third 与 second 重叠→ 新盘整（ongoing）。
    """
    first = _zhongshu(1, zs_low=12.0, zs_high=13.0, day=1)
    second = _zhongshu(2, zs_low=10.5, zs_high=11.5, day=4)
    third = _zhongshu(3, zs_low=10.7, zs_high=11.4, day=7)
    second.is_terminated = True
    second.exit_bi_id = 29
    second.superseded_by_zs_id = third.zs_id
    second.is_reabsorbed_by_larger_expansion = True

    state = build_structure_state([], [first, second, third])

    assert state["last_completed"]["type"] == "down"
    assert state["last_completed"]["zs_count"] == 2
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"


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
    # 严格同级别分解忽略 reabsorbed 标记，三个重叠中枢各自独立成盘整。
    assert [entry["type"] for entry in state["type_chain"]] == ["range", "range", "range"]
    assert state["last_completed"]["type"] == "range"
    assert state["last_completed"]["start_zs_id"] == zhongshus[1].zs_id
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["start_zs_id"] == zhongshus[2].zs_id
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"


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
    assert state["relationship"]["transition_state"] == "ongoing_new_type"
    assert state["current_structure_status"] == "completed_then_new_type"
    assert state["consumption_level"] == "confirmed"


def test_build_structure_state_without_completed_predecessor_keeps_transition_state_none() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.2, day=4),
    ]

    state = build_structure_state([], zhongshus)

    assert state["last_completed"] is None
    assert state["relationship"]["kind"] == "undetermined"
    assert state["relationship"]["transition_state"] == "none"


def test_build_structure_state_ignores_reabsorbed_ghost_zhongshu_in_current_group() -> None:
    first = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    second = _zhongshu(2, zs_low=10.4, zs_high=10.9, day=4)
    third = _zhongshu(3, zs_low=11.5, zs_high=12.2, day=7)
    second.is_terminated = True
    second.is_reabsorbed_by_larger_expansion = True
    second.superseded_by_zs_id = third.zs_id

    state = build_structure_state([], [first, second, third])

    # 严格同级别分解：reabsorbed 标记被忽略，second 仍参与分解（与 third 同向不重叠=上涨）。
    assert state["last_completed"] is not None
    assert state["last_completed"]["type"] == "range"
    assert state["last_completed"]["start_zs_id"] == first.zs_id
    assert state["last_completed"]["end_zs_id"] == first.zs_id
    assert state["current_ongoing"]["type"] == "up"
    assert state["current_ongoing"]["start_zs_id"] == second.zs_id
    assert state["current_ongoing"]["end_zs_id"] == third.zs_id
    assert state["current_ongoing"]["zs_count_so_far"] == 2
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["relationship"]["transition_state"] == "ongoing_new_type"
    assert state["current_structure_status"] == "completed_then_new_type"


def test_analyze_chanlun_signals_marks_stable_new_type_as_single_confirmed() -> None:
    raw_bars = [SimpleNamespace(ts=datetime(2026, 5, 9, 14, 30), close=11.9)]
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=10.4, zs_high=10.9, day=4),
        _zhongshu(3, zs_low=11.5, zs_high=12.2, day=7),
    ]

    signals = analyze_chanlun_signals(raw_bars, [], zhongshus, [])

    assert signals["same_level_decomposition_mode"] == "single_confirmed"
    assert signals["same_level_consumption_level"] == "confirmed"


def test_analyze_chanlun_signals_marks_range_divergence_as_higher_level_range() -> None:
    current_zs = _zhongshu(10, zs_low=10.0, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=10),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=11),
        _bi(3, BiDirection.UP, high=11.0, low=10.3, day=12),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=4.0, dif=1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=2.0, dif=0.8),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["divergence"]["range"]["active"] is True
    assert signals["post_divergence_route"] == "higher_level_range"

    range_div = signals["divergence"]["range"]
    assert range_div["strict"] is True
    assert range_div["reference_zs_id"] == 10
    assert range_div["touches_boundary"] is True
    assert range_div["strength_comparison"]["candidate_bi_id"] == 3
    assert range_div["strength_comparison"]["reference_bi_id"] == 1
    assert range_div["strength_comparison"]["decayed"] is True


def test_analyze_chanlun_signals_range_divergence_without_touching_boundary_is_not_strict() -> None:
    current_zs = _zhongshu(10, zs_low=10.0, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.UP, high=10.5, low=10.2, day=10),
        _bi(2, BiDirection.DOWN, high=10.4, low=10.1, day=11),
        _bi(3, BiDirection.UP, high=10.6, low=10.3, day=12),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=4.0, dif=1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=2.0, dif=0.8),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    range_div = signals["divergence"]["range"]
    assert range_div["active"] is True
    assert range_div["strict"] is False
    assert range_div["touches_boundary"] is False
    assert signals["post_divergence_route"] == "last_zs_extension"


def test_analyze_chanlun_signals_marks_trend_divergence_as_higher_level_reverse_trend() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.2, day=4),
    ]
    bis = [
        _bi(10, BiDirection.UP, high=12.0, low=11.3, day=4),
        _bi(11, BiDirection.DOWN, high=11.8, low=11.4, day=5),
        _bi(12, BiDirection.UP, high=12.6, low=11.6, day=6),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=0.9),
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points)

    assert signals["divergence"]["trend"]["active"] is True
    assert signals["post_divergence_route"] == "higher_level_reverse_trend"

    trend = signals["divergence"]["trend"]
    assert trend["strict"] is True
    assert trend["reference_zs_id"] == 2
    assert trend["departure_confirmed"] is True
    assert trend["strength_comparison"]["candidate_bi_id"] == 12
    assert trend["strength_comparison"]["reference_bi_id"] == 10
    assert trend["strength_comparison"]["decayed"] is True


def test_analyze_chanlun_signals_trend_divergence_without_departure_confirmation_is_not_strict() -> None:
    zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.2, day=4),
    ]
    bis = [
        _bi(10, BiDirection.UP, high=12.0, low=11.3, day=4),
        _bi(11, BiDirection.DOWN, high=11.8, low=11.4, day=5),
        _bi(12, BiDirection.UP, high=12.1, low=11.6, day=6),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=0.9),
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points)

    trend = signals["divergence"]["trend"]
    assert trend["active"] is True
    assert trend["strict"] is False
    assert trend["departure_confirmed"] is False
    assert signals["post_divergence_route"] == "last_zs_extension"


def test_analyze_chanlun_signals_trend_and_range_divergence_tracks_are_mutually_exclusive() -> None:
    """趋势 vs 盘整分轨互斥：同一次信号不会同时 active trend 与 range。

    TD2/TD3 通过 `ongoing_type` 分轨（up/down -> trend 轨，range -> range 轨），
    不允许同一结构同时落入两条背驰判定轨（TD5 第五条「趋势 vs 盘整分轨」案例）。
    """
    # 趋势轨：ongoing_type=up + top_divergence
    trend_zhongshus = [
        _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1),
        _zhongshu(2, zs_low=11.5, zs_high=12.2, day=4),
    ]
    trend_bis = [
        _bi(10, BiDirection.UP, high=12.0, low=11.3, day=4),
        _bi(11, BiDirection.DOWN, high=11.8, low=11.4, day=5),
        _bi(12, BiDirection.UP, high=12.6, low=11.6, day=6),
    ]
    trend_macd = [
        SimpleNamespace(ts=trend_bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=trend_bis[2].end_ts, macd=3.0, dif=0.9),
    ]
    trend_signals = analyze_chanlun_signals([], trend_bis, trend_zhongshus, trend_macd)
    assert trend_signals["divergence"]["trend"]["active"] is True
    assert trend_signals["divergence"]["range"]["active"] is False

    # 盘整轨：ongoing_type=range + top_divergence
    range_zs = _zhongshu(10, zs_low=10.0, zs_high=10.8, day=10)
    range_bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=10),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=11),
        _bi(3, BiDirection.UP, high=11.0, low=10.3, day=12),
    ]
    range_macd = [
        SimpleNamespace(ts=range_bis[0].end_ts, macd=4.0, dif=1.0),
        SimpleNamespace(ts=range_bis[2].end_ts, macd=2.0, dif=0.8),
    ]
    range_signals = analyze_chanlun_signals([], range_bis, [range_zs], range_macd)
    assert range_signals["divergence"]["range"]["active"] is True
    assert range_signals["divergence"]["trend"]["active"] is False


def test_analyze_chanlun_signals_emits_pre_breakdown_when_close_presses_lower_zs_edge() -> None:
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.55),
        SimpleNamespace(ts=datetime(2026, 5, 2, 14, 30), close=10.08),
    ]

    signals = analyze_chanlun_signals(
        raw_bars,
        [],
        [_zhongshu(1, zs_low=10.0, zs_high=10.4, day=1)],
        [],
    )

    assert signals["zs_monitor_alert"] == "pre_breakdown"


def test_analyze_chanlun_signals_emits_pre_breakout_when_close_presses_upper_zs_edge() -> None:
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.15),
        SimpleNamespace(ts=datetime(2026, 5, 2, 14, 30), close=10.32),
    ]

    signals = analyze_chanlun_signals(
        raw_bars,
        [],
        [_zhongshu(1, zs_low=10.0, zs_high=10.4, day=1)],
        [],
    )

    assert signals["zs_monitor_alert"] == "pre_breakout"


def test_build_zs_monitor_state_keeps_pre_breakout_when_buy3_exists_but_same_level_is_pending() -> None:
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.15),
        SimpleNamespace(ts=datetime(2026, 5, 2, 14, 30), close=10.32),
    ]
    monitor_state = _build_zs_monitor_state(
        raw_bars,
        _zhongshu(1, zs_low=10.0, zs_high=10.4, day=1),
        buy_points=["buy_3"],
        sell_points=[],
    )

    assert monitor_state["zs_monitor_bias"] == "strong"
    assert monitor_state["zs_monitor_alert"] == "pre_breakout"


def test_analyze_chanlun_signals_emits_down_bias_when_latest_up_strength_weakens_inside_zs() -> None:
    zhongshus = [_zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)]
    bis = [
        _bi(10, BiDirection.UP, high=10.9, low=10.0, day=2),
        _bi(11, BiDirection.DOWN, high=10.7, low=10.2, day=3),
        _bi(12, BiDirection.UP, high=11.0, low=10.3, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=2.31, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=1.10, dif=-0.6),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.89, dif=0.8),
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points)

    assert signals["oscillation_rhythm_state"] == "down_bias"


def test_analyze_chanlun_signals_emits_balanced_rhythm_when_latest_same_direction_ratio_is_neutral() -> None:
    zhongshus = [_zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)]
    bis = [
        _bi(20, BiDirection.UP, high=10.9, low=10.0, day=2),
        _bi(21, BiDirection.DOWN, high=10.7, low=10.2, day=3),
        _bi(22, BiDirection.UP, high=11.0, low=10.3, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=1.94, dif=0.9),
        SimpleNamespace(ts=bis[1].end_ts, macd=1.20, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.99, dif=0.92),
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points)

    assert signals["oscillation_rhythm_state"] == "balanced"


def test_build_signal_summary_fields_includes_zs_monitor_alert() -> None:
    payload = build_signal_summary_fields(
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "range"}},
            "same_level_decomposition_mode": "dual_interpretation_pending",
            "post_divergence_route": "higher_level_range",
            "oscillation_rhythm_state": "down_bias",
            "divergence": {"trend": {"active": False}},
            "zs_monitor_alert": "pre_breakout",
        }
    )

    assert payload["zs_monitor_alert"] == "pre_breakout"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["post_divergence_route"] == "higher_level_range"
    assert payload["oscillation_rhythm_state"] == "down_bias"


def test_build_signal_summary_fields_preserves_pre_breakdown_pending_gate() -> None:
    payload = build_signal_summary_fields(
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "range"}},
            "same_level_decomposition_mode": "dual_interpretation_pending",
            "post_divergence_route": "higher_level_range",
            "oscillation_rhythm_state": "down_bias",
            "divergence": {"trend": {"active": False}},
            "zs_monitor_alert": "pre_breakdown",
        }
    )

    assert payload["zs_monitor_alert"] == "pre_breakdown"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"


def test_build_signal_summary_fields_preserves_pre_breakout_pending_gate() -> None:
    payload = build_signal_summary_fields(
        {
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "structure_state": {"current_ongoing": {"type": "range"}},
            "same_level_decomposition_mode": "dual_interpretation_pending",
            "post_divergence_route": "higher_level_reverse_trend",
            "oscillation_rhythm_state": "balanced",
            "divergence": {"trend": {"active": False}},
            "zs_monitor_alert": "pre_breakout",
        }
    )

    assert payload["zs_monitor_alert"] == "pre_breakout"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"


# 注：原 `test_real_1m_pre_breakdown_sample_preserves_independent_tech_json_gate`
# 读取过期 fixture `data/reports/000651/1m/tech.json`（generated_at 2026-08-20，内部自相矛盾），
# 已移除。同语义覆盖改由 replay gate 承担：
#   test_real_1m_pre_breakdown_replay_sample_preserves_independent_gate
# 以及 synthetic gate：test_analyze_chanlun_signals_emits_pre_breakdown_when_close_presses_lower_zs_edge
# 与 test_build_signal_summary_fields_preserves_pre_breakdown_pending_gate。


def test_real_1m_pre_breakout_replay_sample_preserves_independent_gate() -> None:
    rows = probe_module._load_rows("002555", "1m")
    payload = probe_module._replay("002555", "三七互娱", "2026-08-04 13:35", rows)

    assert payload["cutoff"] == "2026-08-04 13:35"
    assert payload["zs_monitor_alert"] == "none"
    assert payload["zs_monitor_midline"] == 20.1
    assert payload["zs_monitor_bias"] == "strong"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    # 严格一类卖点需「离开段 vs 进入段」段级顶背驰：该 cutoff 中枢尚未终结（无确认离开段 exit_bi_id），
    # 故不报 sell_1（旧笔级口径 sell_1 已被段级力度口径收紧）。
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "震荡，等待方向选择。"
    assert payload["latest_zs_low"] == 19.97
    assert payload["latest_zs_high"] == 20.24
    assert "结论：震荡，等待方向选择。" in payload["advice_text"]
    assert "离开线段：未出现。" in payload["advice_text"]
    assert "监视器：中枢中线 20.10，当前偏强，预警状态 无预警。" in payload["advice_text"]
    assert "节奏监视：节奏偏弱，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "确认三买" not in payload["advice_text"]


def test_real_1m_pre_breakout_replay_sample_03690_preserves_independent_gate() -> None:
    # 第二个真实 1m pre_breakout 锚点（非 002555），港股 03690 美团，
    # 用于降低单标偏置。与 002555 同为「无中枢 fallback 监视带 + dual_interpretation_pending」。
    rows = probe_module._load_rows("03690", "1m")
    payload = probe_module._replay("03690", "美团", "2026-08-05 09:56", rows)

    assert payload["cutoff"] == "2026-08-05 09:56"
    assert payload["zs_monitor_alert"] == "none"
    assert payload["zs_monitor_midline"] == 92.3
    assert payload["zs_monitor_bias"] == "strong"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "震荡，等待方向选择。"
    assert payload["latest_zs_low"] == 91.0
    assert payload["latest_zs_high"] == 93.6
    assert "结论：震荡，等待方向选择。" in payload["advice_text"]
    assert "监视器：中枢中线 92.30，当前偏强，预警状态 无预警。" in payload["advice_text"]
    assert "节奏监视：节奏偏弱，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "当前按三卖确认处理。" not in payload["advice_text"]


def test_real_1m_pre_breakout_replay_sample_600900_preserves_independent_gate() -> None:
    # 第三个真实 1m pre_breakout 锚点（非 002555），CN 600900 长江电力（防御/电力标的），
    # 与 002555（CN 游戏）、03690（HK 互联网）形成市场/行业多样性，继续降低单标偏置。
    rows = probe_module._load_rows("600900", "1m")
    payload = probe_module._replay("600900", "长江电力", "2026-08-04 13:18", rows)

    assert payload["cutoff"] == "2026-08-04 13:18"
    assert payload["zs_monitor_alert"] == "pre_breakdown"
    assert payload["zs_monitor_midline"] == 28.78
    assert payload["zs_monitor_bias"] == "weak"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "观察，等待确认。"
    assert payload["latest_zs_low"] == 28.71
    assert payload["latest_zs_high"] == 28.85
    assert "结论：观察，等待确认。" in payload["advice_text"]
    assert "监视器：中枢中线 28.78，当前偏弱，预警状态 向下预警。" in payload["advice_text"]
    assert "节奏监视：节奏偏强，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "确认三买" not in payload["advice_text"]


def test_real_1m_pre_breakout_replay_sample_01024_preserves_independent_gate() -> None:
    # 第四个真实 1m 回放锚点（01024 快手），用于扩展 pre_breakout 样本广度。
    # 该断言避免绑定易漂移的价位数值，重点锁 pending/watch 语义与不误升 confirmed。
    rows = probe_module._load_rows("01024", "1m")
    payload = probe_module._replay("01024", "快手", "2026-08-10 09:56", rows)

    assert payload["cutoff"] == "2026-08-10 09:56"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["zs_monitor_alert"] in {"none", "pre_breakout", "pre_breakdown"}
    assert payload["zs_monitor_bias"] in {"strong", "weak"}
    assert isinstance(payload["conclusion"], str)
    assert payload["conclusion"]
    assert "监视器：中枢中线" in payload["advice_text"]
    assert "当前按三买确认处理。" not in payload["advice_text"]


def test_real_1m_pre_breakout_replay_sample_09988_preserves_independent_gate() -> None:
    # 第五个真实 1m 回放锚点（09988 阿里巴巴），继续扩展 pre_breakout 样本广度。
    # 断言锁 pending/watch 语义，避免绑定易漂移的具体价位。
    rows = probe_module._load_rows("09988", "1m")
    payload = probe_module._replay("09988", "阿里巴巴", "2026-08-05 10:01", rows)

    assert payload["cutoff"] == "2026-08-05 10:01"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["zs_monitor_alert"] in {"none", "pre_breakout", "pre_breakdown"}
    assert payload["zs_monitor_bias"] in {"strong", "weak"}
    assert isinstance(payload["conclusion"], str)
    assert payload["conclusion"]
    assert "监视器：中枢中线" in payload["advice_text"]
    assert "当前按三买确认处理。" not in payload["advice_text"]


def test_real_1m_pre_breakout_replay_sample_00700_preserves_independent_gate() -> None:
    # 第六个真实 1m 回放锚点（00700 腾讯），补齐本轮 pre_breakout 扩样本收口。
    rows = probe_module._load_rows("00700", "1m")
    payload = probe_module._replay("00700", "腾讯", "2026-08-05 10:01", rows)

    assert payload["cutoff"] == "2026-08-05 10:01"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["zs_monitor_alert"] in {"none", "pre_breakout", "pre_breakdown"}
    assert payload["zs_monitor_bias"] in {"strong", "weak"}
    assert isinstance(payload["conclusion"], str)
    assert payload["conclusion"]
    assert "监视器：中枢中线" in payload["advice_text"]
    assert "当前按三买确认处理。" not in payload["advice_text"]


def test_real_1m_pre_breakdown_replay_sample_preserves_independent_gate() -> None:
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-07-30 10:21", rows)

    assert payload["cutoff"] == "2026-07-30 10:21"
    assert payload["zs_monitor_alert"] == "pre_breakdown"
    assert payload["zs_monitor_midline"] == 41.83
    assert payload["zs_monitor_bias"] == "weak"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "出现向下预警，但当前不构成确认三卖。"
    assert payload["latest_zs_low"] is None
    assert payload["latest_zs_high"] is None
    assert "结论：出现向下预警，但当前不构成确认三卖。" in payload["advice_text"]
    assert "监视器：中枢中线 41.83，当前偏弱，预警状态 向下预警。" in payload["advice_text"]
    assert "节奏监视：节奏待判定，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "当前按三卖确认处理。" not in payload["advice_text"]


def test_real_1m_pre_breakdown_replay_sample_03690_preserves_independent_gate() -> None:
    # 第二个真实 1m pre_breakdown 锚点（非 000651），港股 03690 美团 2026-08-05 09:46。
    # 与既有 03690 2026-08-05 09:56 pre_breakout 构成「同日同标的下破→上破」对照，
    # 降低单标偏置并覆盖向下预警链的第二个真实样本。
    rows = probe_module._load_rows("03690", "1m")
    payload = probe_module._replay("03690", "美团", "2026-08-05 09:46", rows)

    assert payload["cutoff"] == "2026-08-05 09:46"
    assert payload["zs_monitor_alert"] == "pre_breakdown"
    assert payload["zs_monitor_midline"] == 92.3
    assert payload["zs_monitor_bias"] == "weak"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "出现向下预警，但当前不构成确认三卖。"
    assert payload["latest_zs_low"] == 91.0
    assert payload["latest_zs_high"] == 93.6
    assert "结论：出现向下预警，但当前不构成确认三卖。" in payload["advice_text"]
    assert "监视器：中枢中线 92.30，当前偏弱，预警状态 向下预警。" in payload["advice_text"]
    assert "节奏监视：节奏偏弱，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "当前按三卖确认处理。" not in payload["advice_text"]


def test_real_1m_trend_divergence_replay_sample_000651_down_non_strict() -> None:
    # 真实 1m 下跌趋势背驰（非严格）样本：修正中枢离开判定（贯穿段方向性前瞻）后，
    # ZS0 不再吸收向下离开段 s5，ZS0 [41.75,41.92] 与 ZS1 [40.21,40.51] 波动区间不再回探重叠，
    # 构成干净下跌趋势（rel=down、非扩张）。同向下探力度衰减但未跌破 -> trend_active=True、strict=False，
    # route 回落 last_zs_extension。见 trend-divergence-tasks.md「趋势背驰（下跌非严格）000651 双锚点」。
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-08-12 10:38", rows)

    assert payload["cutoff"] == "2026-08-12 10:38"
    assert payload["ongoing_type"] == "down"
    assert payload["divergence_trend_active"] is True
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is False
    assert payload["post_divergence_route"] == "last_zs_extension"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"


def test_real_1m_trend_divergence_replay_sample_000651_down_second_anchor() -> None:
    # 第二个 cutoff 锚点：与 08-12 同一下跌趋势背驰（非严格），锁追加更多 bar 后
    # 结构分类与背驰结论不漂移（ongoing=down、trend_active=True、strict=False、route=last_zs_extension）。
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-08-14 10:57", rows)

    assert payload["cutoff"] == "2026-08-14 10:57"
    assert payload["ongoing_type"] == "down"
    assert payload["divergence_trend_active"] is True
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is False
    assert payload["post_divergence_route"] == "last_zs_extension"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"


def test_real_day_range_divergence_replay_sample_000591_down_strict() -> None:
    # 严格盘整底背驰真实样本（day 级）：000591 太阳能 2026-08-03。
    # 前两中枢（zs0 [6.67,9.54] -> zs1 [4.98,5.54]）构成干净下跌趋势已完结，
    # 当前 zs1/zs2 区间不重叠但波动回探重叠（中枢扩张）归入盘整，落 strict=True
    # 盘整背驰轨道（route=higher_level_range、dual_interpretation_pending/pending）。
    rows = probe_module._load_rows("000591", "day")
    payload = probe_module._replay("000591", "太阳能", "2026-08-03", rows)

    assert payload["cutoff"] == "2026-08-03"
    assert payload["ongoing_type"] == "range"
    assert payload["divergence_trend_active"] is False
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is True
    assert payload["divergence_range_strict"] is True
    assert payload["divergence_range_touches_boundary"] is True
    assert payload["divergence_range_direction"] == "down"
    assert payload["post_divergence_route"] == "higher_level_range"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["same_level_consumption_level"] == "pending"


def test_real_day_range_divergence_replay_sample_000591_only_marks_small_to_large_candidate_without_buy3() -> None:
    """真实 000591 day 严格盘整底背驰样本：未见次级别三买前，只能标记为小转大候选。"""
    rows = probe_module._load_rows("000591", "day")
    payload = probe_module._replay("000591", "太阳能", "2026-08-03", rows)

    assert payload["post_divergence_route"] == "higher_level_range"
    assert payload["same_level_consumption_level"] == "pending"
    assert payload["buy_points"] == []
    assert payload["sell_points"] == []

    higher_signals = {
        "post_divergence_route": payload["post_divergence_route"],
        "same_level_consumption_level": payload["same_level_consumption_level"],
        "structure_state": {"current_ongoing": {"type": payload["ongoing_type"]}},
        "divergence": {
            "trend": {"active": False},
            "range": {
                "active": payload["divergence_range_active"],
                "direction": payload["divergence_range_direction"],
                "time": payload["cutoff"],
            },
        },
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [
            {
                "point": "buy2",
                "active": True,
                "time": payload["cutoff"],
                "price": 5.12,
                "basis": "buy1_pullback_confirmation",
            }
        ],
        "signal_catalog": [
            {
                "point": "buy2",
                "active": True,
                "time": payload["cutoff"],
                "price": 5.12,
                "basis": "buy1_pullback_confirmation",
            }
        ],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="60m",
        lower_timeframe_label="60M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert entry["higher_consumption_level"] == "pending"
    assert entry["small_to_large_status"] == "candidate"
    assert entry["small_to_large_status_label"] == "小转大候选"
    assert "最后一个次级别中枢" in entry["small_to_large_status_note"]
    assert "不按严格区间套执行" in entry["note"]


def test_real_day_range_divergence_replay_sample_601328_up_strict() -> None:
    # 严格盘整顶背驰真实样本（day 级）：601328 交通银行 2025-06-24。
    # 连续中枢区间不重叠但波动区间回探重叠（中枢扩张），按第20课归入盘整，
    # 落 strict=True 盘整背驰轨道（route=higher_level_range、dual_interpretation_pending/pending）。
    rows = probe_module._load_rows("601328", "day")
    payload = probe_module._replay("601328", "交通银行", "2025-06-24", rows)

    assert payload["cutoff"] == "2025-06-24"
    assert payload["ongoing_type"] == "range"
    assert payload["divergence_trend_active"] is False
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is True
    assert payload["divergence_range_strict"] is True
    assert payload["divergence_range_touches_boundary"] is True
    assert payload["divergence_range_direction"] == "up"
    assert payload["post_divergence_route"] == "higher_level_range"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["same_level_consumption_level"] == "pending"


def test_real_1m_range_divergence_replay_sample_300124_up_non_strict() -> None:
    # 非严格盘整顶背驰真实样本（1m 级）：300124 汇川技术 2026-08-05 10:29。
    # 两个中枢区间不重叠但波动回探重叠（中枢扩张）归入盘整，落非严格盘整背驰轨道
    # （route=last_zs_extension），与 000651 下跌非严格对称。
    rows = probe_module._load_rows("300124", "1m")
    payload = probe_module._replay("300124", "汇川技术", "2026-08-05 10:29", rows)

    assert payload["cutoff"] == "2026-08-05 10:29"
    assert payload["ongoing_type"] == "range"
    assert payload["divergence_trend_active"] is False
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is True
    assert payload["divergence_range_strict"] is False
    assert payload["divergence_range_touches_boundary"] is False
    assert payload["divergence_range_direction"] == "up"
    assert payload["post_divergence_route"] == "last_zs_extension"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["same_level_consumption_level"] == "pending"


def test_real_1m_range_divergence_replay_sample_000651_strict() -> None:
    # 严格盘整背驰真实样本（1m 级）：000651 格力电器 2026-08-03 13:47，
    # 补 TD5 长期缺失的盘整背驰真实样本（range_active=True、strict=True、
    # touches_boundary=True、route=higher_level_range、dual_interpretation_pending）。
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-08-03 13:47", rows)

    assert payload["cutoff"] == "2026-08-03 13:47"
    assert payload["ongoing_type"] == "range"
    assert payload["divergence_trend_active"] is False
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is True
    assert payload["divergence_range_strict"] is True
    assert payload["divergence_range_touches_boundary"] is True
    assert payload["post_divergence_route"] == "higher_level_range"
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["same_level_consumption_level"] == "pending"


def test_real_1m_confirmed_buy2like_replay_sample_01024() -> None:
    # 真实 1m confirmed 买侧样本：01024 快手 2026-08-03 15:33。
    # 当前窗口已进入 single_confirmed + confirmed，且 buy2like 生效，
    # 可作为前端 `1m confirmed` 买侧 live 对照候选。
    rows = probe_module._load_rows("01024", "1m")
    payload = probe_module._replay("01024", "快手", "2026-08-03 15:33", rows)

    assert payload["cutoff"] == "2026-08-03 15:33"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"
    assert payload["buy_points"] == ["buy_2like"]
    assert payload["sell_points"] == []
    assert payload["zs_monitor_alert"] == "none"
    assert payload["oscillation_rhythm_state"] == "up_bias"
    assert payload["ongoing_type"] == "up"
    assert payload["post_divergence_route"] is None


def test_real_1m_confirmed_buy2like_replay_sample_00175() -> None:
    # 第二个真实 1m confirmed 买侧样本：00175 吉利汽车 2026-08-05 10:43。
    # 该窗口同样进入 single_confirmed + confirmed，且仅保留 buy2like，
    # 可作为 01024 之外的第二个买侧 replay 对照，降低单标偏置。
    rows = probe_module._load_rows("00175", "1m")
    payload = probe_module._replay("00175", "吉利汽车", "2026-08-05 10:43", rows)

    assert payload["cutoff"] == "2026-08-05 10:43"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"
    assert payload["buy_points"] == ["buy_2like"]
    assert payload["sell_points"] == []
    assert payload["conclusion"] == "偏多，允许轻仓试错。"
    assert payload["zs_monitor_alert"] == "pre_breakout"
    assert payload["oscillation_rhythm_state"] == "down_bias"
    assert payload["ongoing_type"] == "down"


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
            "same_level_decomposition_mode": "single_confirmed",
            "oscillation_rhythm_state": "balanced",
            "divergence": {"trend": {"active": False}},
            "zs_monitor_alert": "none",
        }
    )

    assert payload["buy_points"] == ["buy1"]
    assert payload["signal_points"][0]["point"] == "buy1"
    assert len(payload["signal_catalog"]) == 6
    assert payload["zs_monitor_alert"] == "none"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["oscillation_rhythm_state"] == "balanced"


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
    prev_zs = _zhongshu(3, zs_low=11.6, zs_high=12.2, day=1)
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
        Bi(
            bi_id=6,
            direction=BiDirection.UP,
            start_fx_id=6,
            end_fx_id=7,
            start_ts=datetime(2026, 5, 15, 10, 30),
            end_ts=datetime(2026, 5, 15, 14, 30),
            high=11.4,
            low=10.5,
            norm_bar_range=(6, 7),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
        SimpleNamespace(ts=bis[5].end_ts, macd=1.0, dif=0.2),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert "buy_2" in signals["buy_points"]
    assert signals["signal_catalog"][1]["active"] is True
    assert signals["signal_catalog"][1]["basis"] == "buy1_pullback_confirmation"


def test_analyze_chanlun_signals_flags_second_sell_after_sell1_rebound() -> None:
    prev_zs = _zhongshu(0, zs_low=8.2, zs_high=8.8, day=1)
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
        Bi(
            bi_id=16,
            direction=BiDirection.DOWN,
            start_fx_id=16,
            end_fx_id=17,
            start_ts=datetime(2026, 5, 20, 10, 30),
            end_ts=datetime(2026, 5, 20, 14, 30),
            high=10.5,
            low=9.7,
            norm_bar_range=(16, 17),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=2.0, dif=0.4),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.0, dif=0.2),
        SimpleNamespace(ts=bis[4].end_ts, macd=0.8, dif=0.1),
        SimpleNamespace(ts=bis[5].end_ts, macd=-0.6, dif=-0.1),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert "sell_2" in signals["sell_points"]
    assert signals["signal_catalog"][4]["active"] is True
    assert signals["signal_catalog"][4]["basis"] == "sell1_rebound_confirmation"


def test_analyze_chanlun_signals_does_not_flag_buy2_when_renew_up_fails_new_high() -> None:
    """BS3 二买「再度走强」力度：回抽后出现向上笔但未创新高 -> 二买不成立。"""
    current_zs = _zhongshu(10, zs_low=10.2, zs_high=10.8, day=10)
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
        Bi(
            bi_id=6,
            direction=BiDirection.UP,
            start_fx_id=6,
            end_fx_id=7,
            start_ts=datetime(2026, 5, 15, 10, 30),
            end_ts=datetime(2026, 5, 15, 14, 30),
            high=11.2,
            low=10.5,
            norm_bar_range=(6, 7),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
        SimpleNamespace(ts=bis[5].end_ts, macd=1.0, dif=0.2),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_does_not_flag_sell2_when_renew_down_fails_new_low() -> None:
    """BS3 二卖「再度走弱」力度：反抽后出现向下笔但未创新低 -> 二卖不成立。"""
    current_zs = _zhongshu(11, zs_low=10.2, zs_high=10.8, day=15)
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
        Bi(
            bi_id=16,
            direction=BiDirection.DOWN,
            start_fx_id=16,
            end_fx_id=17,
            start_ts=datetime(2026, 5, 20, 10, 30),
            end_ts=datetime(2026, 5, 20, 14, 30),
            high=10.5,
            low=9.9,
            norm_bar_range=(16, 17),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=2.0, dif=0.4),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.0, dif=0.2),
        SimpleNamespace(ts=bis[4].end_ts, macd=0.8, dif=0.1),
        SimpleNamespace(ts=bis[5].end_ts, macd=-0.6, dif=-0.1),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == []
    # 顶背驰仍构成 sell_1，但反抽后向下笔未创新低 -> 二卖不成立。
    assert "sell_2" not in signals["sell_points"]


def test_analyze_chanlun_signals_does_not_reflag_buy2_on_second_pullback() -> None:
    """BS3 二买「首次回抽锁定」：一买后已出现一次不破前低的确认性回抽，第二次回抽即便同样不破前低也不得重复标二买。"""
    current_zs = _zhongshu(8, zs_low=10.2, zs_high=10.8, day=10)
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
        Bi(
            bi_id=6,
            direction=BiDirection.UP,
            start_fx_id=6,
            end_fx_id=7,
            start_ts=datetime(2026, 5, 15, 10, 30),
            end_ts=datetime(2026, 5, 15, 14, 30),
            high=11.2,
            low=10.5,
            norm_bar_range=(6, 7),
            is_confirmed=False,
        ),
        Bi(
            bi_id=7,
            direction=BiDirection.DOWN,
            start_fx_id=7,
            end_fx_id=8,
            start_ts=datetime(2026, 5, 16, 10, 30),
            end_ts=datetime(2026, 5, 16, 14, 30),
            high=11.15,
            low=10.45,
            norm_bar_range=(7, 8),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_2" not in signals["buy_points"]


def test_analyze_chanlun_signals_does_not_reflag_sell2_on_second_rebound() -> None:
    """BS3 二卖「首次反抽锁定」：一卖后已出现一次不破前高的确认性反抽，第二次反抽即便同样不破前高也不得重复标二卖。"""
    current_zs = _zhongshu(9, zs_low=10.2, zs_high=10.8, day=15)
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
        Bi(
            bi_id=16,
            direction=BiDirection.DOWN,
            start_fx_id=16,
            end_fx_id=17,
            start_ts=datetime(2026, 5, 20, 10, 30),
            end_ts=datetime(2026, 5, 20, 14, 30),
            high=10.5,
            low=9.9,
            norm_bar_range=(16, 17),
            is_confirmed=False,
        ),
        Bi(
            bi_id=17,
            direction=BiDirection.UP,
            start_fx_id=17,
            end_fx_id=18,
            start_ts=datetime(2026, 5, 21, 10, 30),
            end_ts=datetime(2026, 5, 21, 14, 30),
            high=10.65,
            low=10.0,
            norm_bar_range=(17, 18),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=2.0, dif=0.4),
        SimpleNamespace(ts=bis[2].end_ts, macd=1.0, dif=0.2),
        SimpleNamespace(ts=bis[4].end_ts, macd=0.8, dif=0.1),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "sell_2" not in signals["sell_points"]


def test_analyze_chanlun_signals_does_not_flag_buy2_without_renew_up_after_pullback() -> None:
    """BS3 二买「再度走强」：一买后回抽不破前低，但尚未出现再度向上的笔 -> 二买不成立。"""
    current_zs = _zhongshu(10, zs_low=10.2, zs_high=10.8, day=10)
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

    assert "buy_2" not in signals["buy_points"]


def test_analyze_chanlun_signals_does_not_flag_sell2_without_renew_down_after_rebound() -> None:
    """BS3 二卖「再度走弱」：一卖后反抽不破前高，但尚未出现再度向下的笔 -> 二卖不成立。"""
    current_zs = _zhongshu(12, zs_low=10.2, zs_high=10.8, day=15)
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

    assert "sell_2" not in signals["sell_points"]


def test_analyze_chanlun_signals_flags_first_buy_on_bottom_divergence_below_zs_low() -> None:
    """BS2 一买正例：最近中枢 + 向下离开段跌破中枢下沿 + 底背驰 -> buy_1。

    一买核心是「背驰导致的转折」，不是单纯触边；本用例锁定背驰三元组
    （最近中枢 + 离开段 + 力度衰减）下的 buy_1 判定。
    """
    prev_zs = _zhongshu(0, zs_low=11.6, zs_high=12.2, day=1)
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(3, BiDirection.DOWN, high=11.0, low=10.0, day=3),
        _bi(4, BiDirection.UP, high=11.3, low=10.2, day=4),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 5, 10, 30),
            end_ts=datetime(2026, 5, 5, 14, 30),
            high=11.0,
            low=9.8,
            norm_bar_range=(5, 6),
            is_confirmed=True,
        ),
        Bi(
            bi_id=6,
            direction=BiDirection.UP,
            start_fx_id=7,
            end_fx_id=8,
            start_ts=datetime(2026, 5, 6, 10, 30),
            end_ts=datetime(2026, 5, 6, 14, 30),
            high=11.5,
            low=10.3,
            norm_bar_range=(7, 8),
            is_confirmed=True,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
        SimpleNamespace(ts=bis[5].end_ts, macd=-0.6, dif=0.3),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["buy_points"] == ["buy_1"]
    assert signals["sell_points"] == []
    assert signals["bottom_divergence"] is True


def test_analyze_chanlun_signals_flags_first_sell_on_top_divergence_above_zs_high() -> None:
    """BS2 一卖正例（对称样例）：最近中枢 + 向上离开段越过中枢上沿 + 顶背驰 -> sell_1。"""
    prev_zs = _zhongshu(1, zs_low=8.2, zs_high=8.8, day=1)
    current_zs = _zhongshu(2, zs_low=10.0, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=10.1, day=10),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=11),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=12),
        _bi(4, BiDirection.DOWN, high=11.0, low=10.4, day=13),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 14, 10, 30),
            end_ts=datetime(2026, 5, 14, 14, 30),
            high=10.9,
            low=9.8,
            norm_bar_range=(5, 6),
            is_confirmed=True,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=0.8),
        SimpleNamespace(ts=bis[4].end_ts, macd=2.2, dif=0.6),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["sell_points"] == ["sell_1"]
    assert signals["buy_points"] == []
    assert signals["top_divergence"] is True


def test_analyze_chanlun_signals_buy1_and_sell1_require_confirmed_departure_and_turn() -> None:
    """BS2 严格口径：一类点必须同时满足：离开笔已确认 + 背驰 + 反向转折确认。

    只有在出离段后出现反向确认笔，才允许形成 buy_1 / sell_1；
    若离开笔未确认，或未出现转折确认，则不得报一类点。
    """
    # 买方：唯一跌破下沿的 down 离开笔未确认，且无后续向上确认笔 -> 不触发 buy_1
    buy_zs = _zhongshu(11, zs_low=10.0, zs_high=10.8, day=1)
    buy_bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(3, BiDirection.DOWN, high=11.0, low=10.2, day=3),
        _bi(4, BiDirection.UP, high=11.3, low=10.3, day=4),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 5, 10, 30),
            end_ts=datetime(2026, 5, 5, 14, 30),
            high=11.0,
            low=9.8,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    buy_macd = [
        SimpleNamespace(ts=buy_bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=buy_bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=buy_bis[4].end_ts, macd=-1.0, dif=-0.4),
    ]
    buy_signals = analyze_chanlun_signals([], buy_bis, [buy_zs], buy_macd)
    assert buy_signals["buy_points"] == []

    # 卖方：唯一越上沿的 up 离开笔未确认，且无后续向下确认笔 -> 不触发 sell_1
    sell_zs = _zhongshu(12, zs_low=10.0, zs_high=10.8, day=1)
    sell_bis = [
        _bi(1, BiDirection.UP, high=10.5, low=10.1, day=1),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.0, day=2),
        _bi(3, BiDirection.UP, high=10.7, low=10.2, day=3),
        _bi(4, BiDirection.DOWN, high=10.5, low=10.0, day=4),
        Bi(
            bi_id=5,
            direction=BiDirection.UP,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 5, 10, 30),
            end_ts=datetime(2026, 5, 5, 14, 30),
            high=11.2,
            low=10.4,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    sell_macd = [
        SimpleNamespace(ts=sell_bis[0].end_ts, macd=5.0, dif=1.0),
        SimpleNamespace(ts=sell_bis[2].end_ts, macd=3.0, dif=0.8),
        SimpleNamespace(ts=sell_bis[4].end_ts, macd=2.0, dif=0.6),
    ]
    sell_signals = analyze_chanlun_signals([], sell_bis, [sell_zs], sell_macd)
    assert sell_signals["top_divergence"] is True
    assert sell_signals["sell_points"] == []


def test_analyze_chanlun_signals_requires_up_turn_confirmation_before_buy1() -> None:
    """BS2 严格口径：底背驰但未出现向上转折确认，不得确认 buy_1。"""
    current_zs = _zhongshu(13, zs_low=10.0, zs_high=10.8, day=1)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        Bi(
            bi_id=3,
            direction=BiDirection.DOWN,
            start_fx_id=3,
            end_fx_id=4,
            start_ts=datetime(2026, 5, 3, 10, 30),
            end_ts=datetime(2026, 5, 3, 14, 30),
            high=11.0,
            low=9.8,
            norm_bar_range=(3, 4),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["bottom_divergence"] is True
    assert signals["buy_points"] == []


def test_analyze_chanlun_signals_buy1_uses_segment_divergence_strict_strength() -> None:
    """BS1 力度口径：线段级中枢的一买用「离开段 vs 进入段」力度比较。

    离开段(down)创新低且力度弱于进入段 -> 段级底背驰 -> buy_1；
    即使笔级力度表为空（macd 点落在笔窗外），也应以段级口径为准。
    """
    prev_zs = _segment_zhongshu(0, entering_segment_id=0, exit_segment_id=0, zs_low=11.6, zs_high=12.2)
    zs = _segment_zhongshu(1, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    entering = _segment(1, BiDirection.DOWN, high=11.2, low=10.6, start_day=1)
    exit_seg = _segment(2, BiDirection.DOWN, high=10.9, low=9.8, start_day=3)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(3, BiDirection.DOWN, high=11.0, low=9.8, day=3),
        _bi(4, BiDirection.UP, high=11.5, low=10.2, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=entering.end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=exit_seg.end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, zs], macd_points, segments=[entering, exit_seg])

    assert signals["buy_points"] == ["buy_1"]
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_buy1_requires_segment_strength_decay() -> None:
    """BS1 力度口径（负例）：离开段创新低但力度强于进入段 -> 段级底背驰不成立 -> 不报 buy_1。"""
    zs = _segment_zhongshu(2, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    entering = _segment(1, BiDirection.DOWN, high=11.2, low=10.6, start_day=1)
    exit_seg = _segment(2, BiDirection.DOWN, high=10.9, low=9.8, start_day=3)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(3, BiDirection.DOWN, high=11.0, low=9.8, day=3),
        _bi(4, BiDirection.UP, high=11.5, low=10.2, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=entering.end_ts, macd=-1.0, dif=-0.4),
        SimpleNamespace(ts=exit_seg.end_ts, macd=-5.0, dif=-1.0),
    ]

    signals = analyze_chanlun_signals([], bis, [zs], macd_points, segments=[entering, exit_seg])

    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_sell1_uses_segment_divergence_strict_strength() -> None:
    """BS1 力度口径（对称）：线段级中枢的一卖用「离开段 vs 进入段」力度比较。"""
    prev_zs = _segment_zhongshu(2, entering_segment_id=0, exit_segment_id=0, zs_low=8.2, zs_high=8.8)
    zs = _segment_zhongshu(3, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    entering = _segment(1, BiDirection.UP, high=10.6, low=9.9, start_day=1)
    exit_seg = _segment(2, BiDirection.UP, high=11.2, low=10.3, start_day=3)
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=9.9, day=1),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=2),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=3),
        _bi(4, BiDirection.DOWN, high=10.8, low=10.0, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=entering.end_ts, macd=5.0, dif=1.0),
        SimpleNamespace(ts=exit_seg.end_ts, macd=1.0, dif=0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, zs], macd_points, segments=[entering, exit_seg])

    assert signals["sell_points"] == ["sell_1"]
    assert signals["buy_points"] == []


def test_analyze_chanlun_signals_buy1_anchors_on_exit_segment_end_bi() -> None:
    """BS2 段级信号锚点：一买以离开段末笔为基准，而非更晚出现的最新向下笔。"""
    prev_zs = _segment_zhongshu(30, entering_segment_id=0, exit_segment_id=0, zs_low=11.6, zs_high=12.2)
    zs = _segment_zhongshu(31, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    entering = Segment(
        segment_id=1,
        direction=BiDirection.DOWN,
        start_bi_id=10,
        end_bi_id=11,
        start_ts=datetime(2026, 5, 1, 10, 30),
        end_ts=datetime(2026, 5, 2, 14, 30),
        start_price=11.2,
        end_price=10.6,
        high=11.2,
        low=10.6,
        norm_bar_range=(10, 11),
        bi_ids=[10, 11],
        is_confirmed=True,
    )
    exit_seg = Segment(
        segment_id=2,
        direction=BiDirection.DOWN,
        start_bi_id=13,
        end_bi_id=14,
        start_ts=datetime(2026, 5, 3, 10, 30),
        end_ts=datetime(2026, 5, 4, 14, 30),
        start_price=10.9,
        end_price=9.8,
        high=10.9,
        low=9.8,
        norm_bar_range=(13, 14),
        bi_ids=[13, 14],
        is_confirmed=True,
    )
    bis = [
        _bi(10, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(11, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(12, BiDirection.DOWN, high=11.0, low=10.3, day=3),
        _bi(13, BiDirection.UP, high=10.8, low=10.1, day=4),
        _bi(14, BiDirection.DOWN, high=10.9, low=9.8, day=5),
        _bi(15, BiDirection.UP, high=11.2, low=10.0, day=6),
        _bi(16, BiDirection.DOWN, high=11.1, low=10.2, day=7),
    ]
    macd_points = [
        SimpleNamespace(ts=entering.end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=exit_seg.end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, zs], macd_points, segments=[entering, exit_seg])

    assert signals["buy_points"] == ["buy_1"]
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_buy3_requires_segment_pullback() -> None:
    """BS4 段级三买严格口径：向上离开段越上沿后，若尚未形成回踩线段，不得报 buy_3。

    旧实现会在回踩尚未成段时回退到笔级回试并提前报三买；段级口径要求
    离开段 + 回踩线段同时成立（回归 01339 30m buy3 5.29 误报）。
    """
    zs = _segment_zhongshu(32, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    entering = Segment(
        segment_id=1,
        direction=BiDirection.UP,
        start_bi_id=10,
        end_bi_id=11,
        start_ts=datetime(2026, 5, 1, 10, 30),
        end_ts=datetime(2026, 5, 2, 14, 30),
        start_price=10.0,
        end_price=10.6,
        high=10.6,
        low=9.9,
        norm_bar_range=(10, 11),
        bi_ids=[10, 11],
        is_confirmed=True,
    )
    exit_seg = Segment(
        segment_id=2,
        direction=BiDirection.UP,
        start_bi_id=12,
        end_bi_id=13,
        start_ts=datetime(2026, 5, 3, 10, 30),
        end_ts=datetime(2026, 5, 4, 14, 30),
        start_price=10.4,
        end_price=11.2,
        high=11.2,
        low=10.3,
        norm_bar_range=(12, 13),
        bi_ids=[12, 13],
        is_confirmed=True,
    )
    bis = [
        _bi(10, BiDirection.DOWN, high=10.9, low=10.4, day=1),
        _bi(11, BiDirection.UP, high=10.6, low=9.9, day=2),
        _bi(12, BiDirection.DOWN, high=10.5, low=10.0, day=3),
        _bi(13, BiDirection.UP, high=11.2, low=10.3, day=4),
        _bi(14, BiDirection.DOWN, high=11.2, low=10.9, day=5),
        Bi(
            bi_id=15,
            direction=BiDirection.UP,
            start_fx_id=15,
            end_fx_id=16,
            start_ts=datetime(2026, 5, 6, 10, 30),
            end_ts=datetime(2026, 5, 6, 14, 30),
            high=11.4,
            low=10.95,
            norm_bar_range=(15, 16),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=entering.end_ts, macd=1.0, dif=0.4),
        SimpleNamespace(ts=exit_seg.end_ts, macd=5.0, dif=1.0),
    ]

    signals = analyze_chanlun_signals([], bis, [zs], macd_points, segments=[entering, exit_seg])

    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


def test_compute_segment_strengths_aggregates_macd_area_by_segment_window() -> None:
    """线段力度 = 线段时间窗内 abs(macd) 之和。"""
    seg_a = _segment(1, BiDirection.DOWN, high=11.0, low=10.0, start_day=1)
    seg_b = _segment(2, BiDirection.DOWN, high=10.0, low=9.0, start_day=3)
    macd_points = [
        SimpleNamespace(ts=seg_a.end_ts, macd=-2.0, dif=-0.5),
        SimpleNamespace(ts=seg_b.end_ts, macd=-3.0, dif=-0.7),
    ]

    strengths = compute_segment_strengths([seg_a, seg_b], macd_points)

    assert strengths[1]["macd_sum_abs"] == 2.0
    assert strengths[2]["macd_sum_abs"] == 3.0


def _lb2_gap_segments() -> list[Segment]:
    # A_i(下) - A_{i+1}(上) - A_{i+2}(下)：A_{i+2} 创新低（回踩段）。
    return [
        _segment(1, BiDirection.DOWN, high=11.2, low=10.6, start_day=1),
        _segment(2, BiDirection.UP, high=11.0, low=10.4, start_day=3),
        _segment(3, BiDirection.DOWN, high=10.9, low=9.8, start_day=5),
    ]


def _ls2_gap_segments() -> list[Segment]:
    # A_i(上) - A_{i+1}(下) - A_{i+2}(上)：A_{i+2} 创新高（反抽段）。
    return [
        _segment(1, BiDirection.UP, high=10.6, low=9.9, start_day=1),
        _segment(2, BiDirection.DOWN, high=10.4, low=9.6, start_day=3),
        _segment(3, BiDirection.UP, high=11.2, low=10.3, start_day=5),
    ]


def _down_trend_zhongshus() -> list[Zhongshu]:
    # 两个同向不重叠下移中枢 -> 同级别分解 single_confirmed（下跌趋势），使类二类点门控放行。
    return [
        _zhongshu(8, zs_low=11.0, zs_high=11.6, day=1),
        _zhongshu(9, zs_low=10.0, zs_high=10.8, day=8),
    ]


def _up_trend_zhongshus() -> list[Zhongshu]:
    # 两个同向不重叠上移中枢 -> 同级别分解 single_confirmed（上涨趋势），使类二类点门控放行。
    return [
        _zhongshu(8, zs_low=9.2, zs_high=9.8, day=1),
        _zhongshu(9, zs_low=10.0, zs_high=10.8, day=8),
    ]


def test_analyze_chanlun_signals_flags_buy_2like_on_gap_segment_divergence() -> None:
    """BS7 类二买正例：同级别隔段背驰（A_i vs A_{i+2}）+ 回踩末笔后向上转折 -> buy_2like。"""
    segments = _lb2_gap_segments()
    zhongshus = _down_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.4, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=9.8, day=5),  # A_{i+2} 回踩末笔（低点）
        _bi(33, BiDirection.UP, high=10.5, low=9.9, day=6),  # 回踩后向上转折
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-5.0, dif=-1.0),  # A_i 力度强
        SimpleNamespace(ts=segments[2].end_ts, macd=-1.0, dif=-0.4),  # A_{i+2} 力度衰减
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "buy_2like" in signals["buy_points"]
    assert "sell_2like" not in signals["sell_points"]
    catalog_lb2 = next(entry for entry in signals["signal_catalog"] if entry["point"] == "buy2like")
    assert catalog_lb2["active"] is True
    assert catalog_lb2["basis"] == "gap_segment_divergence_pullback_end"
    assert catalog_lb2["signal_bi_id"] == 32
    assert catalog_lb2["price"] == 9.8


def test_analyze_chanlun_signals_flags_buy_2like_when_pullback_holds_prev_low() -> None:
    """BS7 类二买「不破前低」正例：A_{i+2} 回踩不破 A_i 前低但段级力度衰减 -> 仍报 buy_2like。

    锁定 spec「不需要破前低/前高」：隔段背驰只比较段级力度，不要求 A_{i+2} 创新低。
    """
    segments = [
        _segment(1, BiDirection.DOWN, high=11.2, low=10.6, start_day=1),  # A_i 前低 10.6
        _segment(2, BiDirection.UP, high=11.0, low=10.5, start_day=3),
        _segment(3, BiDirection.DOWN, high=10.9, low=10.7, start_day=5),  # A_{i+2} 低点 10.7 未破前低
    ]
    zhongshus = _down_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.5, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=10.7, day=5),  # 回踩末笔不破前低
        _bi(33, BiDirection.UP, high=10.75, low=10.7, day=6),  # 回踩后向上转折
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-5.0, dif=-1.0),  # A_i 力度强
        SimpleNamespace(ts=segments[2].end_ts, macd=-1.0, dif=-0.4),  # A_{i+2} 力度衰减
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "buy_2like" in signals["buy_points"]
    catalog_lb2 = next(entry for entry in signals["signal_catalog"] if entry["point"] == "buy2like")
    assert catalog_lb2["price"] == 10.7


def test_analyze_chanlun_signals_no_buy_2like_without_gap_divergence() -> None:
    """BS7 类二买反例（无背驰）：A_{i+2} 力度不弱于 A_i -> 不报 buy_2like。"""
    segments = _lb2_gap_segments()
    zhongshus = _down_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.4, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=9.8, day=5),
        _bi(33, BiDirection.UP, high=10.5, low=9.9, day=6),
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-1.0, dif=-0.4),  # A_i 力度弱
        SimpleNamespace(ts=segments[2].end_ts, macd=-5.0, dif=-1.0),  # A_{i+2} 力度反而更强
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "buy_2like" not in signals["buy_points"]


def test_analyze_chanlun_signals_no_buy_2like_when_pullback_not_ended() -> None:
    """BS7 类二买反例（回踩未结束）：A_{i+2} 末笔后无已确认向上转折 -> 不报 buy_2like。"""
    segments = _lb2_gap_segments()
    zhongshus = _down_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.4, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=9.8, day=5),
        Bi(
            bi_id=33,
            direction=BiDirection.UP,
            start_fx_id=33,
            end_fx_id=34,
            start_ts=datetime(2026, 5, 6, 10, 30),
            end_ts=datetime(2026, 5, 6, 14, 30),
            high=10.5,
            low=9.9,
            norm_bar_range=(33, 34),
            is_confirmed=False,  # 反向转折笔尚未确认，回踩未结束
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=segments[2].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "buy_2like" not in signals["buy_points"]


def test_analyze_chanlun_signals_no_buy_2like_when_decomposition_pending() -> None:
    """BS7 类二买门控：单一未确认中枢（dual_interpretation_pending）时只作观察，不发类二买。"""
    segments = _lb2_gap_segments()
    current_zs = _zhongshu(9, zs_low=10.0, zs_high=10.8, day=8)  # 单中枢 -> pending
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.4, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=9.8, day=5),
        _bi(33, BiDirection.UP, high=10.5, low=9.9, day=6),
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=segments[2].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points, segments=segments)

    assert signals["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert "buy_2like" not in signals["buy_points"]


def test_analyze_chanlun_signals_flags_sell_2like_on_gap_segment_divergence() -> None:
    """BS7 类二卖正例（对称）：同级别隔段顶背驰 + 反抽末笔后向下转折 -> sell_2like。"""
    segments = _ls2_gap_segments()
    zhongshus = _up_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.UP, high=10.6, low=9.9, day=1),
        _bi(22, BiDirection.DOWN, high=10.4, low=9.6, day=3),
        _bi(32, BiDirection.UP, high=11.2, low=10.3, day=5),  # A_{i+2} 反抽末笔（高点）
        _bi(33, BiDirection.DOWN, high=11.1, low=10.4, day=6),  # 反抽后向下转折
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=5.0, dif=1.0),  # A_i 力度强
        SimpleNamespace(ts=segments[2].end_ts, macd=1.0, dif=0.4),  # A_{i+2} 力度衰减
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "sell_2like" in signals["sell_points"]
    assert "buy_2like" not in signals["buy_points"]
    catalog_ls2 = next(entry for entry in signals["signal_catalog"] if entry["point"] == "sell2like")
    assert catalog_ls2["active"] is True
    assert catalog_ls2["basis"] == "gap_segment_divergence_rebound_end"
    assert catalog_ls2["signal_bi_id"] == 32
    assert catalog_ls2["price"] == 11.2


def test_analyze_chanlun_signals_no_sell_2like_without_gap_divergence() -> None:
    """BS7 类二卖反例（无背驰）：A_{i+2} 力度不弱于 A_i -> 不报 sell_2like。"""
    segments = _ls2_gap_segments()
    zhongshus = _up_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.UP, high=10.6, low=9.9, day=1),
        _bi(22, BiDirection.DOWN, high=10.4, low=9.6, day=3),
        _bi(32, BiDirection.UP, high=11.2, low=10.3, day=5),
        _bi(33, BiDirection.DOWN, high=11.1, low=10.4, day=6),
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=1.0, dif=0.4),  # A_i 力度弱
        SimpleNamespace(ts=segments[2].end_ts, macd=5.0, dif=1.0),  # A_{i+2} 力度反而更强
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "sell_2like" not in signals["sell_points"]


def _lb1_range_bis() -> list[Bi]:
    # 单中枢中枢震荡下的向下离开段（末笔 bi5 跌破 zs_low）+ 底背驰 + 向上反向转折（bi6）。
    return [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=2),
        _bi(3, BiDirection.DOWN, high=11.0, low=10.0, day=3),
        _bi(4, BiDirection.UP, high=11.3, low=10.2, day=4),
        _bi(5, BiDirection.DOWN, high=11.0, low=9.8, day=5),  # 离开末笔，跌破 zs_low
        _bi(6, BiDirection.UP, high=11.5, low=10.3, day=6),  # 向上反向转折
    ]


def _lb1_divergence_macd(bis: list[Bi]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),  # 离开末笔力度衰减 -> 底背驰
        SimpleNamespace(ts=bis[5].end_ts, macd=-0.6, dif=0.3),
    ]


def test_analyze_chanlun_signals_flags_buy_1like_on_range_consolidation_divergence() -> None:
    """BS8 类一买正例：单中枢中枢震荡（range + ongoing_same_type）+ 盘整背驰 + 向上转折 -> buy_1like。

    标准一买要求 ongoing_type==down（趋势背驰）；此处趋势门控缺席（range），由盘整背驰给出
    类第一类买点（第27/65课）。
    """
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)  # 单中枢 -> range + ongoing_same_type
    bis = _lb1_range_bis()
    macd_points = _lb1_divergence_macd(bis)

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["structure_state"]["current_structure_status"] == "ongoing_same_type"
    assert signals["structure_state"]["current_ongoing"]["type"] == "range"
    assert "buy_1" not in signals["buy_points"]
    assert "buy_1like" in signals["buy_points"]
    assert signals["bottom_divergence"] is True
    catalog_lb1 = next(entry for entry in signals["signal_catalog"] if entry["point"] == "buy1like")
    assert catalog_lb1["active"] is True
    assert catalog_lb1["basis"] == "consolidation_divergence_reverse_low"
    assert catalog_lb1["signal_bi_id"] == 5
    assert catalog_lb1["price"] == 9.8


def test_analyze_chanlun_signals_buy_1_not_buy_1like_under_down_trend_gate() -> None:
    """BS8 类一买反例（趋势门控 down）：同背驰结构但两中枢下移趋势 -> 报标准 buy_1，不报 buy_1like。"""
    prev_zs = _zhongshu(0, zs_low=11.6, zs_high=12.2, day=1)
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)  # 两中枢不重叠下移 -> down
    bis = _lb1_range_bis()
    macd_points = _lb1_divergence_macd(bis)

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["structure_state"]["current_ongoing"]["type"] == "down"
    assert "buy_1" in signals["buy_points"]
    assert "buy_1like" not in signals["buy_points"]


def test_analyze_chanlun_signals_no_buy_1like_without_consolidation_divergence() -> None:
    """BS8 类一买反例（无背驰）：离开末笔力度不弱于进入段 -> 不报 buy_1like。"""
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    bis = _lb1_range_bis()
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-1.0, dif=-0.4),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-5.0, dif=-1.0),  # 离开末笔力度反而更强 -> 无背驰
        SimpleNamespace(ts=bis[5].end_ts, macd=-0.6, dif=0.3),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["bottom_divergence"] is False
    assert "buy_1like" not in signals["buy_points"]


def test_analyze_chanlun_signals_no_buy_1like_without_reverse_turn() -> None:
    """BS8 类一买反例（无反向转折）：离开末笔后无已确认向上转折 -> 不报 buy_1like。"""
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    bis = _lb1_range_bis()[:5] + [
        Bi(
            bi_id=6,
            direction=BiDirection.UP,
            start_fx_id=7,
            end_fx_id=8,
            start_ts=datetime(2026, 5, 6, 10, 30),
            end_ts=datetime(2026, 5, 6, 14, 30),
            high=11.5,
            low=10.3,
            norm_bar_range=(7, 8),
            is_confirmed=False,  # 反向转折笔尚未确认
        ),
    ]
    macd_points = _lb1_divergence_macd(bis)

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_1like" not in signals["buy_points"]


def test_analyze_chanlun_signals_no_buy_1like_when_structure_status_candidate() -> None:
    """BS8 类一买门控反例：前段完成 + 新类型候选未确认（candidate）时只观察，不报 buy_1like。"""
    first = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    second = _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4)
    third = _zhongshu(3, zs_low=11.8, zs_high=12.1, day=7)  # 与 second 重叠 -> range 候选
    bis = [
        _bi(1, BiDirection.DOWN, high=12.4, low=11.8, day=1),
        _bi(2, BiDirection.UP, high=12.1, low=11.6, day=2),
        _bi(3, BiDirection.DOWN, high=12.2, low=11.2, day=3),
        _bi(4, BiDirection.UP, high=12.5, low=11.4, day=4),
        _bi(5, BiDirection.DOWN, high=12.2, low=11.0, day=5),
        _bi(6, BiDirection.UP, high=12.7, low=11.5, day=6),
    ]
    macd_points = _lb1_divergence_macd(bis)

    signals = analyze_chanlun_signals([], bis, [first, second, third], macd_points)

    assert signals["structure_state"]["current_structure_status"] == "candidate_completed_waiting_stability"
    assert "buy_1like" not in signals["buy_points"]


def test_analyze_chanlun_signals_flags_sell_1like_on_range_consolidation_divergence() -> None:
    """BS8 类一卖正例（对称）：单中枢中枢震荡 + 盘整顶背驰 + 向下转折 -> sell_1like。"""
    current_zs = _zhongshu(2, zs_low=10.0, zs_high=10.8, day=10)  # 单中枢 -> range + ongoing_same_type
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=10.1, day=10),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=11),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=12),  # 离开末笔越上沿，创新高
        _bi(4, BiDirection.DOWN, high=11.0, low=10.4, day=13),  # 向下反向转折
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=0.8),  # 离开末笔力度衰减 -> 顶背驰
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["structure_state"]["current_ongoing"]["type"] == "range"
    assert "sell_1" not in signals["sell_points"]
    assert "sell_1like" in signals["sell_points"]
    assert signals["top_divergence"] is True
    catalog_ls1 = next(entry for entry in signals["signal_catalog"] if entry["point"] == "sell1like")
    assert catalog_ls1["active"] is True
    assert catalog_ls1["basis"] == "consolidation_divergence_reverse_high"
    assert catalog_ls1["signal_bi_id"] == 3
    assert catalog_ls1["price"] == 11.2


def test_analyze_chanlun_signals_no_sell_1like_without_consolidation_divergence() -> None:
    """BS8 类一卖反例（无背驰）：离开末笔力度不弱于进入段 -> 不报 sell_1like。"""
    current_zs = _zhongshu(2, zs_low=10.0, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=10.1, day=10),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=11),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=12),
        _bi(4, BiDirection.DOWN, high=11.0, low=10.4, day=13),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=0.8),
        SimpleNamespace(ts=bis[2].end_ts, macd=5.0, dif=1.2),  # 离开末笔力度反而更强 -> 无背驰
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["top_divergence"] is False
    assert "sell_1like" not in signals["sell_points"]


def test_analyze_chanlun_signals_confirmed_points_carry_lifecycle_state() -> None:
    """RS0：已确认买卖点带 lifecycle_state=confirmed 与 invalidated_reason=None（spec §2.8）。"""
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    bis = _lb1_range_bis()
    macd_points = _lb1_divergence_macd(bis)

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_1like" in signals["buy_points"]
    # 确认点带 confirmed 生命周期；反向转折已确认时不重复产出 forming 预备态（避免重复计数）。
    assert signals["forming_points"] == []
    confirmed = next(p for p in signals["signal_points"] if p["point"] == "buy1like")
    assert confirmed["lifecycle_state"] == "confirmed"
    assert confirmed["invalidated_reason"] is None


def test_analyze_chanlun_signals_forming_buy_1_when_divergence_without_reverse_turn() -> None:
    """RS1 一买预备（spec §2.8）：趋势下跌 + 底背驰 + 跌破下沿，但反向转折未确认 -> forming（非 confirmed）。"""
    prev_zs = _zhongshu(0, zs_low=11.6, zs_high=12.2, day=1)
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)  # 两中枢下移 -> down
    bis = _lb1_range_bis()[:5]  # 去掉向上反向转折 bi6
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),  # 离开末笔力度衰减 -> 底背驰
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["structure_state"]["current_ongoing"]["type"] == "down"
    assert signals["buy_points"] == []
    forming = signals["forming_points"]
    assert [p["point"] for p in forming] == ["buy1"]
    assert forming[0]["lifecycle_state"] == "forming"
    assert forming[0]["active"] is False
    assert forming[0]["invalidated_reason"] is None
    assert forming[0]["basis"] == "bottom_divergence_near_zs_low"
    assert forming[0]["signal_bi_id"] == 5
    assert forming[0]["price"] == 9.8


def test_analyze_chanlun_signals_forming_sell_1_when_divergence_without_reverse_turn() -> None:
    """RS1 一卖预备（对称）：趋势上涨 + 顶背驰 + 越上沿，反向转折未确认 -> forming。"""
    prev_zs = _zhongshu(1, zs_low=8.2, zs_high=8.8, day=1)
    current_zs = _zhongshu(2, zs_low=10.0, zs_high=10.8, day=10)  # 两中枢上移 -> up
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=10.1, day=10),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=11),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=12),  # 越上沿的确认 up 离开笔，无后续向下转折
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=5.0, dif=1.2),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=0.8),  # 顶背驰
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["structure_state"]["current_ongoing"]["type"] == "up"
    assert signals["sell_points"] == []
    forming = signals["forming_points"]
    assert [p["point"] for p in forming] == ["sell1"]
    assert forming[0]["lifecycle_state"] == "forming"
    assert forming[0]["basis"] == "top_divergence_near_zs_high"
    assert forming[0]["signal_bi_id"] == 3


def test_analyze_chanlun_signals_forming_buy_1like_when_range_divergence_without_reverse_turn() -> None:
    """RS1 类一买预备（spec §2.8）：range 单中枢盘整背驰 + 跌破下沿，反向转折未确认 -> forming。"""
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)  # 单中枢 -> range + ongoing_same_type
    bis = _lb1_range_bis()[:5]  # 去掉向上反向转折 bi6
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.5, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["structure_state"]["current_structure_status"] == "ongoing_same_type"
    assert signals["structure_state"]["current_ongoing"]["type"] == "range"
    assert signals["buy_points"] == []
    forming = signals["forming_points"]
    assert [p["point"] for p in forming] == ["buy1like"]
    assert forming[0]["lifecycle_state"] == "forming"
    assert forming[0]["basis"] == "consolidation_divergence_reverse_low"
    assert forming[0]["signal_bi_id"] == 5


def test_analyze_chanlun_signals_forming_buy_2_when_pullback_holds_without_renew() -> None:
    """RS1 二买预备（spec §2.8）：一买前置 + 首次回抽不破前低已成立，待再度走强确认 -> forming buy_2。"""
    prev_zs = _zhongshu(3, zs_low=11.6, zs_high=12.2, day=1)
    current_zs = _zhongshu(4, zs_low=10.2, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=10),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=11),
        _bi(3, BiDirection.DOWN, high=11.0, low=10.0, day=12),  # 一买离开（confirmed down）
        _bi(4, BiDirection.UP, high=11.3, low=10.3, day=13),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 14, 10, 30),
            end_ts=datetime(2026, 5, 14, 14, 30),
            high=11.1,
            low=10.4,  # 首次回抽不破前低 10.0，未再度走强
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),  # 底背驰
        SimpleNamespace(ts=bis[4].end_ts, macd=-1.0, dif=-0.4),
    ]

    signals = analyze_chanlun_signals([], bis, [prev_zs, current_zs], macd_points)

    assert signals["structure_state"]["current_ongoing"]["type"] == "down"
    assert "buy_2" not in signals["buy_points"]
    fp = next((p for p in signals["forming_points"] if p["point"] == "buy2"), None)
    assert fp is not None
    assert fp["lifecycle_state"] == "forming"
    assert fp["basis"] == "buy1_pullback_confirmation"
    assert fp["signal_bi_id"] == 5


def test_analyze_chanlun_signals_forming_buy_3_when_pullback_holds_without_renew() -> None:
    """RS1 三买预备（spec §2.8）：向上离开中枢 + 首次回踩守住上沿，待再度走强确认（尚未 renew）-> forming buy_3。"""
    current_zs = _zhongshu(3, zs_low=10.0, zs_high=10.8, day=20)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=20),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=21),
        _bi(3, BiDirection.UP, high=11.5, low=10.9, day=22),  # 向上离开（越上沿）
        _bi(4, BiDirection.DOWN, high=11.2, low=11.0, day=23),  # 首次回踩守住上沿，未 renew
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_3" not in signals["buy_points"]
    fp = next((p for p in signals["forming_points"] if p["point"] == "buy3"), None)
    assert fp is not None
    assert fp["lifecycle_state"] == "forming"
    assert fp["basis"] == "leave_zs_then_pullback_holds_upper_edge"
    assert fp["signal_bi_id"] == 4


def test_analyze_chanlun_signals_forming_buy_2like_when_gap_divergence_without_reverse_turn() -> None:
    """RS1 类二买预备（spec §2.8）：同级别隔段背驰已现但反向转折未确认 -> forming buy_2like。"""
    segments = _lb2_gap_segments()
    zhongshus = _down_trend_zhongshus()
    bis = [
        _bi(12, BiDirection.DOWN, high=11.2, low=10.6, day=1),
        _bi(22, BiDirection.UP, high=11.0, low=10.4, day=3),
        _bi(32, BiDirection.DOWN, high=10.9, low=9.8, day=5),  # A_{i+2} 回踩末笔
        Bi(
            bi_id=33,
            direction=BiDirection.UP,
            start_fx_id=33,
            end_fx_id=34,
            start_ts=datetime(2026, 5, 6, 10, 30),
            end_ts=datetime(2026, 5, 6, 14, 30),
            high=10.5,
            low=9.9,
            norm_bar_range=(33, 34),
            is_confirmed=False,  # 反向转折尚未确认 -> 预备态
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=segments[0].end_ts, macd=-5.0, dif=-1.0),  # A_i 力度强
        SimpleNamespace(ts=segments[2].end_ts, macd=-1.0, dif=-0.4),  # A_{i+2} 力度衰减
    ]

    signals = analyze_chanlun_signals([], bis, zhongshus, macd_points, segments=segments)

    assert "buy_2like" not in signals["buy_points"]
    fp = next((p for p in signals["forming_points"] if p["point"] == "buy2like"), None)
    assert fp is not None
    assert fp["lifecycle_state"] == "forming"
    assert fp["basis"] == "gap_segment_divergence_pullback_end"
    assert fp["signal_bi_id"] == 32


def _lifecycle_frame(
    signal_points: list[dict[str, object]],
    *,
    latest_down: Bi | None = None,
    latest_confirmed_up: Bi | None = None,
    current_zs: Zhongshu | None = None,
) -> dict[str, object]:
    return {
        "signal_points": signal_points,
        "latest_down": latest_down,
        "latest_confirmed_up": latest_confirmed_up,
        "current_zs": current_zs,
    }


def _confirmed_point(point: str, signal_bi_id: int, price: float) -> dict[str, object]:
    return {"point": point, "signal_bi_id": signal_bi_id, "price": price, "lifecycle_state": "confirmed"}


def test_replay_marks_buy_1_invalidated_when_departure_low_broken() -> None:
    """RS0 增量2：一买 confirmed 后，后续帧新低跌破离开段极值 -> invalidated（first_class_extreme_broken）。"""
    frame_a = _lifecycle_frame(
        [_confirmed_point("buy1", 5, 9.8)],
        latest_down=_bi(5, BiDirection.DOWN, high=11.0, low=9.8, day=5),
    )
    frame_b = _lifecycle_frame(
        [],  # 一买从 confirmed 集合消失
        latest_down=_bi(7, BiDirection.DOWN, high=10.4, low=9.5, day=7),  # 新低跌破 9.8
    )

    result = replay_confirmed_signal_lifecycle([frame_a, frame_b])

    assert result["repaint_violations"] == []
    assert len(result["invalidated"]) == 1
    inv = result["invalidated"][0]
    assert inv["point"] == "buy1"
    assert inv["signal_bi_id"] == 5
    assert inv["invalidated_reason"] == "first_class_extreme_broken"
    assert inv["invalidated_frame"] == 1


def test_replay_flags_repaint_violation_when_confirmed_vanishes_without_break() -> None:
    """RS0 增量2 repaint 红线：confirmed 消失但成立前提未破坏 -> repaint 违规（不得凭空消失）。"""
    frame_a = _lifecycle_frame(
        [_confirmed_point("buy1", 5, 9.8)],
        latest_down=_bi(5, BiDirection.DOWN, high=11.0, low=9.8, day=5),
    )
    frame_b = _lifecycle_frame(
        [],  # 消失
        latest_down=_bi(5, BiDirection.DOWN, high=11.0, low=10.5, day=6),  # 未跌破 9.8
    )

    result = replay_confirmed_signal_lifecycle([frame_a, frame_b])

    assert result["invalidated"] == []
    assert len(result["repaint_violations"]) == 1
    assert result["repaint_violations"][0]["kind"] == "vanished_without_break"


def test_replay_keeps_confirmed_persisting_without_invalidation() -> None:
    """RS0 增量2：confirmed 信号跨帧保持 -> 既不失效也不违规（单调保持）。"""
    frame_a = _lifecycle_frame(
        [_confirmed_point("buy1", 5, 9.8)],
        latest_down=_bi(5, BiDirection.DOWN, high=11.0, low=9.8, day=5),
    )
    frame_b = _lifecycle_frame(
        [_confirmed_point("buy1", 5, 9.8)],  # 仍确认
        latest_down=_bi(5, BiDirection.DOWN, high=11.0, low=9.8, day=6),
    )

    result = replay_confirmed_signal_lifecycle([frame_a, frame_b])

    assert result["invalidated"] == []
    assert result["repaint_violations"] == []
    assert [t["transition"] for t in result["timeline"]] == ["confirmed"]


def test_replay_marks_buy_3_invalidated_when_pullback_reenters_zs() -> None:
    """RS0 增量2：三买 confirmed 后回抽重新跌回中枢上沿之下 -> invalidated（third_class_reentered_zs）。"""
    zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    frame_a = _lifecycle_frame(
        [_confirmed_point("buy3", 6, 11.0)],
        current_zs=zs,
        latest_down=_bi(6, BiDirection.DOWN, high=11.4, low=11.0, day=5),  # 回踩守住上沿
    )
    frame_b = _lifecycle_frame(
        [],
        current_zs=zs,
        latest_down=_bi(8, BiDirection.DOWN, high=11.0, low=10.5, day=7),  # 回落到 zs_high=10.8 之下
    )

    result = replay_confirmed_signal_lifecycle([frame_a, frame_b])

    assert result["repaint_violations"] == []
    assert len(result["invalidated"]) == 1
    assert result["invalidated"][0]["invalidated_reason"] == "third_class_reentered_zs"


def test_to_lifecycle_frame_extracts_confirmed_anchors_and_scalars() -> None:
    """RS0 real-frame：to_lifecycle_frame 只保留 confirmed 锚点 + 前提比较标量（可持久化压缩帧）。"""
    current_zs = _zhongshu(1, zs_low=10.0, zs_high=10.8, day=1)
    bis = _lb1_range_bis()
    macd_points = _lb1_divergence_macd(bis)
    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    frame = to_lifecycle_frame(signals)

    assert frame["zs_high"] == 10.8
    assert frame["zs_low"] == 10.0
    assert all(p["lifecycle_state"] == "confirmed" for p in frame["signal_points"])
    assert any(p["point"] == "buy1like" for p in frame["signal_points"])


def test_derive_signal_lifecycle_transitions_marks_invalidated_across_runs() -> None:
    """RS0 real-frame：上次运行 confirmed 一买，本次运行新低跌破 -> invalidated（first_class_extreme_broken）。"""
    previous_frame = {
        "signal_points": [{"point": "buy1", "signal_bi_id": 5, "price": 9.8, "lifecycle_state": "confirmed"}],
        "latest_down_low": 9.8,
        "latest_up_high": None,
        "zs_high": None,
        "zs_low": None,
    }
    current_signals = {
        "signal_points": [],  # 一买不再确认
        "latest_down": _bi(7, BiDirection.DOWN, high=10.4, low=9.5, day=7),  # 新低跌破 9.8
        "latest_confirmed_up": None,
        "current_zs": None,
    }

    result = derive_signal_lifecycle_transitions(previous_frame, current_signals)

    assert result["repaint_violations"] == []
    assert len(result["invalidated_points"]) == 1
    inv = result["invalidated_points"][0]
    assert inv["point"] == "buy1"
    assert inv["lifecycle_state"] == "invalidated"
    assert inv["invalidated_reason"] == "first_class_extreme_broken"
    assert inv["active"] is False


def test_derive_signal_lifecycle_transitions_empty_on_first_frame() -> None:
    """RS0 real-frame：首帧（无上一帧）不产出 invalidated / repaint。"""
    result = derive_signal_lifecycle_transitions(None, {"signal_points": []})
    assert result == {"invalidated_points": [], "repaint_violations": []}


def test_build_signal_summary_fields_includes_invalidated_points_with_previous_frame() -> None:
    """RS0 real-frame：带上一帧时 summary 透出 invalidated_points；无上一帧时为空（向后兼容）。"""
    previous_frame = {
        "signal_points": [{"point": "buy1", "signal_bi_id": 5, "price": 9.8, "lifecycle_state": "confirmed"}],
        "latest_down_low": 9.8,
        "latest_up_high": None,
        "zs_high": None,
        "zs_low": None,
    }
    signals = {
        "buy_points": [],
        "sell_points": [],
        "signal_points": [],
        "signal_catalog": [],
        "forming_points": [],
        "latest_down": _bi(7, BiDirection.DOWN, high=10.4, low=9.5, day=7),
        "latest_confirmed_up": None,
        "current_zs": None,
        "same_level_consumption_level": None,
        "structure_state": {},
    }

    with_prev = build_signal_summary_fields(signals, previous_frame=previous_frame)
    assert len(with_prev["invalidated_points"]) == 1
    assert with_prev["invalidated_points"][0]["invalidated_reason"] == "first_class_extreme_broken"

    without_prev = build_signal_summary_fields(signals)
    assert without_prev["invalidated_points"] == []


def test_analyze_chanlun_signals_flags_third_buy_after_leave_zs_and_pullback_holds_upper_edge() -> None:
    """BS4 三买正例：向上离开中枢 + 首次回抽不重回中枢上沿之下 -> buy_3。"""
    current_zs = _zhongshu(3, zs_low=10.0, zs_high=10.8, day=20)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=20),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=21),
        _bi(3, BiDirection.UP, high=11.5, low=10.9, day=22),
        _bi(4, BiDirection.DOWN, high=11.2, low=11.0, day=23),
        Bi(
            bi_id=5,
            direction=BiDirection.UP,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 24, 10, 30),
            end_ts=datetime(2026, 5, 24, 14, 30),
            high=11.6,
            low=11.1,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == ["buy_3"]
    assert signals["sell_points"] == []
    assert signals["signal_catalog"][2]["basis"] == "leave_zs_then_pullback_holds_upper_edge"


def test_analyze_chanlun_signals_buy3_anchors_first_hold_not_latest_pullback() -> None:
    """BS4 三买锚点：多次回试时锁定首次回试，而非最新回踩（回归 300124 5m 61.5 vs 61.93）。"""
    current_zs = _zhongshu(19, zs_low=10.0, zs_high=10.8, day=20)
    bis = [
        _bi(1, BiDirection.UP, high=11.5, low=10.9, day=20),   # 向上离开
        _bi(2, BiDirection.DOWN, high=11.4, low=11.1, day=21),  # 首次回试（低点 11.1）
        _bi(3, BiDirection.UP, high=11.6, low=11.1, day=22),
        _bi(4, BiDirection.DOWN, high=11.5, low=11.2, day=23),  # 第二次回试（更高低点 11.2）
        Bi(
            bi_id=5,
            direction=BiDirection.UP,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 24, 10, 30),
            end_ts=datetime(2026, 5, 24, 14, 30),
            high=11.7,
            low=11.2,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == ["buy_3"]
    # 锚定在首次回试 bi2（低点 11.1），而非最新回踩 bi4（低点 11.2）。
    assert signals["signal_points"][0]["signal_bi_id"] == 2
    assert signals["signal_points"][0]["price"] == 11.1


def test_analyze_chanlun_signals_flags_third_sell_after_leave_zs_and_rebound_fails_lower_edge() -> None:
    """BS4 三卖正例（对称样例）：向下离开中枢 + 首次反抽不重回中枢下沿之上 -> sell_3。"""
    current_zs = _zhongshu(4, zs_low=10.0, zs_high=10.8, day=1)
    bis = [
        _bi(1, BiDirection.DOWN, high=10.5, low=10.1, day=1),
        _bi(2, BiDirection.UP, high=10.6, low=10.0, day=2),
        _bi(3, BiDirection.DOWN, high=10.4, low=9.5, day=3),
        _bi(4, BiDirection.UP, high=9.8, low=9.4, day=4),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 5, 10, 30),
            end_ts=datetime(2026, 5, 5, 14, 30),
            high=9.7,
            low=9.3,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=1.0, dif=0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=1.0, dif=0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["sell_points"] == ["sell_3"]
    assert signals["buy_points"] == []
    assert signals["signal_catalog"][5]["basis"] == "leave_zs_then_rebound_fails_lower_edge"


def test_analyze_chanlun_signals_flags_buy3_when_renew_up_resumes_without_new_high() -> None:
    """BS4 三买「再度走强」：回试后重新向上即确认（不强制创新高，贴合第20课原文）。"""
    current_zs = _zhongshu(17, zs_low=10.0, zs_high=10.8, day=20)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=20),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=21),
        _bi(3, BiDirection.UP, high=11.5, low=10.9, day=22),
        _bi(4, BiDirection.DOWN, high=11.2, low=11.0, day=23),
        Bi(
            bi_id=5,
            direction=BiDirection.UP,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 24, 10, 30),
            end_ts=datetime(2026, 5, 24, 14, 30),
            high=11.4,
            low=11.1,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == ["buy_3"]
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_flags_sell3_when_renew_down_resumes_without_new_low() -> None:
    """BS4 三卖「再度走弱」：反抽后重新向下即确认（不强制创新低，贴合第20课原文）。"""
    current_zs = _zhongshu(18, zs_low=10.0, zs_high=10.8, day=1)
    bis = [
        _bi(1, BiDirection.DOWN, high=10.5, low=10.1, day=1),
        _bi(2, BiDirection.UP, high=10.6, low=10.0, day=2),
        _bi(3, BiDirection.DOWN, high=10.4, low=9.5, day=3),
        _bi(4, BiDirection.UP, high=9.8, low=9.4, day=4),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 5, 10, 30),
            end_ts=datetime(2026, 5, 5, 14, 30),
            high=9.7,
            low=9.6,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=1.0, dif=0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=1.0, dif=0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == []
    assert signals["sell_points"] == ["sell_3"]


def test_analyze_chanlun_signals_does_not_flag_buy1_on_boundary_touch_without_divergence() -> None:
    """BS2 一买反例（红线）：仅触边不背驰 -> 不得确认 buy_1。

    离开段创新低但力度未衰减（macd 反而更强），不构成背驰导致的转折，
    即使低点已跌破中枢下沿也不得标记为一买。
    """
    current_zs = _zhongshu(5, zs_low=10.0, zs_high=10.8, day=5)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=9.8, day=5),
        _bi(2, BiDirection.UP, high=10.9, low=9.9, day=6),
        Bi(
            bi_id=3,
            direction=BiDirection.DOWN,
            start_fx_id=3,
            end_fx_id=4,
            start_ts=datetime(2026, 5, 7, 10, 30),
            end_ts=datetime(2026, 5, 7, 14, 30),
            high=11.0,
            low=9.7,
            norm_bar_range=(3, 4),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[2].end_ts, macd=-5.0, dif=-1.2),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["bottom_divergence"] is False
    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_does_not_flag_buy3_when_first_pullback_reenters_zs() -> None:
    """BS4 三买反例：首次回抽重新跌回中枢上沿之下 -> buy_3 不成立。"""
    current_zs = _zhongshu(6, zs_low=10.0, zs_high=10.8, day=10)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=10),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=11),
        _bi(3, BiDirection.UP, high=11.5, low=10.9, day=12),
        _bi(4, BiDirection.DOWN, high=11.2, low=10.7, day=13),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


def test_analyze_chanlun_signals_does_not_flag_buy3_without_renew_up_after_pullback() -> None:
    """BS4 三买「再度走强」：向上离开 + 回抽不跌回上沿，但尚未出现再度向上的笔 -> 三买不成立。"""
    current_zs = _zhongshu(13, zs_low=10.0, zs_high=10.8, day=20)
    bis = [
        _bi(1, BiDirection.UP, high=10.7, low=10.2, day=20),
        _bi(2, BiDirection.DOWN, high=10.6, low=10.1, day=21),
        _bi(3, BiDirection.UP, high=11.5, low=10.9, day=22),
        _bi(4, BiDirection.DOWN, high=11.2, low=11.0, day=23),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=-1.0, dif=-0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=3.0, dif=1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=-1.0, dif=-0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_3" not in signals["buy_points"]


def test_analyze_chanlun_signals_does_not_flag_sell3_without_renew_down_after_rebound() -> None:
    """BS4 三卖「再度走弱」：向下离开 + 反抽不站回下沿，但尚未出现再度向下的笔 -> 三卖不成立。"""
    current_zs = _zhongshu(14, zs_low=10.0, zs_high=10.8, day=1)
    bis = [
        _bi(1, BiDirection.DOWN, high=10.5, low=10.1, day=1),
        _bi(2, BiDirection.UP, high=10.6, low=10.0, day=2),
        _bi(3, BiDirection.DOWN, high=10.4, low=9.5, day=3),
        _bi(4, BiDirection.UP, high=9.8, low=9.4, day=4),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[1].end_ts, macd=1.0, dif=0.5),
        SimpleNamespace(ts=bis[2].end_ts, macd=-3.0, dif=-1.0),
        SimpleNamespace(ts=bis[3].end_ts, macd=1.0, dif=0.5),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "sell_3" not in signals["sell_points"]


def test_analyze_chanlun_signals_does_not_flag_buy2_on_continuation_pullback_breaking_prior_low() -> None:
    """BS3 二买易混淆例：中继震荡回抽跌破一买前低 -> 二买不成立。

    即便此前出现过一买结构，若首次确认性回抽跌破前低且力度未衰减，
    既不能确认二买，也不因单纯创新低而误报新一买（需背驰）。
    """
    current_zs = _zhongshu(7, zs_low=10.0, zs_high=10.8, day=15)
    bis = [
        _bi(1, BiDirection.DOWN, high=11.2, low=10.6, day=15),
        _bi(2, BiDirection.UP, high=10.9, low=10.4, day=16),
        _bi(3, BiDirection.DOWN, high=11.0, low=9.9, day=17),
        _bi(4, BiDirection.UP, high=11.3, low=10.2, day=18),
        Bi(
            bi_id=5,
            direction=BiDirection.DOWN,
            start_fx_id=5,
            end_fx_id=6,
            start_ts=datetime(2026, 5, 19, 10, 30),
            end_ts=datetime(2026, 5, 19, 14, 30),
            high=11.0,
            low=9.8,
            norm_bar_range=(5, 6),
            is_confirmed=False,
        ),
    ]
    macd_points = [
        SimpleNamespace(ts=bis[0].end_ts, macd=-5.0, dif=-1.0),
        SimpleNamespace(ts=bis[2].end_ts, macd=-2.0, dif=-0.6),
        SimpleNamespace(ts=bis[4].end_ts, macd=-5.0, dif=-1.2),
    ]

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert "buy_2" not in signals["buy_points"]
    assert signals["buy_points"] == []
    assert signals["sell_points"] == []


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


def test_analyze_chanlun_signals_exports_segment_level_zhongshu_exit_time() -> None:
    """segment 级中枢的 exit_bi_id 存的是线段 id，须按 segments 解析出离开段结束时间。"""
    zs = _segment_zhongshu(20, entering_segment_id=1, exit_segment_id=2, zs_low=10.0, zs_high=10.8)
    zs.is_terminated = True
    entering = _segment(1, BiDirection.UP, high=10.6, low=9.9, start_day=1)
    exit_seg = _segment(2, BiDirection.UP, high=11.2, low=10.3, start_day=3)
    bis = [
        _bi(1, BiDirection.UP, high=10.6, low=9.9, day=1),
        _bi(2, BiDirection.DOWN, high=10.5, low=10.0, day=2),
        _bi(3, BiDirection.UP, high=11.2, low=10.3, day=3),
    ]

    signals = analyze_chanlun_signals([], bis, [zs], [], segments=[entering, exit_seg])

    assert signals["current_zs_exit_bi"] is exit_seg
    assert signals["current_zs_exit_time"] == "2026-05-04T14:30:00"


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


def test_build_lower_timeframe_precision_entry_downgrades_auxiliary_higher_level() -> None:
    """上级别同级别结构为辅助（无稳定标准中枢）时，次级别买卖点不得升格为 actionable。"""
    higher_signals = {
        "buy_points": ["buy_1"],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {"point": "buy1", "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "bottom_divergence_near_zs_low"}
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
        "same_level_consumption_level": "auxiliary",
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "signal_catalog": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert entry["higher_consumption_level"] == "auxiliary"
    assert entry["higher_consumption_level_label"] == "仅辅助观察"
    assert "不按严格区间套执行" in entry["note"]


def test_build_lower_timeframe_precision_entry_downgrades_pending_higher_level() -> None:
    """上级别同级别结构仍待确认（pending）时，次级别买卖点不得升格为 actionable。"""
    higher_signals = {
        "buy_points": ["buy_1"],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {"point": "buy1", "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "bottom_divergence_near_zs_low"}
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
        "same_level_consumption_level": "pending",
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "signal_catalog": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert entry["higher_consumption_level"] == "pending"
    assert entry["higher_consumption_level_label"] == "待确认消费"
    assert "不按严格区间套执行" in entry["note"]


def test_build_lower_timeframe_precision_entry_downgrades_legacy_pending_higher_level() -> None:
    """旧上级别 payload 仅带 structure_state 时，也要沿兼容路径降级次级别买卖点。"""
    higher_signals = {
        "buy_points": ["buy_1"],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {"point": "buy1", "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "bottom_divergence_near_zs_low"}
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
        "structure_state": {
            "current_structure_status": "candidate_completed_waiting_stability",
            "current_ongoing": {"type": "down", "confirmation_basis": "single_active_zhongshu"},
        },
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "signal_catalog": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "watch"
    assert entry["higher_consumption_level"] == "pending"
    assert entry["higher_consumption_level_label"] == "待确认消费"
    assert "不按严格区间套执行" in entry["note"]


def test_build_lower_timeframe_precision_entry_keeps_actionable_when_higher_confirmed() -> None:
    """上级别同级别结构已确认（confirmed）时，次级别买卖点保持 actionable。"""
    higher_signals = {
        "buy_points": ["buy_1"],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {"point": "buy1", "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "bottom_divergence_near_zs_low"}
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
        "same_level_consumption_level": "confirmed",
    }
    lower_signals = {
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "signal_catalog": [{"point": "buy2", "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }

    entry = build_lower_timeframe_precision_entry(
        higher_signals,
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["status"] == "actionable"
    assert entry["higher_consumption_level"] == "confirmed"
    assert entry["higher_consumption_level_label"] == "已确认消费"


def _precision_higher_signals_with_drift(side: str, drift: str) -> dict[str, object]:
    point = f"{side}1"
    return {
        "buy_points": [point] if side == "buy" else [],
        "sell_points": [point] if side == "sell" else [],
        "current_zs": SimpleNamespace(end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False),
        "signal_points": [
            {"point": point, "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "bottom_divergence_near_zs_low"}
        ],
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
        "same_level_consumption_level": "confirmed",
        "structure_state": {"current_ongoing": {"type": drift}},
    }


def _precision_lower_signals(side: str) -> dict[str, object]:
    point = f"{side}2"
    return {
        "buy_points": [point] if side == "buy" else [],
        "sell_points": [point] if side == "sell" else [],
        "signal_points": [{"point": point, "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "signal_catalog": [{"point": point, "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "buy1_pullback_confirmation"}],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }


@pytest.mark.parametrize(
    ("side", "drift", "expected_grade", "expected_label"),
    [
        ("buy", "range", "oscillation_opportunity", "震荡机会"),
        ("buy", "up", "no_operational_value", "无操作价值"),
        ("buy", "down", "warning", "警戒"),
        ("sell", "range", "oscillation_opportunity", "震荡机会"),
        ("sell", "up", "warning", "警戒"),
        ("sell", "down", "no_operational_value", "无操作价值"),
    ],
)
def test_build_lower_timeframe_precision_entry_dynamic_grade(
    side: str,
    drift: str,
    expected_grade: str,
    expected_label: str,
) -> None:
    """86课：次级别买卖点的操作意义随大级别中枢漂移方向动态判级。"""
    entry = build_lower_timeframe_precision_entry(
        _precision_higher_signals_with_drift(side, drift),
        _precision_lower_signals(side),
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["dynamic_grade"] == expected_grade
    assert entry["dynamic_grade_label"] == expected_label


def test_build_lower_timeframe_precision_entry_marks_small_to_large_candidate_without_buy3_sell3() -> None:
    entry = build_lower_timeframe_precision_entry(
        {
            **_precision_higher_signals_with_drift("buy", "down"),
            "post_divergence_route": "higher_level_reverse_trend",
        },
        _precision_lower_signals("buy"),
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["small_to_large_status"] == "candidate"
    assert entry["small_to_large_status_label"] == "小转大候选"
    assert "最后一个次级别中枢" in entry["small_to_large_status_note"]


def test_build_lower_timeframe_precision_entry_marks_small_to_large_necessary_condition_when_buy3_sell3_exists() -> None:
    lower_signals = {
        **_precision_lower_signals("buy"),
        "buy_points": ["buy3"],
        "signal_points": [
            {
                "point": "buy3",
                "active": True,
                "time": "2026-05-10T14:25:00",
                "price": 10.25,
                "basis": "leave_zs_then_pullback_holds_upper_edge",
            }
        ],
        "signal_catalog": [
            {
                "point": "buy3",
                "active": True,
                "time": "2026-05-10T14:25:00",
                "price": 10.25,
                "basis": "leave_zs_then_pullback_holds_upper_edge",
            }
        ],
    }

    entry = build_lower_timeframe_precision_entry(
        {
            **_precision_higher_signals_with_drift("buy", "down"),
            "post_divergence_route": "higher_level_reverse_trend",
        },
        lower_signals,
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )

    assert entry["small_to_large_status"] == "third_class_confirmed"
    assert entry["small_to_large_status_label"] == "小转大必要条件已具备"
    assert "不等于高级别转折充分确认" in entry["small_to_large_status_note"]


def test_build_precision_window_display_includes_dynamic_grade() -> None:
    display = build_precision_window_display(
        {
            "operation_level": "5M",
            "window_basis_label": "中枢到锚点窗口",
            "window_basis_description": "窗口依据：上级别离开笔尚未单独解析。",
            "dynamic_grade": "warning",
            "dynamic_grade_label": "警戒",
        }
    )

    assert display["dynamic_grade"] == "warning"
    assert display["dynamic_grade_label"] == "警戒"
    assert "5M判级：警戒" in display["lines"]


def test_build_precision_window_display_includes_small_to_large_status() -> None:
    display = build_precision_window_display(
        {
            "operation_level": "5M",
            "small_to_large_status": "candidate",
            "small_to_large_status_label": "小转大候选",
        }
    )

    assert display["small_to_large_status"] == "candidate"
    assert display["small_to_large_status_label"] == "小转大候选"
    assert "小转大：小转大候选" in display["lines"]


def test_build_precision_window_display_omits_grade_when_absent() -> None:
    display = build_precision_window_display(
        {
            "operation_level": "5M",
            "window_basis_label": "中枢到锚点窗口",
            "window_basis_description": "窗口依据：上级别离开笔尚未单独解析。",
        }
    )

    assert display["dynamic_grade"] is None
    assert display["dynamic_grade_label"] is None
    assert all("判级" not in line for line in display["lines"])


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