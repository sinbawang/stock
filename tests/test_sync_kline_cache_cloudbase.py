import importlib.util
import sys
from pathlib import Path


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
