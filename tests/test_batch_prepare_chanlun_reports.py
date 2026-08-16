from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "batch_prepare_chanlun_reports",
    SCRIPTS / "batch_prepare_chanlun_reports.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_reuse_existing_hk_5m_case_accepts_effective_only_payload_for_any(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("00700", "腾讯", "HK")
    rows = [
        {"ts": "2026-06-27 09:35:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-06-27 15:55:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ]
    root_dir = tmp_path / "00700" / "5m"
    analyze_dir = root_dir / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)
    layout = SimpleNamespace(
        root_dir=root_dir,
        raw_csv=analyze_dir / "raw.csv",
        normalized_csv=analyze_dir / "normalized.csv",
        fractals_csv=analyze_dir / "fractals.csv",
        confirmed_fractals_csv=analyze_dir / "confirmed_fractals.csv",
        bis_csv=analyze_dir / "bis.csv",
        segments_csv=analyze_dir / "segments.csv",
        zhongshu_csv=analyze_dir / "zhongshu.csv",
        macd_csv=analyze_dir / "macd.csv",
        chart_svg=root_dir / "structure.svg",
        chart_png=root_dir / "structure.png",
        chart_jpg=root_dir / "structure.jpg",
        technical_report_json=root_dir / "tech.json",
    )
    for path in (
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
        root_dir / "analysis.txt",
        root_dir / "advice.txt",
        root_dir / "report.txt",
    ):
        path.write_text("ok", encoding="utf-8")

    layout.technical_report_json.write_text(
        json.dumps(
            {
                "timeframe": "5m",
                "pending_reverse_mode": "effective_only",
                "zhongshu_level": "bi",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    expected = {"report": root_dir / "report.txt"}
    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "load_existing_case", lambda actual_security, timeframe: expected)

    reused = module._reuse_existing_hk_5m_case(
        security,
        rows,
        pending_reverse_mode="any",
        zhongshu_level="bi",
    )

    assert reused == expected


def test_reuse_existing_hk_5m_case_accepts_segment_payload(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("03690", "美团", "HK")
    rows = [
        {"ts": "2026-08-14 15:20:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-08-14 15:25:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ]
    root_dir = tmp_path / "03690" / "5m"
    analyze_dir = root_dir / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)
    layout = SimpleNamespace(
        root_dir=root_dir,
        raw_csv=analyze_dir / "raw.csv",
        normalized_csv=analyze_dir / "normalized.csv",
        fractals_csv=analyze_dir / "fractals.csv",
        confirmed_fractals_csv=analyze_dir / "confirmed_fractals.csv",
        bis_csv=analyze_dir / "bis.csv",
        segments_csv=analyze_dir / "segments.csv",
        zhongshu_csv=analyze_dir / "zhongshu.csv",
        macd_csv=analyze_dir / "macd.csv",
        chart_svg=root_dir / "structure.svg",
        chart_png=root_dir / "structure.png",
        chart_jpg=root_dir / "structure.jpg",
        technical_report_json=root_dir / "tech.json",
    )
    for path in (
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
        root_dir / "analysis.txt",
        root_dir / "advice.txt",
        root_dir / "report.txt",
    ):
        path.write_text("ok", encoding="utf-8")

    layout.technical_report_json.write_text(
        json.dumps(
            {
                "timeframe": "5m",
                "pending_reverse_mode": "effective_only",
                "zhongshu_level": "segment",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    expected = {"report": root_dir / "report.txt"}
    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "load_existing_case", lambda actual_security, timeframe: expected)

    reused = module._reuse_existing_hk_5m_case(
        security,
        rows,
        pending_reverse_mode="effective_only",
        zhongshu_level="segment",
    )

    assert reused == expected


def test_fetch_intraday_rows_reuses_local_hk_5m_cache_before_remote_fetch(monkeypatch) -> None:
    security = module.Security("00700", "腾讯", "HK")
    cached_rows = [
        {"ts": f"2026-06-27 10:{index:02d}", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}
        for index in range(module.HK_REUSABLE_5M_MIN_ROWS)
    ]

    monkeypatch.setattr(module, "_load_reusable_hk_intraday_rows", lambda *args, **kwargs: cached_rows)
    monkeypatch.setattr(module, "resolve_hk_minute_source_selection", lambda: ("xueqiu", ("akshare",), "mainland"))

    def fail_remote_fetch(*args, **kwargs):
        raise AssertionError("remote fetch should not be used when local HK 5m cache is sufficient")

    monkeypatch.setattr(module, "fetch_hk_minute_with_policy", fail_remote_fetch)

    rows, payload = module.fetch_intraday_rows(
        security,
        timeframe="5m",
        period="5",
        start="2026-06-20 09:30",
        bar_count=600,
    )

    assert rows == cached_rows
    assert payload["source"] == "local.hk_5m_cache"
    assert payload["actual_source"] == "local.hk_5m_cache"


def test_fetch_intraday_rows_hk_5m_incremental_probe_skips_local_reuse(monkeypatch) -> None:
    security = module.Security("00700", "腾讯", "HK")
    cached_rows = [
        {"ts": f"2026-06-27 10:{index:02d}", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}
        for index in range(module.HK_REUSABLE_5M_MIN_ROWS)
    ]
    remote_rows = [
        {"ts": "2026-06-30 15:55", "open": 2.0, "high": 2.1, "low": 1.9, "close": 2.0, "volume": 2},
    ]

    monkeypatch.setattr(module, "_load_reusable_hk_intraday_rows", lambda *args, **kwargs: cached_rows)
    monkeypatch.setattr(module, "resolve_hk_minute_source_selection", lambda: ("xueqiu", ("akshare",), "mainland"))
    monkeypatch.setattr(module, "get_last_hk_fetch_metadata", lambda: {"actual_source": "xueqiu", "source_attempts": []})
    monkeypatch.setattr(
        module,
        "fetch_hk_minute_with_policy",
        lambda *args, **kwargs: (remote_rows, "xueqiu"),
    )

    rows, payload = module.fetch_intraday_rows(
        security,
        timeframe="5m",
        period="5",
        start="2026-06-20 09:30",
        bar_count=600,
        source_probe_min_rows=1,
    )

    assert rows == remote_rows
    assert payload["source"] == "xueqiu->akshare"
    assert payload["actual_source"] == "xueqiu"


def test_fetch_with_optional_local_store_uses_incremental_start_and_tail(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("00700", "腾讯", "HK")
    local_rows = [
        {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 10:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ]
    remote_rows = [
        {"ts": "2026-07-01 09:55", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 2},
        {"ts": "2026-07-01 10:05", "open": 1.2, "high": 1.3, "low": 1.1, "close": 1.2, "volume": 3},
    ]
    captured = {}

    def fake_remote_fetcher(start: str):
        captured["start"] = start
        return remote_rows, {"source": "xueqiu", "actual_bar_count": len(remote_rows)}

    monkeypatch.setattr(module, "load_local_rows", lambda *args, **kwargs: local_rows)
    monkeypatch.setattr(
        module,
        "upsert_local_rows",
        lambda *args, **kwargs: (
            [
                {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                {"ts": "2026-07-01 09:55", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 2},
                {"ts": "2026-07-01 10:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                {"ts": "2026-07-01 10:05", "open": 1.2, "high": 1.3, "low": 1.1, "close": 1.2, "volume": 3},
            ],
            SimpleNamespace(added=1, updated=1, total=4),
            tmp_path / "kline.csv",
        ),
    )

    rows, payload = module._fetch_with_optional_local_store(
        security,
        timeframe="5m",
        requested_start="2026-06-20 09:30",
        bar_count=3,
        overlap_bars=2,
        use_local_store=True,
        local_store_read_only=False,
        local_store_root=tmp_path,
        remote_fetcher=fake_remote_fetcher,
    )

    assert captured["start"] == "2026-07-01 09:50"
    assert len(rows) == 3
    assert payload["local_store"]["merged_total_rows"] == 4
    assert payload["local_store"]["analysis_rows"] == 3
    assert payload["actual_bar_count"] == 3