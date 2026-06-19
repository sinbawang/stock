from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from storage_layout import REPORTS_DIR, holdings_file, timeframe_report_paths
import run_cn_60m_chanlun_to_wechat as cn_module
import run_hk_60m_chanlun_to_wechat as hk_module


def _bars() -> list[dict]:
    return [
        {"ts": "2026-05-01 10:30:00"},
        {"ts": "2026-05-29 14:30:00"},
    ]


def test_timeframe_report_paths_uses_reports_symbol_timeframe_layout() -> None:
    paths = timeframe_report_paths("601328", "60m", _bars())

    assert paths.root_dir == REPORTS_DIR / "601328" / "60m"
    assert paths.analyze_dir == REPORTS_DIR / "601328" / "60m" / "analyze"
    assert paths.raw_csv == paths.analyze_dir / "601328_60m_20260501_to_20260529.csv"
    assert paths.normalized_csv == paths.analyze_dir / "601328_60m_20260501_to_20260529_normalized.csv"
    assert paths.segments_csv == paths.analyze_dir / "601328_60m_20260501_to_20260529_normalized_segments.csv"
    assert paths.chart_svg == paths.root_dir / "structure.svg"
    assert paths.technical_report_json == paths.root_dir / "tech.json"


def test_holdings_file_points_to_canonical_stock_holdings_json() -> None:
    assert holdings_file() == ROOT / "data" / "stock_holdings.json"


def test_cn_build_paths_routes_analysis_outputs_under_analyze_dir() -> None:
    paths = cn_module.build_paths("601328", "交通银行", _bars())

    assert paths["base_dir"] == REPORTS_DIR / "601328" / "60m"
    assert paths["raw_csv"].parent == REPORTS_DIR / "601328" / "60m" / "analyze"
    assert paths["fractals_csv"].parent == REPORTS_DIR / "601328" / "60m" / "analyze"
    assert paths["segments_csv"].parent == REPORTS_DIR / "601328" / "60m" / "analyze"
    assert paths["svg"] == REPORTS_DIR / "601328" / "60m" / "structure.svg"


def test_hk_build_paths_routes_analysis_outputs_under_analyze_dir() -> None:
    paths = hk_module.build_paths("00700", "腾讯", _bars())

    assert paths["base_dir"] == REPORTS_DIR / "00700" / "60m"
    assert paths["raw_csv"].parent == REPORTS_DIR / "00700" / "60m" / "analyze"
    assert paths["macd_csv"].parent == REPORTS_DIR / "00700" / "60m" / "analyze"
    assert paths["segments_csv"].parent == REPORTS_DIR / "00700" / "60m" / "analyze"
    assert paths["jpg"] == REPORTS_DIR / "00700" / "60m" / "structure.jpg"