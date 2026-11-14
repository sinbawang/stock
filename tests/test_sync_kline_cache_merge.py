"""K 线缓存 backup 的「云端 + 本地」合并逻辑。

背景（2026-11-14）：容器用自己**不完整**的本地仓库整包备份，把刚补进云端的 600584
历史抹掉（1m 从 4200 根变成几百根）。`backup --merge-cloud`（默认开）先拉云端快照
按 ts 取并集再上传。
"""

from __future__ import annotations

import csv
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


def _write_csv(path: Path, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ts", "open", "high", "low", "close", "volume"])
        for ts, close in rows:
            writer.writerow([ts, close, close, close, close, 100])


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_merge_kline_tree_keeps_cloud_history_when_local_is_partial(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    merged = tmp_path / "merged"

    # 云端：刚补进来的完整历史（4200 根，含 11-14 新 bar）
    _write_csv(cloud / "A/600584/1m.csv", [(f"2026-10-21 13:{i % 60:02d}", 10.0) for i in range(3)])
    # 本地（容器）：只有今天抓到的几根
    _write_csv(local / "A/600584/1m.csv", [("2026-11-14 09:31", 33.0), ("2026-11-14 09:32", 33.1)])

    stats = sync_module.merge_kline_tree(cloud, local, merged)

    rows = _read_rows(merged / "A/600584/1m.csv")
    timestamps = [row["ts"] for row in rows]
    # 并集：云端历史 + 本地新 bar，一根都不能少
    assert timestamps == ["2026-10-21 13:00", "2026-10-21 13:01", "2026-10-21 13:02", "2026-11-14 09:31", "2026-11-14 09:32"]
    assert stats["merged_csv"] == 1


def test_merge_kline_tree_prefers_fresher_side_on_conflict(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    merged = tmp_path / "merged"

    _write_csv(cloud / "A/600900/30m.csv", [("2026-11-14 14:30", 28.0), ("2026-11-14 15:00", 28.5)])
    # 本地更新（最后一根更晚）：冲突 ts 以本地为准
    _write_csv(local / "A/600900/30m.csv", [("2026-11-14 15:00", 28.6), ("2026-11-14 15:30", 28.7)])

    sync_module.merge_kline_tree(cloud, local, merged)

    rows = {row["ts"]: row for row in _read_rows(merged / "A/600900/30m.csv")}
    assert sorted(rows) == ["2026-11-14 14:30", "2026-11-14 15:00", "2026-11-14 15:30"]
    assert float(rows["2026-11-14 15:00"]["close"]) == 28.6


def test_merge_kline_tree_adds_files_only_present_on_either_side(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    merged = tmp_path / "merged"

    _write_csv(cloud / "A/000591/1m.csv", [("2026-11-14 09:31", 4.0)])
    _write_csv(local / "A/600584/day.csv", [("2026-11-13", 50.0)])
    (local / ".scheduler").mkdir(parents=True)
    (local / ".scheduler/last.json").write_text("{}", encoding="utf-8")

    stats = sync_module.merge_kline_tree(cloud, local, merged)

    assert (merged / "A/000591/1m.csv").exists()
    assert (merged / "A/600584/day.csv").exists()
    assert (merged / ".scheduler/last.json").exists()
    assert stats["from_cloud_only"] == 1
    # 本地独有：A/600584/day.csv + .scheduler/last.json
    assert stats["from_local_only"] == 2
