"""线段识别与映射测试。"""

from datetime import datetime, timedelta

from chanlun.models import Bar, Bi, BiDirection, NormalizedBar
from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    SEGMENT_BOOTSTRAP_AUTO,
    GapCandidateState,
    TransitionState,
    _build_standard_feature_sequence,
    _evaluate_gap_candidate_state,
    _evaluate_transition_state,
    build_segment_tail_interpretations,
    identify_segments as _identify_segments,
)
from chanlun.visualization import Plotter


def identify_segments(bis, **kwargs):
    kwargs.setdefault("bootstrap_mode", SEGMENT_BOOTSTRAP_AUTO)
    kwargs.setdefault("strict_segment_rules", False)
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


class TestIdentifySegments:
    def test_empty_bis(self):
        assert identify_segments([]) == []

    def test_requires_three_bis(self):
        bis = [_bi(0, BiDirection.UP, 110, 100), _bi(1, BiDirection.DOWN, 108, 103)]
        assert identify_segments(bis) == []

    def test_identify_confirmed_up_segment_when_reverse_hits_last_high(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 116, 101),
            _bi(4, BiDirection.UP, 109, 102),
            _bi(5, BiDirection.DOWN, 106, 98),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].start_price == 100
        assert result[0].end_price == 115
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_theory_termination_mode_does_not_confirm_by_fallback_reverse_break(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 116, 101),
            _bi(4, BiDirection.UP, 109, 102),
            _bi(5, BiDirection.DOWN, 106, 98),
        ]

        practical = identify_segments(bis)
        theory = identify_segments(bis, termination_mode="theory")

        assert practical[0].stop_reason == "reverse_break"
        assert practical[0].is_confirmed is True
        assert theory[0].stop_reason != "reverse_break"
        assert theory[0].is_confirmed is False

    def test_theory_termination_mode_does_not_emit_same_direction_fallback(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 108, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 109),
            _bi(4, BiDirection.UP, 110.4, 109.4),
            _bi(5, BiDirection.DOWN, 109.6, 109.0),
            _bi(6, BiDirection.UP, 112.2, 108.4),
            _bi(7, BiDirection.DOWN, 109.0, 107.8),
            _bi(8, BiDirection.UP, 116, 109),
        ]

        theory = identify_segments(bis[:6], termination_mode="theory")

        assert theory[0].is_confirmed is False
        assert theory[0].stop_reason != "same_direction_not_extending"

    def test_theory_termination_mode_does_not_emit_same_direction_slot_fallback(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 103),
            _bi(2, BiDirection.UP, 121, 104),
            _bi(3, BiDirection.UP, 122, 105),
        ]

        theory = identify_segments(bis, termination_mode="theory")

        assert theory[0].is_confirmed is False
        assert theory[0].stop_reason not in {"unexpected_same_direction", "same_direction_slot_not_filled", "same_direction_not_extending"}

    def test_theory_mode_ignores_practical_strict_seed_rule(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 105),
            _bi(2, BiDirection.UP, 119, 106),
        ]

        practical_strict = identify_segments(
            bis,
            strict_segment_rules=True,
            termination_mode="practical",
        )
        theory_strict = identify_segments(
            bis,
            strict_segment_rules=True,
            termination_mode="theory",
        )

        assert practical_strict == []
        assert len(theory_strict) == 1
        assert theory_strict[0].direction == BiDirection.UP
        assert theory_strict[0].bi_ids == [0, 1, 2]

    def test_theory_mode_auto_bootstrap_matches_first_valid_seed(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 105),
            _bi(2, BiDirection.UP, 119, 106),
            _bi(3, BiDirection.DOWN, 116, 104),
            _bi(4, BiDirection.UP, 123, 107),
            _bi(5, BiDirection.DOWN, 117, 103),
        ]

        theory_auto = identify_segments(
            bis,
            termination_mode="theory",
            bootstrap_mode=SEGMENT_BOOTSTRAP_AUTO,
            strict_segment_rules=False,
        )
        theory_prefer = identify_segments(
            bis,
            termination_mode="theory",
            bootstrap_mode=SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
            strict_segment_rules=False,
        )
        theory_first_seed = identify_segments(
            bis,
            termination_mode="theory",
            bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
            strict_segment_rules=False,
        )

        assert [segment.bi_ids for segment in theory_auto] == [segment.bi_ids for segment in theory_first_seed]
        assert [segment.bi_ids for segment in theory_prefer] == [segment.bi_ids for segment in theory_first_seed]

    def test_transition_pending_is_explicit_for_initial_break_without_clear_reclaim(self):
        bis = [
            _bi(0, BiDirection.UP, 100, 90),
            _bi(1, BiDirection.DOWN, 95, 85),
            _bi(2, BiDirection.UP, 105, 95),
            _bi(3, BiDirection.DOWN, 94, 80),
            _bi(4, BiDirection.UP, 96, 87),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].is_confirmed is False
        assert result[0].stop_reason == "transition_pending"

    def test_identify_confirmed_up_segment_after_gap_reverse_fails_to_retake_high(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 106),
            _bi(4, BiDirection.UP, 113, 107),
            _bi(5, BiDirection.DOWN, 112, 102),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_identify_confirmed_down_segment_when_reverse_hits_last_low(self):
        bis = [
            _bi(0, BiDirection.DOWN, 120, 110),
            _bi(1, BiDirection.UP, 118, 112),
            _bi(2, BiDirection.DOWN, 116, 105),
            _bi(3, BiDirection.UP, 117, 104),
            _bi(4, BiDirection.DOWN, 116, 106),
            _bi(5, BiDirection.UP, 121, 108),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.DOWN
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.UP
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_identify_confirmed_down_segment_after_gap_reverse_fails_to_retake_low(self):
        bis = [
            _bi(0, BiDirection.DOWN, 120, 110),
            _bi(1, BiDirection.UP, 118, 112),
            _bi(2, BiDirection.DOWN, 116, 105),
            _bi(3, BiDirection.UP, 117, 106),
            _bi(4, BiDirection.DOWN, 115, 107),
            _bi(5, BiDirection.UP, 119, 108),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.DOWN
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[1].direction == BiDirection.UP
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_requires_overlap_for_initial_three_bis(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 95, 90),
            _bi(2, BiDirection.UP, 115, 105),
        ]

        assert identify_segments(bis) == []

    def test_overlap_only_three_bis_can_start_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 105),
            _bi(2, BiDirection.UP, 119, 106),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is False

    def test_strict_mode_requires_third_bi_directional_advance(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 105),
            _bi(2, BiDirection.UP, 119, 106),
        ]

        normal = identify_segments(bis)
        strict = identify_segments(bis, strict_segment_rules=True)

        assert len(normal) == 1
        assert strict == []

    def test_feature_sequence_fractal_confirms_long_up_segment_earlier(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 112, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 111, 105),
            _bi(4, BiDirection.UP, 126, 107),
            _bi(5, BiDirection.DOWN, 118, 108),
            _bi(6, BiDirection.UP, 130, 109),
            _bi(7, BiDirection.DOWN, 110, 102),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2, 3, 4]
        assert result[0].break_bi_id == 5
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [5, 6, 7]
        assert result[1].is_confirmed is False

    def test_feature_sequence_inclusion_is_normalized_before_fractal_check(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 110, 105),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 107),
            _bi(4, BiDirection.UP, 126, 108),
            _bi(5, BiDirection.DOWN, 111, 107.5),
            _bi(6, BiDirection.UP, 127, 109),
            _bi(7, BiDirection.DOWN, 109, 107.2),
        ]

        result = identify_segments(bis)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids[0] == 2
        assert result[0].break_bi_id == 7
        assert result[0].stop_reason == "reverse_break"
        assert result[0].is_confirmed is True

    def test_theory_feature_sequence_break_takes_priority_over_early_reverse_break(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 112, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 111, 103),
            _bi(4, BiDirection.UP, 126, 107),
            _bi(5, BiDirection.DOWN, 114, 106),
            _bi(6, BiDirection.UP, 130, 108),
            _bi(7, BiDirection.DOWN, 113, 105),
        ]

        result = identify_segments(bis)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids[:3] == [0, 1, 2]
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[0].is_confirmed is True

    def test_gap_feature_sequence_waits_for_opposite_sequence_fractal(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 108, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 109),
            _bi(4, BiDirection.UP, 111.5, 110),
            _bi(5, BiDirection.DOWN, 110, 107),
            _bi(6, BiDirection.UP, 114, 108),
            _bi(7, BiDirection.DOWN, 109, 103),
            _bi(8, BiDirection.UP, 116, 109),
        ]

        result = identify_segments(bis)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids[:3] == [0, 1, 2]
        assert result[0].stop_reason in {"feature_sequence_gap_fractal", "reverse_break"}
        assert result[0].is_confirmed is True

    def test_gap_candidate_state_is_explicitly_deferred_for_local_gap_false(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 108, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 110, 109),
            _bi(4, BiDirection.UP, 115, 110),
            _bi(5, BiDirection.DOWN, 112, 107),
            _bi(6, BiDirection.UP, 114, 108),
        ]

        state, _, _, _, _ = _evaluate_gap_candidate_state(
            bis,
            3,
            should_defer_after_local_gap_false=True,
        )

        assert state == GapCandidateState.DEFERRED

    def test_transition_state_is_pending_until_reclaim_is_confirmed(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 102),
            _bi(4, BiDirection.DOWN, 113, 101),
            _bi(5, BiDirection.DOWN, 112, 100),
        ]

        assert _evaluate_transition_state(bis, 3, BiDirection.UP) == TransitionState.PENDING

    def test_transition_branch_third_pen_breaks_first_pen_end_keeps_new_segment_path(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 99),
            _bi(4, BiDirection.UP, 112, 101),
            _bi(5, BiDirection.DOWN, 111, 98),
            _bi(6, BiDirection.UP, 113, 100),
        ]

        # 对上升前段而言，转折第一笔是向下笔；第三笔继续向下并破第一笔终点，
        # 应视为新段方向得到延续而非回收旧段。
        assert _evaluate_transition_state(bis, 3, BiDirection.UP) == TransitionState.NONE

    def test_transition_branch_third_pen_breaks_first_pen_start_reclaims_prior_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 99),
            _bi(4, BiDirection.UP, 116, 102),
            _bi(5, BiDirection.DOWN, 113, 100),
            _bi(6, BiDirection.UP, 115.5, 101),
        ]

        # 第三笔（向上）先破第一笔起点（向下笔的高点），应回收到前段语义。
        assert _evaluate_transition_state(bis, 3, BiDirection.UP) == TransitionState.RECLAIMED

    def test_feature_sequence_elements_expose_explicit_context(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 110, 105),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 107),
            _bi(4, BiDirection.UP, 126, 108),
            _bi(5, BiDirection.DOWN, 111, 107.5),
        ]

        elements = _build_standard_feature_sequence(bis, [1, 3, 5])

        assert elements
        assert all(element.feature_sequence_id == 1 for element in elements)
        assert elements[0].belongs_to_prior_segment is True
        assert elements[0].belongs_to_new_segment is False
        assert elements[0].in_transition is False
        assert elements[-1].belongs_to_prior_segment is False
        assert elements[-1].belongs_to_new_segment is True

    def test_same_direction_not_extending_can_be_reclaimed_by_prior_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 105),
            _bi(4, BiDirection.UP, 113, 106),
            _bi(5, BiDirection.DOWN, 112, 106.5),
            _bi(6, BiDirection.UP, 116, 107),
        ]

        result = identify_segments(bis)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.DOWN
        assert result[-1].direction == BiDirection.UP
        assert result[-1].stop_reason == "exhausted_confirmed_bis"

    def test_tail_interpretation_is_emitted_for_unconfirmed_tail_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 105),
            _bi(4, BiDirection.UP, 113, 106),
            _bi(5, BiDirection.DOWN, 112, 106.5),
            _bi(6, BiDirection.UP, 116, 107),
        ]

        segments = identify_segments(bis)
        interpretations = build_segment_tail_interpretations(bis, segments)

        assert interpretations
        interpretation = interpretations[-1]
        assert interpretation.segment_id == segments[-1].segment_id
        assert interpretation.kind == "pending_confirmation"
        assert interpretation.confidence in {"low", "medium", "high"}
        assert interpretation.uncertainty
        assert interpretation.suggested_catalyst

    def test_reverse_break_can_be_reclaimed_by_prior_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 102),
            _bi(4, BiDirection.UP, 113, 103),
            _bi(5, BiDirection.DOWN, 112, 103.5),
            _bi(6, BiDirection.UP, 116, 104),
        ]

        result = identify_segments(bis)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.DOWN
        assert result[-1].direction == BiDirection.UP
        assert result[-1].stop_reason == "exhausted_confirmed_bis"

    def test_next_segment_waits_for_fresh_three_bi_seed_after_break(self):
        bis = [
            _bi(0, BiDirection.DOWN, 16.99, 14.96),
            _bi(1, BiDirection.UP, 19.14, 14.96),
            _bi(2, BiDirection.DOWN, 19.14, 17.54),
            _bi(3, BiDirection.UP, 21.58, 17.54),
            _bi(4, BiDirection.DOWN, 21.58, 20.42),
            _bi(5, BiDirection.UP, 24.98, 20.42),
            _bi(6, BiDirection.DOWN, 24.98, 23.92),
            _bi(7, BiDirection.UP, 25.62, 23.92),
            _bi(8, BiDirection.DOWN, 25.62, 23.64),
            _bi(9, BiDirection.UP, 25.18, 23.64),
            _bi(10, BiDirection.DOWN, 25.18, 23.66),
            _bi(11, BiDirection.UP, 25.06, 23.66),
            _bi(12, BiDirection.DOWN, 25.06, 21.58),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [1, 2, 3, 4, 5, 6, 7]
        assert result[0].break_bi_id == 8
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [8, 9, 10]
        assert result[1].break_bi_id == 11
        assert result[1].stop_reason == "reverse_break"
        assert result[1].is_confirmed is True

    def test_extend_unconfirmed_segment_by_rising_pair(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 112, 105),
            _bi(4, BiDirection.UP, 118, 106),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].bi_ids == [1, 2, 3]
        assert result[0].is_confirmed is True
        assert result[0].stop_reason == "reverse_break"
        assert result[0].norm_bar_range == (1, 4)

    def test_ignore_unconfirmed_bis_when_identifying_segments(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 107, 101),
        ]
        bis[-1].is_confirmed = False

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is False


class TestPlotterMapping:
    def test_normalized_index_maps_by_ts_end(self):
        bars = [
            Bar(datetime(2024, 1, 1, 9, 30), 10, 11, 9, 10.5),
            Bar(datetime(2024, 1, 1, 10, 30), 10.5, 11.2, 10.2, 11),
            Bar(datetime(2024, 1, 1, 11, 30), 11, 12, 10.8, 11.5),
            Bar(datetime(2024, 1, 1, 12, 30), 11.5, 11.8, 10.9, 11.1),
            Bar(datetime(2024, 1, 1, 13, 30), 11.1, 12.5, 11.0, 12.2),
        ]
        normalized_bars = [
            NormalizedBar(0, 11.2, 9.0, bars[0].ts, bars[1].ts, src_indices=[0, 1]),
            NormalizedBar(1, 12.0, 10.8, bars[2].ts, bars[2].ts, src_indices=[2]),
            NormalizedBar(2, 12.5, 10.9, bars[3].ts, bars[4].ts, src_indices=[3, 4]),
        ]

        plotter = Plotter()

        assert plotter._normalized_index_to_bar_index(bars, normalized_bars, 0) == 1
        assert plotter._normalized_index_to_bar_index(bars, normalized_bars, 2) == 4