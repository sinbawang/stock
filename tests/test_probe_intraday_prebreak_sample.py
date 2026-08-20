from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build" / "probe_intraday_prebreak_sample.py"

spec = importlib.util.spec_from_file_location("probe_intraday_prebreak_sample", MODULE_PATH)
assert spec is not None and spec.loader is not None
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


def test_select_auto_cutoffs_filters_duplicates_and_time_window() -> None:
    rows = [
        {"ts": "2026-08-01 09:31"},
        {"ts": "2026-08-01 09:31"},
        {"ts": "2026-08-01 09:32"},
        {"ts": "2026-08-01 09:33"},
        {"ts": "2026-08-01 09:34"},
    ]

    cutoffs = probe_module._select_auto_cutoffs(rows, "2026-08-01 09:32", "2026-08-01 09:33")

    assert cutoffs == ["2026-08-01 09:32", "2026-08-01 09:33"]


def test_filter_auto_find_results_keeps_first_matching_alerts() -> None:
    scan_results = [
        {"cutoff": "2026-08-01 09:31", "zs_monitor_alert": "none"},
        {"cutoff": "2026-08-01 09:32", "zs_monitor_alert": "pre_breakout"},
        {"cutoff": "2026-08-01 09:33", "zs_monitor_alert": "pre_breakout"},
    ]

    payload = probe_module._filter_auto_find_results(
        scan_results,
        symbol="01339",
        target_alert="pre_breakout",
        start="2026-08-01 09:31",
        end="2026-08-01 09:33",
        limit=1,
    )

    assert payload == [{"cutoff": "2026-08-01 09:32", "zs_monitor_alert": "pre_breakout"}]


def test_filter_auto_find_results_emits_no_match_summary() -> None:
    scan_results = [
        {"cutoff": "2026-08-01 09:31", "zs_monitor_alert": "none"},
        {"cutoff": "2026-08-01 09:32", "zs_monitor_alert": "none"},
    ]

    payload = probe_module._filter_auto_find_results(
        scan_results,
        symbol="01339",
        target_alert="pre_breakout",
        start="2026-08-01 09:31",
        end="2026-08-01 09:32",
        limit=3,
    )

    assert payload == [
        {
            "symbol": "01339",
            "target_alert": "pre_breakout",
            "start": "2026-08-01 09:31",
            "end": "2026-08-01 09:32",
            "matches": 0,
            "scanned": 2,
        }
    ]