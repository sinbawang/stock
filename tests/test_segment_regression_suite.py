from pathlib import Path

import pytest

from chanlun.segment import StopOutcomeCategory, classify_stop_reason
from tests.segment_regression_support import identify_segments_from_csv, load_bis_from_csv


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    {
        "name": "000591-day",
        "csv_path": ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20210902_to_20260818.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break"},
        "min_segments": 3,
        "min_confirmed": 2,
        "min_preprocessing": 0,
    },
    {
        "name": "000591-60m",
        "csv_path": ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20260213_to_20260618.csv",
        "expected_stop_reasons": {"reverse_break"},
        "min_segments": 2,
        "min_confirmed": 2,
        "min_preprocessing": 0,
    },
    {
        "name": "00700-30m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260527_to_20260814.csv",
        "expected_stop_reasons": {"reverse_break", "feature_sequence_gap_fractal", "exhausted_confirmed_bis"},
        "min_segments": 6,
        "min_confirmed": 5,
        "min_preprocessing": 0,
    },
    {
        "name": "00700-60m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "60m" / "analyze" / "00700_60m_20260213_to_20260624.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break"},
        "min_segments": 5,
        "min_confirmed": 5,
        "min_preprocessing": 0,
    },
    {
        "name": "03690-30m",
        "csv_path": ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260527_to_20260814.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "exhausted_confirmed_bis"},
        "min_segments": 5,
        "min_confirmed": 4,
        "min_preprocessing": 1,
    },
    {
        "name": "03690-60m",
        "csv_path": ROOT / "data" / "reports" / "03690" / "60m" / "analyze" / "03690_60m_20260223_to_20260626.csv",
        "expected_stop_reasons": {"same_direction_not_extending", "reverse_break"},
        "min_segments": 2,
        "min_confirmed": 1,
        "min_preprocessing": 1,
    },
    {
        "name": "300124-15m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "15m" / "analyze" / "300124_15m_20260506_to_20260618.csv",
        "expected_stop_reasons": {"feature_sequence_gap_fractal", "same_direction_not_extending"},
        "min_segments": 2,
        "min_confirmed": 1,
        "min_preprocessing": 1,
    },
    {
        "name": "300124-60m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "60m" / "analyze" / "300124_60m_20260213_to_20260618.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break"},
        "min_segments": 5,
        "min_confirmed": 4,
        "min_preprocessing": 1,
    },
]


CROSS_CYCLE_GROUPS = {
    "000591": ["000591-day", "000591-60m"],
    "00700": ["00700-30m", "00700-60m"],
    "03690": ["03690-30m", "03690-60m"],
    "300124": ["300124-15m", "300124-60m"],
}


def _status_summary(segments: list) -> tuple[int, int]:
    confirmed = sum(1 for segment in segments if segment.is_confirmed)
    preprocessing = sum(1 for segment in segments if not segment.is_confirmed)
    return confirmed, preprocessing


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[item["name"] for item in SCENARIOS],
)
def test_regression_suite_fixture_paths_exist(scenario: dict[str, object]) -> None:
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[item["name"] for item in SCENARIOS],
)
def test_regression_suite_key_stop_reasons_are_present(scenario: dict[str, object]) -> None:
    csv_path = scenario["csv_path"]
    expected_stop_reasons = scenario["expected_stop_reasons"]
    min_segments = scenario["min_segments"]
    min_confirmed = scenario["min_confirmed"]
    min_preprocessing = scenario["min_preprocessing"]

    assert isinstance(csv_path, Path)
    assert isinstance(expected_stop_reasons, set)
    assert isinstance(min_segments, int)
    assert isinstance(min_confirmed, int)
    assert isinstance(min_preprocessing, int)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    segments = identify_segments_from_csv(csv_path)
    confirmed, preprocessing = _status_summary(segments)
    status_msg = (
        f"status summary for {csv_path.name}: total={len(segments)}, "
        f"confirmed={confirmed}, preprocessing={preprocessing}"
    )

    assert len(segments) >= min_segments, status_msg
    assert confirmed >= min_confirmed, status_msg
    assert preprocessing >= min_preprocessing, status_msg

    reasons = {segment.stop_reason for segment in segments}
    missing = expected_stop_reasons - reasons
    assert not missing, f"missing stop_reasons: {sorted(missing)} from {csv_path.name}; {status_msg}"


