import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "sync_kline_cache_cloudbase.py"

spec = importlib.util.spec_from_file_location("sync_kline_cache_cloudbase", MODULE_PATH)
sync_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_module)


def test_snapshot_archive_round_trip(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "alpha.txt").write_text("hello world", encoding="utf-8")
    (source_dir / "beta.bin").write_bytes(b"\x00\x01\x02")

    archive_path = tmp_path / "snapshot.tar.gz"
    manifest = sync_module.create_snapshot_archive(source_dir, archive_path)

    assert archive_path.exists()
    assert manifest["file_count"] == 2
    assert {entry["path"] for entry in manifest["files"]} == {"beta.bin", "nested/alpha.txt"}

    restored_dir = tmp_path / "restored"
    restored_manifest = sync_module.restore_snapshot_archive(archive_path, restored_dir)

    assert (restored_dir / "nested" / "alpha.txt").read_text(encoding="utf-8") == "hello world"
    assert (restored_dir / "beta.bin").read_bytes() == b"\x00\x01\x02"
    assert restored_manifest["file_count"] == 2


def test_backup_dry_run_writes_expanded_manifest_with_snapshot(tmp_path):
    source_dir = tmp_path / "kline"
    (source_dir / "A" / "000001").mkdir(parents=True)
    (source_dir / "A" / "000001" / "5m.csv").write_text(
        "ts,open,high,low,close,volume\n1,1,1,1,1,1\n",
        encoding="utf-8",
    )
    (source_dir / "A" / "000001" / "1m.csv").write_text(
        "ts,open,high,low,close,volume\n1,1,1,1,1,1\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "build" / "manifest.json"
    pointer_path = tmp_path / "build" / "pointer.json"
    args = SimpleNamespace(
        env_id=None,
        dry_run=True,
        source_dir=str(source_dir),
        manifest_path=str(manifest_path),
        pointer_path=str(pointer_path),
        cloud_prefix="stock-kline-cache/latest",
        region="ap-guangzhou",
        upload_expanded_files=True,
        force_upload=False,
    )

    assert sync_module.command_backup(args) == 0

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files") or []
    assert any(item.get("relative_path") == "A/000001/5m.csv" for item in files)
    assert any(item.get("relative_path") == "A/000001/1m.csv" for item in files)

    snapshot = payload.get("snapshot") or {}
    assert snapshot.get("archive_cloud_path") == "stock-kline-cache/latest/snapshot.tar.gz"
    assert snapshot.get("file_count") == 2
