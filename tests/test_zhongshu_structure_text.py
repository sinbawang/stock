from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_cn_60m_chanlun_report as cn_report
from batch_prepare_chanlun_reports import build_advice, build_technical_summary


@dataclass
class FakeBi:
    bi_id: int
    direction: str
    start_ts: datetime
    end_ts: datetime
    high: float
    low: float
    is_confirmed: bool = True

    def is_up(self) -> bool:
        return self.direction == "up"

    def is_down(self) -> bool:
        return self.direction == "down"


def _sample_zhongshu(
    exit_bi_id: int | None = None,
    *,
    zs_id: int = 2,
    entering_bi_id: int = 8,
    superseded_by_zs_id: int | None = None,
    is_reabsorbed_by_larger_expansion: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        zs_id=zs_id,
        structure_level="bi",
        recognition_mode="fixed_first_three_overlap",
        render_mode="core_plus_extension",
        zs_low=10.1,
        zs_high=10.8,
        start_ts=datetime(2026, 5, 1, 10, 30),
        end_ts=datetime(2026, 5, 29, 14, 30),
        entering_bi_id=entering_bi_id,
        core_bi_ids=[9, 10, 11],
        bi_ids=[9, 10, 11, 12],
        exit_bi_id=exit_bi_id,
        superseded_by_zs_id=superseded_by_zs_id,
        is_reabsorbed_by_larger_expansion=is_reabsorbed_by_larger_expansion,
    )


def test_build_advice_mentions_core_and_extended_bis() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": None,
        "latest_down": None,
        "buy_points": [],
        "sell_points": [],
        "top_divergence": False,
        "bottom_divergence": False,
    }
    raw_bars = [SimpleNamespace(close=10.5)]

    text = build_advice("示例标的", "60M", raw_bars, signals)

    assert "本体三笔(core_bi_ids)：9,10,11" in text
    assert "扩展参与笔(bi_ids)：9,10,11,12" in text
    assert "离开笔：未出现" in text


def test_build_advice_describes_second_buy_in_plain_language() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": None,
        "latest_down": SimpleNamespace(low=10.25),
        "buy_points": ["buy_2"],
        "sell_points": [],
        "top_divergence": False,
        "bottom_divergence": False,
        "signal_points": [
            {
                "point": "buy2",
                "active": True,
                "price": 10.25,
                "basis": "buy1_pullback_confirmation",
                "related_zs_id": 2,
            }
        ],
    }
    raw_bars = [SimpleNamespace(close=10.5)]

    text = build_advice("示例标的", "60M", raw_bars, signals)

    assert "出现 二买" in text
    assert "信号说明：二买，一买后回抽确认，低点未再跌破前低，参考价 10.25，关联中枢 ZS2。" in text


def test_build_advice_keeps_pre_breakdown_as_pending_watch() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": None,
        "latest_down": None,
        "buy_points": [],
        "sell_points": [],
        "top_divergence": False,
        "bottom_divergence": False,
        "oscillation_rhythm_state": "down_bias",
        "zs_monitor_alert": "pre_breakdown",
        "zs_monitor_midline": 10.45,
        "zs_monitor_bias": "weak",
    }
    raw_bars = [SimpleNamespace(close=10.18)]

    text = build_advice("示例标的", "60M", raw_bars, signals)

    assert "出现向下预警，但当前不构成确认三卖。" in text
    assert "监视器：中枢中线 10.45，当前偏弱，预警状态 向下预警。" in text
    assert "节奏监视：节奏偏弱，当前只作辅助观察，不单独升级主结论。" in text


# 注：原 `test_real_1m_pre_breakdown_sample_keeps_pending_watch_advice_and_analysis`
# 已移除：其锚点 `data/reports/000651/1m/tech.json`（generated_at 2026-08-20）过期且内部自相矛盾，
# 且当前 16 个 1m 标的中不存在真实 `pre_breakdown`（见 zhongshu-tasks.md ZS5.3.b 锚点漂移记录）。
# 同语义覆盖改由 replay gate 承担：
#   tests/test_chanlun_analysis.py::test_real_1m_pre_breakdown_replay_sample_preserves_independent_gate
# 以及 build_advice 单测 test_build_advice_keeps_pre_breakdown_as_pending_watch。


