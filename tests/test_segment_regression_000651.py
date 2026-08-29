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
CSV = ROOT / "data" / "reports" / "000651" / "1m" / "analyze" / "000651_1m_20260810_to_20260828.csv"


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


def test_000651_1m_lesson71_first_bi_break_then_third_extends_confirms_head() -> None:
    """数据刷新后 000651 1m 新窗口的 71课「第一笔破坏前段 + 第三笔破第一笔结束位」
    确认锚点落在段头（首段），而非旧窗口的 S4/S5 中段。

    段 0（up 0-2）：bootstrap 后首段，经 first_bi_break_then_third_extends 确认，
    break=3。锁住该识别规则在当前窗口仍产出 theory-confirmed 首段。
    """
    segments = _segments_theory()

    assert len(segments) >= 1
    head = segments[0]

    assert head.direction.value == "up"
    assert head.start_bi_id == 0
    assert head.end_bi_id == 2
    assert head.is_confirmed is True
    assert head.stop_reason == "first_bi_break_then_third_extends"
    assert head.break_bi_id == 3
