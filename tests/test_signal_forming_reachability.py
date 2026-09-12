"""RS1 实时预备态（forming）**已下架**闸门（spec §2.8）。

背景
----
RS1 曾标「完成（1/2/3 + 类一 / 类二 forming 均已落地并双边回归）」，但那些回归全部由**构造输入**
驱动（把离开笔截成链尾）。真实链路上 forming 恒为空：287 帧冻结真实窗口 forming=0。

根因（2026-09-12 归因）：confirmed / forming 共用同一判别式。该判别式拿**历史锦点**去和**实时
尾部**比——历史锦点之后必然已有后续笔（笔严格交替），于是判别式恒等于「已确认」，
**confirmed 分支永远先赢、forming 被同类型去重遮蔽**；且背驰只在「已终结、有离开段」中枢上可算，
与「未终结中枢待转折」互斥。合取构造不可达 → 已删除生产逻辑（见 signal-realtime-lifecycle-design.md §4.1）。

本闸门已由「可达性 strict xfail」改为「**下架后恒空**」的正向断言：
真实窗口 `forming_points` 必须恒为空；若有人重新引入非空 forming，本例会失败，
强制回到 §4.1 重新决策（而非悠然重新启用一个死特性）。

另保留「若真产出 forming 则必须满足 watch 独立列表契约」的不变量检查（防未来回退）。

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


@pytest.mark.parametrize(
    ("label", "csv_path", "timeframe"),
    _fixture_params(),
    ids=[item[0] for item in _fixture_params()],
)
def test_forming_is_retired_and_stays_empty(label: str, csv_path: Path, timeframe: str) -> None:
    """RS1 forming 已下架（2026-09-12）：真实窗口 `forming_points` 必须恒为空。

    原「可达性」诉求已推翻——confirmed / forming 共用同一判别式（历史锚点之后必已有后续笔 → 恒真
    → confirmed 永远先赢），且背驰只在已终结中枢可算、与「未终结中枢待转折」互斥，合取构造不可达。
    生产逻辑已删（`analyze_chanlun_signals` 不再产出 forming），本闸门反向钉住：一旦有人重新引入
    非空 forming，本例会失败，强制回到设计文档 §4.1 重新决策。
    """
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
        forming = list(signals.get("forming_points") or [])
        assert forming == [], f"{label}@{cutoff}: RS1 已下架，forming_points 应为空，却出现 {forming[:3]}"


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