def test_real_01024_1m_up_warning_live_sample_keeps_current_state() -> None:
    # 数据刷新（2026-08-28）后，01024 1m 真实样本已不再产生确认三卖，而是「向上预警 + 偏强持有」态；
    # confirmed 三卖文案由 test_build_advice_prefers_confirmed_sell3_when_downtrend_conflicts_with_buy1 与
    # bundle 层 reference anchor 兜底。
    sample_path = ROOT / "data" / "reports" / "01024" / "1m" / "tech.json"
    payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert payload["timeframe"] == "1m"
    assert payload["summary"]["conclusion"] == "偏强，持有为主。"
    assert payload["summary"]["same_level_consumption_level"] == "confirmed"
    assert payload["summary"]["same_level_consumption_level_label"] == "已确认消费"
    assert payload["summary"]["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["summary"]["oscillation_rhythm_state"] == "down_bias"
    assert payload["summary"]["buy_points"] == []
    assert payload["summary"]["sell_points"] == []
    assert "消费等级：已确认消费" in payload["analysis_text"]
    assert "买点：当前无确认一二三类买点" in payload["analysis_text"]
    assert "卖点：当前无确认一二三类卖点" in payload["analysis_text"]
    assert "结论：偏强，持有为主。" in payload["advice_text"]
    assert "预警状态 向上预警" in payload["advice_text"]
    assert "三卖" not in payload["advice_text"]
    assert "三买" not in payload["advice_text"]


def test_real_002555_1m_down_warning_live_sample_keeps_current_state() -> None:
    # 数据刷新（2026-08-28）后，002555 1m 真实样本已不再产生确认三卖，而是「向下预警 + 偏弱观望」态。
    sample_path = ROOT / "data" / "reports" / "002555" / "1m" / "tech.json"
    payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert payload["timeframe"] == "1m"
    assert payload["summary"]["conclusion"] == "偏弱，先观望。"
    assert payload["summary"]["same_level_consumption_level"] == "confirmed"
    assert payload["summary"]["same_level_consumption_level_label"] == "已确认消费"
    assert payload["summary"]["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["summary"]["oscillation_rhythm_state"] == "up_bias"
    assert payload["summary"]["buy_points"] == []
    assert payload["summary"]["sell_points"] == []
    assert "消费等级：已确认消费" in payload["analysis_text"]
    assert "买点：当前无确认一二三类买点" in payload["analysis_text"]
    assert "卖点：当前无确认一二三类卖点" in payload["analysis_text"]
    assert "结论：偏弱，先观望。" in payload["advice_text"]
    assert "预警状态 向下预警" in payload["advice_text"]
    assert "三卖" not in payload["advice_text"]
    assert "三买" not in payload["advice_text"]


def test_real_600900_1m_down_warning_live_sample_keeps_current_state() -> None:
    # 数据刷新（2026-08-28）后，600900 1m 真实样本已不再产生确认三买，而是「向下预警 + 偏弱观望」态。
    sample_path = ROOT / "data" / "reports" / "600900" / "1m" / "tech.json"
    payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert payload["timeframe"] == "1m"
    assert payload["summary"]["conclusion"] == "偏弱，先观望。"
    assert payload["summary"]["same_level_consumption_level"] == "confirmed"
    assert payload["summary"]["same_level_consumption_level_label"] == "已确认消费"
    assert payload["summary"]["same_level_decomposition_mode"] == "single_confirmed"
    assert payload["summary"]["oscillation_rhythm_state"] == "up_bias"
    assert payload["summary"]["buy_points"] == []
    assert payload["summary"]["sell_points"] == []
    assert "消费等级：已确认消费" in payload["analysis_text"]
    assert "买点：当前无确认一二三类买点" in payload["analysis_text"]
    assert "卖点：当前无确认一二三类卖点" in payload["analysis_text"]
    assert "结论：偏弱，先观望。" in payload["advice_text"]
    assert "预警状态 向下预警" in payload["advice_text"]
    assert "三卖" not in payload["advice_text"]
    assert "三买" not in payload["advice_text"]
    assert "出现向上预警，但当前不构成确认三买。" not in payload["advice_text"]


def test_build_advice_downgrades_buy_signal_when_same_level_decomposition_is_pending() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": None,
        "latest_down": SimpleNamespace(low=10.25),
        "buy_points": ["buy_2"],
        "sell_points": [],
        "top_divergence": False,
        "bottom_divergence": False,
        "same_level_consumption_level": "pending",
        "same_level_decomposition_mode": "dual_interpretation_pending",
        "signal_points": [
            {
                "point": "buy2",
                "active": True,
                "price": 10.25,
                "basis": "buy1_pullback_confirmation",
                "related_zs_id": 2,
            }
        ],
    }
    raw_bars = [SimpleNamespace(close=10.5)]

    text = build_advice("示例标的", "60M", raw_bars, signals)

    assert "结论：观察，等待确认。" in text
    assert "已出现 二买，但当前同级别结构仍处待确认消费，不能直接上升为已确认买点。" in text
    assert "消费说明：当前同级别结构处于 待确认消费，当前已有结构线索，但还不能直接升级为同级别强确认结论。" in text
    assert "结论：偏多，允许轻仓试错。" not in text


def test_build_advice_prefers_confirmed_sell3_when_downtrend_conflicts_with_buy1() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": SimpleNamespace(high=33.94),
        "latest_down": SimpleNamespace(low=33.52),
        "buy_points": ["buy_1"],
        "sell_points": ["sell_3"],
        "top_divergence": False,
        "bottom_divergence": True,
        "same_level_consumption_level": "confirmed",
        "structure_state": {
            "current_ongoing": {
                "type": "down",
                "status": "ongoing",
                "start_ts": "2026-08-05T10:18:00",
                "latest_ts": "2026-08-20T15:56:00",
                "zs_count_so_far": 3,
            }
        },
        "signal_points": [
            {
                "point": "buy1",
                "active": True,
                "price": 33.52,
                "basis": "bottom_divergence_near_zs_low",
                "related_zs_id": 2,
            },
            {
                "point": "sell3",
                "active": True,
                "price": 33.94,
                "basis": "leave_zs_then_rebound_fails_lower_edge",
                "related_zs_id": 2,
            },
        ],
    }
    raw_bars = [SimpleNamespace(close=33.52)]

    text = build_advice("示例标的", "1M", raw_bars, signals)

    assert "结论：跌破中枢后反抽下沿失败，当前按三卖确认处理。" in text
    assert "理由：出现 三卖，且当前同级别结构已具备稳定消费基础。" in text
    assert "建议：反抽不过 33.94 以减仓为主，不逆势加仓。" in text
    assert "结论：偏多，允许轻仓试错。" not in text


