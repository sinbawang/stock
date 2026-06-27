from __future__ import annotations

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


def _sample_zhongshu(exit_bi_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        zs_id=2,
        structure_level="bi",
        recognition_mode="fixed_first_three_overlap",
        render_mode="core_plus_extension",
        zs_low=10.1,
        zs_high=10.8,
        start_ts=datetime(2026, 5, 1, 10, 30),
        end_ts=datetime(2026, 5, 29, 14, 30),
        entering_bi_id=8,
        core_bi_ids=[9, 10, 11],
        bi_ids=[9, 10, 11, 12],
        exit_bi_id=exit_bi_id,
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

    def fake_analyze(raw_bars, bis, zhongshus, macd_points):
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


def test_build_technical_summary_includes_action_value_score() -> None:
    signals = {
        "current_zs": _sample_zhongshu(),
        "buy_points": ["buy_2"],
        "sell_points": [],
        "signal_points": [],
        "signal_catalog": [],
        "structure_state": {
            "current_ongoing": {"type": "up"},
            "relationship": {"kind": "completed_then_new_type_ongoing"},
        },
        "divergence": {
            "trend": {"active": True},
            "range": {"active": False},
            "top": {"active": False},
            "bottom": {"active": True},
        },
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
    assert summary["score_breakdown"] == {
        "structure": 30,
        "location": 18,
        "signal": 22,
        "divergence": 15,
        "execution": 10,
    }