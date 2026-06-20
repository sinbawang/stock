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

import run_cn_60m_chanlun_to_wechat as cn_report
from batch_prepare_chanlun_reports import build_advice


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