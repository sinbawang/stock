"""000651 1m 线段回归（港股/深市首选 1m 真实窗口）。

spec_id: SPEC.SEGMENT.CORE。

锚点：71课「第一笔破坏前线段 + 第三笔破第一笔结束位置 → 新线段一定形成、
前线段一定结束」。导出工件 `data/reports/000651/1m` 用
`pending_reverse_mode="effective_only"` + theory 模式 + first_valid_seed 生成，
S4（down 38-40）与 S5（up 41-43）此前被标成 `exhausted_confirmed_bis`（pending），
但按 71课原文两者都应 theory-confirmed。
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
CSV = ROOT / "data" / "reports" / "000651" / "1m" / "analyze" / "000651_1m_20260806_to_20260824.csv"


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


def test_000651_1m_s4_s5_confirmed_by_lesson71_first_bi_break_then_third_extends() -> None:
    """S4/S5 满足 71课「第一笔破坏前段 + 第三笔破第一笔结束位」，应 theory-confirmed。

    - S4（down 38-40）：bi41(上) 高 40.78 > bi38(下) 高 40.70 破坏前段；
      bi43(上) 高 40.80 > bi41 高 40.78 破第一笔结束位 → S4 确认结束，break=41。
    - S5（up 41-43）：bi44(下) 低 40.43 < bi41(上) 低 40.46 破坏前段；
      bi46(下) 低 40.37 < bi44 低 40.43 破第一笔结束位 → S5 确认结束，break=44。
    """
    segments = _segments_theory()

    assert len(segments) >= 7
    s4 = segments[4]
    s5 = segments[5]

    assert s4.direction.value == "down"
    assert s4.start_bi_id == 38
    assert s4.end_bi_id == 40
    assert s4.is_confirmed is True
    assert s4.stop_reason == "first_bi_break_then_third_extends"
    assert s4.break_bi_id == 41

    assert s5.direction.value == "up"
    assert s5.start_bi_id == 41
    assert s5.end_bi_id == 43
    assert s5.is_confirmed is True
    assert s5.stop_reason == "first_bi_break_then_third_extends"
    assert s5.break_bi_id == 44
