from pathlib import Path

import pytest

from tests.segment_regression_support import identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    {
        "name": "000591-day",
        "csv_path": ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20230925_to_20260618.csv",
        "expected_stop_reasons": {"reverse_break_after_gap", "feature_sequence_gap_fractal"},
        "min_segments": 8,
        "min_confirmed": 6,
        "min_preprocessing": 1,
    },
    {
        "name": "000591-60m",
        "csv_path": ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20260213_to_20260618.csv",
        "expected_stop_reasons": {"reverse_break"},
        "min_segments": 3,
        "min_confirmed": 3,
        "min_preprocessing": 0,
    },
    {
        "name": "00700-30m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260511_to_20260717.csv",
        "expected_stop_reasons": {"reverse_break", "feature_sequence_fractal"},
        "min_segments": 4,
        "min_confirmed": 4,
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
        "csv_path": ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260511_to_20260717.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "exhausted_confirmed_bis"},
        "min_segments": 3,
        "min_confirmed": 2,
        "min_preprocessing": 1,
    },
    {
        "name": "03690-60m",
        "csv_path": ROOT / "data" / "reports" / "03690" / "60m" / "analyze" / "03690_60m_20260223_to_20260626.csv",
        "expected_stop_reasons": {"feature_sequence_gap_fractal", "reverse_break"},
        "min_segments": 4,
        "min_confirmed": 2,
        "min_preprocessing": 1,
    },
    {
        "name": "300124-15m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "15m" / "analyze" / "300124_15m_20260506_to_20260618.csv",
        "expected_stop_reasons": {"feature_sequence_gap_fractal", "feature_sequence_fractal"},
        "min_segments": 7,
        "min_confirmed": 5,
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
