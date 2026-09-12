"""下游链完整性闸门：锁住「标准中枢 / 类中枢静默停滞」这一类缺陷。

背景
----
2026-09-12 修掉了一个**静默**缺陷：practical 模式中段 pending 停扫会把其后全部笔丢弃
（`300124 30m` 116 笔只剩 2 段），不报错、也不让任何单点断言失败，只是「安静地少给结构」。
事后为 bi -> segment 补了 `tests/test_segment_chain_integrity.py`。

但下游三层（标准中枢 / 笔级类中枢 / 买卖点）当时**没有等价护栏**。越靠下游，退化越难发现：
买卖点变少看起来只是「这段没信号」，中枢变少看起来只是「这段是盘整」。

本闸门把下游两层的「推进程度」变成可断言的不变量：

1. `segment -> 标准中枢`：段链非空时中枢不得为空；且最后一个标准中枢覆盖到的段
   不得离段链尾部过远（lag 比例阈值），防止「中枢只建在头部几段」。
2. `确认笔 -> 笔级类中枢`：确认笔足够多时类中枢不得为空；且类中枢覆盖的笔距尾部不得过远。

阈值取观测值的保守上界（见下方常量注释），只抓「量级级」停滞，不承担精确数值回归职责。
量级基线（2026-09-12 探针，22 个冻结窗口，theory 口径）：
`segment -> 标准中枢` lag 比例最大 8/22 = 0.36；`确认笔 -> 类中枢` lag 比例最大 4/60 = 0.07。

spec_id: SPEC.ZHONGSHU.DUAL_TRACK。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    identify_segments,
)
from chanlun.zhongshu import identify_zhongshu
from tests.real_fixture_support import FIXTURES_ROOT
from tests.segment_regression_support import load_bis_from_csv

# 观测最差值 0.36，留约 1.4x 余量。
MAX_ZHONGSHU_LAG_RATIO = 0.5
# 观测最差值 0.07，留约 3.5x 余量。
MAX_LEI_LAG_RATIO = 0.25
# 低于这两个规模时「没有中枢」是正常现象，不做断言。
MIN_SEGMENTS_FOR_ZHONGSHU = 6
MIN_CONFIRMED_BI_FOR_LEI = 30


@dataclass(frozen=True)
class DownstreamEvidence:
    """单一窗口的下游推进程度。"""

    segment_count: int
    zhongshu_count: int
    zhongshu_covered_segment: int
    confirmed_bi: int
    lei_zhongshu_count: int
    lei_covered_bi: int


def evaluate_downstream_integrity(label: str, evidence: DownstreamEvidence) -> list[str]:
    """纯函数：返回下游停滞异常列表（空列表 = 通过）。

    抽成纯函数是为了能用「构造的停滞指标」自证闸门有效，不依赖真实窗口恰好退化。
    """
    issues: list[str] = []
    segments = evidence.segment_count

    if segments >= MIN_SEGMENTS_FOR_ZHONGSHU and evidence.zhongshu_count == 0:
        issues.append(f"{label}: 段链 {segments} 段但标准中枢为 0（下游未推进）")
    # 仅在「确实建出了中枢」时才判停滞：否则 covered=0 会让 lag 比例恒为 1.0，
    # 把小窗口误报成停滞（而「一个都没有」的判断应由上面的非空检查负责）。
    if segments > 0 and evidence.zhongshu_count > 0:
        lag_ratio = (segments - evidence.zhongshu_covered_segment) / segments
        if lag_ratio > MAX_ZHONGSHU_LAG_RATIO:
            issues.append(
                f"{label}: 标准中枢疑似停滞——仅覆盖到段 "
                f"{evidence.zhongshu_covered_segment}/{segments}"
                f"（lag={lag_ratio:.2f}，中枢数={evidence.zhongshu_count}）"
            )

    if evidence.confirmed_bi >= MIN_CONFIRMED_BI_FOR_LEI and evidence.lei_zhongshu_count == 0:
        issues.append(f"{label}: 确认笔 {evidence.confirmed_bi} 但笔级类中枢为 0（下游未推进）")
    if evidence.confirmed_bi > 0 and evidence.lei_zhongshu_count > 0:
        lag_ratio = (evidence.confirmed_bi - evidence.lei_covered_bi) / evidence.confirmed_bi
        if lag_ratio > MAX_LEI_LAG_RATIO:
            issues.append(
                f"{label}: 笔级类中枢疑似停滞——仅覆盖到 bi "
                f"{evidence.lei_covered_bi}/{evidence.confirmed_bi}"
                f"（lag={lag_ratio:.2f}，类中枢数={evidence.lei_zhongshu_count}）"
            )
    return issues


def _bootstrap_for(timeframe: str) -> str:
    return SEGMENT_BOOTSTRAP_FIRST_VALID_SEED if timeframe == "1m" else SEGMENT_BOOTSTRAP_PREFER_EARLIER_START


def build_evidence(csv_path: Path, timeframe: str) -> DownstreamEvidence:
    """按 pipeline 口径（theory + strict_segment_rules）复算下游两层。

    注意：`structure_level="segment"` 时 `Zhongshu.end_bi_id` 承载的是 **segment_id**，
    `structure_level="bi"` 时才是 bi_id——这是上游模型的既有命名，这里沿用其语义。
    """
    bis = load_bis_from_csv(csv_path)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    segments = identify_segments(
        bis,
        bootstrap_mode=_bootstrap_for(timeframe),
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
    )
    zhongshus = identify_zhongshu(segments, structure_level="segment")
    lei_zhongshus = identify_zhongshu(confirmed_bis, structure_level="bi")
    return DownstreamEvidence(
        segment_count=len(segments),
        zhongshu_count=len(zhongshus),
        zhongshu_covered_segment=zhongshus[-1].end_bi_id if zhongshus else 0,
        confirmed_bi=len(confirmed_bis),
        lei_zhongshu_count=len(lei_zhongshus),
        lei_covered_bi=lei_zhongshus[-1].end_bi_id if lei_zhongshus else 0,
    )


def _fixture_params() -> list[tuple[str, Path, str]]:
    params: list[tuple[str, Path, str]] = []
    for path in sorted(FIXTURES_ROOT.glob("*.csv")):
        if "_normalized" in path.name:
            continue
        parts = path.stem.split("_")
        if len(parts) < 3:
            continue
        params.append((f"{parts[0]}-{parts[1]}", path, parts[1]))
    return params


def test_gate_flags_a_stalled_zhongshu_layer() -> None:
    """闸门有效性自证：中枢只建在头部几段时必须报出停滞。"""
    issues = evaluate_downstream_integrity(
        "stalled",
        DownstreamEvidence(
            segment_count=22,
            zhongshu_count=1,
            zhongshu_covered_segment=5,
            confirmed_bi=115,
            lei_zhongshu_count=15,
            lei_covered_bi=113,
        ),
    )

    assert any("疑似停滞" in issue for issue in issues), issues


def test_gate_flags_a_missing_zhongshu_layer() -> None:
    issues = evaluate_downstream_integrity(
        "empty",
        DownstreamEvidence(
            segment_count=22,
            zhongshu_count=0,
            zhongshu_covered_segment=0,
            confirmed_bi=115,
            lei_zhongshu_count=0,
            lei_covered_bi=0,
        ),
    )

    assert any("标准中枢为 0" in issue for issue in issues), issues
    assert any("类中枢为 0" in issue for issue in issues), issues


def test_gate_accepts_a_healthy_downstream_chain() -> None:
    """健康链必须零告警（用探针观测的真实最差值构造）。"""
    issues = evaluate_downstream_integrity(
        "healthy",
        DownstreamEvidence(
            segment_count=22,
            zhongshu_count=2,
            zhongshu_covered_segment=14,
            confirmed_bi=191,
            lei_zhongshu_count=27,
            lei_covered_bi=189,
        ),
    )

    assert issues == []


def test_gate_ignores_small_windows() -> None:
    """规模不足时「没有中枢」是正常的，不得误报。"""
    issues = evaluate_downstream_integrity(
        "small",
        DownstreamEvidence(
            segment_count=2,
            zhongshu_count=0,
            zhongshu_covered_segment=0,
            confirmed_bi=12,
            lei_zhongshu_count=0,
            lei_covered_bi=0,
        ),
    )

    assert issues == []


def test_gate_reports_absence_not_stall_when_layer_is_empty() -> None:
    """空层只由「未推进」负责，不得同时报「停滞」。

    回归 2026-09-12 的一个闸门自身缺陷：`covered=0` 时 lag 比例恒为 1.0，
    导致「一个中枢都没有」被同时判成「疑似停滞」，把小窗口误伤成红灯。
    """
    issues = evaluate_downstream_integrity(
        "empty-but-large-enough",
        DownstreamEvidence(
            segment_count=8,
            zhongshu_count=0,
            zhongshu_covered_segment=0,
            confirmed_bi=40,
            lei_zhongshu_count=0,
            lei_covered_bi=0,
        ),
    )

    assert any("标准中枢为 0" in issue for issue in issues), issues
    assert not any("疑似停滞" in issue for issue in issues), issues


@pytest.mark.parametrize(
    ("label", "csv_path", "timeframe"),
    _fixture_params(),
    ids=[item[0] for item in _fixture_params()],
)
def test_downstream_layers_do_not_silently_stall(label: str, csv_path: Path, timeframe: str) -> None:
    evidence = build_evidence(csv_path, timeframe)

    assert evidence.segment_count > 0, f"{label}: 段链为空，无法判定下游"

    issues = evaluate_downstream_integrity(label, evidence)

    assert issues == [], issues
