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
CSV = ROOT / "data" / "reports" / "000651" / "1m" / "analyze" / "000651_1m_20260817_to_20260904.csv"


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


def test_000651_1m_lesson71_first_bi_break_then_contained_third_confirms_segment() -> None:
    """数据刷新到 20260904 后 000651 1m 新窗口不再含 first_bi_break_then_third_extends，
    但仍含 71课「第一笔破坏前段 + 第三笔被第一笔包含、先破第一笔结束位」确认规则：
    段 1（down 7-9）theory-confirmed，break=10。锁住该 71课识别规则在真实 1m 窗口仍生效。
    """
    segments = _segments_theory()

    assert len(segments) >= 2
    seg = segments[1]

    assert seg.direction.value == "down"
    assert seg.start_bi_id == 7
    assert seg.end_bi_id == 9
    assert seg.is_confirmed is True
    assert seg.stop_reason == "first_bi_break_then_contained_third_breaks_end"
    assert seg.break_bi_id == 10