def test_build_advice_explains_candidate_new_type_transition_state() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "latest_confirmed_up": None,
        "latest_down": None,
        "buy_points": [],
        "sell_points": [],
        "top_divergence": False,
        "bottom_divergence": False,
        "same_level_decomposition_mode": "dual_interpretation_pending",
        "structure_state": {
            "relationship": {
                "kind": "completed_then_new_type_ongoing",
                "transition_state": "candidate_new_type",
            }
        },
    }
    raw_bars = [SimpleNamespace(close=10.5)]

    text = build_advice("示例标的", "60M", raw_bars, signals)

    assert "消费说明：当前同级别结构处于 待确认消费，当前已有结构线索，但还不能直接升级为同级别强确认结论。" in text
    assert "转场说明：新走势候选，前段走势已完成，但当前新走势仍处候选待确认阶段。" in text


def test_analyze_current_state_mentions_core_and_extended_bis(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "最新中枢结构：本体三笔(core_bi_ids)：9,10,11" in text
    assert "扩展参与笔(bi_ids)：9,10,11,12" in text
    assert "离开笔：13" in text
    assert "当前正在进行走势类型：range" in text
    assert "盘整背驰：无" in text


def test_analyze_current_state_includes_cut_status_text(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    original_analyze = cn_report.analyze_chanlun_signals
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]

    def fake_analyze(raw_bars, bis, zhongshus, macd_points, segments=None):
        payload = original_analyze(raw_bars, bis, zhongshus, macd_points)
        payload["structure_state"]["current_structure_status"] = "candidate_completed_waiting_stability"
        return payload

    monkeypatch.setattr(cn_report, "analyze_chanlun_signals", fake_analyze)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "切分状态：前段走势已具备完成候选，但边界仍待右侧结构确认稳定。" in text


def test_analyze_current_state_includes_consumption_level_text(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    original_analyze = cn_report.analyze_chanlun_signals
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]

    def fake_analyze(raw_bars, bis, zhongshus, macd_points, segments=None):
        payload = original_analyze(raw_bars, bis, zhongshus, macd_points)
        payload["same_level_consumption_level"] = "pending"
        payload["structure_state"]["consumption_level"] = "pending"
        return payload

    monkeypatch.setattr(cn_report, "analyze_chanlun_signals", fake_analyze)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "消费等级：待确认消费，当前已有结构线索，但还不能直接升级为同级别强确认结论。" in text


def test_analyze_current_state_includes_transition_state_text(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    original_analyze = cn_report.analyze_chanlun_signals
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]

    def fake_analyze(raw_bars, bis, zhongshus, macd_points, segments=None):
        payload = original_analyze(raw_bars, bis, zhongshus, macd_points)
        payload["structure_state"] = {
            "last_completed": {
                "type": "up",
                "status": "completed",
                "start_ts": "2026-05-01T10:30:00",
                "end_ts": "2026-05-10T10:30:00",
            },
            "current_ongoing": {
                "type": "down",
                "status": "ongoing",
                "start_ts": "2026-05-15T10:30:00",
                "latest_ts": "2026-05-29T10:30:00",
            },
            "relationship": {
                "kind": "completed_then_new_type_ongoing",
                "transition_state": "candidate_new_type",
            },
            "current_structure_status": "candidate_completed_waiting_stability",
        }
        return payload

    monkeypatch.setattr(cn_report, "analyze_chanlun_signals", fake_analyze)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "转场状态：新走势候选，前段走势已完成，但当前新走势仍处候选待确认阶段。" in text


def test_analyze_current_state_includes_reabsorption_debug_text(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]
    previous_zs = _sample_zhongshu(29, zs_id=2, entering_bi_id=18, superseded_by_zs_id=3, is_reabsorbed_by_larger_expansion=True)
    current_zs = _sample_zhongshu(None, zs_id=3, entering_bi_id=29)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [previous_zs, current_zs], [])

    assert "重写说明：前一中枢 ZS2 虽已走出，但其走出笔 29 被当前中枢 ZS3 复用为进入笔 29，当前按更大级别扩展吸收处理。" in text


