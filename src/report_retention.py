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


def prune_analyze_csv_families(keep_raw_csv: Path) -> tuple[Path, ...]:
    """Keep only the current symbol/timeframe CSV family under analyze/.

    For a filename like `01024_5m_20260722_to_20260813.csv`, this function keeps
    all files starting with `01024_5m_20260722_to_20260813` (including
    `_normalized_*` companions) and removes other `01024_5m_*.csv` files.
    """
    if not keep_raw_csv.exists() or not keep_raw_csv.is_file():
        return tuple()

    stem = keep_raw_csv.stem
    parts = stem.split("_")
    if len(parts) < 3:
        return tuple()

    symbol = parts[0]
    timeframe = parts[1]
    keep_prefix = stem
    target_dir = keep_raw_csv.parent

    removed_paths: list[Path] = []
    for existing_path in sorted(target_dir.glob(f"{symbol}_{timeframe}_*.csv")):
        if not existing_path.is_file():
            continue
        if existing_path.stem.startswith(keep_prefix):
            continue
        existing_path.unlink()
        removed_paths.append(existing_path)
    return tuple(removed_paths)