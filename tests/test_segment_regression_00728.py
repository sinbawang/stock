"""00728 day 线段回归（港股 day 真实窗口）。

spec_id: SPEC.SEGMENT.CORE。

锚点：71课复杂情形「第一笔破坏前线段 + 第三笔完全在第一笔范围内 →
后续先破第一笔结束位置，前线段一定结束」。

00728 day 尾部：
- s8（down 61-65）转折第一笔 bi66 破坏前段（6.12 > 5.95），
  第三笔 bi68 完全落在 bi66 [5.26, 6.12] 内，之后 bi70 先破 bi66 结束位置 6.12；
- s9（up 66-70）同理，bi71 破坏前段、bi73 落在 bi71 内、bi77 先破 bi71 结束位置 5.22。

两者此前均被标成 `exhausted_confirmed_bis`（pending），按 71课原文应 theory-confirmed。
"""

from pathlib import Path

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    identify_segments,
)


ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "reports" / "00728" / "day" / "analyze" / "00728_day_20211015_to_20260828.csv"


def _segments_theory():
    bars = clean_bars(read_bars_from_csv(str(CSV)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="effective_only")
    return identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
        termination_mode="theory",
    )


def _segment_by_start(segments, start_bi_id: int):
    return next(s for s in segments if s.start_bi_id == start_bi_id)


def test_00728_day_s8_contained_third_confirms_down_segment() -> None:
    """s8（down 61-65）：bi66 破坏前段、bi68 被 bi66 包含、bi70 先破 bi66 结束位置，
    应 theory-confirmed，break=66。"""
    segments = _segments_theory()

    s8 = _segment_by_start(segments, 61)
    assert s8.direction.value == "down"
    assert s8.start_bi_id == 61
    assert s8.end_bi_id == 65
    assert s8.is_confirmed is True
    assert s8.stop_reason == "first_bi_break_then_contained_third_breaks_end"
    assert s8.break_bi_id == 66


def test_00728_day_s9_contained_third_confirms_up_segment() -> None:
    """s9（up 66-70）：bi71 破坏前段、bi73 被 bi71 包含、bi77 先破 bi71 结束位置，
    应 theory-confirmed，break=71。"""
    segments = _segments_theory()

    s9 = _segment_by_start(segments, 66)
    assert s9.direction.value == "up"
    assert s9.start_bi_id == 66
    assert s9.end_bi_id == 70
    assert s9.is_confirmed is True
    assert s9.stop_reason == "first_bi_break_then_contained_third_breaks_end"
    assert s9.break_bi_id == 71
