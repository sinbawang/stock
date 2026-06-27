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
    assert module.file_should_always_upload("stocks/00700/charts/30m.svg") is False


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