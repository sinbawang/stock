from __future__ import annotations

from pathlib import Path


def prune_older_outputs(target_dir: Path, pattern: str, keep_path: Path) -> tuple[Path, ...]:
    removed_paths: list[Path] = []
    for existing_path in sorted(target_dir.glob(pattern)):
        if existing_path == keep_path or not existing_path.is_file():
            continue
        existing_path.unlink()
        removed_paths.append(existing_path)
    return tuple(removed_paths)