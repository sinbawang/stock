"""输出指定时间段的包含处理逐步演算。"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.models import Bar
from chanlun.normalize import has_inclusion, merge_bars


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def build_temp_bar(high: float, low: float, ts_end: datetime) -> Bar:
    return Bar(ts=ts_end, open=high, high=high, low=low, close=low, volume=0)


def infer_direction(bar_a: Bar, bar_b: Bar) -> str | None:
    if bar_a.high < bar_b.high and bar_a.low < bar_b.low:
        return "up"
    if bar_a.high > bar_b.high and bar_a.low > bar_b.low:
        return "down"
    return None


def outer_union(bar_a: Bar, bar_b: Bar) -> tuple[float, float]:
    return max(bar_a.high, bar_b.high), min(bar_a.low, bar_b.low)


def fmt_bar(bar: Bar) -> str:
    return f"{bar.ts.strftime('%m-%d %H:%M')}[{bar.high:.2f},{bar.low:.2f}]"


def load_bars(path: Path, start_ts: datetime, end_ts: datetime) -> list[Bar]:
    bars: list[Bar] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts = parse_ts(row["ts"])
            if start_ts <= ts <= end_ts:
                bars.append(
                    Bar(
                        ts=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(float(row.get("volume", 0) or 0)),
                    )
                )
    return bars


def trace_segment(bars: list[Bar]) -> None:
    print("RAW BARS")
    for index, bar in enumerate(bars):
        print(f"{index}: {bar.ts.strftime('%Y-%m-%d %H:%M')} high={bar.high:.2f} low={bar.low:.2f}")

    print("\nTRACE")
    current_high = bars[0].high
    current_low = bars[0].low
    current_ts_start = bars[0].ts
    current_ts_end = bars[0].ts
    current_direction: str | None = None
    src_indices = [0]
    pending = [bars[0]]

    print(f"start pending={[fmt_bar(bar) for bar in pending]} dir={current_direction}")

    for index in range(1, len(bars)):
        bar = bars[index]
        temp = build_temp_bar(current_high, current_low, current_ts_end)
        a_contains_b = has_inclusion(temp, bar)
        b_contains_a = has_inclusion(bar, temp)

        print(f"\nstep {index}: incoming {fmt_bar(bar)}")
        print(
            f"  temp={fmt_bar(temp)} dir={current_direction} "
            f"a_contains_b={a_contains_b} b_contains_a={b_contains_a}"
        )

        if a_contains_b or b_contains_a:
            pending.append(bar)
            src_indices.append(index)

            if current_direction is None:
                current_high, current_low = outer_union(temp, bar)
                current_ts_end = bar.ts
                print(
                    f"  direction unresolved -> pending union [{current_high:.2f},{current_low:.2f}] "
                    f"pending={[fmt_bar(item) for item in pending]}"
                )
                continue

            merged_high, merged_low = merge_bars(temp, bar, current_direction)
            current_high = merged_high
            current_low = merged_low
            current_ts_end = bar.ts
            print(f"  merge by dir={current_direction} -> [{merged_high:.2f},{merged_low:.2f}]")
            print(f"  pending now={[fmt_bar(item) for item in pending]}")
            continue

        inferred = infer_direction(temp, bar)
        print(f"  no inclusion; inferred_direction from temp vs incoming = {inferred}")

        if current_direction is None and inferred is not None:
            current_direction = inferred
            print(f"  resolve pending chain with dir={current_direction}")
            replay_high = pending[0].high
            replay_low = pending[0].low
            replay_end = pending[0].ts
            print(f"    replay start {fmt_bar(pending[0])}")
            for pending_bar in pending[1:]:
                replay_temp = build_temp_bar(replay_high, replay_low, replay_end)
                replay_high, replay_low = merge_bars(replay_temp, pending_bar, current_direction)
                replay_end = pending_bar.ts
                print(f"    replay merge {fmt_bar(pending_bar)} -> [{replay_high:.2f},{replay_low:.2f}]")
            current_high = replay_high
            current_low = replay_low
            current_ts_end = replay_end
            print(
                f"  resolved current standardized bar = [{current_high:.2f},{current_low:.2f}] "
                f"from pending {[fmt_bar(item) for item in pending]}"
            )

        print(
            f"  emit standardized bar: ts_start={current_ts_start.strftime('%m-%d %H:%M')} "
            f"ts_end={current_ts_end.strftime('%m-%d %H:%M')} high={current_high:.2f} "
            f"low={current_low:.2f} dir={current_direction} src_indices={src_indices}"
        )

        current_direction = infer_direction(build_temp_bar(current_high, current_low, current_ts_end), bar)
        print(f"  reset with incoming bar; next dir baseline={current_direction}")

        current_high = bar.high
        current_low = bar.low
        current_ts_start = bar.ts
        current_ts_end = bar.ts
        src_indices = [index]
        pending = [bar]

    print(
        f"\nfinal pending emit: ts_start={current_ts_start.strftime('%m-%d %H:%M')} "
        f"ts_end={current_ts_end.strftime('%m-%d %H:%M')} high={current_high:.2f} "
        f"low={current_low:.2f} dir={current_direction} src_indices={src_indices}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="追踪一段 K 线的包含处理过程")
    parser.add_argument("--input", required=True, help="原始 K 线 CSV")
    parser.add_argument("--start", required=True, help="起始时间，如 2026-02-04 15:00")
    parser.add_argument("--end", required=True, help="结束时间，如 2026-02-06 14:00")
    args = parser.parse_args()

    bars = load_bars(Path(args.input), parse_ts(args.start), parse_ts(args.end))
    trace_segment(bars)


if __name__ == "__main__":
    main()