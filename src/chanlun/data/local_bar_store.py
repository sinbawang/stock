from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from storage_layout import KLINE_CACHE_DIR


_INTRADAY_MINUTES = {
    "60m": 60,
    "30m": 30,
    "15m": 15,
    "5m": 5,
    "1m": 1,
}


@dataclass(frozen=True)
class MergeStats:
    added: int
    updated: int
    total: int


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析 K 线时间戳: {value}")


def _format_ts(value: datetime, timeframe: str) -> str:
    normalized = timeframe.strip().lower()
    if normalized == "day":
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M")


def local_kline_store_path(symbol: str, market: str, timeframe: str, *, root: Path | None = None) -> Path:
    base_root = root or KLINE_CACHE_DIR
    normalized_symbol = symbol.strip()
    normalized_market = market.strip().upper()
    normalized_timeframe = timeframe.strip().lower()
    return base_root / normalized_market / normalized_symbol / f"{normalized_timeframe}.csv"


def load_local_rows(symbol: str, market: str, timeframe: str, *, root: Path | None = None) -> list[dict]:
    path = local_kline_store_path(symbol, market, timeframe, root=root)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {
                "ts": str(row.get("ts") or "").strip(),
                "open": float(row.get("open") or 0),
                "high": float(row.get("high") or 0),
                "low": float(row.get("low") or 0),
                "close": float(row.get("close") or 0),
                "volume": int(float(row.get("volume") or 0)),
            }
            for row in reader
            if str(row.get("ts") or "").strip()
        ]

    rows.sort(key=lambda item: item["ts"])
    return rows


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ts", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)


def merge_rows(existing_rows: list[dict], new_rows: list[dict]) -> tuple[list[dict], MergeStats]:
    by_ts: dict[str, dict] = {}
    for row in existing_rows:
        by_ts[str(row["ts"])]= {
            "ts": str(row["ts"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(float(row.get("volume") or 0)),
        }

    added = 0
    updated = 0
    for row in new_rows:
        ts = str(row["ts"])
        normalized = {
            "ts": ts,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(float(row.get("volume") or 0)),
        }
        previous = by_ts.get(ts)
        if previous is None:
            added += 1
            by_ts[ts] = normalized
            continue
        if previous != normalized:
            updated += 1
            by_ts[ts] = normalized

    merged = [by_ts[key] for key in sorted(by_ts.keys())]
    return merged, MergeStats(added=added, updated=updated, total=len(merged))


def upsert_local_rows(
    symbol: str,
    market: str,
    timeframe: str,
    new_rows: list[dict],
    *,
    root: Path | None = None,
) -> tuple[list[dict], MergeStats, Path]:
    existing_rows = load_local_rows(symbol, market, timeframe, root=root)
    merged_rows, stats = merge_rows(existing_rows, new_rows)
    store_path = local_kline_store_path(symbol, market, timeframe, root=root)
    _write_rows(store_path, merged_rows)
    return merged_rows, stats, store_path


def infer_incremental_start(last_ts: str, timeframe: str, overlap_bars: int = 120) -> str:
    if overlap_bars < 0:
        raise ValueError("overlap_bars 必须 >= 0")

    normalized_timeframe = timeframe.strip().lower()
    last_dt = _parse_ts(last_ts)
    if normalized_timeframe == "day":
        return (last_dt - timedelta(days=overlap_bars)).strftime("%Y-%m-%d")

    step = _INTRADAY_MINUTES.get(normalized_timeframe)
    if step is None:
        raise ValueError(f"不支持的周期: {timeframe}")
    delta = timedelta(minutes=step * overlap_bars)
    return _format_ts(last_dt - delta, normalized_timeframe)


def tail_rows(rows: list[dict], limit: int | None) -> list[dict]:
    if limit is None or limit <= 0:
        return list(rows)
    if len(rows) <= limit:
        return list(rows)
    return list(rows[-limit:])