def test_analyze_current_state_uses_human_readable_signal_names(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]
    original_analyze = cn_report.analyze_chanlun_signals

    def fake_analyze(raw_bars, bis, zhongshus, macd_points, segments=None):
        payload = original_analyze(raw_bars, bis, zhongshus, macd_points)
        payload["buy_points"] = ["buy_2"]
        payload["signal_points"] = [
            {
                "point": "buy2",
                "active": True,
                "price": 10.25,
                "basis": "buy1_pullback_confirmation",
                "related_zs_id": 2,
            }
        ]
        return payload

    monkeypatch.setattr(cn_report, "analyze_chanlun_signals", fake_analyze)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "买点：二买" in text
    assert "信号细化：二买，一买后回抽确认，低点未再跌破前低，参考价 10.25，关联中枢 ZS2" in text


def test_analyze_current_state_labels_same_type_extension_as_confirmed_slice(monkeypatch) -> None:
    monkeypatch.setattr(cn_report, "compute_bi_strengths", lambda bis, macd_points: {})
    original_analyze = cn_report.analyze_chanlun_signals
    raw_bars = [
        SimpleNamespace(ts=datetime(2026, 5, 1, 10, 30), close=10.2),
        SimpleNamespace(ts=datetime(2026, 5, 29, 14, 30), close=10.6),
    ]
    bis = [
        FakeBi(7, "up", datetime(2026, 5, 1, 10, 30), datetime(2026, 5, 8, 14, 30), 10.9, 10.0),
        FakeBi(12, "down", datetime(2026, 5, 9, 10, 30), datetime(2026, 5, 29, 14, 30), 10.8, 10.2, is_confirmed=False),
    ]

    def fake_analyze(raw_bars, bis, zhongshus, macd_points, segments=None):
        payload = original_analyze(raw_bars, bis, zhongshus, macd_points)
        payload["structure_state"] = {
            "last_completed": {
                "type": "down",
                "status": "completed",
                "start_ts": "2026-05-01T10:30:00",
                "end_ts": "2026-05-10T10:30:00",
            },
            "current_ongoing": {
                "type": "down",
                "status": "ongoing",
                "start_ts": "2026-05-15T10:30:00",
                "latest_ts": "2026-05-29T10:30:00",
            },
            "relationship": {
                "kind": "same_type_extension",
                "note": "当前结构更接近前一走势类型的同类延伸，暂未看到清晰的新类型完成边界。",
            },
            "current_structure_status": "ongoing_same_type",
        }
        return payload

    monkeypatch.setattr(cn_report, "analyze_chanlun_signals", fake_analyze)

    text = cn_report.analyze_current_state("示例标的", raw_bars, bis, [_sample_zhongshu(13)], [])

    assert "前段已确认同型片段：down，起于 2026-05-01 10:30，止于 2026-05-10 10:30" in text
    assert "上一个已完成走势类型：down" not in text


