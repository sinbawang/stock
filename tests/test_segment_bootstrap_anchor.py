"""线段起点锚定策略测试。"""

from datetime import datetime, timedelta

import pytest

from chanlun.models import Bi, BiDirection
from chanlun.segment import (
    DEFAULT_SEGMENT_BOOTSTRAP_MODE,
    SEGMENT_BOOTSTRAP_AUTO,
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE,
    identify_segments as _identify_segments,
)


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


def test_auto_bootstrap_selects_coherent_seed_without_manual_skip() -> None:
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
    assert segments[0].start_bi_id > 0


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
