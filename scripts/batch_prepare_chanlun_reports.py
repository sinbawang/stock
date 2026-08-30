from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from functools import lru_cache
import hashlib
import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report_retention import prune_analyze_csv_families, prune_older_outputs

from chanlun.analysis import (
    analyze_chanlun_signals,
    build_signal_explanation_lines,
    build_signal_summary_fields,
    describe_consumption_level,
    describe_transition_state,
    format_consumption_level_label,
    format_signal_point_labels,
    format_transition_state_label,
)
from chanlun.bi import identify_bis
from chanlun.chart_export import save_structure_charts
from chanlun.default_ranges import (
    default_day_start_for_bar_target,
    default_intraday_start_for_bar_target,
    default_structure_start,
)
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_fetcher import fetch_hk_daily, save_to_csv as save_hk_daily_csv
from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy, get_last_fetch_metadata as get_last_hk_fetch_metadata, save_to_csv as save_hk_minute_csv
from chanlun.data.kline_fetcher import fetch_kline, get_last_fetch_metadata, save_to_csv as save_kline_csv
from chanlun.data.local_bar_store import infer_incremental_start, load_local_rows, tail_rows, upsert_local_rows
from chanlun.data.source_profiles import describe_source_chain, resolve_a_share_intraday_source_label, resolve_hk_minute_source_selection
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import identify_segments
from chanlun.zhongshu import identify_zhongshu

from export_structures_with_boxes import (
    calculate_macd,
    export_bis,
    export_confirmed_fractals,
    export_fractals,
    export_macd,
    export_segments,
    format_zhongshu_structure_text,
    serialize_zhongshu,
    serialize_zhongshus,
    export_zhongshus,
)
from report_json import write_json
from run_hk_60m_chanlun_report import analyze_current_state, compute_bi_strengths, write_normalized_csv
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file, stock_report_dir, timeframe_report_paths


@dataclass(frozen=True)
class Security:
    symbol: str
    name: str
    market: str


SECURITIES = [
    Security("03690", "美团", "HK"),
    Security("01339", "中国人保", "HK"),
    Security("300124", "汇川技术", "A"),
    Security("00728", "中国电信", "HK"),
    Security("000591", "太阳能", "A"),
    Security("02357", "中航科工", "HK"),
    Security("002555", "三七互娱", "A"),
    Security("01024", "快手", "HK"),
    Security("00700", "腾讯", "HK"),
    Security("00981", "中芯国际", "HK"),
]

DEFAULT_HOLDINGS_FILE = holdings_file()
INTRADAY_SOURCE_PROBE_ROWS = 1200
M1_BAR_DEFAULT = 3500
BAR_COUNT_POLICY = "feasible_maximum"
HK_REUSABLE_5M_MIN_ROWS = 480

# tech.json 内容决定源码集合；这些文件变化时，已缓存的 5m/1m 报告应失效重算。
TECH_REPORT_SOURCE_ROOTS = (
    SRC / "chanlun",
    SRC / "report_json.py",
    SRC / "storage_layout.py",
    SCRIPTS / "batch_prepare_chanlun_reports.py",
    SCRIPTS / "run_hk_60m_chanlun_report.py",
    SCRIPTS / "export_structures_with_boxes.py",
)


@lru_cache(maxsize=1)
def compute_tech_report_fingerprint() -> str:
    """返回决定 tech.json 内容的源码稳定指纹（SHA-256）。"""
    hasher = hashlib.sha256()
    files: set[Path] = set()
    for base in TECH_REPORT_SOURCE_ROOTS:
        if base.is_dir():
            files.update(path for path in base.rglob("*.py") if "__pycache__" not in path.parts)
        elif base.is_file():
            files.add(base)
    for path in sorted(files, key=lambda p: str(p).replace("\\", "/")):
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(path.read_bytes())
        hasher.update(b"\x00")
    return hasher.hexdigest()


