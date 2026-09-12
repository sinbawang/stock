"""信号生命周期锚点红线闸门（spec §2.8 §3.3）——基于冻结真实窗口的确定性跨帧回放。

背景
----
§3.3 第一条红线：**`confirmed` 仅锚定 `is_confirmed=True` 的笔 / 线段；未确认笔只能承载 `forming`。**

原闸门 `tests/test_signal_repaint_gate.py` 只读 `data/reports/**/tech.json`（gitignored），
**没有本地报告时直接 `pytest.skip`** —— 干净检出 / CI 里这条红线实际没有被执行（空转闸门），
因此红线违约可以长期潜伏。

2026-09-12 用本文件的回放口径（固定窗口起点、逐 cutoff 扩张尾段）在 21 个冻结真实窗口上
检出真实违约：`000591 day` cutoff=1010 的 `buy1` 以 `lifecycle_state=confirmed` 锚定在
**未确认的 pending 尾笔** bi=95 上。根因是发点门控与载荷锚点不一致：
门控校验的是离开段末笔（`exit_segment.end_bi_id`，已确认），而
`build_signal_point_payloads` 的 `buy_1` / `buy_2` / `sell_2` 没有专用锚点参数，
落到 `latest_down` / `latest_up`（可能正是未确认尾笔），随后被「active 即 confirmed」的
兜底无条件盖成确认态。已修：补 `buy1/buy2/sell1/sell2_signal_bi` 专用锚点，
并让生命周期兜底 fail closed（锚点未确认只能给 `forming`）。

本闸门同时守住两件事：
1. `confirmed` 锚点必须已确认（§3.3 红线 1）；
2. 回放设置本身有效（固定起点 → 不得出现 `window_rebased`，否则比较被豁免路径掩盖）。

反空转：断言观测到的 confirmed 点数量达到下限，避免「什么都没发」也算通过。

spec_id: SPEC.BUY_SELL.CORE。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for _extra in (SRC, SCRIPTS):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from chanlun.analysis import (  # noqa: E402
    analyze_chanlun_signals,
    replay_confirmed_signal_lifecycle,
    to_lifecycle_frame,
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

FRAMES_PER_WINDOW = 5
MIN_BARS = 60
# 反空转下限：21 个窗口 × 5 帧下实测远高于此值（观测 confirmed 点总数约 90+）。
MIN_OBSERVED_CONFIRMED = 25


@dataclass(frozen=True)
class AnchorEvidence:
    """单窗口回放的锚点红线证据。"""

    frames: int
    confirmed_seen: int
    anchor_violations: list[str]
    window_rebased: bool


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


def evaluate_anchor_violations(
    signal_points: list[dict[str, object]],
    *,
    confirmed_bi_ids: set[int],
    cutoff: int,
) -> list[str]:
    """纯函数：返回 §3.3 锚点红线违约（空列表 = 通过）。

    抽成纯函数是为了能用「构造的历史违约形态」自证闸门有效，
    不依赖真实窗口恰好退化。
    """
    violations: list[str] = []
    for payload in signal_points:
        if payload.get("lifecycle_state") != "confirmed":
            continue
        if payload.get("signal_bi_id") not in confirmed_bi_ids:
            violations.append(
                f"cutoff={cutoff} {payload.get('point')} "
                f"anchored on unconfirmed bi {payload.get('signal_bi_id')}"
            )
    return violations


def replay_window(csv_path: Path, timeframe: str) -> AnchorEvidence:
    """固定窗口起点、逐 cutoff 扩张尾段回放，返回锚点红线证据。"""
    bars_all = clean_bars(read_bars_from_csv(str(csv_path)))
    cutoffs = _cutoffs(len(bars_all))
    if not cutoffs:
        return AnchorEvidence(frames=0, confirmed_seen=0, anchor_violations=[], window_rebased=False)

    # 固定起点 → data_window 恒定，跨帧锚点可比，不会被「窗口重基」豁免掩盖。
    data_window = str(getattr(bars_all[0], "ts"))
    frames: list[dict[str, object]] = []
    violations: list[str] = []
    confirmed_seen = 0

    for cutoff in cutoffs:
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
        frames.append(to_lifecycle_frame(signals, data_window=data_window))

        confirmed_ids = {bi.bi_id for bi in bis if bi.is_confirmed}
        confirmed_seen += sum(
            1
            for payload in signals.get("signal_points") or []
            if payload.get("lifecycle_state") == "confirmed"
        )
        violations.extend(
            evaluate_anchor_violations(
                list(signals.get("signal_points") or []),
                confirmed_bi_ids=confirmed_ids,
                cutoff=cutoff,
            )
        )

    replay = replay_confirmed_signal_lifecycle(frames)
    return AnchorEvidence(
        frames=len(frames),
        confirmed_seen=confirmed_seen,
        anchor_violations=violations,
        window_rebased=bool(replay["window_rebased"]),
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


def test_evaluator_flags_confirmed_anchored_on_unconfirmed_bi() -> None:
    """自证：固化历史违约形态（000591 day cutoff=1010 的 buy1 → 未确认 bi 95）必须被检出。"""
    violations = evaluate_anchor_violations(
        [{"point": "buy1", "lifecycle_state": "confirmed", "signal_bi_id": 95}],
        confirmed_bi_ids={93, 94},
        cutoff=1010,
    )

    assert len(violations) == 1, violations
    assert "buy1" in violations[0] and "95" in violations[0]


def test_evaluator_accepts_confirmed_anchor() -> None:
    violations = evaluate_anchor_violations(
        [{"point": "sell1", "lifecycle_state": "confirmed", "signal_bi_id": 94}],
        confirmed_bi_ids={93, 94},
        cutoff=1010,
    )

    assert violations == []


def test_evaluator_ignores_non_confirmed_states() -> None:
    """forming 允许锚定未确认笔，不得误报。"""
    violations = evaluate_anchor_violations(
        [{"point": "buy1", "lifecycle_state": "forming", "signal_bi_id": 95}],
        confirmed_bi_ids={93, 94},
        cutoff=1010,
    )

    assert violations == []


def test_replay_setup_keeps_window_stable() -> None:
    """回放设置自证：固定起点必须使 data_window 恒定，不得触发窗口重基豁免。"""
    path = next((p for p in FIXTURES_ROOT.glob("03690_5m_*.csv") if "_normalized" not in p.name), None)
    assert path is not None, "缺少 03690 5m 冻结 fixture"

    evidence = replay_window(path, "5m")

    assert evidence.frames > 0
    assert evidence.window_rebased is False
    assert evidence.anchor_violations == [], evidence.anchor_violations


@pytest.mark.parametrize(
    ("label", "csv_path", "timeframe"),
    _fixture_params(),
    ids=[item[0] for item in _fixture_params()],
)
def test_confirmed_signals_anchor_confirmed_bis(label: str, csv_path: Path, timeframe: str) -> None:
    """spec §3.3 红线 1：confirmed 只能锚定已确认笔。"""
    evidence = replay_window(csv_path, timeframe)

    assert evidence.anchor_violations == [], f"{label}: {evidence.anchor_violations}"


def test_anchor_gate_is_not_vacuous() -> None:
    """反空转：全部窗口累计观测到的 confirmed 点必须达到下限，避免「什么都没发」也算通过。"""
    total = sum(
        replay_window(csv_path, timeframe).confirmed_seen
        for _, csv_path, timeframe in _fixture_params()
    )

    assert total >= MIN_OBSERVED_CONFIRMED, f"仅观测到 {total} 个 confirmed 点，闸门可能空转"
