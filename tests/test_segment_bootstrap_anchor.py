"""线段起点锚定策略测试。"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from chanlun.models import Bi, BiDirection
from chanlun.segment import (
    DEFAULT_SEGMENT_BOOTSTRAP_MODE,
    SEGMENT_BOOTSTRAP_AUTO,
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE,
    StopOutcomeCategory,
    classify_stop_reason,
    identify_segments as _identify_segments,
)
from tests.segment_regression_support import load_bis_from_csv


def identify_segments(bis, **kwargs):
    kwargs.setdefault("termination_mode", "practical")
    return _identify_segments(bis, **kwargs)


def _bi(bi_id: int, direction: BiDirection, high: float, low: float) -> Bi:
    start = datetime(2024, 1, 1) + timedelta(hours=bi_id)
    end = start + timedelta(minutes=30)
    return Bi(
        bi_id=bi_id,
        direction=direction,
        start_fx_id=bi_id,
        end_fx_id=bi_id + 1,
        start_ts=start,
        end_ts=end,
        high=high,
        low=low,
        norm_bar_range=(bi_id, bi_id + 1),
        is_confirmed=True,
    )


def _sample_bis() -> list[Bi]:
    # 这组笔在左侧和中段都可形成三笔种子，用于 A/B 对照起点锚定差异。
    return [
        _bi(0, BiDirection.UP, 110, 100),
        _bi(1, BiDirection.DOWN, 109, 103),
        _bi(2, BiDirection.UP, 114, 104),
        _bi(3, BiDirection.DOWN, 113, 106),
        _bi(4, BiDirection.UP, 116, 107),
        _bi(5, BiDirection.DOWN, 115, 108),
        _bi(6, BiDirection.UP, 117, 109),
        _bi(7, BiDirection.DOWN, 116, 110),
        _bi(8, BiDirection.UP, 118, 111),
    ]


def test_default_bootstrap_mode_matches_prefer_earlier_start() -> None:
    bis = _sample_bis()

    baseline = identify_segments(bis)
    explicit_default = identify_segments(
        bis,
        bootstrap_mode=DEFAULT_SEGMENT_BOOTSTRAP_MODE,
        bootstrap_skip_confirmed_bis=0,
    )

    assert baseline
    assert [segment.bi_ids for segment in baseline] == [segment.bi_ids for segment in explicit_default]


def test_invalid_bootstrap_mode_raises_value_error() -> None:
    bis = _sample_bis()

    with pytest.raises(ValueError, match="Unsupported bootstrap_mode"):
        identify_segments(bis, bootstrap_mode="invalid_mode")


def test_negative_bootstrap_skip_count_raises_value_error() -> None:
    bis = _sample_bis()

    with pytest.raises(ValueError, match="bootstrap_skip_confirmed_bis"):
        identify_segments(bis, bootstrap_skip_confirmed_bis=-1)


def test_skip_left_edge_bootstrap_moves_first_seed_right() -> None:
    bis = _sample_bis()

    baseline = identify_segments(bis)
    anchored = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE,
        bootstrap_skip_confirmed_bis=3,
    )

    assert baseline
    assert anchored
    assert anchored[0].start_bi_id > baseline[0].start_bi_id
    assert anchored[0].bi_ids[0] >= 3


def test_auto_bootstrap_can_keep_leftmost_pending_seed_without_manual_skip() -> None:
    bis = [
        _bi(0, BiDirection.UP, 10.0, 9.0),
        _bi(1, BiDirection.DOWN, 10.0, 8.0),
        _bi(2, BiDirection.UP, 11.0, 8.5),
        _bi(3, BiDirection.DOWN, 10.5, 8.0),
        _bi(4, BiDirection.UP, 10.5, 8.5),
        _bi(5, BiDirection.DOWN, 11.0, 8.0),
        _bi(6, BiDirection.UP, 12.0, 9.0),
        _bi(7, BiDirection.DOWN, 13.0, 8.5),
        _bi(8, BiDirection.UP, 13.5, 9.0),
    ]

    segments = identify_segments(bis, bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO)

    assert segments
    assert segments[0].start_bi_id == 0
    assert segments[0].is_confirmed is False
    assert segments[0].stop_reason == "exhausted_confirmed_bis"


def test_first_valid_seed_bypasses_scored_bootstrap_optimization() -> None:
    bis = [
        _bi(0, BiDirection.UP, 10.0, 9.0),
        _bi(1, BiDirection.DOWN, 10.0, 8.0),
        _bi(2, BiDirection.UP, 11.0, 8.5),
        _bi(3, BiDirection.DOWN, 10.5, 8.0),
        _bi(4, BiDirection.UP, 10.5, 8.5),
        _bi(5, BiDirection.DOWN, 11.0, 8.0),
        _bi(6, BiDirection.UP, 12.0, 9.0),
        _bi(7, BiDirection.DOWN, 13.0, 8.5),
        _bi(8, BiDirection.UP, 13.5, 9.0),
    ]

    auto_segments = identify_segments(bis, bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO)
    first_seed_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    )

    assert auto_segments
    assert first_seed_segments
    assert auto_segments[0].start_bi_id >= first_seed_segments[0].start_bi_id
    assert first_seed_segments[0].start_bi_id == 0


def test_prefer_earlier_start_biases_left_within_near_best_quality() -> None:
    bis = [
        _bi(0, BiDirection.UP, 10.0, 9.0),
        _bi(1, BiDirection.DOWN, 10.0, 8.0),
        _bi(2, BiDirection.UP, 11.0, 8.5),
        _bi(3, BiDirection.DOWN, 10.5, 8.0),
        _bi(4, BiDirection.UP, 10.5, 8.5),
        _bi(5, BiDirection.DOWN, 11.0, 8.0),
        _bi(6, BiDirection.UP, 12.0, 9.0),
        _bi(7, BiDirection.DOWN, 13.0, 8.5),
        _bi(8, BiDirection.UP, 13.5, 9.0),
    ]

    auto_segments = identify_segments(bis, bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO)
    preferred_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    )

    assert auto_segments
    assert preferred_segments
    assert preferred_segments[0].start_bi_id <= auto_segments[0].start_bi_id


@pytest.mark.parametrize(
    ("mode", "expected_direction"),
    [
        (SEGMENT_BOOTSTRAP_AUTO, BiDirection.UP),
        (SEGMENT_BOOTSTRAP_PREFER_EARLIER_START, BiDirection.UP),
    ],
)
def test_scored_bootstrap_modes_keep_left_pending_segment_over_later_confirmed_seed(
    mode: str,
    expected_direction: BiDirection,
) -> None:
    bis = [
        _bi(0, BiDirection.UP, 100, 90),
        _bi(1, BiDirection.DOWN, 95, 85),
        _bi(2, BiDirection.UP, 105, 95),
        _bi(3, BiDirection.DOWN, 96, 80),
        _bi(4, BiDirection.UP, 94, 86),
        _bi(5, BiDirection.DOWN, 98, 81),
        _bi(6, BiDirection.UP, 96, 87),
    ]

    segments = identify_segments(bis, bootstrap_mode=mode)

    assert segments
    assert segments[0].start_bi_id == 0
    assert segments[0].direction == expected_direction
    assert segments[0].is_confirmed is False
    assert segments[0].stop_reason != "reverse_break"


@pytest.mark.parametrize("mode", [SEGMENT_BOOTSTRAP_AUTO, SEGMENT_BOOTSTRAP_PREFER_EARLIER_START])
def test_scored_bootstrap_modes_keep_left_reclaiming_segment_over_later_confirmed_seed(
    mode: str,
) -> None:
    bis = [
        _bi(0, BiDirection.UP, 110, 100),
        _bi(1, BiDirection.DOWN, 108, 103),
        _bi(2, BiDirection.UP, 115, 104),
        _bi(3, BiDirection.DOWN, 114, 105),
        _bi(4, BiDirection.UP, 113, 106),
        _bi(5, BiDirection.DOWN, 112, 106.5),
        _bi(6, BiDirection.UP, 116, 107),
    ]

    segments = identify_segments(bis, bootstrap_mode=mode)

    assert segments
    assert segments[0].start_bi_id == 0
    assert segments[0].direction == BiDirection.UP
    assert segments[0].is_confirmed is False


def test_bootstrap_modes_do_not_introduce_unknown_stop_categories() -> None:
    bis = _sample_bis()
    modes = [
        DEFAULT_SEGMENT_BOOTSTRAP_MODE,
        SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        SEGMENT_BOOTSTRAP_AUTO,
        SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
        SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE,
    ]

    for mode in modes:
        kwargs = {"bootstrap_mode": mode}
        if mode == SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE:
            kwargs["bootstrap_skip_confirmed_bis"] = 1
        segments = identify_segments(bis, **kwargs)
        assert segments
        for segment in segments:
            category = classify_stop_reason(segment.stop_reason)
            assert category != StopOutcomeCategory.UNKNOWN, (
                f"unknown stop category under bootstrap_mode={mode}: {segment.stop_reason}"
            )


@pytest.mark.parametrize(
    "csv_path",
    [
        Path(r"c:\sandbox\sinba\stock\data\reports\000591\day\analyze\000591_day_20210902_to_20260818.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\000591\60m\analyze\000591_60m_20260213_to_20260618.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\300124\15m\analyze\300124_15m_20260506_to_20260618.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\300124\60m\analyze\300124_60m_20260213_to_20260618.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\00700\30m\analyze\00700_30m_20260527_to_20260814.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\00700\60m\analyze\00700_60m_20260213_to_20260624.csv"),
        Path(r"c:\sandbox\sinba\stock\data\reports\03690\30m\analyze\03690_30m_20260527_to_20260814.csv"),
    ],
    ids=["000591-day", "000591-60m", "300124-15m", "300124-60m", "00700-30m", "00700-60m", "03690-30m"],
)
def test_preferred_bootstrap_keeps_left_seed_on_real_fixtures(csv_path: Path) -> None:
    bis = load_bis_from_csv(csv_path)

    first_seed_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    )
    auto_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO,
    )
    preferred_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    )

    assert first_seed_segments
    assert auto_segments
    assert preferred_segments
    assert preferred_segments[0].start_bi_id == first_seed_segments[0].start_bi_id
    assert preferred_segments[0].direction == first_seed_segments[0].direction
    assert auto_segments[0].start_bi_id == preferred_segments[0].start_bi_id
    assert auto_segments[0].direction == preferred_segments[0].direction


def test_practical_stop_outcome_is_stable_across_bootstrap_modes_on_000591_60m_fixture() -> None:
    csv_path = Path(r"c:\sandbox\sinba\stock\data\reports\000591\60m\analyze\000591_60m_20260213_to_20260618.csv")
    bis = load_bis_from_csv(csv_path)

    first_seed_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    )
    auto_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO,
    )
    preferred_segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    )

    assert first_seed_segments
    assert auto_segments
    assert preferred_segments
    assert first_seed_segments[0].start_bi_id == auto_segments[0].start_bi_id == preferred_segments[0].start_bi_id
    assert first_seed_segments[0].end_bi_id == auto_segments[0].end_bi_id == preferred_segments[0].end_bi_id
    assert first_seed_segments[0].is_confirmed == auto_segments[0].is_confirmed == preferred_segments[0].is_confirmed
    assert first_seed_segments[0].stop_reason == auto_segments[0].stop_reason == preferred_segments[0].stop_reason
