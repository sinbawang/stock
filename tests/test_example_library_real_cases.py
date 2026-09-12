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
from chanlun.analysis import build_lower_timeframe_precision_entry  # noqa: E402
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

# 区间套 / 小转大卡片。`cutoff_index` 是高级别 `analysis_cutoffs` 的下标；
# 次级别按同一时刻 T 截断，模拟生产同时取两级数据。
PRECISION_CARDS = (
    {
        # 生产口径：PRIMARY_TECHNICAL_TIMEFRAME=30m + LOWER_PRECISION_TIMEFRAME=5m
        "card": "区间套 P1 · 00700 30m->5m 候选",
        "symbol": "00700",
        "higher": "30m",
        "lower": "5m",
        "cutoff_index": 9,
        "cutoff": 915,
        "status": "watch",
        "small_to_large": "candidate",
        "window_basis": "中枢到锚点窗口",
        "side": "sell",
        "trigger": "higher_range_divergence",
        "dynamic_grade": "oscillation_opportunity",
    },
    {
        "card": "区间套 P2 · 03690 5m->1m 离开笔窗口",
        "symbol": "03690",
        "higher": "5m",
        "lower": "1m",
        "cutoff_index": 11,
        "cutoff": 1831,
        "status": "watch",
        "small_to_large": "candidate",
        "window_basis": "离开笔窗口",
        "side": "buy",
        "trigger": "buy2like",
        "dynamic_grade": "warning",
    },
    {
        "card": "区间套 P3 · 000591 1m->5m 候选",
        "symbol": "000591",
        "higher": "1m",
        "lower": "5m",
        "cutoff_index": 13,
        "cutoff": 3500,
        "status": "watch",
        "small_to_large": "candidate",
        "window_basis": "中枢到锚点窗口",
        "side": "sell",
        "trigger": "higher_range_divergence",
        "dynamic_grade": "oscillation_opportunity",
    },
    {
        "card": "区间套 P4 · 000591 day->5m standby",
        "symbol": "000591",
        "higher": "day",
        "lower": "5m",
        "cutoff_index": 12,
        "cutoff": 1200,
        "status": "standby",
        "small_to_large": None,
        "window_basis": None,
        "side": None,
        "trigger": None,
        "dynamic_grade": None,
    },
    {
        "card": "区间套 P5 · 000591 1m->5m 锚点跟踪窗口",
        "symbol": "000591",
        "higher": "1m",
        "lower": "5m",
        "cutoff_index": 2,
        "cutoff": 632,
        "status": "watch",
        "small_to_large": None,
        "window_basis": "锚点跟踪窗口",
        "side": "buy",
        "trigger": "higher_bottom_divergence",
        "dynamic_grade": None,
    },
)

# 全部 (高级别, 次级别) 组合；前三个是生产实际会用到的口径。
PRECISION_PAIRS = (
    ("30m", "5m"),
    ("day", "5m"),
    ("1m", "5m"),
    ("day", "1m"),
    ("30m", "1m"),
    ("5m", "1m"),
)
PRECISION_SYMBOLS = ("000591", "00700", "03690", "300124", "600900")

# 文档记录：这三档在真实窗口上从未出现，只有构造 / 契约回归覆盖。
UNOBSERVED_HIGHER_STATES = ("actionable", "third_class_confirmed", "higher_level_confirmed")


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


def _precision_entry(symbol: str, higher_tf: str, lower_tf: str, cutoff: int) -> dict[str, object]:
    """高级别取 cutoff，次级别按同一时刻 T 截断，再构建区间套入口。"""
    higher_all = clean_bars(read_bars_from_csv(str(frozen_csv(symbol, higher_tf))))
    lower_all = clean_bars(read_bars_from_csv(str(frozen_csv(symbol, lower_tf))))
    higher_bars = higher_all[:cutoff]
    t_end = getattr(higher_bars[-1], "ts")
    lower_bars = [bar for bar in lower_all if getattr(bar, "ts") <= t_end]

    def _signals(bars, timeframe: str) -> dict[str, object]:
        normalized = normalize_bars(bars)
        fractals = filter_consecutive_fractals(identify_fractals(normalized))
        bis = identify_bis(fractals, normalized, pending_reverse_mode="effective_only")
        segments = identify_segments(
            bis,
            bootstrap_mode=_bootstrap_for(timeframe),
            bootstrap_skip_confirmed_bis=0,
            strict_segment_rules=True,
        )
        zhongshus = identify_zhongshu(segments, structure_level="segment")
        return analyze_chanlun_signals(bars, bis, zhongshus, calculate_macd(bars), segments=segments)

    return build_lower_timeframe_precision_entry(
        _signals(higher_bars, higher_tf),
        _signals(lower_bars, lower_tf),
        lower_timeframe=lower_tf,
        lower_timeframe_label=lower_tf.upper(),
        pending_reverse_mode="effective_only",
    )


