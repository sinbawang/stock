from __future__ import annotations

import importlib
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
import storage_layout
import run_cn_60m_chanlun_report as cn_module
import run_hk_60m_chanlun_report as hk_module


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


def test_holdings_file_falls_back_to_config_when_data_file_missing(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    fallback = config_dir / "stock_holdings.json"
    fallback.write_text('{"markets": {"CN": [], "HK": []}}', encoding="utf-8")

    monkeypatch.setattr(storage_layout, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage_layout, "CONFIG_DIR", config_dir)

    assert storage_layout.holdings_file() == fallback


def test_kline_cache_dir_honors_local_store_root_env(monkeypatch) -> None:
    override_dir = ROOT / "build" / "persistent-cache"
    monkeypatch.setenv("STOCK_LOCAL_STORE_ROOT", str(override_dir))
    monkeypatch.delenv("STOCK_KLINE_CACHE_DIR", raising=False)

    import storage_layout

    reloaded = importlib.reload(storage_layout)

    assert reloaded.KLINE_CACHE_DIR == override_dir


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