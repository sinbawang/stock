from __future__ import annotations

import pytest

from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    StopOutcomeCategory,
    classify_stop_reason,
    identify_segments,
)
from tests.segment_lesson_boundary_fixtures import get_lesson_boundary_cases


LESSON_CASES = get_lesson_boundary_cases()


@pytest.mark.parametrize("case", LESSON_CASES, ids=[case.name for case in LESSON_CASES])
@pytest.mark.parametrize("mode", ["theory", "practical"])
def test_lesson_boundary_fixtures_are_stable_across_modes(case, mode: str) -> None:
    segments = identify_segments(
        case.bis,
        termination_mode=mode,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        strict_segment_rules=False,
    )

    assert segments, f"{case.name} produced no segments in mode={mode}"
    expected_min = case.expected_min_segments_theory if mode == "theory" else case.expected_min_segments_practical
    assert len(segments) >= expected_min, (
        f"{case.name} segment count in mode={mode} is below baseline: "
        f"actual={len(segments)}, expected_min={expected_min}"
    )

    first = segments[0]
    expected_reason = (
        case.expected_first_stop_reason_practical
        if mode == "practical" and case.expected_first_stop_reason_practical
        else case.expected_first_stop_reason
    )
    assert first.stop_reason == expected_reason
    assert first.is_confirmed is case.expected_first_confirmed

    for segment in segments:
        category = classify_stop_reason(segment.stop_reason)
        assert category != StopOutcomeCategory.UNKNOWN, (
            f"{case.name} produced unknown stop category in mode={mode}: {segment.stop_reason}"
        )


def test_lesson78_practical_is_not_shorter_than_theory() -> None:
    lesson78 = next(case for case in LESSON_CASES if case.lesson == 78)
    practical_segments = identify_segments(
        lesson78.bis,
        termination_mode="practical",
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        strict_segment_rules=False,
    )
    theory_segments = identify_segments(
        lesson78.bis,
        termination_mode="theory",
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        strict_segment_rules=False,
    )

    assert len(practical_segments) >= len(theory_segments)
