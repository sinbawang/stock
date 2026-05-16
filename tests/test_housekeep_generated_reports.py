from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
housekeep_spec = importlib.util.spec_from_file_location(
    "housekeep_generated_reports",
    SCRIPTS / "housekeep_generated_reports.py",
)
if housekeep_spec is None or housekeep_spec.loader is None:
    raise RuntimeError("failed to load housekeep_generated_reports.py for tests")
housekeep_module = importlib.util.module_from_spec(housekeep_spec)
sys.modules[housekeep_spec.name] = housekeep_module
housekeep_spec.loader.exec_module(housekeep_module)

ArchiveAction = housekeep_module.ArchiveAction
build_housekeep_plan = housekeep_module.build_housekeep_plan
execute_plan = housekeep_module.execute_plan
plan_latest_alias_archives = housekeep_module.plan_latest_alias_archives
plan_meta_keep_latest = housekeep_module.plan_meta_keep_latest


def test_plan_meta_keep_latest_archives_older_duplicate_reports(tmp_path):
    meta_dir = tmp_path / "data" / "_meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "00700_腾讯_fundamental_brief_20260510_013524.txt").write_text("old", encoding="utf-8")
    (meta_dir / "00700_腾讯_fundamental_brief_20260512_005912.txt").write_text("new", encoding="utf-8")
    (meta_dir / "analysis_preview.txt").write_text("keep", encoding="utf-8")

    plan = plan_meta_keep_latest(meta_dir, "_archive_keep_latest", "20260516_130000")

    assert plan.actions == (
        ArchiveAction(
            source=meta_dir / "00700_腾讯_fundamental_brief_20260510_013524.txt",
            archive_dir=meta_dir / "_archive_keep_latest_20260516_130000",
        ),
    )


def test_plan_latest_alias_archives_only_when_latest_exists(tmp_path):
    data_dir = tmp_path / "data"
    target_dir = data_dir / "603986_兆易创新" / "15m"
    target_dir.mkdir(parents=True)
    (target_dir / "603986_15m_from_20260224_1130.csv").write_text("snapshot", encoding="utf-8")
    (target_dir / "603986_15m_latest.csv").write_text("latest", encoding="utf-8")
    (target_dir / "603986_15m_from_20260225_1130_kline.png").write_text("png", encoding="utf-8")

    plan = plan_latest_alias_archives(data_dir, "_archive_keep_latest", "20260516_130000")

    assert plan.actions == (
        ArchiveAction(
            source=target_dir / "603986_15m_from_20260224_1130.csv",
            archive_dir=target_dir / "_archive_keep_latest_20260516_130000",
        ),
    )


def test_execute_plan_moves_files_and_writes_manifest(tmp_path):
    archive_dir = tmp_path / "data" / "_meta" / "_archive_keep_latest_20260516_130000"
    source_dir = tmp_path / "data" / "_meta"
    source_dir.mkdir(parents=True)
    source = source_dir / "00700_腾讯_fundamental_brief_20260510_013524.txt"
    source.write_text("old", encoding="utf-8")

    manifests = execute_plan(
        housekeep_module.HousekeepPlan(
            actions=(ArchiveAction(source=source, archive_dir=archive_dir),)
        )
    )

    manifest = archive_dir / "_manifest.txt"
    assert manifests == (manifest,)
    assert not source.exists()
    assert (archive_dir / source.name).exists()
    assert manifest.read_text(encoding="utf-8") == source.name + "\n"


def test_build_housekeep_plan_combines_meta_and_latest_rules(tmp_path):
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "_meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "03690_美团_fundamental_brief_20260511_214930.txt").write_text("old", encoding="utf-8")
    (meta_dir / "03690_美团_fundamental_brief_20260512_010142.txt").write_text("new", encoding="utf-8")

    target_dir = data_dir / "603986_兆易创新" / "15m"
    target_dir.mkdir(parents=True)
    (target_dir / "603986_15m_from_20260224_1130.csv").write_text("snapshot", encoding="utf-8")
    (target_dir / "603986_15m_latest.csv").write_text("latest", encoding="utf-8")

    plan = build_housekeep_plan(data_dir, "_archive_keep_latest", "20260516_130000")

    assert len(plan.actions) == 2
    assert {action.source.name for action in plan.actions} == {
        "03690_美团_fundamental_brief_20260511_214930.txt",
        "603986_15m_from_20260224_1130.csv",
    }