def test_build_technical_summary_includes_action_value_score() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [],
        "signal_catalog": [],
        "structure_state": {
            "current_ongoing": {"type": "up"},
            "relationship": {
                "kind": "completed_then_new_type_ongoing",
                "transition_state": "ongoing_new_type",
            },
        },
        "same_level_decomposition_mode": "single_confirmed",
        "same_level_consumption_level": "confirmed",
        "post_divergence_route": "higher_level_reverse_trend",
        "oscillation_rhythm_state": "balanced",
        "divergence": {
            "trend": {"active": True},
            "range": {"active": False},
            "top": {"active": False},
            "bottom": {"active": True},
        },
        "zs_monitor_alert": "pre_breakout",
        "zs_monitor_midline": 10.45,
        "zs_monitor_bias": "strong",
    }
    raw_bars = [SimpleNamespace(close=10.2)]

    summary = build_technical_summary(
        "30M",
        signals,
        "结论：偏多，允许轻仓试错。\n建议：分批试仓。",
        raw_bars=raw_bars,
        precision_entry={"status": "actionable"},
    )

    assert summary["score"] == 95
    assert summary["rating"] == "A"
    assert summary["bias"] == "偏多"
    assert summary["same_level_decomposition_mode"] == "single_confirmed"
    assert summary["same_level_consumption_level"] == "confirmed"
    assert summary["same_level_consumption_level_label"] == "已确认消费"
    assert summary["same_level_consumption_level_note"] == "当前同级别结构已具备稳定消费基础，可直接按主结构结论解释。"
    assert summary["post_divergence_route"] == "higher_level_reverse_trend"
    assert summary["oscillation_rhythm_state"] == "balanced"
    assert summary["route_level_from"] == "30m"
    assert summary["route_level_to"] == "day"
    assert summary["zs_monitor_alert"] == "pre_breakout"
    assert summary["zs_monitor_midline"] == 10.45
    assert summary["zs_monitor_bias"] == "strong"
    assert summary["transition_state"] == "ongoing_new_type"
    assert summary["transition_state_label"] == "新走势进行中"
    assert summary["transition_state_note"] == "前段走势已完成，当前新的同级别走势类型正在运行中。"
    assert summary["score_breakdown"] == {
        "structure": 30,
        "location": 18,
        "signal": 22,
        "divergence": 15,
        "execution": 10,
    }