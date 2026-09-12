"""区间套 replay 样本辅助函数（`--auto-find` 相关）的单元测试。

**历史注记**：本模块原本从**未入版本库**的 `build/probe_intraday_prebreak_sample.py`
导入被测函数，导致在干净机器上收集阶段就报错。被测实现现已搬到受版本控制的
`tests/replay_support.py`；断言语义未变。
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.replay_support import filter_auto_find_results, select_auto_cutoffs  # noqa: E402


def test_select_auto_cutoffs_filters_duplicates_and_time_window() -> None:
    rows = [
        {"ts": "2026-08-01 09:31"},
        {"ts": "2026-08-01 09:31"},
        {"ts": "2026-08-01 09:32"},
        {"ts": "2026-08-01 09:33"},
        {"ts": "2026-08-01 09:34"},
    ]

    cutoffs = select_auto_cutoffs(rows, "2026-08-01 09:32", "2026-08-01 09:33")

    assert cutoffs == ["2026-08-01 09:32", "2026-08-01 09:33"]


def test_filter_auto_find_results_keeps_first_matching_alerts() -> None:
    scan_results = [
        {"cutoff": "2026-08-01 09:31", "zs_monitor_alert": "none"},
        {"cutoff": "2026-08-01 09:32", "zs_monitor_alert": "pre_breakout"},
        {"cutoff": "2026-08-01 09:33", "zs_monitor_alert": "pre_breakout"},
    ]

    payload = filter_auto_find_results(
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

    payload = filter_auto_find_results(
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