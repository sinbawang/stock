"""RS1 实时预备态（forming）闸门（spec §2.8）——**2026-09-13 重启版契约（rev2：线段口径）**。

背景
----
RS1 第一版（已下架 2026-09-12）：confirmed / forming 共用同一判别式，该判别式拿**历史锚点**去和
实时尾部比——锚点之后必然已有后续笔（笔严格交替），判别式恒等于「已确认」→ confirmed 永远先赢、
forming 被同类型去重遮蔽。287 帧冻结真实窗口 forming=0，合取构造不可达。

重启（2026-09-13）：forming 定义为**纯结构条件**（不叠任何附加确认），允许漂移失效，目标即时提示。
rev2 修正（2026-09-13，用户上报 7 例误报后）：三类（buy_3 / sell_3）的 forming 判据改为与
confirmed **同源的线段口径**——「离开线段 + 反试 / 反抽线段不进入中枢」，**不再接受笔级尾部对**
（旧笔级口径在 7 个持仓案例上误报：离开笔+反抽笔、离开线段+反抽笔均被判成立）。

发射契约：forming 经 `signal_points` 透传（`lifecycle_state=forming` / `active=False`）；
同族已确认点优先（同点遮蔽禁止）；旧 `forming_points` 槽位废弃恒空；confirmed 集合零变化
（发射快照 129 行与重启前逐字节一致）。

rev2 实测（build/probe_forming_seg_diag.py，4566 帧 / step=7）：
- 线段对结构大量存在（sell 1570 帧 / buy 515 帧），但**全部与 confirmed 同帧共存**：
  confirmed 锚点就是同一个 hold 段末笔，且 renewal（hold 末笔之后存在更晚反向笔）恒已成立
  （1570/1570、515/515）→ forming 被「confirmed 优先」规则覆盖；
- 结构必因：段层尾部永远落后于笔链（`segments[-1].end_bi_id != bis[-1].bi_id` 实测 4566/4566 帧），
  尾段之后必有 pending 反向笔 → renewal 恒真；
- 结论：**三类 forming 是 confirmed 的真子集且窗口为空**（当前 renewal 规则下），属已知边界——
  待 confirmed 收累（非单调性、renewal 重定义）后再重新度量；不得用笔级判据重新打开（用户已否决）。
- 7 个用户案例（000651-1m / 00981-30m / 03690-30m / 00700-30m / 00175-30m / 002555-30m /
  300124-30m 的 sell3）在各自上报时间点回放：线段口径均**不命中**，误报消除
  （build/probe_sell3_forming_replay.py）。

本闸门钉住四件事：
1. forming 载荷不变量（生命周期 / active / 不混入门控名单 / 旧槽恒空）；
2. 三类 forming 在冻结语料的**被遮蔽边界**（confirmed > 0 且 forming == 0，防空转靠 confirmed 计数）；
3. 线段判据纯函数语义（接受合格对；拒绝反抽笔 / 反抽进入中枢 / 离开早于中枢起点）；
4. 回放非空转（帧数 / confirmed 点存在）。

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

from chanlun.analysis import (  # noqa: E402
    _find_buy3_tail_segment_pair,
    _find_sell3_tail_segment_pair,
    analyze_chanlun_signals,
)
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
    confirmed_by_point: dict[str, int] = field(default_factory=dict)


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
            confirmed = [
                p for p in signals.get("signal_points") or [] if p.get("lifecycle_state") == "confirmed"
            ]
            evidence.confirmed_seen += len(confirmed)
            for payload in confirmed:
                key = str(payload.get("point"))
                evidence.confirmed_by_point[key] = evidence.confirmed_by_point.get(key, 0) + 1
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


def test_three_class_forming_shadowed_by_confirmed_on_frozen_windows() -> None:
    """rev2 边界（2026-09-13）：三类 forming 是 confirmed 的真子集，冻结语料上窗口为空。

    实测（build/probe_forming_seg_diag.py，4566 帧）：线段对结构 sell 1570 / buy 515 帧
    **全部**与 confirmed 同帧共存（confirmed 锚点 = 同一 hold 段末笔；renewal 1570/1570、515/515
    恒真）→ forming 被「同族 confirmed 优先」规则覆盖。结构必因：段层尾部永远落后于笔链
    （`segments[-1].end_bi_id != bis[-1].bi_id` 实测 4566/4566 帧），尾段之后必有 pending 反向笔。

    防空转：confirmed 三类计数必须 > 0（否则本断言无意义）；一旦未来 confirmed 收累打开 forming
    窗口，本用例会失败并强制回到设计文档重新决策。
    """
    evidence = replay_all()

    # 载荷 point 为无下划线格式（buy3 / sell3）。
    assert evidence.confirmed_by_point.get("buy3", 0) > 0, "冻结语料未产出 confirmed 三买，判据口径可能已失效"
    assert evidence.confirmed_by_point.get("sell3", 0) > 0, "冻结语料未产出 confirmed 三卖，判据口径可能已失效"
    assert evidence.forming_by_point.get("buy3", 0) == 0, "三买 forming 出现：confirmed 遮蔽机制已被改变，需重新决策"
    assert evidence.forming_by_point.get("sell3", 0) == 0, "三卖 forming 出现：confirmed 遮蔽机制已被改变，需重新决策"


def test_legacy_forming_points_slot_stays_empty() -> None:
    """重启后旧 `forming_points` 槽位废弃：真实窗口恒空（forming 经 signal_points 透传）。"""
    evidence = replay_all()

    assert evidence.legacy_forming_seen == 0, "旧 forming_points 槽位应为空（forming 经 signal_points 透传）"


@dataclass
class FakeSegment:
    """线段判据纯函数用例的最小假段（只含判据读取的字段）。"""

    segment_id: int
    direction: str
    start_bi_id: int
    end_bi_id: int
    high: float
    low: float
    is_confirmed: bool = True

    def is_up(self) -> bool:
        return self.direction == "up"

    def is_down(self) -> bool:
        return self.direction == "down"


def _seg(segment_id: int, direction: str, *, high: float, low: float) -> FakeSegment:
    return FakeSegment(
        segment_id=segment_id,
        direction=direction,
        start_bi_id=segment_id * 10,
        end_bi_id=segment_id * 10 + 2,
        high=high,
        low=low,
    )


def test_sell3_tail_segment_pair_accepts_valid_leave_and_hold() -> None:
    """rev2：尾部段对 = 离开线段（low < 中枢下沿）+ 反抽线段（high <= 中枢下沿，仍在尾部）→ 命中。"""
    leave = _seg(1, "down", high=10.8, low=9.0)
    hold = _seg(2, "up", high=10.0, low=9.2)

    assert _find_sell3_tail_segment_pair([leave, hold], 10.0, 1) == (leave, hold)
    # 尾部为「反抽段已完成、新下跌段刚起步」时回看前一对（hold 为倒数第二段）。
    tail = _seg(3, "down", high=10.2, low=8.8)
    assert _find_sell3_tail_segment_pair([leave, hold, tail], 10.0, 1) == (leave, hold)


def test_sell3_tail_segment_pair_rejects_hold_reentering_zhongshu() -> None:
    """rev2：反抽线段进入中枢（high > 中枢下沿，哪怕只超 0.05）→ 不得判成立（000651 用户案例形状）。"""
    leave = _seg(1, "down", high=10.8, low=9.0)
    hold = _seg(2, "up", high=10.05, low=9.2)

    assert _find_sell3_tail_segment_pair([leave, hold], 10.0, 1) == (None, None)


def test_sell3_tail_segment_pair_rejects_leave_not_below_level() -> None:
    """rev2：离开段 low 必须严格低于中枢下沿（相等不算离开）→ 不得判成立。"""
    leave = _seg(1, "down", high=10.8, low=10.0)
    hold = _seg(2, "up", high=10.0, low=9.2)

    assert _find_sell3_tail_segment_pair([leave, hold], 10.0, 1) == (None, None)


def test_sell3_tail_segment_pair_rejects_pair_before_zhongshu_start() -> None:
    """rev2：离开段早于中枢起点（segment_id < min_segment_id）→ 不得判成立。"""
    leave = _seg(1, "down", high=10.8, low=9.0)
    hold = _seg(2, "up", high=10.0, low=9.2)

    assert _find_sell3_tail_segment_pair([leave, hold], 10.0, 2) == (None, None)


def test_buy3_tail_segment_pair_accepts_and_rejects_mirror() -> None:
    """rev2（买侧对称）：离开线段（high > 中枢上沿）+ 回试线段（low >= 中枢上沿）命中；回试跌回中枢则拒绝。"""
    leave = _seg(1, "up", high=11.0, low=9.5)
    hold = _seg(2, "down", high=10.8, low=10.0)

    assert _find_buy3_tail_segment_pair([leave, hold], 10.0, 1) == (leave, hold)

    dipping_hold = _seg(2, "down", high=10.8, low=9.95)
    assert _find_buy3_tail_segment_pair([leave, dipping_hold], 10.0, 1) == (None, None)
