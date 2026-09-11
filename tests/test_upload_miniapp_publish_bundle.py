from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

module_spec = importlib.util.spec_from_file_location(
    "upload_miniapp_publish_bundle",
    SCRIPTS / "upload_miniapp_publish_bundle.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_file_should_always_upload_matches_entry_points() -> None:
    assert module.file_should_always_upload("index.json") is True
    assert module.file_should_always_upload("groups/portfolio.json") is True
    assert module.file_should_always_upload("stocks/00700/base.json") is True
    assert module.file_should_always_upload("stocks/00700/detail.json") is True
    assert module.file_should_always_upload("stocks/00700/summary.json") is True
    # 图表数据 JSON 必须每次上传（云端与 manifest 易漂移，否则图表长期不更新）。
    assert module.file_should_always_upload("stocks/00700/charts/30m.json") is True
    assert module.file_should_always_upload("stocks/00700/charts/1m.json") is True
    # 图表图片资产（svg/png/jpg）仍走增量哈希跳过，不进 always-upload。
    assert module.file_should_always_upload("stocks/00700/charts/30m.svg") is False


def test_plan_uploads_always_reuploads_chart_json_even_when_hash_unchanged(tmp_path: Path) -> None:
    """RS/上传闸门：charts/*.json 命中 always-upload，即使 sha256 与上次 manifest 相同也重新上传。"""
    chart_path = tmp_path / "stocks" / "00700" / "charts"
    chart_path.mkdir(parents=True, exist_ok=True)
    chart_file = chart_path / "1m.json"
    chart_file.write_text('{"bars": [1, 2, 3]}', encoding="utf-8")

    files = module.iter_local_files(tmp_path, "miniapp-publish/latest")
    chart_sha = next(item.sha256 for item in files if item.relative_path == "stocks/00700/charts/1m.json")
    previous_manifest = {
        "env_id": "env-1",
        "region": "ap-guangzhou",
        "cloud_prefix": "miniapp-publish/latest",
        "files": [
            {
                "relative_path": "stocks/00700/charts/1m.json",
                "cloud_path": "miniapp-publish/latest/stocks/00700/charts/1m.json",
                "file_id": "cloud://chart-json",
                "sha256": chart_sha,  # 与本地一致：旧逻辑会跳过
            }
        ],
    }

    upload_plan, skipped = module.plan_uploads(
        files,
        previous_manifest,
        env_id="env-1",
        region="ap-guangzhou",
        cloud_prefix="miniapp-publish/latest",
    )

    planned_paths = {item.relative_path for item in upload_plan}
    assert "stocks/00700/charts/1m.json" in planned_paths
    assert all(item.get("relative_path") != "stocks/00700/charts/1m.json" for item in skipped)


def test_plan_uploads_skips_unchanged_noncritical_files_but_keeps_critical_files(tmp_path: Path) -> None:
    chart_path = tmp_path / "stocks" / "00700" / "charts"
    detail_path = tmp_path / "stocks" / "00700"
    chart_path.mkdir(parents=True, exist_ok=True)
    detail_path.mkdir(parents=True, exist_ok=True)

    chart_file = chart_path / "30m.svg"
    base_file = detail_path / "base.json"
    detail_file = detail_path / "detail.json"
    chart_file.write_text("same-chart", encoding="utf-8")
    base_file.write_text('{"base": true}', encoding="utf-8")
    detail_file.write_text('{"changed": false}', encoding="utf-8")

    files = module.iter_local_files(tmp_path, "miniapp-publish/latest")
    previous_manifest = {
        "env_id": "env-1",
        "region": "ap-guangzhou",
        "cloud_prefix": "miniapp-publish/latest",
        "files": [
            {
                "relative_path": "stocks/00700/charts/30m.svg",
                "cloud_path": "miniapp-publish/latest/stocks/00700/charts/30m.svg",
                "file_id": "cloud://chart",
                "sha256": next(item.sha256 for item in files if item.relative_path == "stocks/00700/charts/30m.svg"),
            },
            {
                "relative_path": "stocks/00700/base.json",
                "cloud_path": "miniapp-publish/latest/stocks/00700/base.json",
                "file_id": "cloud://base",
                "sha256": next(item.sha256 for item in files if item.relative_path == "stocks/00700/base.json"),
            },
            {
                "relative_path": "stocks/00700/detail.json",
                "cloud_path": "miniapp-publish/latest/stocks/00700/detail.json",
                "file_id": "cloud://detail",
                "sha256": next(item.sha256 for item in files if item.relative_path == "stocks/00700/detail.json"),
            },
        ],
    }

    upload_plan, skipped = module.plan_uploads(
        files,
        previous_manifest,
        env_id="env-1",
        region="ap-guangzhou",
        cloud_prefix="miniapp-publish/latest",
    )

    assert [item.relative_path for item in upload_plan] == ["stocks/00700/base.json", "stocks/00700/detail.json"]
    assert skipped == [
        {
            "relative_path": "stocks/00700/charts/30m.svg",
            "cloud_path": "miniapp-publish/latest/stocks/00700/charts/30m.svg",
            "file_id": "cloud://chart",
            "size": chart_file.stat().st_size,
            "sha256": next(item.sha256 for item in files if item.relative_path == "stocks/00700/charts/30m.svg"),
            "status": "skipped",
        }
    ]


def test_load_previous_manifest_returns_none_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not json}", encoding="utf-8")

    assert module.load_previous_manifest(path) is None


