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

from chanlun.analysis import _build_zs_monitor_state, analyze_chanlun_signals, build_lower_timeframe_precision_entry, build_signal_point_payloads, build_signal_summary_fields, build_structure_state
from chanlun.models import Bi, BiDirection, Zhongshu
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
        {"type": "up", "status": "completed", "zs_count": 2, "start_zs_id": 1, "end_zs_id": 2},
        {"type": "range", "status": "ongoing", "zs_count": 1, "start_zs_id": 3, "end_zs_id": 3},
    ]


def test_build_structure_state_type_chain_single_and_empty() -> None:
    empty_state = build_structure_state([], [])
    assert empty_state["type_chain"] == []

    single_state = build_structure_state([], [_zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)])
    assert single_state["type_chain"] == [
        {"type": "range", "status": "ongoing", "zs_count": 1, "start_zs_id": 1, "end_zs_id": 1},
    ]


def test_build_structure_state_type_chain_folds_multiple_completed_runs() -> None:
    """TD1 复杂前缀链：多个已完成的同级别 run 折叠为 completed，当前 ongoing 尾段保留。

    构造三个 run：up（zs1->zs2 终结）→ down（zs4->zs5 终结）→ range（zs7 ongoing），
    中间用被更大扩张吸收的中枢分隔。验证 type_chain 把两个历史 run 按 run 粒度折叠为
    completed，并保留当前 ongoing，且 last_completed 指向最近的 completed run（down）。
    """
    # run1: up（zs1 -> zs2 向上推进，zs2 终结）
    up1 = _zhongshu(1, zs_low=10.0, zs_high=11.0, day=1)
    up2 = _zhongshu(2, zs_low=11.5, zs_high=12.0, day=4)
    up2.is_terminated = True
    # 分隔：被更大扩张吸收，打断 run1
    sep1 = _zhongshu(3, zs_low=12.5, zs_high=13.0, day=7)
    sep1.superseded_by_zs_id = 4
    sep1.is_reabsorbed_by_larger_expansion = True
    # run2: down（zs4 -> zs5 向下推进，zs5 终结）
    down1 = _zhongshu(4, zs_low=9.0, zs_high=9.4, day=10)
    down2 = _zhongshu(5, zs_low=8.6, zs_high=8.9, day=13)
    down2.is_terminated = True
    # 分隔：打断 run2（不重叠，不影响当前 rng 判断）
    sep2 = _zhongshu(6, zs_low=8.2, zs_high=8.6, day=16)
    sep2.superseded_by_zs_id = 7
    sep2.is_reabsorbed_by_larger_expansion = True
    # run3: range ongoing
    rng = _zhongshu(7, zs_low=10.0, zs_high=10.5, day=19)

    state = build_structure_state([], [up1, up2, sep1, down1, down2, sep2, rng])

    assert state["type_chain"] == [
        {"type": "up", "status": "completed", "zs_count": 2, "start_zs_id": 1, "end_zs_id": 2},
        {"type": "down", "status": "completed", "zs_count": 2, "start_zs_id": 4, "end_zs_id": 5},
        {"type": "range", "status": "ongoing", "zs_count": 1, "start_zs_id": 7, "end_zs_id": 7},
    ]
    assert state["last_completed"]["type"] == "down"
    assert state["last_completed"]["zs_count"] == 2
    assert state["last_completed"]["status"] == "completed"
    assert state["current_ongoing"]["type"] == "range"
    assert state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["relationship"]["transition_state"] == "candidate_new_type"


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

    assert state["last_completed"] is not None
    assert state["last_completed"]["start_zs_id"] == first.zs_id
    assert state["last_completed"]["end_zs_id"] == first.zs_id
    assert state["current_ongoing"]["start_zs_id"] == third.zs_id
    assert state["current_ongoing"]["end_zs_id"] == third.zs_id
    assert state["current_ongoing"]["zs_count_so_far"] == 1
    assert state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert state["relationship"]["transition_state"] == "candidate_new_type"
    assert state["current_structure_status"] == "candidate_completed_waiting_stability"


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
    # 严格二卖需「反抽不破前高 + 反抽后再度走弱」；该 cutoff 反抽(58)尚未被向下笔跟随，故只报 sell_1。
    assert payload["sell_points"] == ["sell_1"]
    assert payload["conclusion"] == "观察，等待确认。"
    assert payload["latest_zs_low"] == 19.97
    assert payload["latest_zs_high"] == 20.24
    assert "结论：观察，等待确认。" in payload["advice_text"]
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
    assert payload["sell_points"] == ["sell_3"]
    assert payload["conclusion"] == "观察，等待确认。"
    assert payload["latest_zs_low"] == 28.71
    assert payload["latest_zs_high"] == 28.85
    assert "结论：观察，等待确认。" in payload["advice_text"]
    assert "监视器：中枢中线 28.78，当前偏弱，预警状态 向下预警。" in payload["advice_text"]
    assert "节奏监视：节奏偏强，当前只作辅助观察，不单独升级主结论。" in payload["advice_text"]
    assert "确认三买" not in payload["advice_text"]


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
    # 背驰模块首个真实 1m 下跌趋势底背驰（非严格）样本：
    # 两个不重叠中枢（zs0 [41.75,41.92]、zs1 [40.04,40.51]）构成下跌趋势，
    # 同向下探力度衰减但离开段未跌破 zs1 下沿 -> trend_active=True、strict=False，
    # route 回落 last_zs_extension（TD2 趋势轨）。
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-08-12 10:38", rows)

    assert payload["cutoff"] == "2026-08-12 10:38"
    assert payload["ongoing_type"] == "down"
    assert payload["divergence_trend_active"] is True
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is False
    assert payload["divergence_range_strict"] is False
    assert payload["divergence_range_touches_boundary"] is None
    assert payload["post_divergence_route"] == "last_zs_extension"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"


