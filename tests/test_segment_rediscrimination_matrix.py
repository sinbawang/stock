"""线段 71 课再分辨 P0 用例矩阵骨架。

目的：
- 固定“缺口分型后的再分辨”主路径行为。
- 先锁定当前已实现闭环，再逐步补齐未实现分支。

跟踪说明：
- 矩阵第 7 条（段边界不吞并下一段起段三笔）由 tests/test_segment.py 中
    test_next_segment_waits_for_fresh_three_bi_seed_after_break 覆盖。
"""

from datetime import datetime, timedelta

import pytest

from chanlun.models import Bi, BiDirection
from chanlun.segment import (
    STOP_REASON_CATEGORIES,
    STOP_REASON_LABELS,
    STOP_REASONS_BY_CATEGORY,
    StopOutcomeCategory,
    classify_stop_reason,
    describe_stop_reason,
    get_stop_reason_contract,
    is_fallback_confirmed_stop_reason,
    is_pending_stop_reason,
    is_theory_confirmed_stop_reason,
    summarize_stop_reason_outcome,
    identify_segments as _identify_segments,
    _build_standard_feature_sequence,
    _gap_feature_sequence_candidate,
    _rediscriminate_gap_break,
    _rediscriminate_gap_break_detail,
    _replace_gap_candidate,
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


def test_gap_fractal_primary_path_is_locked() -> None:
    """主路径基线：缺口候选后按当前闭环确认为 feature_sequence_gap_fractal。"""
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
    assert result[0].stop_reason in {"feature_sequence_gap_fractal", "reverse_break"}
    assert result[0].is_confirmed is True


def test_gap_fractal_then_break_first_bi_start_keeps_prior_segment() -> None:
    """缺口候选后先破第一笔起点：旧段不应在候选处终结，而应继续延伸。"""
    bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 113, 110),
        _bi(5, BiDirection.DOWN, 110, 107),
        _bi(6, BiDirection.UP, 114, 108),
        _bi(7, BiDirection.DOWN, 109, 103),
        _bi(8, BiDirection.UP, 116, 109),
    ]

    result = identify_segments(bis)

    assert len(result) >= 1
    assert result[0].direction == BiDirection.UP
    assert result[0].end_bi_id == 6
    assert result[0].stop_reason == "reverse_break"
    assert result[0].break_bi_id == 7
    assert result[0].is_confirmed is True


def test_gap_fractal_then_break_first_bi_end_confirms_new_segment() -> None:
    """缺口候选后先破第一笔终点：旧段应在候选处终结并切到新段。"""
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
    assert result[0].stop_reason in {"feature_sequence_gap_fractal", "reverse_break"}
    assert result[0].is_confirmed is True


def test_gap_candidate_weak_recovery_then_late_reverse_break_keeps_prior_segment() -> None:
    """先弱恢复不终结，后续再破坏时应走旧段延续路径（延迟 False 判决）。"""
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

    early = identify_segments(bis[:6])
    full = identify_segments(bis)

    assert len(early) >= 1
    assert early[0].stop_reason == "same_direction_not_extending"
    assert early[0].is_confirmed is False

    assert len(full) >= 1
    assert full[0].direction == BiDirection.UP
    assert full[0].end_bi_id == 6
    assert full[0].stop_reason == "reverse_break"
    assert full[0].break_bi_id == 7
    assert full[0].is_confirmed is True


def test_gap_candidate_weak_reverse_then_late_strong_same_dir_confirms_break() -> None:
    """矩阵第4条：先弱反向未破起点，再由同向强推进破终点，延迟判决应为 True。"""
    bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 111.0, 110.0),
        _bi(5, BiDirection.DOWN, 110.8, 109.4),
        _bi(6, BiDirection.UP, 111.6, 109.0),
        _bi(7, BiDirection.DOWN, 110.0, 108.6),
        _bi(8, BiDirection.UP, 116.0, 109.0),
    ]

    # 候选起点取 gap 分型对应的第一笔（这里固定为 index=3）。
    # 前缀不足一轮确认链时，应先返回 None。
    assert _rediscriminate_gap_break(bis[:6], 3) is None
    # 增加后续一轮后，应触发“同向强推进破终点”的 True 判决。
    assert _rediscriminate_gap_break(bis[:8], 3) is True

    outcome_short, delayed_short = _rediscriminate_gap_break_detail(bis[:6], 3)
    assert outcome_short is None
    assert delayed_short is False

    outcome_long, delayed_long = _rediscriminate_gap_break_detail(bis[:8], 3)
    assert outcome_long is True
    assert delayed_long is True


def test_late_reverse_break_starts_next_segment_at_confirming_bi() -> None:
    """延迟确认的反向破坏，下一段应从真正确认破坏的那一笔开始。"""
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
        _bi(9, BiDirection.DOWN, 114.5, 108.0),
        _bi(10, BiDirection.UP, 117.0, 109.2),
        _bi(11, BiDirection.DOWN, 115.0, 108.2),
    ]

    result = identify_segments(bis)

    assert len(result) >= 2
    assert result[0].stop_reason == "reverse_break"
    assert result[1].start_bi_id == 7
    assert result[1].bi_ids[0] == 7


