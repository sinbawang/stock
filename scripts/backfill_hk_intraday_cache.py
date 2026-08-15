from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.local_bar_store import load_local_rows, merge_rows, upsert_local_rows  # noqa: E402


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            ts = str(row.get("ts") or "").strip()
            if not ts:
                continue
            rows.append(
                {
                    "ts": ts,
                    "open": float(row.get("open") or 0),
                    "high": float(row.get("high") or 0),
                    "low": float(row.get("low") or 0),
                    "close": float(row.get("close") or 0),
                    "volume": int(float(row.get("volume") or 0)),
                }
            )
    rows.sort(key=lambda item: item["ts"])
    return rows


def _run_fetch(
    *,
    symbol: str,
    period: str,
    start: str,
    end: str,
    source: str,
    output: Path,
    timeout_seconds: int,
) -> tuple[bool, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{SRC}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(SRC)

    command = [
        sys.executable,
        "-m",
        "chanlun.data.hk_minute_fetcher",
        "--symbol",
        symbol,
        "--period",
        period,
        "--start",
        start,
        "--end",
        end,
        "--source",
        source,
        "--output",
        str(output),
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout_seconds}s"

    if completed.returncode != 0:
        raw = (completed.stderr or completed.stdout or "").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        tail = " | ".join(lines[-6:]) if lines else "no stderr/stdout"
        return False, f"exit={completed.returncode} {tail}"
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill HK intraday cache before current earliest bar with per-source timeout.")
    parser.add_argument("--symbol", default="01024", help="HK symbol, e.g. 01024")
    parser.add_argument("--timeframe", default="30m", choices=["1m", "5m", "15m", "30m", "60m"], help="Timeframe to backfill")
    parser.add_argument("--start", required=True, help="Backfill start, e.g. 2025-12-01 09:30")
    parser.add_argument("--end", required=True, help="Backfill end, e.g. 2026-05-27 15:00")
    parser.add_argument("--timeout-seconds", type=int, default=90, help="Per-source timeout in seconds")
    parser.add_argument("--sources", nargs="+", default=["xueqiu", "akshare"], choices=["xueqiu", "akshare"], help="Try sources in order")
    args = parser.parse_args()

    period = args.timeframe.replace("m", "")
    staging_root = ROOT / "build" / "backfill"
    staging_root.mkdir(parents=True, exist_ok=True)

    existing = load_local_rows(args.symbol, "HK", args.timeframe)
    existing_first = existing[0]["ts"] if existing else None
    print(f"existing_rows={len(existing)} earliest={existing_first}")

    fetched_total: list[dict] = []
    for source in args.sources:
        output = staging_root / f"{args.symbol}_{args.timeframe}_{source}_{args.start[:10].replace('-', '')}_to_{args.end[:10].replace('-', '')}.csv"
        ok, info = _run_fetch(
            symbol=args.symbol,
            period=period,
            start=args.start,
            end=args.end,
            source=source,
            output=output,
            timeout_seconds=args.timeout_seconds,
        )
        print(f"source={source} status={info}")
        if not ok:
            continue
        if not output.exists():
            print(f"source={source} output_missing={output}")
            continue
        rows = _read_csv_rows(output)
        print(f"source={source} fetched_rows={len(rows)} first={(rows[0]['ts'] if rows else None)} last={(rows[-1]['ts'] if rows else None)}")
        fetched_total.extend(rows)

    if not fetched_total:
        print("backfill_result=no_rows_fetched")
        return

    fetched_total.sort(key=lambda item: item["ts"])
    deduped, _ = merge_rows([], fetched_total)
    merged_rows, stats, store_path = upsert_local_rows(args.symbol, "HK", args.timeframe, deduped)
    merged_first = merged_rows[0]["ts"] if merged_rows else None
    merged_last = merged_rows[-1]["ts"] if merged_rows else None
    print(f"store_path={store_path}")
    print(f"merge_added={stats.added} merge_updated={stats.updated} merge_total={stats.total}")
    print(f"merged_range={merged_first} -> {merged_last}")


if __name__ == "__main__":
    main()
