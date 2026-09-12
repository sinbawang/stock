"""BS6 / D2 / T1：买卖点案例库的真实样本锚点。

**为什么需要本文件**：`tests/test_chanlun_analysis.py` 里 T1 的用例是**构造输入**（合成 bi /
中枢），能锁住判定逻辑，但锁不住「真实窗口上是否还发得出来」。`docs/chanlun/
buy-sell-multi-level-example-cases.md` 里的案例卡用的是真实冻结 fixture，本文件把每张卡
钉成自动化锚点，使文档与实现不会各说各话（BS6 验收第 1 条）。

口径与 `tests/real_fixture_support.py::analysis_cutoffs` 一致：21 个冻结窗口 × 12 cutoff。
若卡片失效，先确认是**有意**的规则变更，再按新口径更新卡片与本文档；不要为了绿灯放宽断言。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for _extra in (SRC, SCRIPTS):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from chanlun.analysis import analyze_chanlun_signals  # noqa: E402
from chanlun.bi import identify_bis  # noqa: E402
from chanlun.data import read_bars_from_csv  # noqa: E402
from chanlun.data.cleaner import clean_bars  # noqa: E402
from chanlun.fractal import filter_consecutive_fractals, identify_fractals  # noqa: E402
from chanlun.normalize import normalize_bars  # noqa: E402
from chanlun.segment import (  # noqa: E402
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    identify_segments,
)
from chanlun.zhongshu import identify_zhongshu  # noqa: E402
from export_structures_with_boxes import calculate_macd  # noqa: E402
from tests.real_fixture_support import FIXTURES_ROOT, analysis_cutoffs, frozen_csv  # noqa: E402

TIMEFRAMES = ("1m", "5m", "30m", "day")

# 文档卡片 -> 自动化锚点。字段含义见 docs/chanlun/buy-sell-multi-level-example-cases.md。
CASE_CARDS = (
    {
        "card": "1B · 000591 day",
        "symbol": "000591",
        "timeframe": "day",
        "cutoff_index": 10,
        "cutoff": 1010,
        "point": "buy1",
        "signal_bi": 77,
        "price": 4.19,
        "related_zs": 1,
        "basis": "bottom_divergence_near_zs_low",
    },
    {
        "card": "1BL · 00700 1m",
        "symbol": "00700",
        "timeframe": "1m",
        "cutoff_index": 13,
        "cutoff": 3500,
        "point": "buy1like",
        "signal_bi": 96,
        "price": 436.4,
        "related_zs": 0,
        "basis": "consolidation_divergence_reverse_low",
    },
    {
        "card": "2BL · 00700 5m",
        "symbol": "00700",
        "timeframe": "5m",
        "cutoff_index": 11,
        "cutoff": 1831,
        "point": "buy2like",
        "signal_bi": 105,
        "price": 432.8,
        "related_zs": 1,
        "basis": "gap_segment_divergence_pullback_end",
    },
    {
        "card": "3B · 00728 day",
        "symbol": "00728",
        "timeframe": "day",
        "cutoff_index": 11,
        "cutoff": 1105,
        "point": "buy3",
        "signal_bi": 63,
        "price": 5.26,
        "related_zs": 0,
        "basis": "leave_zs_then_pullback_holds_upper_edge",
    },
    {
        "card": "2SL · 000651 1m",
        "symbol": "000651",
        "timeframe": "1m",
        "cutoff_index": 7,
        "cutoff": 2062,
        "point": "sell2like",
        "signal_bi": 110,
        "price": 39.09,
        "related_zs": 1,
        "basis": "gap_segment_divergence_rebound_end",
    },
    {
        "card": "3S · 000591 5m",
        "symbol": "000591",
        "timeframe": "5m",
        "cutoff_index": 13,
        "cutoff": 2000,
        "point": "sell3",
        "signal_bi": 59,
        "price": 4.4,
        "related_zs": 0,
        "basis": "leave_zs_then_rebound_fails_lower_edge",
    },
    {
        "card": "3S · 000591 day",
        "symbol": "000591",
        "timeframe": "day",
        "cutoff_index": 5,
        "cutoff": 535,
        "point": "sell3",
        "signal_bi": 52,
        "price": 5.81,
        "related_zs": 0,
        "basis": "leave_zs_then_rebound_fails_lower_edge",
    },
)

# 文档中记录的「真实样本覆盖为零」的点类型。真实窗口上若开始发点，说明文档的缺口清单过期。
ZERO_REAL_COVERAGE = ("sell1", "sell2", "buy2", "sell1like")


def _bootstrap_for(timeframe: str) -> str:
    return SEGMENT_BOOTSTRAP_FIRST_VALID_SEED if timeframe == "1m" else SEGMENT_BOOTSTRAP_PREFER_EARLIER_START


def _confirmed_points(symbol: str, timeframe: str, cutoff: int) -> list[dict[str, object]]:
    bars_all = clean_bars(read_bars_from_csv(str(frozen_csv(symbol, timeframe))))
    bars = bars_all[:cutoff]
    norm = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(norm))
    bis = identify_bis(fractals, norm, pending_reverse_mode="effective_only")
    segments = identify_segments(
        bis,
        bootstrap_mode=_bootstrap_for(timeframe),
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
    )
    zhongshus = identify_zhongshu(segments, structure_level="segment")
    signals = analyze_chanlun_signals(bars, bis, zhongshus, calculate_macd(bars), segments=segments)
    return [
        point
        for point in signals.get("signal_points", [])
        if point.get("lifecycle_state") == "confirmed"
    ]


@pytest.mark.parametrize("card", CASE_CARDS, ids=[c["card"] for c in CASE_CARDS])
def test_case_card_reproduces_on_frozen_window(card: dict[str, object]) -> None:
    cutoffs = analysis_cutoffs(len(clean_bars(read_bars_from_csv(str(frozen_csv(card["symbol"], card["timeframe"]))))))
    index = int(card["cutoff_index"])
    assert index < len(cutoffs), f"{card['card']}: cutoff 序号越界（窗口只有 {len(cutoffs)} 帧）"
    assert cutoffs[index] == card["cutoff"], (
        f"{card['card']}: cutoff 序列口径已变（期望 {card['cutoff']}，实得 {cutoffs[index]}）；"
        "若窗口被重新冻结，请同步更新卡片与文档。"
    )

    points = _confirmed_points(card["symbol"], card["timeframe"], int(card["cutoff"]))
    matches = [p for p in points if p.get("point") == card["point"]]
    matched = [
        p
        for p in matches
        if p.get("signal_bi_id") == card["signal_bi"] and p.get("related_zs_id") == card["related_zs"]
    ]

    assert matched, (
        f"{card['card']}: 冻结窗口上已找不到卡片样本 "
        f"（cutoff={card['cutoff']} 期望 {card['point']} 锚点 bi{card['signal_bi']} 中枢 zs{card['related_zs']}）；"
        f"该 cutoff 实际 {card['point']} 发点为 {[ (p.get('signal_bi_id'), p.get('related_zs_id')) for p in matches ]}，"
        f"全部 confirmed 为 {[(p.get('point'), p.get('signal_bi_id')) for p in points]}。"
        "规则变更请同步更新卡片与文档，不要放宽本断言。"
    )

    point = matched[0]
    assert point.get("basis") == card["basis"], f"{card['card']}: 依据码已变"
    assert point.get("price") == pytest.approx(card["price"], rel=1e-9), f"{card['card']}: 价格已变"


def test_case_library_is_not_vacuous() -> None:
    """卡片必须覆盖多种点类型与多个真实窗口，避免退化成单一样本。"""
    assert len(CASE_CARDS) >= 6
    assert len({c["point"] for c in CASE_CARDS}) >= 5
    assert len({(c["symbol"], c["timeframe"]) for c in CASE_CARDS}) >= 4
    assert {c["timeframe"] for c in CASE_CARDS} <= set(TIMEFRAMES)


def test_zero_real_coverage_types_are_still_absent() -> None:
    """文档记录的「真实窗口零样本」点类型必须仍然为零，否则文档缺口清单已过期。"""
    seen: dict[str, list[str]] = {}

    for path in sorted(FIXTURES_ROOT.glob("*.csv")):
        if "_normalized" in path.name:
            continue
        parts = path.stem.split("_")
        if len(parts) < 3 or parts[1] not in TIMEFRAMES:
            continue
        symbol, timeframe = parts[0], parts[1]
        bars_all = clean_bars(read_bars_from_csv(str(path)))

        for cutoff in analysis_cutoffs(len(bars_all)):
            for point in _confirmed_points(symbol, timeframe, cutoff):
                seen.setdefault(str(point.get("point")), []).append(
                    f"{symbol}-{timeframe}@{cutoff} bi{point.get('signal_bi_id')}"
                )

    for point_type in ZERO_REAL_COVERAGE:
        assert point_type not in seen, (
            f"{point_type} 已在真实窗口发点（{seen[point_type][:3]}），"
            "说明文档中「真实样本覆盖为零」的缺口清单已过期，请更新卡片。"
        )
