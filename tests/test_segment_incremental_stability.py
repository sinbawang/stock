"""段链增量稳定性闸门：相邻 cutoff 之间段数不得骤降（spec §2.2 段识别稳定性）。

背景
----
2026-09-12 定位：`000651 1m` 在 cutoff 2588→2628（仅 +2 bi，笔 152→154）时段数由 **19 骤降到 6**，
其后段全部塌成一根 `bi33->151`（span=118）的**未确认**下降段（`stop=exhausted_confirmed_bis`）。
已确认前缀（seg0~4）在塌缩前后完全一致——不稳定只在**未确认的临时尾部**。

危害：下游三类门控把这根 118-bi 未确认巨型段当「离开段」，于是 `zhongshus[-1]` 退化成两周前的
远古中枢，发出锚在陈旧中枢上的垃圾三类点（design §4.2.11）。

判据定标（`build/probe_segment_drop_per_fixture.py`，仅 1m/5m/30m/day）：
`000651_1m` 最大跌幅 **12**（孤例）；其余 20 个 fixture 最大跌幅 **≤ 2**。
故取阈值 `MAX_ADJACENT_DROP = 4`（正常侧 2 之上留足余量），可干净分离。

`000651_1m` 目前必然触发 → 标 `xfail(strict)` 钉住这个已知段层缺陷：
一旦有人修好增量分段稳定性，本例 XPASS→失败，强制回来删标记。

spec_id: SPEC.SEGMENT.CORE。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for _extra in (SRC, SCRIPTS):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

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
from tests.real_fixture_support import FIXTURES_ROOT  # noqa: E402

FRAMES_PER_WINDOW = 12
MIN_BARS = 60
ALLOWED_TIMEFRAMES = {"1m", "5m", "30m", "day"}
# 相邻 cutoff 段数最大允许跌幅：正常侧实测 ≤2，000651_1m 孤例=12，取 4 留余量。
MAX_ADJACENT_DROP = 4
# 已知增量分段塌缩的 fixture（strict xfail 钉住，修好即 XPASS→失败强制收尾）。
KNOWN_COLLAPSE = {"000651-1m"}


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


def _segment_count(bars: list, timeframe: str) -> int:
    normalized = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized))
    bis = identify_bis(fractals, normalized, pending_reverse_mode="effective_only")
    segments = identify_segments(
        bis,
        bootstrap_mode=_bootstrap_for(timeframe),
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
    )
    return len(segments)


def _fixture_params() -> list:
    params: list = []
    for path in sorted(FIXTURES_ROOT.glob("*.csv")):
        if "_normalized" in path.name:
            continue
        parts = path.stem.split("_")
        if len(parts) < 3 or parts[1] not in ALLOWED_TIMEFRAMES:
            continue
        label = f"{parts[0]}-{parts[1]}"
        entry = (label, path, parts[1])
        if label in KNOWN_COLLAPSE:
            params.append(pytest.param(*entry, id=label, marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "已知增量分段塌缩（2026-09-12）：cutoff 2588→2628（+2 bi）段数 19→6，"
                    "其后段塌成一根 bi33->151（span=118）未确认下降段；已确认前缀稳定，"
                    "不稳定只在未确认临时尾部。下游三类门控据此发出锚在陈旧中枢的垃圾点。"
                    "根因在 identify_segments 增量稳定性，属段层课题；修好即 XPASS→失败，回来删标记。"
                ),
            )))
        else:
            params.append(pytest.param(*entry, id=label))
    return params


_PARAMS = _fixture_params()


@pytest.mark.parametrize(("label", "csv_path", "timeframe"), _PARAMS)
def test_segment_count_has_no_incremental_collapse(label: str, csv_path: Path, timeframe: str) -> None:
    """相邻 cutoff 段数跌幅不得超过 MAX_ADJACENT_DROP（增量分段不得整体塌缩）。"""
    bars_all = clean_bars(read_bars_from_csv(str(csv_path)))
    cutoffs = _cutoffs(len(bars_all))
    counts = [_segment_count(bars_all[:c], timeframe) for c in cutoffs]

    worst_drop = 0
    worst_where = ""
    for i in range(1, len(counts)):
        drop = counts[i - 1] - counts[i]
        if drop > worst_drop:
            worst_drop = drop
            worst_where = f"cutoff[{i-1}]={cutoffs[i-1]}({counts[i-1]}) -> cutoff[{i}]={cutoffs[i]}({counts[i]})"

    assert worst_drop <= MAX_ADJACENT_DROP, (
        f"{label}: 相邻 cutoff 段数骤降 {worst_drop} > {MAX_ADJACENT_DROP}（{worst_where}）；"
        "疑似增量分段塌缩，下游结构会锚在陈旧中枢上。"
    )


def test_stability_gate_is_not_vacuous() -> None:
    """反空转：真实窗口确实被扫过，且非塌缩 fixture 的最大跌幅落在阈值内（闸门有边界意义）。"""
    checked = 0
    max_normal_drop = 0
    for label, csv_path, timeframe in [(p.values[0], p.values[1], p.values[2]) for p in _PARAMS]:
        if label in KNOWN_COLLAPSE:
            continue
        bars_all = clean_bars(read_bars_from_csv(str(csv_path)))
        cutoffs = _cutoffs(len(bars_all))
        if len(cutoffs) < 2:
            continue
        counts = [_segment_count(bars_all[:c], timeframe) for c in cutoffs]
        checked += 1
        for i in range(1, len(counts)):
            max_normal_drop = max(max_normal_drop, counts[i - 1] - counts[i])

    assert checked >= 15, f"被扫 fixture 过少：{checked}"
    assert 0 < MAX_ADJACENT_DROP, "阈值必须为正"
    assert max_normal_drop <= MAX_ADJACENT_DROP, (
        f"非塌缩 fixture 出现跌幅 {max_normal_drop} > 阈值 {MAX_ADJACENT_DROP}，阈值需重新定标"
    )