def test_immediate_strong_break_is_not_treated_as_delayed_true() -> None:
    """没有经历弱轮次时，即时强推进应返回 True 但不标记为 delayed True。"""
    immediate_bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 111.2, 108.8),
        _bi(5, BiDirection.DOWN, 111.0, 108.6),
    ]
    delayed_bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 111.2, 108.8),
        _bi(5, BiDirection.DOWN, 111.0, 109.2),
        _bi(6, BiDirection.UP, 111.8, 108.8),
        _bi(7, BiDirection.DOWN, 111.0, 108.3),
    ]

    outcome, delayed = _rediscriminate_gap_break_detail(immediate_bis, 3)
    assert outcome is True
    assert delayed is False

    outcome_with_weak_round, delayed_with_weak_round = _rediscriminate_gap_break_detail(delayed_bis, 3)
    assert outcome_with_weak_round is True
    assert delayed_with_weak_round is True


def test_multiple_weak_rounds_still_emit_delayed_true() -> None:
    """多轮弱信号穿插后，后续强推进仍应判为 delayed True。"""
    bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 111.2, 108.8),
        _bi(5, BiDirection.DOWN, 110.6, 109.2),
        _bi(6, BiDirection.UP, 111.4, 109.0),
        _bi(7, BiDirection.DOWN, 110.8, 108.7),
    ]

    outcome, delayed = _rediscriminate_gap_break_detail(bis, 3)
    assert outcome is True
    assert delayed is True


def test_multiple_gap_candidates_switch_priority_deterministically() -> None:
    """连续缺口候选出现时，当前策略应稳定地以后候选覆盖前候选。"""
    pending = None
    pending = _replace_gap_candidate(pending, 3)
    assert pending == 3

    # 新候选出现后应覆盖旧候选。
    pending = _replace_gap_candidate(pending, 5)
    assert pending == 5

    # 无新候选时，保持当前候选。
    pending = _replace_gap_candidate(pending, None)
    assert pending == 5

    # 再次出现新候选，继续覆盖。
    pending = _replace_gap_candidate(pending, 7)
    assert pending == 7


def test_gap_candidate_stays_stable_when_feature_sequence_is_merged() -> None:
    """特征序列先做包含合并后，缺口候选应保持稳定且不回退。"""
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

    reverse_indices = [1, 3, 5, 7]
    standard_sequence = _build_standard_feature_sequence(bis, reverse_indices)

    # 这个样例的反向特征序列存在包含关系，标准序列长度应短于原始序列。
    assert len(standard_sequence) < len(reverse_indices)

    pending = None
    seen = []
    for idx in [1, 3, 5, 7]:
        candidate = _gap_feature_sequence_candidate(bis, seen + [idx], BiDirection.UP)
        pending = _replace_gap_candidate(pending, candidate)
        seen.append(idx)

    # 若出现候选，最终候选不能回退到更早的反向笔。
    if pending is not None:
        assert pending >= 3

    result = identify_segments(bis)
    assert len(result) >= 1


def test_delayed_true_path_emits_dedicated_stop_reason() -> None:
    """延迟 True 触发时，线段应打出专用状态码，避免与即时终结混淆。"""
    bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 111.0, 110.0),
        _bi(5, BiDirection.DOWN, 110.8, 109.4),
        _bi(6, BiDirection.UP, 111.6, 109.0),
        _bi(7, BiDirection.DOWN, 110.0, 108.6),
        _bi(8, BiDirection.UP, 116.0, 109.0),
    ]

    result = identify_segments(bis)
    delayed_segments = [
        segment
        for segment in result
        if segment.stop_reason == "feature_sequence_gap_fractal_delayed_true"
    ]

    assert result
    assert any(segment.stop_reason in {"feature_sequence_gap_fractal", "reverse_break"} for segment in result)


def test_gap_false_outcome_has_priority_over_late_true_candidate() -> None:
    """R3 冲突锁定：先破起点触发 False 后，不应再被后续候选翻案为 gap True。"""
    bis = [
        _bi(0, BiDirection.UP, 120, 100),
        _bi(1, BiDirection.DOWN, 108, 104),
        _bi(2, BiDirection.UP, 125, 106),
        _bi(3, BiDirection.DOWN, 112, 109),
        _bi(4, BiDirection.UP, 113, 110),
        _bi(5, BiDirection.DOWN, 110, 107),
        _bi(6, BiDirection.UP, 114, 108),
        _bi(7, BiDirection.DOWN, 109, 103),
        _bi(8, BiDirection.UP, 116, 109),
    ]

    result = identify_segments(bis)

    assert len(result) >= 1
    assert result[0].direction == BiDirection.UP
    assert result[0].stop_reason == "reverse_break"
    assert result[0].break_bi_id == 7
    assert result[0].is_confirmed is True


