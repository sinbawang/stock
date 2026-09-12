"""消费层 replay 样本的支持模块（**只读冻结 fixture**）。

**为什么需要本模块**：`tests/test_build_miniapp_publish_bundle.py` 等四个模块原本在导入期加载
`build/probe_intraday_prebreak_sample.py`，而该文件**未被版本控制**（`build/` 在 `.gitignore` 里，
只有 `build/scan_real_1m_confirmed_buy_samples.py` 一个文件被强制加入）；
那个探针的 `_load_rows` 又只从 `data/reports/**` 与 `data/cache/kline/**` 读取，同样未入版本库。
后果：在没有本地 `build/` 与 `data/` 的机器上，这些测试模块在**收集阶段**就
`FileNotFoundError`（`no tests collected`），它承载的全部「真实样本」锚点对 reviewer 不可复现。

本模块把同一套 replay 逻辑改为只读 `tests/fixtures/real/replay/`，使这些锚点在任何机器上可复现。
算法与探针保持一致（`bootstrap_mode="first_valid_seed"` / `strict_segment_rules=True` /
`pending_reverse_mode="effective_only"`），**不要**为了让断言通过而修改这里的口径：
口径一变，消费层样本的业务含义就变了。
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for _extra in (SRC, SCRIPTS, ROOT):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from batch_prepare_chanlun_reports import build_advice, build_technical_summary, extract_signals  # noqa: E402
from chanlun.bi import identify_bis  # noqa: E402
from chanlun.data import read_bars_from_dataframe  # noqa: E402
from chanlun.data.cleaner import clean_bars  # noqa: E402
from chanlun.fractal import filter_consecutive_fractals, identify_fractals  # noqa: E402
from chanlun.normalize import normalize_bars  # noqa: E402
from chanlun.segment import identify_segments  # noqa: E402
from chanlun.zhongshu import identify_zhongshu  # noqa: E402
from export_structures_with_boxes import calculate_macd  # noqa: E402
from tests.real_fixture_support import replay_fixture_csv  # noqa: E402


def load_replay_rows(symbol: str, timeframe: str) -> list[dict[str, object]]:
    """读取冻结的 replay 窗口原始 K 线行（与探针的 DictReader 读法一致）。"""
    path = replay_fixture_csv(symbol, timeframe)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _coerce_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def select_auto_cutoffs(rows: list[dict[str, object]], start: str | None, end: str | None) -> list[str]:
    """从行序列里取出 [start, end] 内的去重时间截（升序，保持原顺序）。

    与 `build/probe_intraday_prebreak_sample.py::_select_auto_cutoffs` 同语义；
    搬到本模块是为了让依赖它的用例不再需要未受版本控制的 `build/` 探针。
    """
    cutoffs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ts = str(row.get("ts") or "")
        if not ts or ts in seen:
            continue
        if start and ts < start:
            continue
        if end and ts > end:
            continue
        seen.add(ts)
        cutoffs.append(ts)
    return cutoffs


def filter_auto_find_results(
    scan_results: list[dict[str, object]],
    *,
    symbol: str,
    target_alert: str,
    start: str | None,
    end: str | None,
    limit: int,
) -> list[dict[str, object]]:
    """保留命中目标预警的前 `limit` 条；一条不中时返回带 `matches: 0` 的说明条目。

    与 `build/probe_intraday_prebreak_sample.py::_filter_auto_find_results` 同语义。
    """
    matching_results = [result for result in scan_results if result.get("zs_monitor_alert") == target_alert]
    payload = matching_results[: max(limit, 0)]
    if payload:
        return payload
    return [
        {
            "symbol": symbol,
            "target_alert": target_alert,
            "start": start,
            "end": end,
            "matches": 0,
            "scanned": len(scan_results),
        }
    ]


def replay(symbol: str, name: str, cutoff: str, rows: list[dict[str, object]]) -> dict[str, object]:
    """把冻结窗口回放到 `cutoff`（含），返回与探针一致的诊断载荷。"""
    subset = [row for row in rows if str(row.get("ts") or "") <= cutoff]
    if not subset:
        return {"cutoff": cutoff, "rows": 0, "error": "no_rows_before_cutoff"}

    raw_bars = clean_bars(read_bars_from_dataframe(_coerce_frame(subset)))
    normalized_bars = normalize_bars(raw_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="effective_only")
    segments = identify_segments(
        bis,
        bootstrap_mode="first_valid_seed",
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
    )
    zhongshus = identify_zhongshu(segments, structure_level="segment")
    macd_points = calculate_macd(raw_bars)
    signals = extract_signals(bis, zhongshus, macd_points, raw_bars=raw_bars, segments=segments)
    latest_zs = zhongshus[-1] if zhongshus else None

    structure_state = signals.get("structure_state") or {}
    ongoing = structure_state.get("current_ongoing") or {}
    divergence = signals.get("divergence") or {}
    divergence_trend = divergence.get("trend") or {}
    divergence_range = divergence.get("range") or {}

    advice_text = build_advice(name, "1M", raw_bars, signals)
    summary = build_technical_summary("1M", signals, advice_text, raw_bars=raw_bars)

    return {
        "cutoff": cutoff,
        "rows": len(subset),
        "last_ts": subset[-1].get("ts"),
        "zs_monitor_alert": signals.get("zs_monitor_alert"),
        "zs_monitor_midline": signals.get("zs_monitor_midline"),
        "zs_monitor_bias": signals.get("zs_monitor_bias"),
        "same_level_decomposition_mode": signals.get("same_level_decomposition_mode"),
        "same_level_consumption_level": signals.get("same_level_consumption_level"),
        "buy_points": signals.get("buy_points"),
        "sell_points": signals.get("sell_points"),
        "conclusion": summary.get("conclusion"),
        "latest_zs_low": getattr(latest_zs, "zs_low", None),
        "latest_zs_high": getattr(latest_zs, "zs_high", None),
        "advice_text": advice_text,
        "ongoing_type": ongoing.get("type"),
        "divergence_trend_active": divergence_trend.get("active"),
        "divergence_trend_strict": divergence_trend.get("strict"),
        "divergence_range_active": divergence_range.get("active"),
        "divergence_range_strict": divergence_range.get("strict"),
        "divergence_range_touches_boundary": divergence_range.get("touches_boundary"),
        "divergence_range_direction": divergence_range.get("direction"),
        "divergence_range_reference_zs_id": divergence_range.get("reference_zs_id"),
        "post_divergence_route": signals.get("post_divergence_route"),
        "oscillation_rhythm_state": signals.get("oscillation_rhythm_state"),
    }
