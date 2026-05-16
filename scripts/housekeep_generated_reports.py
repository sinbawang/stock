from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


TIMESTAMP_SUFFIX_RE = re.compile(r"^(?P<base>.+)_\d{8}_\d{4,6}$")
FROM_TIMESTAMP_RE = re.compile(r"(?P<prefix>.+)_from_(?P<stamp>\d{8}_\d{4,6})(?P<suffix>(?:_|\.).+)$")


@dataclass(frozen=True)
class ArchiveAction:
    source: Path
    archive_dir: Path


@dataclass(frozen=True)
class HousekeepPlan:
    actions: tuple[ArchiveAction, ...]

    @property
    def affected_dirs(self) -> tuple[Path, ...]:
        dirs = sorted({action.archive_dir for action in self.actions})
        return tuple(dirs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive older generated reports and timestamped snapshots while keeping the newest or latest aliases in place."
    )
    parser.add_argument("--data-dir", default=str(ROOT / "data"), help="Root data directory to housekeep")
    parser.add_argument(
        "--archive-prefix",
        default="_archive_keep_latest",
        help="Archive directory prefix created under each affected directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files into archive directories. Without this flag the script only prints a dry-run summary.",
    )
    return parser.parse_args()


def _build_archive_dir(directory: Path, archive_prefix: str, stamp: str) -> Path:
    return directory / f"{archive_prefix}_{stamp}"


def _top_level_timestamp_files(directory: Path) -> Iterable[Path]:
    return (
        path
        for path in directory.iterdir()
        if path.is_file() and TIMESTAMP_SUFFIX_RE.match(path.stem)
    )


def plan_meta_keep_latest(meta_dir: Path, archive_prefix: str, stamp: str) -> HousekeepPlan:
    grouped: dict[str, list[Path]] = {}
    for path in _top_level_timestamp_files(meta_dir):
        match = TIMESTAMP_SUFFIX_RE.match(path.stem)
        if match is None:
            continue
        grouped.setdefault(match.group("base"), []).append(path)

    archive_dir = _build_archive_dir(meta_dir, archive_prefix, stamp)
    actions: list[ArchiveAction] = []
    for paths in grouped.values():
        if len(paths) <= 1:
            continue
        sorted_paths = sorted(paths, key=lambda item: item.stem)
        for path in sorted_paths[:-1]:
            actions.append(ArchiveAction(source=path, archive_dir=archive_dir))
    return HousekeepPlan(actions=tuple(actions))


def _iter_non_meta_dirs(data_dir: Path) -> Iterable[Path]:
    for path in data_dir.rglob("*"):
        if not path.is_dir():
            continue
        if path == data_dir / "_meta":
            continue
        if path.name.startswith("_archive_keep_latest"):
            continue
        if "_meta" in path.parts:
            continue
        yield path


def plan_latest_alias_archives(data_dir: Path, archive_prefix: str, stamp: str) -> HousekeepPlan:
    actions: list[ArchiveAction] = []
    for directory in _iter_non_meta_dirs(data_dir):
        archive_dir = _build_archive_dir(directory, archive_prefix, stamp)
        for path in directory.iterdir():
            if not path.is_file():
                continue
            match = FROM_TIMESTAMP_RE.match(path.name)
            if match is None:
                continue
            latest_name = f"{match.group('prefix')}_latest{match.group('suffix')}"
            if (directory / latest_name).exists():
                actions.append(ArchiveAction(source=path, archive_dir=archive_dir))
    return HousekeepPlan(actions=tuple(actions))


def build_housekeep_plan(data_dir: Path, archive_prefix: str, stamp: str) -> HousekeepPlan:
    meta_plan = plan_meta_keep_latest(data_dir / "_meta", archive_prefix, stamp)
    latest_plan = plan_latest_alias_archives(data_dir, archive_prefix, stamp)
    return HousekeepPlan(actions=meta_plan.actions + latest_plan.actions)


def execute_plan(plan: HousekeepPlan) -> tuple[Path, ...]:
    manifests: list[Path] = []
    by_archive_dir: dict[Path, list[Path]] = {}
    for action in plan.actions:
        by_archive_dir.setdefault(action.archive_dir, []).append(action.source)

    for archive_dir, sources in sorted(by_archive_dir.items()):
        archive_dir.mkdir(parents=True, exist_ok=True)
        moved_names: list[str] = []
        for source in sorted(sources):
            target = archive_dir / source.name
            source.rename(target)
            moved_names.append(source.name)
        manifest = archive_dir / "_manifest.txt"
        manifest.write_text("\n".join(moved_names) + "\n", encoding="utf-8")
        manifests.append(manifest)

    return tuple(manifests)


def _print_plan(plan: HousekeepPlan) -> None:
    print(f"planned_moves={len(plan.actions)}")
    print(f"affected_directories={len(plan.affected_dirs)}")
    for archive_dir in plan.affected_dirs:
        count = sum(1 for action in plan.actions if action.archive_dir == archive_dir)
        print(f"{archive_dir}: {count}")


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan = build_housekeep_plan(data_dir, args.archive_prefix, stamp)
    _print_plan(plan)
    if not args.apply:
        print("dry_run=true")
        return
    manifests = execute_plan(plan)
    print("dry_run=false")
    for manifest in manifests:
        print(manifest)


if __name__ == "__main__":
    main()