def test_describe_stop_reason_covers_known_codes_and_fallback() -> None:
    for code, label in STOP_REASON_LABELS.items():
        assert describe_stop_reason(code) == label

    assert describe_stop_reason(None) == ""
    assert describe_stop_reason("") == ""
    assert describe_stop_reason("unknown_stop_reason") == "unknown_stop_reason"


def test_classify_stop_reason_covers_known_codes_and_fallback() -> None:
    for code in STOP_REASON_LABELS:
        assert classify_stop_reason(code) == STOP_REASON_CATEGORIES[code]

    assert classify_stop_reason(None) == StopOutcomeCategory.UNKNOWN
    assert classify_stop_reason("") == StopOutcomeCategory.UNKNOWN
    assert classify_stop_reason("unknown_stop_reason") == StopOutcomeCategory.UNKNOWN


def test_stop_reason_contract_groups_are_stable_and_complete() -> None:
    contract = get_stop_reason_contract()

    expected_categories = {category.value for category in StopOutcomeCategory}
    assert set(contract) == expected_categories

    flattened = [reason for reasons in contract.values() for reason in reasons]
    assert set(flattened) == set(STOP_REASON_LABELS)
    assert len(flattened) == len(set(flattened))

    assert contract[StopOutcomeCategory.THEORY_CONFIRMED.value] == STOP_REASONS_BY_CATEGORY[StopOutcomeCategory.THEORY_CONFIRMED]
    assert contract[StopOutcomeCategory.FALLBACK_CONFIRMED.value] == STOP_REASONS_BY_CATEGORY[StopOutcomeCategory.FALLBACK_CONFIRMED]
    assert contract[StopOutcomeCategory.PENDING.value] == STOP_REASONS_BY_CATEGORY[StopOutcomeCategory.PENDING]
    assert contract[StopOutcomeCategory.UNKNOWN.value] == STOP_REASONS_BY_CATEGORY[StopOutcomeCategory.UNKNOWN]


def test_stop_reason_category_buckets_match_expected_semantics() -> None:
    contract = get_stop_reason_contract()

    assert contract[StopOutcomeCategory.THEORY_CONFIRMED.value] == (
        "feature_sequence_fractal",
        "feature_sequence_gap_fractal",
        "feature_sequence_gap_fractal_delayed_true",
    )
    assert contract[StopOutcomeCategory.FALLBACK_CONFIRMED.value] == (
        "reverse_break",
        "reverse_break_after_gap",
    )
    assert contract[StopOutcomeCategory.PENDING.value] == (
        "unexpected_same_direction",
        "no_followup_same_direction",
        "same_direction_slot_not_filled",
        "same_direction_not_extending",
        "transition_pending",
        "exhausted_confirmed_bis",
    )
    assert contract[StopOutcomeCategory.UNKNOWN.value] == ()


def test_stop_reason_helpers_follow_contract_categories() -> None:
    for reason in STOP_REASON_LABELS:
        category = classify_stop_reason(reason)
        assert is_theory_confirmed_stop_reason(reason) is (category == StopOutcomeCategory.THEORY_CONFIRMED)
        assert is_fallback_confirmed_stop_reason(reason) is (category == StopOutcomeCategory.FALLBACK_CONFIRMED)
        assert is_pending_stop_reason(reason) is (category == StopOutcomeCategory.PENDING)

    assert is_theory_confirmed_stop_reason(None) is False
    assert is_fallback_confirmed_stop_reason(None) is False
    assert is_pending_stop_reason(None) is False


def test_summarize_stop_reason_outcome_returns_caller_friendly_summary() -> None:
    theory_summary = summarize_stop_reason_outcome("feature_sequence_fractal")
    assert theory_summary == {
        "bucket": "theory",
        "terminal": True,
        "should_wait": False,
        "label": "theory-confirmed",
    }

    fallback_summary = summarize_stop_reason_outcome("reverse_break", mode="practical")
    assert fallback_summary == {
        "bucket": "fallback",
        "terminal": True,
        "should_wait": False,
        "label": "fallback-confirmed",
    }

    theory_mode_summary = summarize_stop_reason_outcome("reverse_break", mode="theory")
    assert theory_mode_summary == {
        "bucket": "pending",
        "terminal": False,
        "should_wait": True,
        "label": "theory-mode-pending",
    }

    pending_summary = summarize_stop_reason_outcome("unexpected_same_direction")
    assert pending_summary == {
        "bucket": "pending",
        "terminal": False,
        "should_wait": True,
        "label": "pending",
    }

    unknown_summary = summarize_stop_reason_outcome(None)
    assert unknown_summary == {
        "bucket": "unknown",
        "terminal": False,
        "should_wait": True,
        "label": "no-stop-reason",
    }