@pytest.mark.parametrize(
    "symbol, scenario_names",
    CROSS_CYCLE_GROUPS.items(),
    ids=[symbol for symbol in CROSS_CYCLE_GROUPS],
)
def test_regression_suite_cross_cycle_stop_category_consistency(
    symbol: str,
    scenario_names: list[str],
) -> None:
    scenario_map = {item["name"]: item for item in SCENARIOS}

    categories = set()
    for scenario_name in scenario_names:
        scenario = scenario_map[scenario_name]
        csv_path = scenario["csv_path"]
        assert isinstance(csv_path, Path)
        assert csv_path.exists(), f"missing fixture csv: {csv_path}"

        segments = identify_segments_from_csv(csv_path)
        assert segments, f"no segments for {scenario_name}"

        for segment in segments:
            category = classify_stop_reason(segment.stop_reason)
            assert category != StopOutcomeCategory.UNKNOWN, (
                f"unknown stop category for {symbol} {scenario_name}: {segment.stop_reason}"
            )
            categories.add(category)

    assert StopOutcomeCategory.THEORY_CONFIRMED in categories, (
        f"{symbol} cross-cycle fixtures lost theory_confirmed coverage"
    )
    assert StopOutcomeCategory.FALLBACK_CONFIRMED in categories, (
        f"{symbol} cross-cycle fixtures lost fallback_confirmed coverage"
    )


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[item["name"] for item in SCENARIOS],
)
def test_regression_suite_dual_mode_has_no_unknown_stop_category(scenario: dict[str, object]) -> None:
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    for mode in ("theory", "practical"):
        segments = identify_segments_from_csv(csv_path, termination_mode=mode)
        assert segments, f"no segments in {mode} mode for {csv_path.name}"
        for segment in segments:
            category = classify_stop_reason(segment.stop_reason)
            assert category != StopOutcomeCategory.UNKNOWN, (
                f"unknown stop category in {mode} mode for {csv_path.name}: {segment.stop_reason}"
            )


KEY_LANDMARK_SCENARIOS = [
    "00700-60m",
    "300124-60m",
]


@pytest.mark.parametrize("scenario_name", KEY_LANDMARK_SCENARIOS)
def test_regression_suite_key_landmarks_do_not_collapse_to_single_overlong_segment(
    scenario_name: str,
) -> None:
    scenario_map = {item["name"]: item for item in SCENARIOS}
    scenario = scenario_map[scenario_name]
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    bis = load_bis_from_csv(csv_path)
    assert bis, f"no bis in fixture: {csv_path.name}"
    total_bis = len(bis)

    for mode in ("theory", "practical"):
        segments = identify_segments_from_csv(csv_path, termination_mode=mode)
        assert len(segments) >= 2, (
            f"{scenario_name} collapsed to <2 segments in {mode} mode"
        )

        longest_segment_len = max(len(segment.bi_ids) for segment in segments)
        assert longest_segment_len < total_bis, (
            f"{scenario_name} collapsed to one overlong segment in {mode} mode: "
            f"longest={longest_segment_len}, total_bis={total_bis}"
        )


def test_00700_60m_practical_keeps_post_seed_feature_sequence_fractal() -> None:
    scenario = next(item for item in SCENARIOS if item["name"] == "00700-60m")
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    practical_segments = identify_segments_from_csv(csv_path, termination_mode="practical")

    assert len(practical_segments) >= 3
    third = practical_segments[2]
    assert third.start_bi_id == 6
    assert third.end_bi_id == 10
    assert third.direction.value == "down"
    assert third.is_confirmed is True
    assert third.stop_reason == "feature_sequence_fractal"


def test_00700_60m_reverse_break_restart_anchor_survives_latent_reclaim() -> None:
    scenario = next(item for item in SCENARIOS if item["name"] == "00700-60m")
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    practical_segments = identify_segments_from_csv(csv_path, termination_mode="practical")

    assert len(practical_segments) >= 5
    fourth = practical_segments[3]
    fifth = practical_segments[4]

    assert fourth.direction.value == "up"
    assert fourth.stop_reason == "reverse_break"
    assert fourth.break_bi_id == 16
    assert fourth.end_bi_id == 15
    assert fifth.start_bi_id == fourth.break_bi_id


def test_300124_60m_keeps_mixed_overlap_and_restart_anchors() -> None:
    scenario = next(item for item in SCENARIOS if item["name"] == "300124-60m")
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    practical_segments = identify_segments_from_csv(csv_path, termination_mode="practical")

    assert len(practical_segments) >= 5
    second = practical_segments[1]
    third = practical_segments[2]
    fourth = practical_segments[3]
    fifth = practical_segments[4]

    assert second.direction.value == "up"
    assert second.end_bi_id == 8
    assert second.break_bi_id == 11
    assert second.stop_reason == "reverse_break"
    assert third.direction.value == "down"
    assert third.start_bi_id == 9
    assert 11 in third.bi_ids
    assert third.break_bi_id == 12
    assert third.stop_reason == "reverse_break"
    assert fourth.direction.value == "up"
    assert fourth.start_bi_id == third.break_bi_id
    assert fourth.break_bi_id == 17
    assert fourth.stop_reason == "reverse_break"
    assert fifth.direction.value == "down"
    assert fifth.start_bi_id == fourth.break_bi_id
    assert fifth.start_bi_id == 17
    assert fifth.break_bi_id == 20