def test_filter_incremental_files_can_skip_stock_meta_and_index_groups(tmp_path: Path) -> None:
    stock_dir = tmp_path / "stocks" / "03690"
    charts_dir = stock_dir / "charts"
    groups_dir = tmp_path / "groups"
    alerts_dir = tmp_path / "alerts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    groups_dir.mkdir(parents=True, exist_ok=True)
    alerts_dir.mkdir(parents=True, exist_ok=True)

    (tmp_path / "index.json").write_text("{}", encoding="utf-8")
    (groups_dir / "portfolio.json").write_text("{}", encoding="utf-8")
    (alerts_dir / "missing_artifacts.json").write_text("[]", encoding="utf-8")
    (stock_dir / "summary.json").write_text("{}", encoding="utf-8")
    (stock_dir / "detail.json").write_text("{}", encoding="utf-8")
    (charts_dir / "5m.json").write_text("{}", encoding="utf-8")
    (charts_dir / "1m.json").write_text("{}", encoding="utf-8")

    files = module.iter_local_files(tmp_path, "miniapp-publish/latest")
    filtered = module.filter_incremental_files(
        files,
        chart_timeframes={"5m", "1m"},
        symbols={"03690"},
        include_stock_meta=False,
        include_index_groups=False,
    )

    assert [item.relative_path for item in filtered] == [
        "alerts/missing_artifacts.json",
        "stocks/03690/charts/1m.json",
        "stocks/03690/charts/5m.json",
    ]


def test_validate_source_bundle_requires_index_and_portfolio_for_publish_payloads(tmp_path: Path) -> None:
    stock_dir = tmp_path / "stocks" / "03690"
    charts_dir = stock_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    (stock_dir / "summary.json").write_text("{}", encoding="utf-8")
    (stock_dir / "detail.json").write_text("{}", encoding="utf-8")
    (charts_dir / "5m.json").write_text("{}", encoding="utf-8")

    files = module.iter_local_files(tmp_path, "miniapp-publish/latest")

    try:
        module.validate_source_bundle(
            files,
            include_stock_meta=True,
            include_index_groups=True,
        )
    except module.CloudBaseUploadError as error:
        assert "missing required publish entry files" in str(error)
        assert "index.json" in str(error)
        assert "groups/portfolio.json" in str(error)
    else:
        raise AssertionError("expected validate_source_bundle to fail for incomplete publish bundle")


def test_verify_uploaded_files_retries_download_errors(monkeypatch, tmp_path: Path) -> None:
    local_path = tmp_path / "index.json"
    local_path.write_text('{"ok": true}', encoding="utf-8")
    payload = local_path.read_bytes()
    sha256 = module.hashlib.sha256(payload).hexdigest()
    local_file = module.LocalFile(
        relative_path="index.json",
        local_path=local_path,
        cloud_path="miniapp-publish/latest/index.json",
        size=len(payload),
        sha256=sha256,
    )
    uploaded = module.UploadedItem(file=local_file, file_id="cloud://index")
    attempts = {"count": 0}

    def fake_download(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise module.requests.exceptions.ChunkedEncodingError("boom")
        return payload

    monkeypatch.setattr(module, "download_cloud_bytes", fake_download)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    session = module.new_session()
    try:
        results = module.verify_uploaded_files(
            session,
            env_id="env",
            region="ap-guangzhou",
            api_key="key",
            uploaded_items=[uploaded],
            retries=3,
            retry_wait_seconds=0.0,
        )
    finally:
        session.close()

    assert attempts["count"] == 2
    assert results[0].matched is True