@pytest.mark.parametrize("card", PRECISION_CARDS, ids=[c["card"] for c in PRECISION_CARDS])
def test_precision_card_reproduces_on_frozen_window(card: dict[str, object]) -> None:
    higher_all = clean_bars(read_bars_from_csv(str(frozen_csv(card["symbol"], card["higher"]))))
    cutoffs = analysis_cutoffs(len(higher_all))
    index = int(card["cutoff_index"])
    assert index < len(cutoffs), f"{card['card']}: cutoff 序号越界（窗口只有 {len(cutoffs)} 帧）"
    assert cutoffs[index] == card["cutoff"], (
        f"{card['card']}: cutoff 序列口径已变（期望 {card['cutoff']}，实得 {cutoffs[index]}）；"
        "若窗口被重新冻结，请同步更新卡片与文档。"
    )

    entry = _precision_entry(
        card["symbol"], card["higher"], card["lower"], int(card["cutoff"])
    )
    nested = entry.get("nested_from") or {}
    actual = {
        "status": entry.get("status"),
        "small_to_large": entry.get("small_to_large_status"),
        "window_basis": entry.get("window_basis_label"),
        "side": nested.get("side"),
        "trigger": nested.get("trigger"),
        "dynamic_grade": entry.get("dynamic_grade"),
    }
    expected = {key: card[key] for key in actual}

    assert actual == expected, (
        f"{card['card']}: 冻结窗口上区间套卡片已变化（cutoff={card['cutoff']}）；"
        f"期望 {expected}，实得 {actual}。规则变更请同步更新卡片与文档，不要放宽本断言。"
    )


def test_precision_card_library_is_not_vacuous() -> None:
    """卡片必须同时覆盖有窗口 / 无窗口两种形态，且 window_basis 不得单一。"""
    assert len(PRECISION_CARDS) >= 4
    statuses = {c["status"] for c in PRECISION_CARDS}
    assert {"watch", "standby"} <= statuses
    assert None in {c["small_to_large"] for c in PRECISION_CARDS}
    assert len({c["window_basis"] for c in PRECISION_CARDS if c["window_basis"]}) >= 3


def test_precision_higher_states_stay_unobserved_on_real_windows() -> None:
    """文档记录：`actionable` / `third_class_confirmed` / `higher_level_confirmed` 在真实窗口上未观测到。

    本用例同时是**文档同步闸门**：若这三档开始在真实窗口出现，说明文档里「仅构造 / 契约覆盖」
    的说法已过期，需要补真实卡片并更新覆盖矩阵。
    """
    status_counts: dict[str, int] = {}
    small_to_large_counts: dict[str, int] = {}
    scans = 0

    for symbol in PRECISION_SYMBOLS:
        for higher_tf, lower_tf in PRECISION_PAIRS:
            try:
                higher_all = clean_bars(read_bars_from_csv(str(frozen_csv(symbol, higher_tf))))
                lower_all = clean_bars(read_bars_from_csv(str(frozen_csv(symbol, lower_tf))))
            except FileNotFoundError:
                continue
            for cutoff in analysis_cutoffs(len(higher_all)):
                higher_bars = higher_all[:cutoff]
                if not higher_bars:
                    continue
                t_end = getattr(higher_bars[-1], "ts")
                lower_bars = [bar for bar in lower_all if getattr(bar, "ts") <= t_end]
                if len(lower_bars) < 60:
                    continue
                entry = _precision_entry(symbol, higher_tf, lower_tf, cutoff)
                scans += 1
                status = str(entry.get("status"))
                status_counts[status] = status_counts.get(status, 0) + 1
                if entry.get("small_to_large_status") is not None:
                    key = str(entry.get("small_to_large_status"))
                    small_to_large_counts[key] = small_to_large_counts.get(key, 0) + 1

    # 非空转：确实扫到足够多的帧，且低位档确实出现过，否则「高位档未出现」没有意义。
    assert scans >= 100, f"扫描帧数过少（{scans}），本闸门可能已空转"
    assert status_counts.get("watch", 0) >= 10, f"watch 样本过少：{status_counts}"
    assert status_counts.get("standby", 0) >= 5, f"standby 样本过少：{status_counts}"
    assert small_to_large_counts.get("candidate", 0) >= 5, f"candidate 样本过少：{small_to_large_counts}"

    assert "actionable" not in status_counts, (
        f"precision_entry.status 已在真实窗口出现 actionable（{status_counts}）；"
        "文档中「仅构造覆盖」的说法需更新。"
    )
    for state in UNOBSERVED_HIGHER_STATES:
        if state == "actionable":
            continue
        assert state not in small_to_large_counts, (
            f"small_to_large_status 已在真实窗口出现 {state}（{small_to_large_counts}）；"
            "文档中「仅构造覆盖」的说法需更新，并补对应真实卡片。"
        )


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
