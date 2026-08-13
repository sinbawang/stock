from pathlib import Path

import pytest

from chanlun.segment import StopOutcomeCategory, classify_stop_reason, summarize_stop_reason_outcome
from tests.segment_regression_support import identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCENARIOS = [
    {
        "name": "000591-day",
        "csv_path": ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20230925_to_20260618.csv",
    },
    {
        "name": "00700-30m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260511_to_20260717.csv",
    },
]


@pytest.mark.parametrize("scenario", SMOKE_SCENARIOS, ids=[item["name"] for item in SMOKE_SCENARIOS])
def test_consumer_smoke_dual_mode_category_alignment(scenario: dict[str, object]) -> None:
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    for mode in ("theory", "practical"):
        segments = identify_segments_from_csv(csv_path, termination_mode=mode)
        assert segments, f"no segments for {scenario['name']} in mode={mode}"

        for segment in segments:
            stop_reason = segment.stop_reason
            category = classify_stop_reason(stop_reason)
            summary = summarize_stop_reason_outcome(stop_reason, mode=mode)

            assert category != StopOutcomeCategory.UNKNOWN, (
                f"{scenario['name']} emitted unknown category in mode={mode}: {stop_reason}"
            )

            if category == StopOutcomeCategory.PENDING:
                assert summary["terminal"] is False
                assert summary["should_wait"] is True

            if mode == "theory" and category == StopOutcomeCategory.FALLBACK_CONFIRMED:
                assert summary["bucket"] == "pending"
                assert summary["terminal"] is False


@pytest.mark.parametrize("scenario", SMOKE_SCENARIOS, ids=[item["name"] for item in SMOKE_SCENARIOS])
def test_consumer_smoke_terminal_semantics_follow_mode_contract(scenario: dict[str, object]) -> None:
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)

    practical = identify_segments_from_csv(csv_path, termination_mode="practical")
    theory = identify_segments_from_csv(csv_path, termination_mode="theory")

    assert practical
    assert theory

    for segment in practical:
        category = classify_stop_reason(segment.stop_reason)
        terminal = summarize_stop_reason_outcome(segment.stop_reason, mode="practical")["terminal"]
        assert terminal is (category in {StopOutcomeCategory.THEORY_CONFIRMED, StopOutcomeCategory.FALLBACK_CONFIRMED})

    for segment in theory:
        category = classify_stop_reason(segment.stop_reason)
        terminal = summarize_stop_reason_outcome(segment.stop_reason, mode="theory")["terminal"]
        assert terminal is (category == StopOutcomeCategory.THEORY_CONFIRMED)
