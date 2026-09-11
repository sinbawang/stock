from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import Future
from datetime import datetime
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


def test_export_case_uses_in_memory_rows_instead_of_csv_reread(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("03690", "美团", "HK")
    rows = [
        {"ts": "2026-08-14 15:20:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
        {"ts": "2026-08-14 15:25:00", "open": 1.0, "high": 1.2, "low": 0.95, "close": 1.1, "volume": 2},
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
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "save_rows", lambda *args, **kwargs: captured.setdefault("saved", True))

    def fake_clean_bars(raw_bars):
        captured["raw_bars"] = raw_bars
        return raw_bars

    monkeypatch.setattr(module, "clean_bars", fake_clean_bars)
    monkeypatch.setattr(module, "normalize_bars", lambda raw_bars: [])
    monkeypatch.setattr(module, "write_normalized_csv", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "identify_fractals", lambda normalized_bars: [])
    monkeypatch.setattr(module, "filter_consecutive_fractals", lambda fractals: fractals)
    monkeypatch.setattr(module, "identify_bis", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "identify_segments", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "identify_zhongshu", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "calculate_macd", lambda raw_bars: [])
    monkeypatch.setattr(module, "export_fractals", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_confirmed_fractals", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_bis", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_segments", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_zhongshus", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_macd", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "analyze_current_state", lambda *args, **kwargs: "analysis")
    monkeypatch.setattr(module, "extract_signals", lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "build_advice", lambda *args, **kwargs: "advice")
    monkeypatch.setattr(module, "build_technical_summary", lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "serialize_zhongshu", lambda zs: {"zs": True})
    monkeypatch.setattr(module, "serialize_zhongshus", lambda zs_list: [])
    monkeypatch.setattr(module, "compute_tech_report_fingerprint", lambda: "test-fp")
    monkeypatch.setattr(module, "write_json", lambda path, payload: path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8"))
    monkeypatch.setattr(module, "prune_analyze_csv_families", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "read_bars_from_csv", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("CSV reread should not be used")))

    outputs = module.export_case(
        security,
        "5m",
        rows,
        "03690 美团 5m",
        export_structure_images=False,
    )

    raw_bars = captured["raw_bars"]
    assert captured["saved"] is True
    assert len(raw_bars) == 2
    assert all(isinstance(item, module.Bar) for item in raw_bars)
    assert raw_bars[0].ts == datetime(2026, 8, 14, 15, 20)
    assert raw_bars[1].close == 1.1
    assert outputs["tech_json"] == layout.technical_report_json


def test_reuse_existing_hk_5m_case_rejects_legacy_bi_payload(monkeypatch, tmp_path: Path) -> None:
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
        zhongshu_level="segment",
    )

    assert reused is None


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
                "code_fingerprint": "test-fp",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    expected = {"report": root_dir / "report.txt"}
    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "load_existing_case", lambda actual_security, timeframe: expected)
    monkeypatch.setattr(module, "compute_tech_report_fingerprint", lambda: "test-fp")

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


def test_run_batch_prepare_uses_requested_parallelism(monkeypatch, tmp_path: Path) -> None:
    securities = [
        module.Security("000651", "格力电器", "A"),
        module.Security("03690", "美团", "HK"),
    ]
    captured: dict[str, object] = {}

    class FakeExecutor:
        def __init__(self, max_workers: int):
            captured["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args, **kwargs):
            future = Future()
            future.set_result(fn(*args, **kwargs))
            return future

    def fake_prepare_security_result(security, **kwargs):
        return module.PreparedSecurityResult(
            security=security,
            day_case={},
            m60_case={},
            timeframe_diagnostics=[],
        )

    monkeypatch.setattr(module, "load_securities", lambda path: securities)
    monkeypatch.setattr(module, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(module, "as_completed", lambda futures: list(futures))
    monkeypatch.setattr(module, "_prepare_security_result", fake_prepare_security_result)
    monkeypatch.setattr(module, "REPORTS_META_DIR", tmp_path)

    result = module.run_batch_prepare(
        holdings_path=tmp_path / "holdings.json",
        timeframes=("5m", "1m"),
        parallelism=4,
    )

    assert captured["max_workers"] == 2
    assert result.security_count == 2


def test_reuse_existing_exact_case_accepts_matching_1m_payload(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("03690", "美团", "HK")
    rows = [
        {"ts": "2026-08-14 15:20:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
        {"ts": "2026-08-14 15:21:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
    ]
    root_dir = tmp_path / "03690" / "1m"
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
    layout.raw_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-08-14 15:20:00,1,1.1,0.9,1,1\n"
        "2026-08-14 15:21:00,1,1.1,0.9,1,1\n",
        encoding="utf-8",
    )
    layout.technical_report_json.write_text(
        json.dumps(
            {
                "timeframe": "1m",
                "pending_reverse_mode": "effective_only",
                "zhongshu_level": "segment",
                "code_fingerprint": "test-fp",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    expected = {"report": root_dir / "report.txt"}
    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "load_existing_case", lambda actual_security, timeframe: expected)
    monkeypatch.setattr(module, "compute_tech_report_fingerprint", lambda: "test-fp")

    reused = module._reuse_existing_exact_case(
        security,
        "1m",
        rows,
        pending_reverse_mode="effective_only",
        zhongshu_level="segment",
    )

    assert reused == expected


def test_reuse_existing_exact_case_rejects_stale_raw_csv(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("03690", "美团", "HK")
    rows = [
        {"ts": "2026-08-14 15:20:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
        {"ts": "2026-08-14 15:21:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
    ]
    root_dir = tmp_path / "03690" / "1m"
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
    layout.raw_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-08-14 15:20:00,1,1.1,0.9,1,1\n"
        "2026-08-14 15:22:00,1,1.1,0.9,1,1\n",
        encoding="utf-8",
    )
    layout.technical_report_json.write_text(
        json.dumps(
            {
                "timeframe": "1m",
                "pending_reverse_mode": "effective_only",
                "zhongshu_level": "segment",
                "code_fingerprint": "test-fp",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "compute_tech_report_fingerprint", lambda: "test-fp")

    reused = module._reuse_existing_exact_case(
        security,
        "1m",
        rows,
        pending_reverse_mode="effective_only",
        zhongshu_level="segment",
    )

    assert reused is None


def test_reuse_existing_exact_case_rejects_stale_code_fingerprint(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("03690", "美团", "HK")
    rows = [
        {"ts": "2026-08-14 15:20:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
        {"ts": "2026-08-14 15:21:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
    ]
    root_dir = tmp_path / "03690" / "1m"
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
    layout.raw_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-08-14 15:20:00,1,1.1,0.9,1,1\n"
        "2026-08-14 15:21:00,1,1.1,0.9,1,1\n",
        encoding="utf-8",
    )
    layout.technical_report_json.write_text(
        json.dumps(
            {
                "timeframe": "1m",
                "pending_reverse_mode": "effective_only",
                "zhongshu_level": "segment",
                "code_fingerprint": "stale-fp",
                "data_fetch": {"actual_bar_count": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "timeframe_report_paths", lambda symbol, timeframe, bars: layout)
    monkeypatch.setattr(module, "compute_tech_report_fingerprint", lambda: "current-fp")

    reused = module._reuse_existing_exact_case(
        security,
        "1m",
        rows,
        pending_reverse_mode="effective_only",
        zhongshu_level="segment",
    )

    assert reused is None


def test_fetch_with_optional_local_store_uses_incremental_start_and_tail(monkeypatch, tmp_path: Path) -> None:
    security = module.Security("00700", "腾讯", "HK")
    local_rows = [
        {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 09:45", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
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


def test_fetch_with_optional_local_store_backfills_when_local_short(monkeypatch, tmp_path: Path) -> None:
    """本地仓库未覆盖目标根数时应从完整窗口全量抓取，而非只补最近增量。"""
    security = module.Security("00700", "腾讯", "HK")
    local_rows = [
        {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 10:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ]
    captured = {}

    def fake_remote_fetcher(start: str):
        captured["start"] = start
        return [
            {"ts": "2026-07-01 09:55", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 2},
        ], {"source": "xueqiu", "actual_bar_count": 1}

    monkeypatch.setattr(module, "load_local_rows", lambda *args, **kwargs: local_rows)
    monkeypatch.setattr(
        module,
        "upsert_local_rows",
        lambda *args, **kwargs: (
            local_rows,
            SimpleNamespace(added=0, updated=0, total=2),
            tmp_path / "kline.csv",
        ),
    )

    module._fetch_with_optional_local_store(
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

    # 本地仅 2 根 < 目标 3 根 → 不从 last_ts 增量，而是从 requested_start 全量抓取
    assert captured["start"] == "2026-06-20 09:30"


def test_fetch_with_optional_local_store_falls_back_to_full_on_incremental_gap(monkeypatch, tmp_path: Path) -> None:
    """RS4 增量重算稳健性：增量窗口与缓存不连续（远端最早根晚于缓存末根，跳空 / 停牌）时，
    回退到 requested_start 全量窗口重抓再合并，避免把带隐藏缺口的序列喂给下游切分。"""
    security = module.Security("00700", "腾讯", "HK")
    local_rows = [
        {"ts": "2026-07-01 09:30", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 09:45", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 10:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ]
    gap_rows = [
        {"ts": "2026-07-01 10:30", "open": 2.0, "high": 2.1, "low": 1.9, "close": 2.0, "volume": 5},
        {"ts": "2026-07-01 10:45", "open": 2.1, "high": 2.2, "low": 2.0, "close": 2.1, "volume": 6},
    ]
    full_rows = [
        {"ts": "2026-07-01 09:45", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 10:00", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"ts": "2026-07-01 10:15", "open": 1.5, "high": 1.6, "low": 1.4, "close": 1.5, "volume": 4},
        {"ts": "2026-07-01 10:30", "open": 2.0, "high": 2.1, "low": 1.9, "close": 2.0, "volume": 5},
    ]
    calls: list[str] = []
    captured_upsert: dict[str, object] = {}

    def fake_remote_fetcher(start: str, _min_rows: int = 1):
        calls.append(start)
        # 第一次（增量）返回跳空数据；第二次（回退全量）返回连续全窗。
        return (gap_rows if len(calls) == 1 else full_rows), {"source": "xueqiu", "actual_bar_count": 2}

    def fake_upsert(symbol, market, timeframe, rows, *, root=None):
        captured_upsert["rows"] = rows
        by_ts = {r["ts"]: r for r in local_rows}
        for r in rows:
            by_ts[r["ts"]] = r
        merged = [by_ts[k] for k in sorted(by_ts)]
        return merged, SimpleNamespace(added=len(rows), updated=0, total=len(merged)), tmp_path / "kline.csv"

    monkeypatch.setattr(module, "load_local_rows", lambda *args, **kwargs: local_rows)
    monkeypatch.setattr(module, "upsert_local_rows", fake_upsert)

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

    assert len(calls) == 2  # 增量 + 回退全量各一次
    assert calls[1] == "2026-06-20 09:30"  # 回退到 requested_start 全量窗口
    assert payload["local_store"]["incremental_fallback"] is True
    assert payload["local_store"]["effective_start"] == "2026-06-20 09:30"
    # 合并用的是全量重抓的连续数据，而非跳空增量
    assert captured_upsert["rows"] == full_rows
