"""RS1 实时预备态（forming）可达性闸门（spec §2.8）。

背景
----
`buy-sell-multi-level-tasks.md` 的 RS1 标「完成（1/2/3 + 类一 / 类二 forming 均已落地并双边回归）」，
但那些回归全部由**构造输入**驱动：例如
`test_chanlun_analysis.py::test_analyze_chanlun_signals_forming_buy_1_when_divergence_without_reverse_turn`
用 `bis = _lb1_range_bis()[:5]`（注释「去掉向上反向转折 bi6」）把**离开笔截成链尾**，
于是 `_has_reverse_turn_after` 为 False、forming 成立。

真实链路上没有这个截断：`analyze_chanlun_signals` 的 `buy_signal_bi` 取的是
`exit_segment.end_bi_id`——一根**已完成线段**的末笔，其后必然还有后续笔（笔严格交替）。
2026-09-12 实测（21 个冻结真实窗口 × 287 帧）：

- `forming_points` 出现 **0 次**；
- `_has_reverse_turn_after` 调用 42 次，**True 42 次（100%）**；
- 本地 96 个真实 `data/reports/**/tech.json` 中 64 个带 `forming_points`，**非空 0 个**。

即：页面 / 发布链路都支持 forming 渲染，但真实数据产不出可渲染的 forming——
「合成用例绿」不等于「功能活着」。本闸门用冻结真实窗口把「可达性」钉成可执行断言。

反空转：只有当回放确实跑出过 confirmed 点时才判定（否则说明回放口径本身失效）。

spec_id: SPEC.BUY_SELL.CORE。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
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
from tests.real_fixture_support import FIXTURES_ROOT  # noqa: E402

FRAMES_PER_WINDOW = 12
MIN_BARS = 60
# 可达性下限：真实窗口上应能观察到 forming；取保守下限 1，抓「恒为 0」这一量级损伤。
MIN_FORMING_OCCURRENCES = 1


@dataclass
class FormingEvidence:
    """整轮回放的 forming 可达性证据。"""

    frames: int = 0
    confirmed_seen: int = 0
    forming_seen: int = 0
    forming_violations: list[str] = field(default_factory=list)
    forming_by_point: dict[str, int] = field(default_factory=dict)


def _bootstrap_for(timeframe: str) -> str:
    return SEGMENT_BOOTSTRAP_FIRST_VALID_SEED if timeframe == "1m" else SEGMENT_BOOTSTRAP_PREFER_EARLIER_START


def _cutoffs(total: int) -> list[int]:
    start = min(MIN_BARS, max(20, total // 3))
    if total - start < 5:
        return []
    step = max(1, (total - start) // FRAMES_PER_WINDOW)
    cutoffs = list(range(start, total + 1, step))
    if cutoffs[-1] != total:
        cutoffs.append(total)
    return cutoffs


def check_forming_invariants(signals: dict[str, object], *, label: str) -> list[str]:
    """纯函数：forming 的既有契约不变量（空列表 = 通过）。

    1. `lifecycle_state` 必须是 `forming`（不得升 confirmed）；
    2. `active` 必须为 False（watch 档，不得进可操作集）；
    3. 不得混入 `signal_points` / `buy_points` / `sell_points`（独立列表契约）。
    """
    issues: list[str] = []
    forming = list(signals.get("forming_points") or [])
    for payload in forming:
        if payload.get("lifecycle_state") != "forming":
            issues.append(f"{label}: forming_points 内出现非 forming 生命周期：{payload.get('point')}")
        if payload.get("active"):
            issues.append(f"{label}: forming 点 active=True（应仅 watch）：{payload.get('point')}")

    forming_keys = {(p.get("point"), p.get("signal_bi_id")) for p in forming}
    for name in ("signal_points", "buy_points", "sell_points"):
        for entry in signals.get(name) or []:
            if not isinstance(entry, dict):
                continue
            if (entry.get("point"), entry.get("signal_bi_id")) in forming_keys:
                issues.append(f"{label}: forming 点混入 {name}：{entry.get('point')}")
    return issues


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


def replay_all() -> FormingEvidence:
    evidence = FormingEvidence()
    for label, csv_path, timeframe in _fixture_params():
        bars_all = clean_bars(read_bars_from_csv(str(csv_path)))
        for cutoff in _cutoffs(len(bars_all)):
            bars = bars_all[:cutoff]
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
            signals = analyze_chanlun_signals(
                bars, bis, zhongshus, calculate_macd(bars), segments=segments
            )
            evidence.frames += 1
            evidence.confirmed_seen += sum(
                1
                for p in signals.get("signal_points") or []
                if p.get("lifecycle_state") == "confirmed"
            )
            forming = list(signals.get("forming_points") or [])
            evidence.forming_seen += len(forming)
            for payload in forming:
                key = str(payload.get("point"))
                evidence.forming_by_point[key] = evidence.forming_by_point.get(key, 0) + 1
            evidence.forming_violations.extend(
                check_forming_invariants(signals, label=f"{label}@{cutoff}")
            )
    return evidence


def test_forming_invariants_hold_whenever_forming_fires() -> None:
    """不管可达与否，只要真产出 forming，就必须满足 watch 独立列表契约。"""
    evidence = replay_all()

    assert evidence.forming_violations == [], evidence.forming_violations[:10]


def test_replay_is_not_vacuous() -> None:
    """反空转：回放必须真的跑出了 confirmed 点，否则可达性判定无意义。"""
    evidence = replay_all()

    assert evidence.frames >= 100, f"回放帧数过少：{evidence.frames}"
    assert evidence.confirmed_seen > 0, "回放未产出任何 confirmed 点，回放口径可能已失效"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "已知不可达（2026-09-12 归因）：forming 的触发是一个「构造上互斥」的合取。"
        "287 帧冻结真实窗口下 forming=0；各合取项命中如下："
        "① `seg_pair_present`（当前中枢同时解析出 entering 与 exit 段）= 30/203 —— "
        "背驰只在**已终结、有离开段**的中枢上可算，而 ongoing 中枢的 exit_bi_id 为 None，"
        "故 segment_bottom_divergence 在 173/203 帧根本不参与计算；"
        "② `tail_ok`（尾部同向笔在 zs 边界外且无反向转折）= 129；"
        "③ `segment_bottom_divergence=True` = 14；"
        "④ `tail_ok ∧ ongoing_down ∧ bottom_div=True` = 3，但这 3 帧 `buy_1` 已 confirmed，"
        "forming 按「不与已确认点重复」设计跳过。"
        "结论：「背驰已现」需要已终结中枢，「待转折确认」只存在于未终结的最新中枢，两者互斥 → 需设计决策。"
        "本标记为 strict：一旦有人把 forming 变成可达，本用例会 XPASS→失败，强制回来删掉这个标记。"
    ),
)
def test_forming_is_reachable_on_real_windows() -> None:
    """RS1 可达性：真实窗口必须能产出 forming，否则「实时预备态」在真实链路上是死代码。"""
    evidence = replay_all()

    assert evidence.forming_seen >= MIN_FORMING_OCCURRENCES, (
        f"{evidence.frames} 帧真实窗口产出 forming {evidence.forming_seen} 次"
        f"（confirmed={evidence.confirmed_seen}）。"
        "RS1 的 forming 目前只在构造输入下成立，真实链路不可达。"
    )


@pytest.mark.parametrize(
    ("label", "csv_path", "timeframe"),
    _fixture_params(),
    ids=[item[0] for item in _fixture_params()],
)
def test_forming_invariants_per_window(label: str, csv_path: Path, timeframe: str) -> None:
    bars_all = clean_bars(read_bars_from_csv(str(csv_path)))
    violations: list[str] = []
    for cutoff in _cutoffs(len(bars_all)):
        bars = bars_all[:cutoff]
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
        signals = analyze_chanlun_signals(
            bars, bis, zhongshus, calculate_macd(bars), segments=segments
        )
        violations.extend(check_forming_invariants(signals, label=f"{label}@{cutoff}"))

    assert violations == [], violations[:10]