INTRADAY_TIMEFRAME_SPECS = (
    ("60m", "60", "60M"),
    ("30m", "30", "30M"),
    ("15m", "15", "15M"),
    ("5m", "5", "5M"),
    ("1m", "1", "1M"),
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BatchPrepareResult:
    security_count: int
    selected_timeframes: tuple[str, ...]
    manifest_path: Path
    summary_path: Path | None
    timeframe_diagnostics: list[dict[str, object]]


@dataclass(frozen=True)
class PreparedSecurityResult:
    security: Security
    day_case: dict[str, Path]
    m60_case: dict[str, Path]
    timeframe_diagnostics: list[dict[str, object]]


def timeframe_display_label(timeframe: str) -> str:
    normalized = timeframe.strip().lower()
    if normalized == "day":
        return "日线"
    return normalized.upper()


def _data_fetch_payload(
    source: str,
    rows: list[dict],
    requested_min_rows: int | None,
    *,
    actual_source: str | None = None,
    source_attempts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    actual_bar_count = len(rows)
    return {
        "source": source,
        "actual_source": actual_source or source,
        "source_attempts": source_attempts or [],
        "actual_bar_count": actual_bar_count,
        "requested_min_rows": requested_min_rows,
        "fulfilled_min_rows": actual_bar_count >= requested_min_rows if requested_min_rows is not None else None,
        "bar_count_policy": BAR_COUNT_POLICY,
        "source_probe_min_rows": INTRADAY_SOURCE_PROBE_ROWS if requested_min_rows is None else requested_min_rows,
    }


def _build_timeframe_diagnostic(
    security: Security,
    timeframe: str,
    rows: list[dict],
    fetch_meta: dict[str, object] | None,
    exported: dict[str, Path] | None,
    *,
    requested_start: str,
    bar_count: int,
    reused_existing_case: bool,
) -> dict[str, object]:
    tech_payload: dict[str, object] = {}
    if exported and exported.get("tech_json"):
        try:
            tech_payload = json.loads(Path(exported["tech_json"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            tech_payload = {}

    artifacts = tech_payload.get("artifacts") or {}
    local_store = (fetch_meta or {}).get("local_store") or {}
    raw_csv = artifacts.get("raw_csv")
    raw_csv_name = Path(raw_csv).name if raw_csv else None
    return {
        "symbol": security.symbol,
        "market": security.market,
        "timeframe": timeframe,
        "requested_start": requested_start,
        "requested_bar_count": bar_count,
        "actual_bar_count": len(rows),
        "first_bar_ts": str(rows[0].get("ts") or "") if rows else None,
        "last_bar_ts": str(rows[-1].get("ts") or "") if rows else None,
        "source": (fetch_meta or {}).get("source"),
        "actual_source": (fetch_meta or {}).get("actual_source"),
        "source_attempts": list((fetch_meta or {}).get("source_attempts") or []),
        "raw_csv": raw_csv,
        "raw_csv_name": raw_csv_name,
        "generated_at": tech_payload.get("generated_at"),
        "reused_existing_case": reused_existing_case,
        "local_store": {
            "enabled": bool(local_store.get("enabled")),
            "read_only": bool(local_store.get("read_only")),
            "local_rows_before": local_store.get("local_rows_before"),
            "remote_rows": local_store.get("remote_rows"),
            "merged_total_rows": local_store.get("merged_total_rows"),
            "added_rows": local_store.get("added_rows"),
            "updated_rows": local_store.get("updated_rows"),
            "analysis_rows": local_store.get("analysis_rows"),
            "effective_start": local_store.get("effective_start"),
            "store_path": local_store.get("store_path"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成最新日线、30M、5M、1M 缠论图、分析文本、操作建议")
    parser.add_argument("--day-start", default=None, help="日线起始日期；未指定时按日线根数自动回推")
    parser.add_argument("--day-bars", type=int, default=1200, help="日线抓取目标根数，默认 1200")
    parser.add_argument("--m60-start", default=None, help="60M 起始时间；未指定时按 60M 根数自动回推")
    parser.add_argument("--m60-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="60M 抓取目标根数，默认 1200")
    parser.add_argument("--m30-start", default=None, help="30M 起始时间；未指定时按 30M 根数自动回推")
    parser.add_argument("--m30-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="30M 抓取目标根数，默认 1200")
    parser.add_argument("--m15-start", default=None, help="15M 起始时间；未指定时按 15M 根数自动回推")
    parser.add_argument("--m15-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="15M 抓取目标根数，默认 1200")
    parser.add_argument("--m5-start", default=None, help="5M 起始时间；未指定时按 5M 根数自动回推")
    parser.add_argument("--m5-bars", type=int, default=2000, help="5M 抓取目标根数，默认 2000")
    parser.add_argument("--m1-start", default=None, help="1M 起始时间；未指定时按 1M 根数自动回推")
    parser.add_argument("--m1-bars", type=int, default=M1_BAR_DEFAULT, help="1M 抓取目标根数，默认 3500")
    parser.add_argument(
        "--holdings-file",
        default=str(DEFAULT_HOLDINGS_FILE),
        help="持仓清单 JSON 文件，默认读取 config/stock_holdings.json；不存在时回退到脚本内置名单。",
    )
    parser.add_argument(
        "--pending-reverse-mode",
        choices=("any", "effective_only", "tail_mixed"),
        default="effective_only",
        help="笔尾部反向分型占位口径：any=当前保守口径，effective_only=全局仅允许满足间隔的反向分型占位，tail_mixed=仅对最后未确认尾笔链路启用 effective_only。",
    )
    parser.add_argument(
        "--zhongshu-level",
        choices=("segment",),
        default="segment",
        help="中枢主口径层级：segment=标准中枢(默认)。",
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=["day", "30m", "5m", "1m"],
        help="需要生成的技术级别；默认生成 day/30m/5m/1m。",
    )
    parser.add_argument(
        "--force-regenerate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="忽略已有报告复用判定，强制重新生成所有技术级别报告。",
    )
    parser.add_argument(
        "--use-local-store",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否启用本地历史 K 线仓库（默认启用）。启用后会增量抓取并合并到 data/cache/kline。",
    )
    parser.add_argument(
        "--incremental-overlap-bars",
        type=int,
        default=120,
        help="增量抓取时回看重叠根数，用于覆盖远端补数据场景；默认 120。",
    )
    parser.add_argument(
        "--local-store-root",
        default=None,
        help="可选，本地 K 线仓库根目录覆盖。默认使用 data/cache/kline。",
    )
    parser.add_argument(
        "--local-store-read-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="已废弃且忽略；始终允许远端增量抓取并合并本地 K 线仓库。",
    )
    parser.add_argument(
        "--export-structure-images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否导出结构图文件（svg/png/jpg）。默认 true；设为 false 可仅生成结构数据与文本，提升批量速度。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="按持仓并行生成的 worker 数，默认最多 4。",
    )
    return parser.parse_args()


def _market_code_to_security_market(market_code: str, symbol: str) -> str:
    if market_code == "HK":
        return "HK"
    if market_code == "CN":
        return "A"
    return "HK" if len(symbol) == 5 else "A"


def load_securities(holdings_file: Path | None = None) -> list[Security]:
    holdings_path = holdings_file or DEFAULT_HOLDINGS_FILE
    if not holdings_path.exists():
        return SECURITIES

    payload = json.loads(holdings_path.read_text(encoding="utf-8"))
    raw_entries: list[tuple[str | None, dict]] = []
    markets = payload.get("markets")
    if isinstance(markets, dict):
        for market_code, market_holdings in markets.items():
            if not isinstance(market_holdings, list):
                continue
            raw_entries.extend((market_code, entry) for entry in market_holdings if isinstance(entry, dict))
    else:
        for entry in payload.get("holdings", []):
            if isinstance(entry, dict):
                raw_entries.append((payload.get("market"), entry))

    dedup: dict[str, Security] = {}
    for market_code, entry in raw_entries:
        symbol = str(entry.get("symbol") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not symbol or not name:
            continue
        dedup[f"{symbol}:{name}"] = Security(
            symbol=symbol,
            name=name,
            market=_market_code_to_security_market(str(market_code or "").upper(), symbol),
        )
    return list(dedup.values()) or SECURITIES


def fetch_day_rows(security: Security, start: str, day_bars: int) -> tuple[list[dict], dict[str, object]]:
    if security.market == "HK":
        rows = fetch_hk_daily(security.symbol, start=start, limit=day_bars)
        return rows, _data_fetch_payload("tencent.hk_daily", rows, day_bars)
    rows = fetch_kline(security.symbol, start=start, interval="day", limit=day_bars)
    return rows, _data_fetch_payload("tencent.day", rows, day_bars)


def fetch_m60_rows(security: Security, start: str, m60_bars: int) -> tuple[list[dict], dict[str, object]]:
    return fetch_intraday_rows(security, timeframe="60m", period="60", start=start, bar_count=m60_bars)


def fetch_intraday_rows(
    security: Security,
    *,
    timeframe: str,
    period: str,
    start: str,
    bar_count: int,
    source_probe_min_rows: int | None = None,
) -> tuple[list[dict], dict[str, object]]:
    interval = f"m{period}"
    if security.market == "HK":
        probe_min_rows = bar_count if source_probe_min_rows is None else source_probe_min_rows
        if timeframe == "5m" and probe_min_rows >= bar_count:
            reused_rows = _load_reusable_hk_intraday_rows(security, timeframe, min(bar_count, HK_REUSABLE_5M_MIN_ROWS))
            if reused_rows is not None:
                return reused_rows, _data_fetch_payload("local.hk_5m_cache", reused_rows, bar_count, actual_source="local.hk_5m_cache")
        primary_source, fallback_sources, _ = resolve_hk_minute_source_selection()
        rows, _ = fetch_hk_minute_with_policy(
            security.symbol,
            period=period,
            start=start,
            adjust="",
            primary_source=primary_source,
            fallback_sources=fallback_sources,
            min_rows=probe_min_rows,
            stop_on_sufficient_rows=timeframe in {"30m", "5m", "1m"},
        )
        fetch_meta = get_last_hk_fetch_metadata()
        return rows, _data_fetch_payload(
            describe_source_chain(primary_source, fallback_sources),
            rows,
            bar_count,
            actual_source=str(fetch_meta.get("actual_source") or primary_source),
            source_attempts=list(fetch_meta.get("source_attempts") or []),
        )
    fetch_source, _ = resolve_a_share_intraday_source_label()
    probe_min_rows = bar_count if source_probe_min_rows is None else source_probe_min_rows
    rows = fetch_kline(security.symbol, start=start, interval=interval, limit=bar_count, min_rows=probe_min_rows)
    fetch_meta = get_last_fetch_metadata()
    return rows, _data_fetch_payload(
        fetch_source,
        rows,
        bar_count,
        actual_source=str(fetch_meta.get("actual_source") or fetch_source),
        source_attempts=list(fetch_meta.get("source_attempts") or []),
    )


def _load_reusable_hk_intraday_rows(security: Security, timeframe: str, min_rows: int) -> list[dict] | None:
    analyze_dir = stock_report_dir(security.symbol) / timeframe / "analyze"
    if not analyze_dir.exists():
        return None

    candidates = [
        path
        for path in analyze_dir.glob(f"{security.symbol}_{timeframe}_*.csv")
        if "_normalized" not in path.name
    ]
    if not candidates:
        return None

    latest_path = max(candidates, key=lambda item: item.stat().st_mtime)
    with latest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {
                "ts": str(row.get("ts") or "").strip(),
                "open": float(row.get("open") or 0),
                "high": float(row.get("high") or 0),
                "low": float(row.get("low") or 0),
                "close": float(row.get("close") or 0),
                "volume": int(float(row.get("volume") or 0)),
            }
            for row in reader
            if str(row.get("ts") or "").strip()
        ]
    if len(rows) < min_rows:
        return None
    return rows


def fetch_m15_rows(security: Security, start: str, m15_bars: int) -> tuple[list[dict], dict[str, object]]:
    return fetch_intraday_rows(security, timeframe="15m", period="15", start=start, bar_count=m15_bars)


def save_rows(security: Security, timeframe: str, rows: list[dict], path: Path) -> None:
    if timeframe == "day":
        if security.market == "HK":
            save_hk_daily_csv(rows, str(path))
        else:
            save_kline_csv(rows, str(path))
        return

    if security.market == "HK":
        save_hk_minute_csv(rows, str(path))
    else:
        save_kline_csv(rows, str(path))


def _fetch_with_optional_local_store(
    security: Security,
    *,
    timeframe: str,
    requested_start: str,
    bar_count: int,
    overlap_bars: int,
    use_local_store: bool,
    local_store_read_only: bool,
    local_store_root: Path | None,
    remote_fetcher,
) -> tuple[list[dict], dict[str, object]]:
    effective_start = requested_start
    local_before = 0
    local_covers_target = False
    if use_local_store:
        local_rows = load_local_rows(security.symbol, security.market, timeframe, root=local_store_root)
        local_before = len(local_rows)
        local_covers_target = local_before >= bar_count
        if local_rows and local_covers_target:
            # 本地仓库已覆盖目标根数时才走增量（只补最近 delta）；否则从完整窗口
            # requested_start 全量抓取补齐缺口（例如目标根数被调高、或首次回填）。
            effective_start = infer_incremental_start(local_rows[-1]["ts"], timeframe, overlap_bars=overlap_bars)

    if use_local_store and local_store_read_only and local_before > 0:
        analysis_rows = tail_rows(local_rows, bar_count)
        return analysis_rows, {
            "source": "local_store_read_only",
            "actual_source": "local_store_read_only",
            "source_attempts": [],
            "actual_bar_count": len(analysis_rows),
            "requested_min_rows": bar_count,
            "fulfilled_min_rows": len(analysis_rows) >= bar_count,
            "bar_count_policy": BAR_COUNT_POLICY,
            "source_probe_min_rows": 1,
            "local_store": {
                "enabled": True,
                "read_only": True,
                "requested_start": requested_start,
                "effective_start": effective_start,
                "overlap_bars": overlap_bars,
                "local_rows_before": local_before,
                "remote_rows": 0,
                "merged_total_rows": local_before,
                "added_rows": 0,
                "updated_rows": 0,
                "analysis_rows": len(analysis_rows),
            },
        }

    remote_probe_min_rows = bar_count
    if use_local_store and local_covers_target and timeframe != "day":
        # Incremental mode only needs recent deltas. Avoid forcing full-count
        # remote rows, which can trigger costly fallback probing for HK minute data.
        remote_probe_min_rows = 1

    remote_fetcher_params = inspect.signature(remote_fetcher).parameters
    if len(remote_fetcher_params) <= 1:
        rows, fetch_meta = remote_fetcher(effective_start)
    else:
        rows, fetch_meta = remote_fetcher(effective_start, remote_probe_min_rows)
    if not use_local_store:
        return rows, fetch_meta

    merged_rows, merge_stats, store_path = upsert_local_rows(
        security.symbol,
        security.market,
        timeframe,
        rows,
        root=local_store_root,
    )
    analysis_rows = tail_rows(merged_rows, bar_count)
    payload = dict(fetch_meta)
    payload["local_store"] = {
        "enabled": True,
        "store_path": str(store_path),
        "requested_start": requested_start,
        "effective_start": effective_start,
        "overlap_bars": overlap_bars,
        "local_rows_before": local_before,
        "remote_rows": len(rows),
        "merged_total_rows": merge_stats.total,
        "added_rows": merge_stats.added,
        "updated_rows": merge_stats.updated,
        "analysis_rows": len(analysis_rows),
    }
    payload["actual_bar_count"] = len(analysis_rows)
    return analysis_rows, payload


def extract_signals(bis, zhongshus, macd_points, *, raw_bars=None, segments=None) -> dict[str, object]:
    return analyze_chanlun_signals(raw_bars or [], bis, zhongshus, macd_points, segments=segments)


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def _technical_rating(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _technical_bias(conclusion: str | None) -> str | None:
    text = (conclusion or "").strip()
    for prefix in ("偏多", "偏强", "震荡", "偏弱", "偏空"):
        if text.startswith(prefix):
            return prefix
    return text.split("，", 1)[0] if text else None


def _score_structure_component(signals: dict[str, object]) -> int:
    structure_state = signals.get("structure_state") or {}
    ongoing = structure_state.get("current_ongoing") or {}
    ongoing_type = ongoing.get("type")
    score = 10
    if ongoing_type in {"up", "down"}:
        score = 20
    elif ongoing_type == "range":
        score = 14
    if signals.get("current_zs") is not None:
        score += 6
    relationship_kind = ((structure_state.get("relationship") or {}).get("kind") or "").strip()
    if relationship_kind and relationship_kind != "undetermined":
        score += 4
    if signals.get("buy_points") or signals.get("sell_points"):
        score += 2
    return min(score, 30)


def _score_location_component(raw_bars, signals: dict[str, object]) -> int:
    current_zs = signals.get("current_zs")
    close_price = getattr(raw_bars[-1], "close", None) if raw_bars else None
    if current_zs is None or close_price is None:
        return 10
    if signals.get("buy_points"):
        return 18
    if signals.get("sell_points"):
        return 17
    if close_price >= current_zs.zs_high:
        return 15
    if close_price <= current_zs.zs_low:
        return 7
    return 11


def _score_signal_component(signals: dict[str, object]) -> int:
    active_points = [str(point) for point in [*(signals.get("buy_points") or []), *(signals.get("sell_points") or [])]]
    if not active_points:
        return 10
    strength_map = {
        "buy_1": 20,
        "buy_2": 22,
        "buy_3": 18,
        "sell_1": 20,
        "sell_2": 22,
        "sell_3": 18,
    }
    return max(strength_map.get(point, 10) for point in active_points)


def _score_divergence_component(signals: dict[str, object]) -> int:
    divergence = signals.get("divergence") or {}
    if (divergence.get("trend") or {}).get("active"):
        return 15
    if (divergence.get("range") or {}).get("active"):
        return 11
    if (divergence.get("top") or {}).get("active") or (divergence.get("bottom") or {}).get("active"):
        return 8
    return 4


def _score_execution_component(precision_entry: dict[str, object] | None) -> int:
    if not precision_entry:
        return 0
    if precision_entry.get("status") == "actionable":
        return 10
    if precision_entry.get("status") == "watch":
        return 5
    return 3


def build_technical_score_summary(
    raw_bars,
    signals: dict[str, object],
    *,
    conclusion: str | None,
    precision_entry: dict[str, object] | None = None,
) -> dict[str, object]:
    structure = _score_structure_component(signals)
    location = _score_location_component(raw_bars, signals)
    signal = _score_signal_component(signals)
    divergence = _score_divergence_component(signals)
    execution = _score_execution_component(precision_entry)
    score = _clamp_score(structure + location + signal + divergence + execution)
    return {
        "score": score,
        "rating": _technical_rating(score),
        "bias": _technical_bias(conclusion),
        "score_breakdown": {
            "structure": structure,
            "location": location,
            "signal": signal,
            "divergence": divergence,
            "execution": execution,
        },
    }


def build_technical_summary(
    timeframe_label: str,
    signals: dict[str, object],
    advice_text: str,
    *,
    raw_bars=None,
    precision_entry: dict[str, object] | None = None,
) -> dict[str, object]:
    conclusion = _extract_prefixed_value_from_text(advice_text, "结论：") or None
    route_fields = _build_route_level_fields(timeframe_label, signals)
    transition_fields = _extract_transition_state_fields(signals)
    return {
        "operation_level": timeframe_label,
        "conclusion": conclusion,
        "suggestion": _extract_prefixed_value_from_text(advice_text, "建议：") or None,
        **build_technical_score_summary(raw_bars, signals, conclusion=conclusion, precision_entry=precision_entry),
        **build_signal_summary_fields(signals),
        **route_fields,
        **transition_fields,
    }


def _normalize_timeframe_label(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).strip().lower()


def _next_route_level(from_level: str | None) -> str | None:
    mapping = {
        "1m": "5m",
        "5m": "30m",
        "15m": "60m",
        "30m": "day",
        "60m": "day",
    }
    return mapping.get(str(from_level or "").lower())


def _build_route_level_fields(timeframe_label: str, signals: dict[str, object]) -> dict[str, object]:
    route = signals.get("post_divergence_route")
    route_level_from = _normalize_timeframe_label(timeframe_label)
    route_level_to = _next_route_level(route_level_from) if route else None
    return {
        "post_divergence_route": route,
        "route_level_from": route_level_from if route else None,
        "route_level_to": route_level_to,
    }


def _extract_transition_state_fields(signals: dict[str, object]) -> dict[str, str | None]:
    structure_state = signals.get("structure_state") or {}
    relationship = structure_state.get("relationship") or {}
    transition_state = str(relationship.get("transition_state") or "").strip() or None
    if not transition_state:
        return {
            "transition_state": None,
            "transition_state_label": None,
            "transition_state_note": None,
        }
    return {
        "transition_state": transition_state,
        "transition_state_label": format_transition_state_label(transition_state),
        "transition_state_note": describe_transition_state(transition_state) or None,
    }


def _resolve_same_level_consumption_level(signals: dict[str, object]) -> str | None:
    explicit = str(signals.get("same_level_consumption_level") or "").strip()
    if explicit:
        return explicit

    structure_state = signals.get("structure_state") or {}
    structure_explicit = str(structure_state.get("consumption_level") or "").strip()
    if structure_explicit:
        return structure_explicit

    current_ongoing = structure_state.get("current_ongoing") or {}
    confirmation_basis = str(current_ongoing.get("confirmation_basis") or "").strip()
    if confirmation_basis == "no_same_level_zhongshu":
        return "auxiliary"

    current_status = str(structure_state.get("current_structure_status") or "").strip()
    if current_status == "candidate_completed_waiting_stability":
        return "pending"
    if confirmation_basis == "single_active_zhongshu":
        return "pending"

    same_level_decomposition_mode = str(signals.get("same_level_decomposition_mode") or "").strip()
    if same_level_decomposition_mode == "dual_interpretation_pending":
        return "pending"
    if same_level_decomposition_mode == "single_confirmed":
        return "confirmed"
    return None


def build_advice(name: str, timeframe_label: str, raw_bars, signals: dict[str, object]) -> str:
    current_zs = signals.get("current_zs")
    latest_up = signals.get("latest_confirmed_up")
    latest_down = signals.get("latest_down")
    buy_points = signals["buy_points"]
    sell_points = signals["sell_points"]
    top_divergence = signals["top_divergence"]
    bottom_divergence = signals["bottom_divergence"]
    same_level_consumption_level = _resolve_same_level_consumption_level(signals)
    oscillation_rhythm_state = signals.get("oscillation_rhythm_state")
    zs_monitor_alert = signals.get("zs_monitor_alert") or "none"
    zs_monitor_midline = signals.get("zs_monitor_midline")
    zs_monitor_bias = signals.get("zs_monitor_bias")
    transition_fields = _extract_transition_state_fields(signals)
    close_price = raw_bars[-1].close
    signal_explanations = build_signal_explanation_lines(signals)
    buy_labels = "、".join(format_signal_point_labels(buy_points))
    sell_labels = "、".join(format_signal_point_labels(sell_points))
    pending_consumption = same_level_consumption_level == "pending"
    confirmed_consumption = same_level_consumption_level == "confirmed"
    structure_state = signals.get("structure_state") or {}
    current_ongoing = structure_state.get("current_ongoing") or {}
    current_ongoing_type = str(current_ongoing.get("type") or "").strip()
    confirmed_sell3 = confirmed_consumption and "sell_3" in sell_points and current_ongoing_type == "down"
    confirmed_buy3 = confirmed_consumption and "buy_3" in buy_points and current_ongoing_type == "up"

    lines = [f"【{name} {timeframe_label} 操作建议】"]
    if pending_consumption and buy_points:
        signal_text = buy_labels or "买点信号"
        lines.extend(
            [
                "结论：观察，等待确认。",
                f"理由：已出现 {signal_text}，但当前同级别结构仍处待确认消费，不能直接上升为已确认买点。",
                "建议：先按观察态处理，等待离开-回抽或级别闭合后再决定是否升级。",
            ]
        )
    elif pending_consumption and sell_points:
        signal_text = sell_labels or "卖点信号"
        lines.extend(
            [
                "结论：观察，等待确认。",
                f"理由：已出现 {signal_text}，但当前同级别结构仍处待确认消费，不能直接上升为已确认卖点。",
                "建议：先按观察态处理，等待反抽失败或级别闭合后再决定是否升级。",
            ]
        )
    elif pending_consumption and current_zs and latest_down and latest_down.low < current_zs.zs_low:
        lines.extend(
            [
                "结论：观察，等待确认。",
                f"理由：价格已落到最新中枢下沿 {current_zs.zs_low:.2f} 下方，但当前同级别结构仍处待确认消费。",
                f"建议：等待重新站回 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 或后续级别闭合后再判断是否升级。",
            ]
        )
    elif pending_consumption and current_zs and close_price >= current_zs.zs_high:
        lines.extend(
            [
                "结论：观察，等待确认。",
                f"理由：价格运行到中枢上沿 {current_zs.zs_high:.2f} 附近或上方，但当前同级别结构仍处待确认消费。",
                f"建议：先看回试是否回中枢，未完成确认链前不按趋势延续或三买确认处理。",
            ]
        )
    elif confirmed_buy3:
        add_hint = f"{current_zs.zs_high:.2f}" if current_zs else (f"{latest_up.high:.2f}" if latest_up else "最近高点")
        lines.extend(
            [
                "结论：突破中枢并完成回试，当前按三买确认处理。",
                f"理由：出现 {buy_labels}，且当前同级别结构已具备稳定消费基础。",
                f"建议：回试不破 {add_hint} 前以持有或顺势跟踪为主。",
            ]
        )
    elif confirmed_sell3:
        reduce_hint = f"{latest_up.high:.2f}" if latest_up else "最近高点"
        lines.extend(
            [
                "结论：跌破中枢后反抽下沿失败，当前按三卖确认处理。",
                f"理由：出现 {sell_labels}，且当前同级别结构已具备稳定消费基础。",
                f"建议：反抽不过 {reduce_hint} 以减仓为主，不逆势加仓。",
            ]
        )
    elif buy_points:
        stop_hint = f"{latest_down.low:.2f}" if latest_down else "最近低点"
        lines.extend(
            [
                "结论：偏多，允许轻仓试错。",
                f"理由：出现 {buy_labels}，结构上已有缠论买点雏形。",
                f"建议：分批试仓，跌破 {stop_hint} 则严格止损。",
            ]
        )
    elif sell_points:
        reduce_hint = f"{latest_up.high:.2f}" if latest_up else "最近高点"
        lines.extend(
            [
                "结论：偏空，优先减仓或兑现。",
                f"理由：出现 {sell_labels}，结构偏向卖点。",
                f"建议：反抽不过 {reduce_hint} 以减仓为主，不逆势加仓。",
            ]
        )
    elif current_zs and latest_down and latest_down.low < current_zs.zs_low:
        lines.extend(
            [
                "结论：偏弱，先观望。",
                f"理由：价格仍在最新中枢下沿 {current_zs.zs_low:.2f} 下方。",
                f"建议：等待重新站回 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 再考虑参与，未站回前不追。",
            ]
        )
    elif current_zs and close_price >= current_zs.zs_high:
        lines.extend(
            [
                "结论：偏强，持有为主。",
                f"理由：价格运行在中枢上沿 {current_zs.zs_high:.2f} 附近或上方。",
                f"建议：已有仓位可继续持有，回踩不破 {current_zs.zs_high:.2f} 再考虑加仓。",
            ]
        )
    elif zs_monitor_alert == "pre_breakout":
        bias_text = {"strong": "节奏偏强", "weak": "节奏偏弱", "neutral": "节奏中性"}.get(str(zs_monitor_bias), "节奏中性")
        midline_text = f"，中枢中线 {float(zs_monitor_midline):.2f}" if zs_monitor_midline is not None else ""
        price_anchor = f"{current_zs.zs_high:.2f}" if current_zs else "最新中枢上沿"
        lines.extend(
            [
                "结论：出现向上预警，但当前不构成确认三买。",
                f"理由：价格贴近{price_anchor}{midline_text}，{bias_text}。",
                "建议：继续观察首次回试是否回中枢，未完成离开-回试确认链前不升级为三买。",
            ]
        )
    elif zs_monitor_alert == "pre_breakdown":
        bias_text = {"strong": "节奏偏强", "weak": "节奏偏弱", "neutral": "节奏中性"}.get(str(zs_monitor_bias), "节奏中性")
        midline_text = f"，中枢中线 {float(zs_monitor_midline):.2f}" if zs_monitor_midline is not None else ""
        price_anchor = f"{current_zs.zs_low:.2f}" if current_zs else "最新中枢下沿"
        lines.extend(
            [
                "结论：出现向下预警，但当前不构成确认三卖。",
                f"理由：价格贴近{price_anchor}{midline_text}，{bias_text}。",
                "建议：继续观察首次回抽是否回中枢，未完成离开-回抽确认链前不升级为三卖。",
            ]
        )
    elif current_zs:
        lines.extend(
            [
                "结论：震荡，等待方向选择。",
                f"理由：当前主要围绕中枢 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 波动。",
                "建议：中枢内少折腾，等向上离开或向下跌破后再做决策。",
            ]
        )
    else:
        lines.extend(
            [
                "结论：信号一般，保持耐心。",
                "理由：当前尚未形成清晰中枢和明确买卖点。",
                "建议：只做跟踪，不做主观重仓下注。",
            ]
        )

    if current_zs:
        lines.append(f"结构说明：{format_zhongshu_structure_text(current_zs)}。")
    if zs_monitor_midline is not None or zs_monitor_bias:
        bias_text = {"strong": "偏强", "weak": "偏弱", "neutral": "中性"}.get(str(zs_monitor_bias), str(zs_monitor_bias or ""))
        alert_text = {
            "pre_breakout": "向上预警",
            "pre_breakdown": "向下预警",
            "none": "无预警",
        }.get(str(zs_monitor_alert), str(zs_monitor_alert))
        midline_text = f"{float(zs_monitor_midline):.2f}" if zs_monitor_midline is not None else "未知"
        lines.append(f"监视器：中枢中线 {midline_text}，当前{bias_text}，预警状态 {alert_text}。")
    if signal_explanations:
        lines.append(f"信号说明：{'；'.join(signal_explanations)}。")
    if pending_consumption:
        consumption_label = format_consumption_level_label(same_level_consumption_level)
        consumption_note = describe_consumption_level(same_level_consumption_level)
        lines.append(
            f"消费说明：当前同级别结构处于 {consumption_label}，{consumption_note or '所有高层结论统一按观察/等待确认处理。'}"
        )
    if transition_fields["transition_state"] and transition_fields["transition_state"] != "none":
        transition_summary = f"转场说明：{transition_fields['transition_state_label']}"
        if transition_fields["transition_state_note"]:
            transition_summary = f"{transition_summary}，{transition_fields['transition_state_note']}"
        lines.append(f"{transition_summary}。")
    rhythm_text = {
        "up_bias": "节奏偏强",
        "down_bias": "节奏偏弱",
        "balanced": "节奏平衡",
        "pending": "节奏待判定",
    }.get(str(oscillation_rhythm_state or "").strip())
    if rhythm_text:
        lines.append(f"节奏监视：{rhythm_text}，当前只作辅助观察，不单独升级主结论。")

    if bottom_divergence and not buy_points:
        lines.append("补充：已有底背驰迹象，但买点尚未确认，最多列入观察名单。")
    if top_divergence and not sell_points:
        lines.append("补充：已有顶背驰迹象，若后续反弹无力，应优先考虑保护利润。")
    if timeframe_label == "30M":
        lines.append("次级别说明：5M 主要用于区间套趋势背驰定位更精确的买卖点，同时承担日内短线做T节奏。")
    lines.append("说明：以上仅基于缠论结构与 MACD 强弱，不构成投资建议。")
    return "\n".join(lines)


def export_case(
    security: Security,
    timeframe: str,
    rows: list[dict],
    title: str,
    data_fetch: dict[str, object] | None = None,
    pending_reverse_mode: str = "effective_only",
    zhongshu_level: str = "segment",
    export_structure_images: bool = True,
) -> dict[str, Path]:
    layout = timeframe_report_paths(security.symbol, timeframe, rows)
    raw_csv = layout.raw_csv
    normalized_csv = layout.normalized_csv
    svg = layout.chart_svg
    png = layout.chart_png
    jpg = layout.chart_jpg
    analysis_path = layout.root_dir / "analysis.txt"
    advice_path = layout.root_dir / "advice.txt"
    report_path = layout.root_dir / "report.txt"
    tech_json_path = layout.technical_report_json
    save_rows(security, timeframe, rows, raw_csv)
    raw_bars = clean_bars(read_bars_from_csv(str(raw_csv)))
    normalized_bars = normalize_bars(raw_bars)
    write_normalized_csv(normalized_csv, normalized_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(
        fractals,
        normalized_bars,
        pending_reverse_mode=pending_reverse_mode,
    )
    segment_bootstrap_mode = "first_valid_seed" if timeframe == "1m" else "prefer_earlier_start"
    segments = identify_segments(
        bis,
        bootstrap_mode=segment_bootstrap_mode,
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=True,
    )
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    # Segment zhongshu should be built on the full segment chain so an ongoing tail
    # does not force a fallback to bi-level primary output.
    segment_zhongshus = identify_zhongshu(segments, structure_level="segment")
    lei_zhongshus = identify_zhongshu(confirmed_bis, structure_level="bi")
    # Enforce segment as the only primary zhongshu layer across all symbols/timeframes.
    zhongshus = segment_zhongshus
    auxiliary_zhongshus = lei_zhongshus
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)
    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    export_fractals(layout.fractals_csv, normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(layout.confirmed_fractals_csv, normalized_bars, fractals, confirmed_fx_ids)
    export_bis(layout.bis_csv, bis)
    export_segments(layout.segments_csv, segments)
    export_zhongshus(layout.zhongshu_csv, zhongshus)
    lei_zhongshu_csv = layout.zhongshu_csv.with_name(f"{layout.zhongshu_csv.stem}_lei.csv")
    export_zhongshus(lei_zhongshu_csv, lei_zhongshus)
    export_macd(layout.macd_csv, macd_points)
    if export_structure_images:
        save_structure_charts(
            bars=raw_bars,
            normalized_bars=normalized_bars,
            fractals=fractals,
            bis=bis,
            zhongshus=zhongshus,
            lei_zhongshus=auxiliary_zhongshus,
            svg_path=svg,
            png_path=png,
            jpg_path=jpg,
            title=title,
            bootstrap_mode=segment_bootstrap_mode,
            bootstrap_skip_confirmed_bis=0,
            strict_segment_rules=True,
        )

    analysis_text = analyze_current_state(security.name, raw_bars, bis, zhongshus, macd_points, segments=segments)
    timeframe_label = timeframe_display_label(timeframe)
    if timeframe != "60m":
        analysis_text = analysis_text.replace("60M", timeframe_label)
    signals = extract_signals(bis, zhongshus, macd_points, raw_bars=raw_bars, segments=segments)
    advice_text = build_advice(security.name, timeframe_label, raw_bars, signals)
    summary_payload = build_technical_summary(
        timeframe_label,
        signals,
        advice_text,
        raw_bars=raw_bars,
    )
    report_text = analysis_text + "\n\n" + advice_text + "\n"
    latest_zhongshu = serialize_zhongshu(zhongshus[-1]) if zhongshus else None
    latest_lei_zhongshu = serialize_zhongshu(lei_zhongshus[-1]) if lei_zhongshus else None

    analysis_path.write_text(analysis_text + "\n", encoding="utf-8")
    advice_path.write_text(advice_text + "\n", encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    write_json(
        tech_json_path,
        {
            "report_type": "technical",
            "symbol": security.symbol,
            "name": security.name,
            "timeframe": timeframe,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": (data_fetch or {}).get("source"),
            "data_fetch": data_fetch,
            "pending_reverse_mode": pending_reverse_mode,
            "zhongshu_level": "segment",
            "code_fingerprint": compute_tech_report_fingerprint(),
            "structure": {
                "primary_zhongshu_level": "segment",
                "latest_zhongshu": latest_zhongshu,
                "zhongshus": serialize_zhongshus(zhongshus),
                "latest_lei_zhongshu": latest_lei_zhongshu,
                "lei_zhongshus": serialize_zhongshus(lei_zhongshus),
            },
            "structure_state": signals.get("structure_state"),
            "same_level_decomposition_mode": signals.get("same_level_decomposition_mode"),
            "same_level_consumption_level": signals.get("same_level_consumption_level"),
            "post_divergence_route": signals.get("post_divergence_route"),
            "route_level_from": timeframe,
            "route_level_to": _next_route_level(timeframe) if signals.get("post_divergence_route") else None,
            "divergence": signals.get("divergence"),
            "zs_monitor_alert": signals.get("zs_monitor_alert", "none"),
            "zs_monitor_midline": signals.get("zs_monitor_midline"),
            "zs_monitor_bias": signals.get("zs_monitor_bias"),
            "summary": summary_payload,
            "analysis_text": analysis_text,
            "advice_text": advice_text,
            "artifacts": {
                "raw_csv": raw_csv,
                "normalized_csv": normalized_csv,
                "fractals_csv": layout.fractals_csv,
                "confirmed_fractals_csv": layout.confirmed_fractals_csv,
                "bis_csv": layout.bis_csv,
                "segments_csv": layout.segments_csv,
                "zhongshu_csv": layout.zhongshu_csv,
                "lei_zhongshu_csv": lei_zhongshu_csv,
                "macd_csv": layout.macd_csv,
                "structure_svg": svg,
                "structure_png": png,
                "structure_jpg": jpg,
                "report_txt": report_path,
            },
        },
    )
    prune_analyze_csv_families(raw_csv)
    return {
        "analysis": analysis_path,
        "advice": advice_path,
        "report": report_path,
        "tech_json": tech_json_path,
        "jpg": jpg,
        "png": png,
        "svg": svg,
    }


def build_send_text(security: Security, day_report: Path, m60_report: Path) -> str:
    return (
        f"【{security.name} {security.symbol}】\n\n"
        f"{day_report.read_text(encoding='utf-8').strip()}\n\n"
        f"{m60_report.read_text(encoding='utf-8').strip()}"
    )


def build_send_text_60m_only(security: Security, m60_report: Path) -> str:
    return f"【{security.name} {security.symbol} 60M】\n\n{m60_report.read_text(encoding='utf-8').strip()}"


def _extract_prefixed_value_from_text(text: str, prefix: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _extract_summary_line(advice_path: Path, prefix: str) -> str:
    for raw_line in advice_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def build_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> str:
    lines = [
        "【全部持仓 60M 缠论综合操作建议】",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"覆盖数量：{len(bundle)} 只持仓",
        "",
        "逐只建议：",
    ]

    bullish: list[str] = []
    neutral: list[str] = []
    bearish: list[str] = []

    for security, _day_case, m60_case in bundle:
        conclusion = _extract_summary_line(m60_case["advice"], "结论：") or "信号一般，保持耐心。"
        suggestion = _extract_summary_line(m60_case["advice"], "建议：") or "继续跟踪后续一笔与中枢突破。"
        lines.append(f"- {security.name}({security.symbol})：{conclusion} 建议：{suggestion}")

        if any(keyword in conclusion for keyword in ("偏多", "偏强", "持有为主", "允许轻仓试错")):
            bullish.append(f"{security.name}({security.symbol})")
        elif any(keyword in conclusion for keyword in ("偏空", "偏弱", "减仓", "兑现")):
            bearish.append(f"{security.name}({security.symbol})")
        else:
            neutral.append(f"{security.name}({security.symbol})")

    lines.extend(
        [
            "",
            "组合层结论：",
            f"- 偏强观察组：{'、'.join(bullish) if bullish else '无'}",
            f"- 震荡观察组：{'、'.join(neutral) if neutral else '无'}",
            f"- 风险控制组：{'、'.join(bearish) if bearish else '无'}",
            "- 操作原则：60M 只用于节奏和仓位管理，真正加减仓以中枢突破/跌破后的确认笔为准。",
            "- 说明：以上仅基于最新 60M 缠论结构与 MACD 强弱，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> Path:
    file_prefix = "group888_60m_operation_summary_"
    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_META_DIR / f"{file_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_path.write_text(build_group_operation_summary(bundle), encoding="utf-8")
    prune_older_outputs(output_path.parent, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path


def load_existing_case(security: Security, timeframe: str) -> dict[str, Path]:
    base_dir = REPORTS_DIR / security.symbol / timeframe
    if (base_dir / "report.txt").exists():
        return {
            "report": base_dir / "report.txt",
            "analysis": base_dir / "analysis.txt",
            "advice": base_dir / "advice.txt",
            "tech_json": base_dir / "tech.json",
            "jpg": base_dir / "structure.jpg",
            "png": base_dir / "structure.png",
            "svg": base_dir / "structure.svg",
        }
    raise FileNotFoundError(f"未找到规范技术报告目录: {base_dir}")


def _reuse_existing_hk_5m_case(
    security: Security,
    rows: list[dict],
    *,
    pending_reverse_mode: str,
    zhongshu_level: str,
) -> dict[str, Path] | None:
    if security.market != "HK" or pending_reverse_mode not in {"any", "effective_only"}:
        return None

    layout = timeframe_report_paths(security.symbol, "5m", rows)
    required_paths = [
        layout.raw_csv,
        layout.normalized_csv,
        layout.fractals_csv,
        layout.confirmed_fractals_csv,
        layout.bis_csv,
        layout.segments_csv,
        layout.zhongshu_csv,
        layout.macd_csv,
        layout.chart_svg,
        layout.chart_png,
        layout.chart_jpg,
        layout.technical_report_json,
        layout.root_dir / "analysis.txt",
        layout.root_dir / "advice.txt",
        layout.root_dir / "report.txt",
    ]
    if any(not path.exists() for path in required_paths):
        return None

    payload = json.loads(layout.technical_report_json.read_text(encoding="utf-8"))
    if payload.get("timeframe") != "5m":
        return None
    if payload.get("pending_reverse_mode") != "effective_only":
        return None
    if str(payload.get("zhongshu_level") or "segment") != zhongshu_level:
        return None
    if str(payload.get("code_fingerprint") or "") != compute_tech_report_fingerprint():
        return None

    data_fetch = payload.get("data_fetch") or {}
    if int(data_fetch.get("actual_bar_count") or 0) < len(rows):
        return None

    return load_existing_case(security, "5m")


def _raw_csv_matches_rows(path: Path, rows: list[dict]) -> bool:
    if not rows or not path.exists():
        return False

    first_ts = str(rows[0].get("ts") or "")
    last_ts = str(rows[-1].get("ts") or "")
    actual_first = ""
    actual_last = ""
    actual_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            ts = str(record.get("ts") or "")
            if actual_count == 0:
                actual_first = ts
            actual_last = ts
            actual_count += 1
    return actual_count == len(rows) and actual_first == first_ts and actual_last == last_ts


def _reuse_existing_exact_case(
    security: Security,
    timeframe: str,
    rows: list[dict],
    *,
    pending_reverse_mode: str,
    zhongshu_level: str,
) -> dict[str, Path] | None:
    layout = timeframe_report_paths(security.symbol, timeframe, rows)
    required_paths = [
        layout.raw_csv,
        layout.normalized_csv,
        layout.fractals_csv,
        layout.confirmed_fractals_csv,
        layout.bis_csv,
        layout.segments_csv,
        layout.zhongshu_csv,
        layout.macd_csv,
        layout.chart_svg,
        layout.chart_png,
        layout.chart_jpg,
        layout.technical_report_json,
        layout.root_dir / "analysis.txt",
        layout.root_dir / "advice.txt",
        layout.root_dir / "report.txt",
    ]
    if any(not path.exists() for path in required_paths):
        return None

    payload = json.loads(layout.technical_report_json.read_text(encoding="utf-8"))
    if payload.get("timeframe") != timeframe:
        return None
    if str(payload.get("pending_reverse_mode") or "") != pending_reverse_mode:
        return None
    if str(payload.get("zhongshu_level") or "segment") != zhongshu_level:
        return None
    if str(payload.get("code_fingerprint") or "") != compute_tech_report_fingerprint():
        return None

    data_fetch = payload.get("data_fetch") or {}
    if int(data_fetch.get("actual_bar_count") or 0) != len(rows):
        return None
    if not _raw_csv_matches_rows(layout.raw_csv, rows):
        return None

    return load_existing_case(security, timeframe)


def _prepare_security_result(
    security: Security,
    *,
    selected_timeframes: tuple[str, ...],
    resolved_day_start: str,
    day_bars: int,
    resolved_m60_start: str,
    m60_bars: int,
    resolved_m30_start: str,
    m30_bars: int,
    resolved_m15_start: str,
    m15_bars: int,
    resolved_m5_start: str,
    m5_bars: int,
    resolved_m1_start: str,
    m1_bars: int,
    pending_reverse_mode: str,
    zhongshu_level: str,
    use_local_store: bool,
    local_store_read_only: bool,
    incremental_overlap_bars: int,
    local_store_root: Path | None,
    export_structure_images: bool,
    force_regenerate: bool = False,
) -> PreparedSecurityResult:
    day_case: dict[str, Path] = {}
    m60_case: dict[str, Path] = {}
    timeframe_diagnostics: list[dict[str, object]] = []

    if "day" in selected_timeframes:
        started = time.perf_counter()
        day_rows, day_fetch = _fetch_with_optional_local_store(
            security,
            timeframe="day",
            requested_start=resolved_day_start,
            bar_count=day_bars,
            overlap_bars=incremental_overlap_bars,
            use_local_store=use_local_store,
            local_store_read_only=local_store_read_only,
            local_store_root=local_store_root,
            remote_fetcher=lambda start, _min_rows: fetch_day_rows(security, start, day_bars),
        )
        day_case = export_case(
            security,
            "day",
            day_rows,
            f"{security.symbol} {security.name} day",
            data_fetch=day_fetch,
            pending_reverse_mode=pending_reverse_mode,
            zhongshu_level=zhongshu_level,
            export_structure_images=export_structure_images,
        )
        timeframe_diagnostics.append(
            _build_timeframe_diagnostic(
                security,
                "day",
                day_rows,
                day_fetch,
                day_case,
                requested_start=resolved_day_start,
                bar_count=day_bars,
                reused_existing_case=False,
            )
        )
        print(f"timing {security.symbol} day seconds={time.perf_counter() - started:.2f}", flush=True)

    timeframe_specs = {
        "60m": ("60", resolved_m60_start, m60_bars),
        "30m": ("30", resolved_m30_start, m30_bars),
        "15m": ("15", resolved_m15_start, m15_bars),
        "5m": ("5", resolved_m5_start, m5_bars),
        "1m": ("1", resolved_m1_start, m1_bars),
    }
    for timeframe in ("60m", "30m", "15m", "5m", "1m"):
        if timeframe not in selected_timeframes:
            continue
        period, start, bar_count = timeframe_specs[timeframe]
        started = time.perf_counter()
        if timeframe == "60m":
            remote_fetcher = lambda effective_start, min_rows: fetch_m60_rows(
                security,
                effective_start,
                bar_count,
            )
        elif timeframe == "15m":
            remote_fetcher = lambda effective_start, min_rows: fetch_m15_rows(
                security,
                effective_start,
                bar_count,
            )
        else:
            remote_fetcher = lambda effective_start, min_rows: fetch_intraday_rows(
                security,
                timeframe=timeframe,
                period=period,
                start=effective_start,
                bar_count=bar_count,
                source_probe_min_rows=min_rows,
            )
        rows, fetch_meta = _fetch_with_optional_local_store(
            security,
            timeframe=timeframe,
            requested_start=start,
            bar_count=bar_count,
            overlap_bars=incremental_overlap_bars,
            use_local_store=use_local_store,
            local_store_read_only=local_store_read_only,
            local_store_root=local_store_root,
            remote_fetcher=remote_fetcher,
        )
        exported = None
        reused_existing_case = False
        if timeframe == "5m" and not force_regenerate:
            exported = _reuse_existing_hk_5m_case(
                security,
                rows,
                pending_reverse_mode=pending_reverse_mode,
                zhongshu_level=zhongshu_level,
            )
            if exported is not None:
                reused_existing_case = True
                print(f"reuse {security.symbol} 5m existing_effective_only_case", flush=True)
        if exported is None and timeframe in {"5m", "1m"} and not force_regenerate:
            exported = _reuse_existing_exact_case(
                security,
                timeframe,
                rows,
                pending_reverse_mode=pending_reverse_mode,
                zhongshu_level=zhongshu_level,
            )
            if exported is not None:
                reused_existing_case = True
                print(f"reuse {security.symbol} {timeframe} existing_exact_case", flush=True)
        if exported is None:
            exported = export_case(
                security,
                timeframe,
                rows,
                f"{security.symbol} {security.name} {timeframe}",
                data_fetch=fetch_meta,
                pending_reverse_mode=pending_reverse_mode,
                zhongshu_level=zhongshu_level,
                export_structure_images=export_structure_images,
            )
        timeframe_diagnostics.append(
            _build_timeframe_diagnostic(
                security,
                timeframe,
                rows,
                fetch_meta,
                exported,
                requested_start=start,
                bar_count=bar_count,
                reused_existing_case=reused_existing_case,
            )
        )
        if timeframe == "60m":
            m60_case = exported
        print(f"timing {security.symbol} {timeframe} seconds={time.perf_counter() - started:.2f}", flush=True)

    print(f"Prepared {security.name}")
    return PreparedSecurityResult(security=security, day_case=day_case, m60_case=m60_case, timeframe_diagnostics=timeframe_diagnostics)


def run_batch_prepare(
    *,
    holdings_path: Path | None = None,
    day_start: str | None = None,
    day_bars: int = 1200,
    m60_start: str | None = None,
    m60_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m30_start: str | None = None,
    m30_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m15_start: str | None = None,
    m15_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m5_start: str | None = None,
    m5_bars: int = 2000,
    m1_start: str | None = None,
    m1_bars: int = M1_BAR_DEFAULT,
    pending_reverse_mode: str = "effective_only",
    zhongshu_level: str = "segment",
    timeframes: tuple[str, ...] = ("day", "30m", "5m", "1m"),
    use_local_store: bool = True,
    local_store_read_only: bool = False,
    incremental_overlap_bars: int = 120,
    local_store_root: Path | None = None,
    export_structure_images: bool = True,
    force_regenerate: bool = False,
    parallelism: int = min(4, max(1, os.cpu_count() or 1)),
) -> BatchPrepareResult:
    local_store_read_only = False
    selected_timeframes = tuple(dict.fromkeys(timeframes))
    resolved_day_start = day_start or default_day_start_for_bar_target(day_bars)
    resolved_m60_start = m60_start or default_intraday_start_for_bar_target("60m", m60_bars)
    resolved_m30_start = m30_start or default_intraday_start_for_bar_target("30m", m30_bars)
    resolved_m15_start = m15_start or default_intraday_start_for_bar_target("15m", m15_bars)
    resolved_m5_start = m5_start or default_intraday_start_for_bar_target("5m", m5_bars)
    resolved_m1_start = m1_start or default_intraday_start_for_bar_target("1m", m1_bars)
    securities = load_securities(holdings_path or DEFAULT_HOLDINGS_FILE)
    worker_count = max(1, min(parallelism, len(securities)))
    bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]] = []
    ordered_results: list[PreparedSecurityResult | None] = [None] * len(securities)
    if worker_count == 1:
        for index, security in enumerate(securities):
            ordered_results[index] = _prepare_security_result(
                security,
                selected_timeframes=selected_timeframes,
                resolved_day_start=resolved_day_start,
                day_bars=day_bars,
                resolved_m60_start=resolved_m60_start,
                m60_bars=m60_bars,
                resolved_m30_start=resolved_m30_start,
                m30_bars=m30_bars,
                resolved_m15_start=resolved_m15_start,
                m15_bars=m15_bars,
                resolved_m5_start=resolved_m5_start,
                m5_bars=m5_bars,
                resolved_m1_start=resolved_m1_start,
                m1_bars=m1_bars,
                pending_reverse_mode=pending_reverse_mode,
                zhongshu_level=zhongshu_level,
                use_local_store=use_local_store,
                local_store_read_only=local_store_read_only,
                incremental_overlap_bars=incremental_overlap_bars,
                local_store_root=local_store_root,
                export_structure_images=export_structure_images,
                force_regenerate=force_regenerate,
            )
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _prepare_security_result,
                    security,
                    selected_timeframes=selected_timeframes,
                    resolved_day_start=resolved_day_start,
                    day_bars=day_bars,
                    resolved_m60_start=resolved_m60_start,
                    m60_bars=m60_bars,
                    resolved_m30_start=resolved_m30_start,
                    m30_bars=m30_bars,
                    resolved_m15_start=resolved_m15_start,
                    m15_bars=m15_bars,
                    resolved_m5_start=resolved_m5_start,
                    m5_bars=m5_bars,
                    resolved_m1_start=resolved_m1_start,
                    m1_bars=m1_bars,
                    pending_reverse_mode=pending_reverse_mode,
                    zhongshu_level=zhongshu_level,
                    use_local_store=use_local_store,
                    local_store_read_only=local_store_read_only,
                    incremental_overlap_bars=incremental_overlap_bars,
                    local_store_root=local_store_root,
                    export_structure_images=export_structure_images,
                    force_regenerate=force_regenerate,
                ): index
                for index, security in enumerate(securities)
            }
            for future in as_completed(futures):
                ordered_results[futures[future]] = future.result()

    for prepared in ordered_results:
        if prepared is None:
            continue
        if prepared.m60_case:
            bundle.append((prepared.security, prepared.day_case, prepared.m60_case))

    timeframe_diagnostics = [
        diagnostic
        for prepared in ordered_results
        if prepared is not None
        for diagnostic in prepared.timeframe_diagnostics
    ]

    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    manifest = REPORTS_META_DIR / f"group888_generation_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    lines = ["group888 生成清单", ""]
    for security, day_case, m60_case in bundle:
        lines.append(f"{security.name} ({security.symbol})")
        lines.append(f"- 60M 报告: {m60_case['report']}")
        lines.append(f"- 60M 图片: {m60_case['jpg']}")
        lines.append("")
    manifest.write_text("\n".join(lines), encoding="utf-8")
    print(f"Manifest: {manifest}")

    summary_path: Path | None = None
    if bundle:
        summary_path = write_group_operation_summary(bundle)
        print(f"Summary: {summary_path}")

    return BatchPrepareResult(
        security_count=len(securities),
        selected_timeframes=selected_timeframes,
        manifest_path=manifest,
        summary_path=summary_path,
        timeframe_diagnostics=timeframe_diagnostics,
    )


def main() -> None:
    args = parse_args()
    run_batch_prepare(
        holdings_path=Path(args.holdings_file) if args.holdings_file else None,
        day_start=args.day_start,
        day_bars=args.day_bars,
        m60_start=args.m60_start,
        m60_bars=args.m60_bars,
        m30_start=args.m30_start,
        m30_bars=args.m30_bars,
        m15_start=args.m15_start,
        m15_bars=args.m15_bars,
        m5_start=args.m5_start,
        m5_bars=args.m5_bars,
        m1_start=args.m1_start,
        m1_bars=args.m1_bars,
        pending_reverse_mode=args.pending_reverse_mode,
        zhongshu_level=args.zhongshu_level,
        timeframes=tuple(args.timeframes),
        use_local_store=args.use_local_store,
        local_store_read_only=args.local_store_read_only,
        incremental_overlap_bars=args.incremental_overlap_bars,
        local_store_root=Path(args.local_store_root) if args.local_store_root else None,
        export_structure_images=bool(args.export_structure_images),
        force_regenerate=args.force_regenerate,
        parallelism=args.parallelism,
    )


if __name__ == "__main__":
    main()