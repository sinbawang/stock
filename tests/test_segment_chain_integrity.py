"""段链完整性闸门：锁住「段链静默截断 / 结构塌陷」这一类缺陷。

背景：`300124 30m` 曾出现 practical 模式下中段 pending 停扫、把其后全部笔整体丢弃的缺陷
（116 笔只剩 2 段；同窗口 theory 22 段）。这类问题不会报错、也不会让单段断言失败，
只会「安静地少给结构」，因此需要跨窗口的不变量闸门，而不是逐个用例的数值断言。

本闸门对 `tests/fixtures/real/` 下全部冻结真实窗口（含 practical 停扫专用 fixture）断言：

1. 两种模式都必须产出非空段链；
2. `coverage`（段链覆盖到的最大 bi / 确认笔跨度）不得低于阈值——防止「只剩头部几段」；
3. 相邻段之间的最大跳空不得超过跨度的阈值——防止中段被整体丢弃；
4. `practical / theory` 段数比不得塌陷——这是本次缺陷最直接的量级哨兵。

阈值刻意取保守值（观测最小值之上留足余量），只用来抓「量级级」损伤，
不承担精确数值回归职责（那是各 `test_segment_regression_*` / `*_real_fixtures` 的职责）。

spec_id: SPEC.SEGMENT.CORE。
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    _confirmed_bis,
    identify_segments,
)
from tests.real_fixture_support import FIXTURES_ROOT
from tests.segment_regression_support import load_bis_from_csv

MIN_COVERAGE = 0.5
MAX_JUMP_RATIO = 0.3
MIN_PRACTICAL_THEORY_RATIO = 0.5


@dataclass(frozen=True)
class ModeEvidence:
    """单一模式下的段链量级指标。"""

    segment_count: int
    covered_bi: int
    coverage: float
    max_jump: int


def evaluate_chain_integrity(label: str, span: int, evidence: dict[str, ModeEvidence]) -> list[str]:
    """纯函数：返回段链完整性异常列表（空列表 = 通过）。

    抽成纯函数是为了能被单测直接用「历史缺陷指标」驱动，从而自证闸门有效，
    而不是只能依赖真实窗口恰好复现。
    """
    issues: list[str] = []
    for mode, item in evidence.items():
        if item.segment_count <= 0:
            issues.append(f"{label} [{mode}]: 段链为空（跨度 {span} 笔）")
            continue
        if item.coverage < MIN_COVERAGE:
            issues.append(
                f"{label} [{mode}]: 段链疑似截断——仅覆盖到 bi {item.covered_bi}/{span}"
                f"（coverage={item.coverage:.2f}，段数={item.segment_count}）"
            )
        if item.max_jump > MAX_JUMP_RATIO * span:
            issues.append(
                f"{label} [{mode}]: 段间跳空过大——{item.max_jump}/{span} 笔"
                f"（段数={item.segment_count}），疑似中段被整体丢弃"
            )
    practical = evidence.get("practical")
    theory = evidence.get("theory")
    if practical and theory and theory.segment_count > 0:
        if practical.segment_count < MIN_PRACTICAL_THEORY_RATIO * theory.segment_count:
            issues.append(
                f"{label}: practical/theory 段数塌陷——"
                f"{practical.segment_count} vs {theory.segment_count}"
            )
    return issues


def _bootstrap_for(timeframe: str) -> str:
    return SEGMENT_BOOTSTRAP_FIRST_VALID_SEED if timeframe == "1m" else SEGMENT_BOOTSTRAP_PREFER_EARLIER_START


def _fixture_params() -> list[tuple[str, object, str]]:
    params: list[tuple[str, object, str]] = []
    for path in sorted(FIXTURES_ROOT.glob("*.csv")):
        if "_normalized" in path.name:
            continue
        parts = path.stem.split("_")
        if len(parts) < 3:
            continue
        params.append((f"{parts[0]}-{parts[1]}", path, parts[1]))
    for path in sorted((FIXTURES_ROOT / "segment_practical_halt").glob("*.csv")):
        parts = path.stem.split("_")
        params.append((f"{parts[0]}-{parts[1]}-halt", path, parts[1]))
    return params


def test_integrity_checker_flags_the_historical_truncation() -> None:
    """闸门有效性自证：喂入该缺陷修复前的真实指标，必须报出「截断」与「段数塌陷」。

    修复前 `300124 30m` 加宽窗口：跨度 115 笔上，practical 只产出 2 段且仅覆盖到 bi 17，
    而同窗口 theory 产出 22 段并覆盖到 bi 113。
    """
    span = 115
    issues = evaluate_chain_integrity(
        "300124-30m-halt",
        span,
        {
            "theory": ModeEvidence(segment_count=22, covered_bi=113, coverage=113 / span, max_jump=4),
            "practical": ModeEvidence(segment_count=2, covered_bi=17, coverage=17 / span, max_jump=6),
        },
    )
    assert any("疑似截断" in issue for issue in issues), issues
    assert any("段数塌陷" in issue for issue in issues), issues


def test_integrity_checker_accepts_a_healthy_chain() -> None:
    """健康链必须零告警，避免闸门本身制造噪声。"""
    span = 115
    issues = evaluate_chain_integrity(
        "healthy",
        span,
        {
            "theory": ModeEvidence(segment_count=22, covered_bi=113, coverage=113 / span, max_jump=4),
            "practical": ModeEvidence(segment_count=21, covered_bi=113, coverage=113 / span, max_jump=4),
        },
    )
    assert issues == []


@pytest.mark.parametrize(
    ("label", "csv_path", "timeframe"),
    _fixture_params(),
    ids=[item[0] for item in _fixture_params()],
)
def test_segment_chain_is_not_silently_truncated(label: str, csv_path, timeframe: str) -> None:
    bis = _confirmed_bis(load_bis_from_csv(csv_path))
    assert len(bis) >= 6, f"{label}: 确认笔过少，无法做完整性判定"
    span = len(bis) - 1

    evidence: dict[str, ModeEvidence] = {}
    for mode in ("theory", "practical"):
        segments = identify_segments(
            bis,
            bootstrap_mode=_bootstrap_for(timeframe),
            bootstrap_skip_confirmed_bis=0,
            strict_segment_rules=True,
            termination_mode=mode,
        )
        covered = max((segment.end_bi_id for segment in segments), default=-1)
        jumps = [
            segments[i + 1].start_bi_id - segments[i].end_bi_id
            for i in range(len(segments) - 1)
        ]
        evidence[mode] = ModeEvidence(
            segment_count=len(segments),
            covered_bi=covered,
            coverage=(covered / span) if span else 1.0,
            max_jump=max(jumps) if jumps else 0,
        )

    assert evaluate_chain_integrity(label, span, evidence) == []
