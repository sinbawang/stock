"""导出去包含后的标准化 K 线 CSV。"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.models import Bar
from chanlun.normalize import normalize_bars as library_normalize_bars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出去包含后的标准化 K 线")
    parser.add_argument("--input", required=True, help="输入原始 K 线 CSV")
    parser.add_argument("--output", required=True, help="输出标准化 CSV")
    return parser.parse_args()


def parse_ts(value: str) -> datetime:
    value = value.strip()
    if len(value) == 10:  # date-only: 2025-01-02
        return datetime.strptime(value, "%Y-%m-%d")
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def read_and_clean_bars(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            bars.append(
                Bar(
                    ts=parse_ts(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row.get("volume", 0) or 0)),
                )
            )

    bars.sort(key=lambda item: item.ts)

    deduped: list[RawBar] = []
    seen_ts: set[datetime] = set()
    for bar in bars:
        if bar.ts in seen_ts:
            continue
        if bar.high < bar.low or bar.high < 0 or bar.low < 0:
            continue
        deduped.append(bar)
        seen_ts.add(bar.ts)

    return deduped


def write_rows(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "idx",
                "ts_start",
                "ts_end",
                "ts_high",
                "ts_low",
                "high",
                "low",
                "direction",
                "src_indices",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "idx": row.idx,
                    "ts_start": row.ts_start.strftime("%Y-%m-%d %H:%M"),
                    "ts_end": row.ts_end.strftime("%Y-%m-%d %H:%M"),
                    "ts_high": row.ts_high.strftime("%Y-%m-%d %H:%M"),
                    "ts_low": row.ts_low.strftime("%Y-%m-%d %H:%M"),
                    "high": row.high,
                    "low": row.low,
                    "direction": row.direction,
                    "src_indices": ",".join(str(index) for index in row.src_indices),
                }
            )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    bars = read_and_clean_bars(input_path)
    rows = library_normalize_bars(bars)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(output_path, rows)

    print(f"输入K线: {len(bars)} 根")
    print(f"标准化K线: {len(rows)} 根")
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    main()