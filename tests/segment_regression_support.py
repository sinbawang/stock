from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import SEGMENT_BOOTSTRAP_FIRST_VALID_SEED, identify_segments


@dataclass(frozen=True)
class LandmarkDiff:
    added: list[tuple[Any, ...]]
    removed: list[tuple[Any, ...]]
    first_mismatch_index: int | None
    expected_at_mismatch: tuple[Any, ...] | None
    actual_at_mismatch: tuple[Any, ...] | None
    start_bi_shift: int | None
    end_bi_shift: int | None
    net_added_count: int
    net_removed_count: int
    added_stop_reasons: list[tuple[str, int]]
    removed_stop_reasons: list[tuple[str, int]]


def _extract_bi_span(landmark: tuple[Any, ...] | None) -> tuple[int, int] | None:
    if landmark is None or len(landmark) < 3:
        return None
    start_bi = landmark[1]
    end_bi = landmark[2]
    if not isinstance(start_bi, int) or not isinstance(end_bi, int):
        return None
    return start_bi, end_bi


def _extract_stop_reason(landmark: tuple[Any, ...]) -> str | None:
    if len(landmark) < 4:
        return None
    reason = landmark[3]
    if not isinstance(reason, str):
        return None
    return reason


def summarize_landmark_diff(expected: list[tuple[Any, ...]], actual: list[tuple[Any, ...]]) -> LandmarkDiff:
    expected_counter = Counter(expected)
    actual_counter = Counter(actual)

    added: list[tuple[Any, ...]] = []
    removed: list[tuple[Any, ...]] = []

    for item, count in (actual_counter - expected_counter).items():
        added.extend([item] * count)
    for item, count in (expected_counter - actual_counter).items():
        removed.extend([item] * count)

    first_mismatch_index: int | None = None
    expected_at_mismatch: tuple[Any, ...] | None = None
    actual_at_mismatch: tuple[Any, ...] | None = None
    max_len = max(len(expected), len(actual))
    for idx in range(max_len):
        left = expected[idx] if idx < len(expected) else None
        right = actual[idx] if idx < len(actual) else None
        if left != right:
            first_mismatch_index = idx
            expected_at_mismatch = left
            actual_at_mismatch = right
            break

    start_bi_shift: int | None = None
    end_bi_shift: int | None = None
    expected_span = _extract_bi_span(expected_at_mismatch)
    actual_span = _extract_bi_span(actual_at_mismatch)
    if expected_span is not None and actual_span is not None:
        start_bi_shift = actual_span[0] - expected_span[0]
        end_bi_shift = actual_span[1] - expected_span[1]

    added_reason_counter = Counter(
        reason for reason in (_extract_stop_reason(item) for item in added) if reason
    )
    removed_reason_counter = Counter(
        reason for reason in (_extract_stop_reason(item) for item in removed) if reason
    )

    return LandmarkDiff(
        added=sorted(added, key=str),
        removed=sorted(removed, key=str),
        first_mismatch_index=first_mismatch_index,
        expected_at_mismatch=expected_at_mismatch,
        actual_at_mismatch=actual_at_mismatch,
        start_bi_shift=start_bi_shift,
        end_bi_shift=end_bi_shift,
        net_added_count=len(added),
        net_removed_count=len(removed),
        added_stop_reasons=sorted(added_reason_counter.items()),
        removed_stop_reasons=sorted(removed_reason_counter.items()),
    )


def format_landmark_diff(diff: LandmarkDiff) -> str:
    if not diff.added and not diff.removed and diff.first_mismatch_index is None:
        return "no landmark diff"

    lines = ["landmark diff summary:"]
    lines.append(f"- net added/removed: +{diff.net_added_count}/-{diff.net_removed_count}")
    if diff.first_mismatch_index is not None:
        lines.append(f"- first mismatch index: {diff.first_mismatch_index}")
        lines.append(f"- expected: {diff.expected_at_mismatch}")
        lines.append(f"- actual:   {diff.actual_at_mismatch}")
        if diff.start_bi_shift is not None and diff.end_bi_shift is not None:
            lines.append(f"- shift(start_bi/end_bi): {diff.start_bi_shift:+d}/{diff.end_bi_shift:+d}")
    if diff.added:
        lines.append(f"- added ({len(diff.added)}):")
        lines.extend(f"  + {item}" for item in diff.added)
    if diff.added_stop_reasons:
        lines.append("- added stop_reasons:")
        lines.extend(f"  + {reason}: {count}" for reason, count in diff.added_stop_reasons)
    if diff.removed:
        lines.append(f"- removed ({len(diff.removed)}):")
        lines.extend(f"  - {item}" for item in diff.removed)
    if diff.removed_stop_reasons:
        lines.append("- removed stop_reasons:")
        lines.extend(f"  - {reason}: {count}" for reason, count in diff.removed_stop_reasons)
    return "\n".join(lines)


def assert_landmarks_equal(expected: list[tuple[Any, ...]], actual: list[tuple[Any, ...]]) -> None:
    diff = summarize_landmark_diff(expected, actual)
    assert actual == expected, format_landmark_diff(diff)


def identify_segments_from_csv(path: Path):
    bars = clean_bars(read_bars_from_csv(str(path)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="any")
    return identify_segments(bis, bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED)
