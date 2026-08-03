from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_META_DIR = REPORTS_DIR / "_meta"
DATA_META_DIR = DATA_DIR / "_meta"


def _resolve_kline_cache_dir() -> Path:
    for env_key in ("STOCK_LOCAL_STORE_ROOT", "STOCK_KLINE_CACHE_DIR"):
        candidate = os.getenv(env_key, "").strip()
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return path
    return DATA_DIR / "cache" / "kline"


KLINE_CACHE_DIR = _resolve_kline_cache_dir()
HOLDINGS_FILE = CONFIG_DIR / "stock_holdings.json"
CAPITAL_FLOW_CACHE_DIR = DATA_META_DIR / "capital_flow_cache"


def holdings_file() -> Path:
    preferred = DATA_DIR / "stock_holdings.json"
    fallback = CONFIG_DIR / "stock_holdings.json"
    if preferred.exists():
        return preferred
    if fallback.exists():
        return fallback
    return preferred


def ensure_reports_meta_dir() -> Path:
    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_META_DIR


def stock_report_dir(symbol: str) -> Path:
    path = REPORTS_DIR / symbol.strip()
    path.mkdir(parents=True, exist_ok=True)
    return path


def stock_base_report_path(symbol: str) -> Path:
    return stock_report_dir(symbol) / "base.json"


def stock_fund_report_path(symbol: str) -> Path:
    return stock_report_dir(symbol) / "fund.json"


def stock_overview_report_path(symbol: str) -> Path:
    return stock_report_dir(symbol) / "overview.txt"


@dataclass(frozen=True)
class TimeframeReportPaths:
    root_dir: Path
    analyze_dir: Path
    raw_csv: Path
    normalized_csv: Path
    fractals_csv: Path
    confirmed_fractals_csv: Path
    bis_csv: Path
    segments_csv: Path
    zhongshu_csv: Path
    macd_csv: Path
    chart_svg: Path
    chart_png: Path
    chart_jpg: Path
    technical_report_json: Path
    stem: str


def timeframe_report_paths(
    symbol: str,
    timeframe: str,
    bars: list[dict],
    stock_root: Optional[Path] = None,
) -> TimeframeReportPaths:
    normalized_symbol = symbol.strip()
    normalized_timeframe = timeframe.strip().lower()
    first_day = str(bars[0]["ts"])[0:10].replace("-", "")
    last_day = str(bars[-1]["ts"])[0:10].replace("-", "")
    base_root = stock_root if stock_root is not None else stock_report_dir(normalized_symbol)
    root_dir = base_root / normalized_timeframe
    analyze_dir = root_dir / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{normalized_symbol}_{normalized_timeframe}_{first_day}_to_{last_day}"
    chart_svg = root_dir / "structure.svg"
    chart_png = root_dir / "structure.png"
    chart_jpg = root_dir / "structure.jpg"
    technical_report_json = root_dir / "tech.json"

    return TimeframeReportPaths(
        root_dir=root_dir,
        analyze_dir=analyze_dir,
        raw_csv=analyze_dir / f"{stem}.csv",
        normalized_csv=analyze_dir / f"{stem}_normalized.csv",
        fractals_csv=analyze_dir / f"{stem}_normalized_fractals.csv",
        confirmed_fractals_csv=analyze_dir / f"{stem}_normalized_confirmed_fractals.csv",
        bis_csv=analyze_dir / f"{stem}_normalized_bis.csv",
        segments_csv=analyze_dir / f"{stem}_normalized_segments.csv",
        zhongshu_csv=analyze_dir / f"{stem}_normalized_zhongshu.csv",
        macd_csv=analyze_dir / f"{stem}_normalized_macd.csv",
        chart_svg=chart_svg,
        chart_png=chart_png,
        chart_jpg=chart_jpg,
        technical_report_json=technical_report_json,
        stem=stem,
    )