from __future__ import annotations

import importlib.util
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "refresh_holdings_publish_to_cloudbase",
    SCRIPTS / "refresh_holdings_publish_to_cloudbase.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_parse_args_defaults_include_5m_2000_and_1m_3500(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["refresh_holdings_publish_to_cloudbase.py"])
    args = module.parse_args()

    assert args.day_bars == 1200
    assert args.m60_bars == 1200
    assert args.m30_bars == 1200
    assert args.m15_bars == 1200
    assert args.m5_bars == 2000
    assert args.m1_bars == 3500
    assert args.sync_kline_cache is True
    assert args.kline_cache_cloud_prefix == "stock-kline-cache/latest"


def test_resolve_kline_cache_source_dir_falls_back_to_container_path(tmp_path, monkeypatch):
    fallback_dir = tmp_path / "data" / "stock-kline-cache"
    fallback_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "ROOT", tmp_path)
    args = module.argparse.Namespace(kline_cache_source_dir=str(tmp_path / "data" / "cache" / "kline"))

    resolved = module._resolve_kline_cache_source_dir(args)

    assert resolved == fallback_dir


def test_classify_publish_failure_recognizes_incomplete_bundle_entry_files() -> None:
    summary = module._classify_publish_failure(
        "source bundle is incomplete: missing required publish entry files index.json, groups/portfolio.json"
    )

    assert summary["code"] == "incomplete_bundle_missing_entry_files"
    assert "index.json" in summary["hint"] or "groups/portfolio.json" in summary["hint"]


def test_upload_publish_bundle_prints_structured_summary_on_retry_failure(monkeypatch, capsys, tmp_path: Path) -> None:
    source_dir = tmp_path / "latest"
    source_dir.mkdir(parents=True)
    args = argparse.Namespace(
        cloud_prefix="miniapp-publish/latest",
        env_id=None,
        region=None,
        api_key=None,
        api_key_name=None,
        api_key_expire_in=None,
        delete_created_api_key=False,
        force_upload=False,
        upload_chart_timeframes=None,
        upload_symbols=None,
        upload_include_stock_meta=True,
        upload_include_index_groups=True,
        upload_dry_run=False,
    )

    calls = {"count": 0}

    def fail_command(command):
        calls["count"] += 1
        raise RuntimeError(
            "source bundle is incomplete: missing required publish entry files index.json, groups/portfolio.json"
        )

    monkeypatch.setattr(module, "_run_command", fail_command)

    try:
        module.upload_publish_bundle(args, source_dir)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected upload_publish_bundle to re-raise the retry failure")

    captured = capsys.readouterr()
    assert calls["count"] == 2
    assert "publish_stage_failure stage=upload_attempt_1 code=incomplete_bundle_missing_entry_files" in captured.out
    assert "publish_stage_failure stage=upload_attempt_2 code=incomplete_bundle_missing_entry_files" in captured.out


def test_write_timing_report_persists_publish_failures(tmp_path: Path, monkeypatch) -> None:
    meta_dir = tmp_path / "meta"
    monkeypatch.setattr(module, "REPORTS_META_DIR", meta_dir)
    args = argparse.Namespace(
        holdings_file="holdings.json",
        market="ALL",
        symbols=None,
        limit=None,
        parallelism=1,
        skip_regenerate=False,
        skip_build=False,
        skip_upload=False,
        skip_gen_base=True,
        skip_gen_fund=False,
        day_bars=1200,
        m60_bars=1200,
        m30_bars=1200,
        m15_bars=1200,
        m5_bars=2000,
        m1_bars=3500,
        pending_reverse_mode="effective_only",
        zhongshu_level="segment",
        tech_timeframes=["day", "30m", "5m", "1m"],
        export_structure_images=True,
        publish_timeframes=None,
        publish_json_only=False,
        force_upload=False,
        sync_kline_cache=True,
        sync_kline_cache_restore_before_regenerate=False,
        local_store_read_only=False,
        kline_cache_cloud_prefix="stock-kline-cache/latest",
    )

    report_path = module._write_timing_report(
        args,
        started_at=datetime(2026, 8, 18, 10, 0, 0),
        completed_at=datetime(2026, 8, 18, 10, 5, 0),
        stage_seconds={"build_seconds": 1.2, "upload_seconds": 2.3},
        regeneration_summary=None,
        latest_dir=tmp_path / "publish" / "latest",
        build_summary={
            "missing_artifact_alert_count": 1,
            "missing_artifact_alert_path": tmp_path / "alerts.json",
            "bundle_integrity": {
                "index_present": True,
                "portfolio_group_present": True,
                "stock_dir_count": 3,
            },
            "snapshot_bundle_integrity": None,
        },
        publish_failures=[
            {
                "stage": "upload_attempt_1",
                "code": "incomplete_bundle_missing_entry_files",
                "hint": "missing index/groups",
                "error": "source bundle is incomplete",
                "source_dir": str(tmp_path / "publish" / "latest"),
            }
        ],
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["publish_failures"][0]["code"] == "incomplete_bundle_missing_entry_files"
    assert payload["publish_failures"][0]["stage"] == "upload_attempt_1"
    assert payload["artifacts"]["bundle_integrity"]["index_present"] is True
    assert payload["artifacts"]["bundle_integrity"]["stock_dir_count"] == 3