def test_real_1m_trend_divergence_replay_sample_000651_down_second_anchor() -> None:
    # 第二个 cutoff 锚点：与 08-12 同一下跌趋势底背驰（非严格），锁追加更多 bar 后
    # 结构分类与背驰结论不漂移（trend_active=True、strict=False、route=last_zs_extension）。
    rows = probe_module._load_rows("000651", "1m")
    payload = probe_module._replay("000651", "格力电器", "2026-08-14 10:57", rows)

    assert payload["cutoff"] == "2026-08-14 10:57"
    assert payload["ongoing_type"] == "down"
    assert payload["divergence_trend_active"] is True
    assert payload["divergence_trend_strict"] is False
    assert payload["divergence_range_active"] is False
    assert payload["divergence_range_strict"] is False
    assert payload["divergence_range_touches_boundary"] is None
    assert payload["post_divergence_route"] == "last_zs_extension"
    assert payload["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["same_level_consumption_level"] == "confirmed"


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

    assert "sell_2" in signals["sell_points"]
    assert signals["signal_catalog"][4]["active"] is True
    assert signals["signal_catalog"][4]["basis"] == "sell1_rebound_confirmation"


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

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

    assert signals["buy_points"] == ["buy_1"]
    assert signals["sell_points"] == []
    assert signals["bottom_divergence"] is True


def test_analyze_chanlun_signals_flags_first_sell_on_top_divergence_above_zs_high() -> None:
    """BS2 一卖正例（对称样例）：最近中枢 + 向上离开段越过中枢上沿 + 顶背驰 -> sell_1。"""
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

    signals = analyze_chanlun_signals([], bis, [current_zs], macd_points)

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


def test_analyze_chanlun_signals_flags_third_buy_after_leave_zs_and_pullback_holds_upper_edge() -> None:
    """BS4 三买正例：向上离开中枢 + 首次回抽不重回中枢上沿之下 -> buy_3。"""
    current_zs = _zhongshu(3, zs_low=10.0, zs_high=10.8, day=20)
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

    assert signals["buy_points"] == ["buy_3"]
    assert signals["sell_points"] == []
    assert signals["signal_catalog"][2]["basis"] == "leave_zs_then_pullback_holds_upper_edge"


def test_analyze_chanlun_signals_flags_third_sell_after_leave_zs_and_rebound_fails_lower_edge() -> None:
    """BS4 三卖正例（对称样例）：向下离开中枢 + 首次反抽不重回中枢下沿之上 -> sell_3。"""
    current_zs = _zhongshu(4, zs_low=10.0, zs_high=10.8, day=1)
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

    assert signals["sell_points"] == ["sell_3"]
    assert signals["buy_points"] == []
    assert signals["signal_catalog"][5]["basis"] == "leave_zs_then_rebound_fails_lower_edge"


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