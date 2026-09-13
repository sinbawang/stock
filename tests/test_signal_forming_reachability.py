"""RS1 实时预备态（forming）闸门（spec §2.8）——**2026-09-13 重启版契约**。

背景
----
RS1 第一版（已下架 2026-09-12）：confirmed / forming 共用同一判别式，该判别式拿**历史锚点**去和
实时尾部比——锚点之后必然已有后续笔（笔严格交替），判别式恒等于「已确认」→ confirmed 永远先赢、
forming 被同类型去重遮蔽。287 帧冻结真实窗口 forming=0，合取构造不可达。

重启（2026-09-13，用户决策）：forming 定义为**纯结构条件**（不叠任何附加确认），允许漂移失效，
目标「即时提示符合理论的买卖点」；确认校验的增强后置到后续迭代。实现要点：
- 三类（buy_3 / sell_3）改**尾部口径**判据（离开 level 后回试 / 反抽不破仍在活跃尾部），
  不再与 confirmed 共用「历史首个匹配」判据 → 同帧可先出 forming、后出 confirmed；
- 发射契约：forming 经 `signal_points` 透传（`lifecycle_state=forming` / `active=False`），
  同族已确认点优先（同点遮蔽禁止）；旧 `forming_points` 槽位废弃恒空；
- confirmed 集合零变化（严格可加）；漂移（forming 后未见同族 confirmed）按设计允许，不回撤。

实证（build/probe_forming_fine.py，逐 bar 快照 31897 帧 / 21 窗口）：buy_3 forming 2100 帧、
sell_3 forming 3386 帧；同帧 confirmed+forming 影子遮蔽 0；串表不变量违规 0；confirmed 发射快照
与重启前逐字节一致（129 行）。buy_1 / buy_1like / buy_2like / sell_2like 因确认条件当前恒真、
暂无 forming 空间（0 帧），属已知状态——待该族确认条件收紧后成对生效，见设计文档 §4.1。

本闸门钉住三件事：
1. 真实窗口 forming 可达（buy_3 / sell_3 计数 > 0）；
2. forming 载荷不变量（生命周期 / active / 不混入门控名单 / 旧槽恒空）；
3. 回放非空转（帧数 / confirmed 点存在）。

spec_id: SPEC.BUY_SELL.CORE。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    legacy_forming_seen: int = 0
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
    """纯函数：forming 载荷不变量（空列表 = 通过）。

    1. 经 `signal_points` 透传：`lifecycle_state` 必须是 `forming`、`active` 必须为 False；
    2. 同帧不得出现同点 confirmed（confirmed 优先 / 遮蔽禁止）；
    3. 点族不得混入 `buy_points` / `sell_points` 门控名单；
    4. 旧 `forming_points` 槽位必须恒空（重启后废弃）。
    """
    issues: list[str] = []
    signal_points = list(signals.get("signal_points") or [])
    forming = [payload for payload in signal_points if payload.get("lifecycle_state") == "forming"]
    confirmed_names = {
        str(payload.get("point")).replace("_", "")
        for payload in signal_points
        if payload.get("lifecycle_state") == "confirmed"
    }
    # 载荷 `point` 为无下划线格式（buy3），门控名单为下划线格式（buy_3），统一去下划线后比较。
    gate_names = {
        str(name).replace("_", "")
        for name in (*list(signals.get("buy_points") or []), *list(signals.get("sell_points") or []))
    }
    for payload in forming:
        point = str(payload.get("point"))
        normalized_point = point.replace("_", "")
        if payload.get("active"):
            issues.append(f"{label}: forming 点 active=True（应仅 watch）：{point}")
        if normalized_point in confirmed_names:
            issues.append(f"{label}: 同帧同点 confirmed+forming 并存（遮蔽禁止）：{point}")
        if normalized_point in gate_names:
            issues.append(f"{label}: forming 点混入门控名单：{point}")

    if signals.get("forming_points"):
        issues.append(f"{label}: 旧 forming_points 槽位非空（应废弃恒空）")
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


_EVIDENCE_CACHE: FormingEvidence | None = None


def replay_all() -> FormingEvidence:
    """整轮回放（带缓存：多测试共享同一轮证据，避免重复跑管线）。"""
    global _EVIDENCE_CACHE
    if _EVIDENCE_CACHE is None:
        _EVIDENCE_CACHE = _replay_all_uncached()
    return _EVIDENCE_CACHE


def _replay_all_uncached() -> FormingEvidence:
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
            forming = [
                p
                for p in signals.get("signal_points") or []
                if p.get("lifecycle_state") == "forming"
            ]
            evidence.forming_seen += len(forming)
            evidence.legacy_forming_seen += len(signals.get("forming_points") or [])
            for payload in forming:
                key = str(payload.get("point"))
                evidence.forming_by_point[key] = evidence.forming_by_point.get(key, 0) + 1
            evidence.forming_violations.extend(
                check_forming_invariants(signals, label=f"{label}@{cutoff}")
            )
    return evidence


def test_forming_invariants_hold_whenever_forming_fires() -> None:
    """不管可达与否，只要真产出 forming，就必须满足载荷不变量。"""
    evidence = replay_all()

    assert evidence.forming_violations == [], evidence.forming_violations[:10]


def test_replay_is_not_vacuous() -> None:
    """反空转：回放必须真的跑出了 confirmed 点，否则可达性判定无意义。"""
    evidence = replay_all()

    assert evidence.frames >= 100, f"回放帧数过少：{evidence.frames}"
    assert evidence.confirmed_seen > 0, "回放未产出任何 confirmed 点，回放口径可能已失效"


def test_forming_reachable_on_frozen_windows() -> None:
    """RS1 重启（2026-09-13）：三类 forming 在真实窗口可达（纯结构条件、尾部口径）。

    细粒度探针（build/probe_forming_fine.py，逐 bar 31897 帧）实测 buy_3 forming 2100 帧、
    sell_3 forming 3386 帧；本闸门以 12 帧/窗口的粗采样钉住「非零可达」。
    """
    evidence = replay_all()

    # 载荷 point 为无下划线格式（buy3 / sell3）。
    assert evidence.forming_seen > 0, "真实窗口未产出任何 forming（重启契约已失效？）"
    assert evidence.forming_by_point.get("buy3", 0) > 0, "三买 forming 在真实窗口不可达"
    assert evidence.forming_by_point.get("sell3", 0) > 0, "三卖 forming 在真实窗口不可达"


def test_legacy_forming_points_slot_stays_empty() -> None:
    """重启后旧 `forming_points` 槽位废弃：真实窗口恒空（forming 经 signal_points 透传）。"""
    evidence = replay_all()

    assert evidence.legacy_forming_seen == 0, "旧 forming_points 槽位应为空（forming 经 signal_points 透传）"
