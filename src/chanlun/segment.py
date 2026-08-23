"""线段识别。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .models import Bi, BiDirection, Segment, SegmentTailInterpretation


STOP_REASON_LABELS = {
    "feature_sequence_fractal": "反向特征序列已形成无缺口分型，旧线段在该极值处终结",
    "feature_sequence_gap_fractal": "反向特征序列形成缺口分型，等待后续再分辨确认旧线段终结",
    "feature_sequence_gap_fractal_delayed_true": "缺口分型经历至少一轮弱同向未突破后，由更晚一轮同向强推进确认终结",
    "reverse_break": "反向笔直接突破最近关键低/高点，旧线段立即确认终结",
    "reverse_break_after_gap": "缺口候选后，后续反向扩张再次破坏关键点，旧线段确认终结",
    "unexpected_same_direction": "在预期反向位置直接出现同向笔，当前线段停止扩展",
    "no_followup_same_direction": "出现反向回撤后，没有等到后续同向推进笔",
    "same_direction_slot_not_filled": "按两笔一组的节奏，预期同向推进笔未出现",
    "same_direction_not_extending": "出现同向笔，但没有继续创新高或新低",
    "transition_pending": "初始反向笔已破坏前线段，但后续回拉/重合尚未形成明确的新线段，先进入待确认过渡态",
    "exhausted_confirmed_bis": "已用尽确认笔序列，线段尾部暂时停住",
}


class StopOutcomeCategory(str, Enum):
    THEORY_CONFIRMED = "theory_confirmed"
    FALLBACK_CONFIRMED = "fallback_confirmed"
    PENDING = "pending"
    UNKNOWN = "unknown"


STOP_REASON_CATEGORIES = {
    "feature_sequence_fractal": StopOutcomeCategory.THEORY_CONFIRMED,
    "feature_sequence_gap_fractal": StopOutcomeCategory.THEORY_CONFIRMED,
    "feature_sequence_gap_fractal_delayed_true": StopOutcomeCategory.THEORY_CONFIRMED,
    "reverse_break": StopOutcomeCategory.FALLBACK_CONFIRMED,
    "reverse_break_after_gap": StopOutcomeCategory.FALLBACK_CONFIRMED,
    "unexpected_same_direction": StopOutcomeCategory.PENDING,
    "no_followup_same_direction": StopOutcomeCategory.PENDING,
    "same_direction_slot_not_filled": StopOutcomeCategory.PENDING,
    "same_direction_not_extending": StopOutcomeCategory.PENDING,
    "transition_pending": StopOutcomeCategory.PENDING,
    "exhausted_confirmed_bis": StopOutcomeCategory.PENDING,
}

STOP_REASONS_BY_CATEGORY = {
    category: tuple(
        reason
        for reason in STOP_REASON_LABELS
        if STOP_REASON_CATEGORIES.get(reason) == category
    )
    for category in StopOutcomeCategory
}

THEORY_STOP_REASONS = {
    reason for reason in STOP_REASON_LABELS if STOP_REASON_CATEGORIES.get(reason) == StopOutcomeCategory.THEORY_CONFIRMED
}
FALLBACK_STOP_REASONS = {
    reason for reason in STOP_REASON_LABELS if STOP_REASON_CATEGORIES.get(reason) == StopOutcomeCategory.FALLBACK_CONFIRMED
}
PENDING_STOP_REASONS = {
    reason for reason in STOP_REASON_LABELS if STOP_REASON_CATEGORIES.get(reason) == StopOutcomeCategory.PENDING
}

SEGMENT_BOOTSTRAP_FIRST_VALID_SEED = "first_valid_seed"
SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE = "skip_left_edge"
SEGMENT_BOOTSTRAP_AUTO = "auto"
SEGMENT_BOOTSTRAP_PREFER_EARLIER_START = "prefer_earlier_start"
DEFAULT_SEGMENT_BOOTSTRAP_MODE = SEGMENT_BOOTSTRAP_PREFER_EARLIER_START
DEFAULT_STRICT_SEGMENT_RULES = True
SEGMENT_TERMINATION_MODE_THEORY = "theory"
SEGMENT_TERMINATION_MODE_PRACTICAL = "practical"
DEFAULT_SEGMENT_TERMINATION_MODE = SEGMENT_TERMINATION_MODE_THEORY


class GapCandidateState(str, Enum):
    NONE = "none"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"
    DEFERRED = "deferred"


class TransitionState(str, Enum):
    NONE = "none"
    PENDING = "pending"
    RECLAIMED = "reclaimed"


@dataclass
class _FeatureSequenceElement:
    high: float
    low: float
    source_indices: List[int] = field(default_factory=list)
    feature_sequence_id: Optional[int] = None
    belongs_to_prior_segment: bool = False
    belongs_to_new_segment: bool = False
    in_transition: bool = False


def _confirmed_bis(bis: List[Bi]) -> List[Bi]:
    """线段只基于已确认笔计算，未确认尾笔不参与段识别。"""
    return [bi for bi in bis if bi.is_confirmed]


def build_segment_tail_interpretations(
    bis: List[Bi],
    segments: List[Segment],
) -> List[SegmentTailInterpretation]:
    """为尾部未确认线段生成独立解释层，不改变正式线段结果。"""
    if not segments:
        return []

    interpretations: List[SegmentTailInterpretation] = []
    for segment in segments:
        if segment.is_confirmed:
            continue

        stop_reason = segment.stop_reason or "unknown"
        if stop_reason in {"same_direction_not_extending", "same_direction_slot_not_filled"}:
            confidence = "medium"
            uncertainty = (
                "当前尾段仍未形成正式终结条件，且同向推进未继续创新高/新低；"
                "这说明当前结构仍处于待确认状态，而非正式终结。"
            )
            suggested_catalyst = (
                "关注后续是否出现更强的反向突破，或新的三笔起段种子。"
            )
        elif stop_reason == "no_followup_same_direction":
            confidence = "medium"
            uncertainty = (
                "出现反向回撤后，后续同向推进笔未跟上，因此尾段仍保持未确认。"
            )
            suggested_catalyst = (
                "若后续同向笔重新创出新高/新低，尾段解释会转为更强的延续信号。"
            )
        elif stop_reason == "exhausted_confirmed_bis":
            confidence = "low"
            uncertainty = (
                "已用尽确认笔序列，当前尾段只能作为窗口末端的待确认状态。"
            )
            suggested_catalyst = (
                "等待新的确认笔进入后，再根据新的三笔种子和突破条件判断。"
            )
        else:
            confidence = "low"
            uncertainty = (
                "当前尾段未被正式确认，暂时只能作为待确认结构处理。"
            )
            suggested_catalyst = "继续观察后续笔的推进与反向突破。"

        stop_category = classify_stop_reason(stop_reason)
        evidence_parts = [f"stop_reason={stop_reason}", f"stop_category={stop_category.value}"]
        if segment.is_reclaimed:
            evidence_parts.append("is_reclaimed=True")
        if segment.absorbed_segment_ids:
            evidence_parts.append(
                "absorbed_segment_ids=" + ",".join(str(segment_id) for segment_id in segment.absorbed_segment_ids)
            )
        if segment.last_same_extreme is not None:
            evidence_parts.append(f"last_same_extreme={segment.last_same_extreme:.2f}")
        if segment.last_reverse_extreme is not None:
            evidence_parts.append(f"last_reverse_extreme={segment.last_reverse_extreme:.2f}")

        interpretations.append(
            SegmentTailInterpretation(
                segment_id=segment.segment_id,
                kind="pending_confirmation",
                confidence=confidence,
                uncertainty=uncertainty,
                evidence="; ".join(evidence_parts),
                suggested_catalyst=suggested_catalyst,
                is_reclaimed=segment.is_reclaimed,
                absorbed_segment_ids=list(segment.absorbed_segment_ids),
            )
        )

    return interpretations


def _score_bootstrap_candidate(
    bis: List[Bi],
    start_idx: int,
    result: Optional[Tuple[int, bool, Optional[int], str, Optional[int]]],
) -> Optional[int]:
    if result is None:
        return None

    end_idx, is_confirmed, _break_idx, stop_reason, _break_bi_id = result
    segment_len = end_idx - start_idx + 1
    score = min(segment_len, 3) * 3
    stop_category = classify_stop_reason(stop_reason)

    if is_confirmed:
        score += 80

    if stop_category in {
        StopOutcomeCategory.THEORY_CONFIRMED,
        StopOutcomeCategory.FALLBACK_CONFIRMED,
    }:
        score += 40
    elif stop_category == StopOutcomeCategory.PENDING:
        score -= 20

    if stop_reason == "exhausted_confirmed_bis":
        score -= 120

    return score


def _candidate_starts_inside_unresolved_predecessor(
    candidate_idx: int,
    candidate_result: Tuple[int, bool, Optional[int], str, Optional[int]],
    earlier_candidates: List[Tuple[int, Tuple[int, bool, Optional[int], str, Optional[int]]]],
) -> bool:
    _end_idx, is_confirmed, _break_idx, _stop_reason, _break_bi_id = candidate_result
    if is_confirmed is False and candidate_idx == 0:
        return False

    for earlier_idx, earlier_result in earlier_candidates:
        earlier_end_idx, earlier_confirmed, _earlier_break_idx, _earlier_stop_reason, earlier_break_bi_id = earlier_result
        if earlier_idx >= candidate_idx or earlier_confirmed:
            continue

        unresolved_limit = earlier_break_bi_id if earlier_break_bi_id is not None else earlier_end_idx + 1
        if candidate_idx <= unresolved_limit:
            return True

    return False


def _validate_bootstrap_config(
    bootstrap_mode: str,
    bootstrap_skip_confirmed_bis: int,
) -> None:
    supported_modes = {
        SEGMENT_BOOTSTRAP_AUTO,
        SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
        SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE,
    }
    if bootstrap_mode not in supported_modes:
        raise ValueError(f"Unsupported bootstrap_mode: {bootstrap_mode}")
    if bootstrap_skip_confirmed_bis < 0:
        raise ValueError("bootstrap_skip_confirmed_bis must be >= 0")


def _validate_termination_mode(termination_mode: str) -> None:
    supported_modes = {
        SEGMENT_TERMINATION_MODE_THEORY,
        SEGMENT_TERMINATION_MODE_PRACTICAL,
    }
    if termination_mode not in supported_modes:
        raise ValueError(f"Unsupported termination_mode: {termination_mode}")


def _resolve_base_bootstrap_start_index(
    total_bis: int,
    *,
    bootstrap_mode: str,
    bootstrap_skip_confirmed_bis: int,
) -> int:
    if total_bis <= 0:
        return 0

    if bootstrap_mode == SEGMENT_BOOTSTRAP_SKIP_LEFT_EDGE:
        max_start = max(0, total_bis - 3)
        return min(max(0, int(bootstrap_skip_confirmed_bis)), max_start)

    return 0


def _resolve_scored_bootstrap_start_index(
    bis: List[Bi],
    *,
    bootstrap_mode: str,
) -> int:
    max_start = max(0, len(bis) - 3)
    best_start: Optional[int] = None
    best_score: Optional[int] = None
    scored_candidates: List[Tuple[int, int]] = []
    candidate_results: List[Tuple[int, Tuple[int, bool, Optional[int], str, Optional[int]]]] = []

    for candidate_idx in range(max_start + 1):
        candidate_result = _extend_segment(bis, candidate_idx)
        candidate_score = _score_bootstrap_candidate(bis, candidate_idx, candidate_result)
        if candidate_score is None:
            continue
        assert candidate_result is not None
        if _candidate_starts_inside_unresolved_predecessor(candidate_idx, candidate_result, candidate_results):
            continue
        candidate_results.append((candidate_idx, candidate_result))
        scored_candidates.append((candidate_idx, candidate_score))
        if best_score is None or candidate_score > best_score or (
            candidate_score == best_score and best_start is not None and candidate_idx < best_start
        ):
            best_score = candidate_score
            best_start = candidate_idx

    if best_start is None:
        return 0

    if bootstrap_mode == SEGMENT_BOOTSTRAP_PREFER_EARLIER_START and best_score is not None:
        score_floor = best_score - 20
        eligible = [idx for idx, score in scored_candidates if score >= score_floor]
        if eligible:
            return min(eligible)

    return best_start


def _resolve_bootstrap_start_index(
    bis: List[Bi],
    *,
    bootstrap_mode: str,
    bootstrap_skip_confirmed_bis: int,
) -> int:
    base_start = _resolve_base_bootstrap_start_index(
        len(bis),
        bootstrap_mode=bootstrap_mode,
        bootstrap_skip_confirmed_bis=bootstrap_skip_confirmed_bis,
    )
    if bootstrap_mode in {SEGMENT_BOOTSTRAP_AUTO, SEGMENT_BOOTSTRAP_PREFER_EARLIER_START}:
        return _resolve_scored_bootstrap_start_index(
            bis,
            bootstrap_mode=bootstrap_mode,
        )
    return base_start


def _resolve_execution_profile(
    *,
    termination_mode: str,
    bootstrap_mode: str,
    strict_segment_rules: bool,
) -> Tuple[bool, str, bool]:
    practical_mode = termination_mode == SEGMENT_TERMINATION_MODE_PRACTICAL
    effective_bootstrap_mode = bootstrap_mode
    effective_strict_segment_rules = practical_mode and strict_segment_rules

    if not practical_mode and bootstrap_mode in {
        SEGMENT_BOOTSTRAP_AUTO,
        SEGMENT_BOOTSTRAP_PREFER_EARLIER_START,
    }:
        effective_bootstrap_mode = SEGMENT_BOOTSTRAP_FIRST_VALID_SEED

    return practical_mode, effective_bootstrap_mode, effective_strict_segment_rules


def describe_stop_reason(stop_reason: Optional[str]) -> str:
    if not stop_reason:
        return ""
    return STOP_REASON_LABELS.get(stop_reason, stop_reason)


def classify_stop_reason(stop_reason: Optional[str]) -> StopOutcomeCategory:
    if not stop_reason:
        return StopOutcomeCategory.UNKNOWN
    return STOP_REASON_CATEGORIES.get(stop_reason, StopOutcomeCategory.UNKNOWN)


def get_stop_reason_contract() -> dict[str, tuple[str, ...]]:
    """Return the stable stop-reason contract grouped by outcome category.

    spec_id: SPEC.SEGMENT.STOP_REASON（见 docs/chanlun/segment-stop-reason-contract.md）。
    """
    return {
        category.value: STOP_REASONS_BY_CATEGORY[category]
        for category in StopOutcomeCategory
    }


def is_theory_confirmed_stop_reason(stop_reason: Optional[str]) -> bool:
    """Whether a stop reason is confirmed by the theory main path."""
    return classify_stop_reason(stop_reason) == StopOutcomeCategory.THEORY_CONFIRMED


def is_fallback_confirmed_stop_reason(stop_reason: Optional[str]) -> bool:
    """Whether a stop reason is confirmed by practical fallback rules."""
    return classify_stop_reason(stop_reason) == StopOutcomeCategory.FALLBACK_CONFIRMED


def is_pending_stop_reason(stop_reason: Optional[str]) -> bool:
    """Whether a stop reason indicates a pending/non-final structural state."""
    return classify_stop_reason(stop_reason) == StopOutcomeCategory.PENDING


def summarize_stop_reason_outcome(
    stop_reason: Optional[str],
    *,
    mode: str = DEFAULT_SEGMENT_TERMINATION_MODE,
) -> Dict[str, Any]:
    """Turn a raw stop reason into a compact, caller-friendly outcome summary."""
    if not stop_reason:
        return {
            "bucket": "unknown",
            "terminal": False,
            "should_wait": True,
            "label": "no-stop-reason",
        }

    if stop_reason in THEORY_STOP_REASONS:
        return {
            "bucket": "theory",
            "terminal": True,
            "should_wait": False,
            "label": "theory-confirmed",
        }

    if stop_reason in FALLBACK_STOP_REASONS:
        if mode == SEGMENT_TERMINATION_MODE_THEORY:
            return {
                "bucket": "pending",
                "terminal": False,
                "should_wait": True,
                "label": "theory-mode-pending",
            }
        return {
            "bucket": "fallback",
            "terminal": True,
            "should_wait": False,
            "label": "fallback-confirmed",
        }

    if stop_reason in PENDING_STOP_REASONS:
        return {
            "bucket": "pending",
            "terminal": False,
            "should_wait": True,
            "label": "pending",
        }

    return {
        "bucket": "unknown",
        "terminal": False,
        "should_wait": True,
        "label": "unknown",
    }


def _is_alternating(bis: List[Bi]) -> bool:
    return all(previous.direction != current.direction for previous, current in zip(bis, bis[1:]))


def _has_common_overlap(window: List[Bi]) -> bool:
    overlap_low = max(bi.low for bi in window)
    overlap_high = min(bi.high for bi in window)
    return overlap_low <= overlap_high


def _third_bi_advances_first(window: List[Bi]) -> bool:
    if len(window) != 3:
        return False

    first, _, third = window
    if first.direction == BiDirection.UP:
        return third.high > first.high
    return third.low < first.low


def _forms_initial_segment(window: List[Bi], *, strict_segment_rules: bool = False) -> bool:
    if len(window) != 3 or not _is_alternating(window) or not _has_common_overlap(window):
        return False
    if strict_segment_rules and not _third_bi_advances_first(window):
        return False
    return True


def _feature_sequence_has_gap(left_bi: Bi, right_bi: Bi) -> bool:
    return max(left_bi.low, right_bi.low) > min(left_bi.high, right_bi.high)


def _contains(left: _FeatureSequenceElement, right: _FeatureSequenceElement) -> bool:
    if (
        left.feature_sequence_id is not None
        and right.feature_sequence_id is not None
        and left.feature_sequence_id != right.feature_sequence_id
    ):
        return False

    return (
        (left.high >= right.high and left.low <= right.low)
        or (right.high >= left.high and right.low <= left.low)
    )


def _feature_sequence_triplet_has_consistent_context(
    left: _FeatureSequenceElement,
    middle: _FeatureSequenceElement,
    right: _FeatureSequenceElement,
) -> bool:
    sequence_ids = {
        element.feature_sequence_id
        for element in (left, middle, right)
        if element.feature_sequence_id is not None
    }
    if len(sequence_ids) > 1:
        return False

    # At least one element should carry explicit prior/new segment context.
    has_context_flag = any(
        element.belongs_to_prior_segment
        or element.belongs_to_new_segment
        or element.in_transition
        for element in (left, middle, right)
    )
    return has_context_flag


def _resolve_feature_sequence_trend(
    previous_element: _FeatureSequenceElement,
    current_element: _FeatureSequenceElement,
    current_trend_up: Optional[bool],
) -> bool:
    if current_trend_up is not None:
        return current_trend_up
    if current_element.high > previous_element.high:
        return True
    if current_element.low < previous_element.low:
        return False
    return current_element.low >= previous_element.low


def _merge_feature_sequence_element(
    left: _FeatureSequenceElement,
    right: _FeatureSequenceElement,
    *,
    trend_up: bool,
) -> _FeatureSequenceElement:
    if trend_up:
        high = max(left.high, right.high)
        low = max(left.low, right.low)
    else:
        high = min(left.high, right.high)
        low = min(left.low, right.low)
    sequence_id = left.feature_sequence_id if left.feature_sequence_id is not None else right.feature_sequence_id
    belongs_to_prior_segment = left.belongs_to_prior_segment or right.belongs_to_prior_segment
    belongs_to_new_segment = left.belongs_to_new_segment or right.belongs_to_new_segment
    return _FeatureSequenceElement(
        high=high,
        low=low,
        source_indices=[*left.source_indices, *right.source_indices],
        feature_sequence_id=sequence_id,
        belongs_to_prior_segment=belongs_to_prior_segment,
        belongs_to_new_segment=belongs_to_new_segment,
        in_transition=belongs_to_prior_segment and belongs_to_new_segment,
    )


def _build_standard_feature_sequence(
    bis: List[Bi],
    reverse_indices: List[int],
) -> List[_FeatureSequenceElement]:
    if not reverse_indices:
        return []

    elements: List[_FeatureSequenceElement] = []
    trend_up: Optional[bool] = None
    sequence_id = reverse_indices[0] if reverse_indices else None

    for reverse_idx in reverse_indices:
        reverse_bi = bis[reverse_idx]
        current = _FeatureSequenceElement(
            high=reverse_bi.high,
            low=reverse_bi.low,
            source_indices=[reverse_idx],
            feature_sequence_id=sequence_id,
            belongs_to_prior_segment=not elements,
            belongs_to_new_segment=bool(elements),
        )

        if not elements:
            elements.append(current)
            continue

        if _contains(elements[-1], current):
            merge_trend_up = _resolve_feature_sequence_trend(elements[-1], current, trend_up)
            elements[-1] = _merge_feature_sequence_element(
                elements[-1],
                current,
                trend_up=merge_trend_up,
            )
            trend_up = merge_trend_up
            continue

        previous = elements[-1]
        if current.high >= previous.high and current.low >= previous.low:
            trend_up = True
        elif current.high <= previous.high and current.low <= previous.low:
            trend_up = False
        elements.append(current)

    return elements


def _feature_element_has_gap(
    left: _FeatureSequenceElement,
    right: _FeatureSequenceElement,
) -> bool:
    return max(left.low, right.low) > min(left.high, right.high)


def _feature_element_pivot_index(
    bis: List[Bi],
    element: _FeatureSequenceElement,
    direction: BiDirection,
) -> int:
    if direction == BiDirection.UP:
        return max(element.source_indices, key=lambda idx: (bis[idx].high, bis[idx].low, -idx))
    return min(element.source_indices, key=lambda idx: (bis[idx].low, bis[idx].high, idx))


def _feature_sequence_break(
    bis: List[Bi],
    reverse_indices: List[int],
    direction: BiDirection,
) -> Optional[Tuple[int, int, str]]:
    standard_sequence = _build_standard_feature_sequence(bis, reverse_indices)
    if len(standard_sequence) < 3:
        return None

    left_element, middle_element, right_element = standard_sequence[-3:]
    if not _feature_sequence_triplet_has_consistent_context(
        left_element,
        middle_element,
        right_element,
    ):
        return None

    if _feature_element_has_gap(left_element, middle_element):
        return None

    if direction == BiDirection.UP:
        is_top_fractal = (
            middle_element.high > left_element.high
            and middle_element.high > right_element.high
            and middle_element.low > left_element.low
            and middle_element.low > right_element.low
        )
        if is_top_fractal:
            pivot_idx = _feature_element_pivot_index(bis, middle_element, direction)
            return pivot_idx - 1, pivot_idx, "feature_sequence_fractal"
        return None

    is_bottom_fractal = (
        middle_element.high < left_element.high
        and middle_element.high < right_element.high
        and middle_element.low < left_element.low
        and middle_element.low < right_element.low
    )
    if is_bottom_fractal:
        pivot_idx = _feature_element_pivot_index(bis, middle_element, direction)
        return pivot_idx - 1, pivot_idx, "feature_sequence_fractal"
    return None


def _gap_feature_sequence_candidate(
    bis: List[Bi],
    reverse_indices: List[int],
    direction: BiDirection,
) -> Optional[int]:
    standard_sequence = _build_standard_feature_sequence(bis, reverse_indices)
    if len(standard_sequence) < 3:
        if len(reverse_indices) == 2:
            left_idx, right_idx = reverse_indices[-2], reverse_indices[-1]
            if _feature_sequence_has_gap(bis[left_idx], bis[right_idx]):
                return right_idx
        return None

    left_element, middle_element, right_element = standard_sequence[-3:]
    if not _feature_sequence_triplet_has_consistent_context(
        left_element,
        middle_element,
        right_element,
    ):
        return None

    if not _feature_element_has_gap(left_element, middle_element):
        return None

    if direction == BiDirection.UP:
        is_gap_top_fractal = (
            middle_element.high > left_element.high
            and middle_element.high > right_element.high
            and middle_element.low > left_element.low
            and middle_element.low > right_element.low
        )
        if is_gap_top_fractal:
            return _feature_element_pivot_index(bis, middle_element, direction)
        return None

    is_gap_bottom_fractal = (
        middle_element.high < left_element.high
        and middle_element.high < right_element.high
        and middle_element.low < left_element.low
        and middle_element.low < right_element.low
    )
    if is_gap_bottom_fractal:
        return _feature_element_pivot_index(bis, middle_element, direction)
    return None


def _replace_gap_candidate(
    pending_gap_break_idx: Optional[int],
    new_gap_candidate_idx: Optional[int],
) -> Optional[int]:
    """缺口候选替代策略：若出现新候选，则以后候选覆盖前候选。"""
    if new_gap_candidate_idx is None:
        return pending_gap_break_idx
    return new_gap_candidate_idx


def _breaks_first_bi_start(direction: BiDirection, candidate_bi: Bi, first_bi: Bi) -> bool:
    if direction == BiDirection.UP:
        return candidate_bi.low < first_bi.low
    return candidate_bi.high > first_bi.high


def _evaluate_transition_state(
    bis: List[Bi],
    transition_idx: int,
    prior_direction: BiDirection,
) -> TransitionState:
    if transition_idx + 1 >= len(bis):
        return TransitionState.NONE

    transition_bi = bis[transition_idx]
    candidate_direction = transition_bi.direction
    if candidate_direction == prior_direction:
        return TransitionState.NONE

    remaining = len(bis) - (transition_idx + 1)
    if remaining <= 2:
        return TransitionState.PENDING

    for idx in range(transition_idx + 1, len(bis)):
        candidate_bi = bis[idx]
        if candidate_bi.direction == candidate_direction:
            if _same_direction_extends(
                candidate_direction,
                candidate_bi,
                transition_bi.high if candidate_direction == BiDirection.UP else transition_bi.low,
            ):
                return TransitionState.NONE
            continue

        if _breaks_first_bi_start(candidate_direction, candidate_bi, transition_bi):
            return TransitionState.RECLAIMED

    return TransitionState.PENDING


def _reclaims_transition_back_to_prior_segment(
    bis: List[Bi],
    transition_idx: int,
    prior_direction: BiDirection,
) -> Optional[int]:
    if _evaluate_transition_state(bis, transition_idx, prior_direction) != TransitionState.RECLAIMED:
        return None

    transition_bi = bis[transition_idx]
    candidate_direction = transition_bi.direction
    for idx in range(transition_idx + 1, len(bis)):
        candidate_bi = bis[idx]
        if candidate_bi.direction == candidate_direction:
            continue

        if _breaks_first_bi_start(candidate_direction, candidate_bi, transition_bi):
            return idx

    return None


def _rediscriminate_gap_break(
    bis: List[Bi],
    start_idx: int,
) -> Optional[bool]:
    outcome, _is_delayed_true = _rediscriminate_gap_break_detail(bis, start_idx)
    return outcome


def _evaluate_gap_candidate_state(
    bis: List[Bi],
    gap_candidate_idx: Optional[int],
    *,
    should_defer_after_local_gap_false: bool = False,
) -> tuple[GapCandidateState, bool, Optional[int], Optional[int], Optional[str]]:
    if gap_candidate_idx is None:
        return GapCandidateState.NONE, False, None, None, None

    pending_gap_outcome, is_delayed_true = _rediscriminate_gap_break_detail(bis, gap_candidate_idx)
    if pending_gap_outcome is True:
        end_idx = gap_candidate_idx - 1
        break_idx = gap_candidate_idx
        stop_reason = (
            "feature_sequence_gap_fractal_delayed_true"
            if is_delayed_true
            else "feature_sequence_gap_fractal"
        )
        return GapCandidateState.CONFIRMED, is_delayed_true, end_idx, break_idx, stop_reason

    if pending_gap_outcome is False:
        if should_defer_after_local_gap_false:
            return GapCandidateState.DEFERRED, False, None, None, None
        return GapCandidateState.INVALIDATED, False, None, None, None

    return GapCandidateState.PENDING, False, None, None, None


def _evaluate_pending_gap_candidate(
    bis: List[Bi],
    gap_candidate_idx: Optional[int],
) -> tuple[Optional[bool], bool, Optional[int], Optional[int], Optional[str]]:
    state, is_delayed_true, end_idx, break_idx, stop_reason = _evaluate_gap_candidate_state(
        bis,
        gap_candidate_idx,
    )
    if state == GapCandidateState.CONFIRMED:
        return True, is_delayed_true, end_idx, break_idx, stop_reason
    if state in {GapCandidateState.INVALIDATED, GapCandidateState.DEFERRED}:
        return False, False, None, None, None
    return None, False, None, None, None


def _rediscriminate_gap_break_detail(
    bis: List[Bi],
    start_idx: int,
) -> tuple[Optional[bool], bool]:
    """
    缺口分型后的再分辨细节。

    Returns:
        (outcome, is_delayed_true)
        - outcome: True / False / None
        - is_delayed_true: 仅当 outcome=True 且经历过至少一轮“弱同向未突破”时为 True
    """
    if start_idx + 2 >= len(bis):
        return None, False

    first_bi = bis[start_idx]
    direction = first_bi.direction
    first_end_extreme = first_bi.high if direction == BiDirection.UP else first_bi.low
    cursor = start_idx + 1
    has_seen_weak_round = False

    while cursor < len(bis):
        reverse_bi = bis[cursor]
        if reverse_bi.direction == direction:
            return None, False

        if _breaks_first_bi_start(direction, reverse_bi, first_bi):
            return False, False

        if cursor + 1 >= len(bis):
            return None, False

        same_dir_bi = bis[cursor + 1]
        if same_dir_bi.direction != direction:
            return None, False

        if _same_direction_extends(direction, same_dir_bi, first_end_extreme):
            # 只有在已经经历过一次弱轮次后，后续的强同向推进才被视为延迟确认。
            return True, has_seen_weak_round

        has_seen_weak_round = True
        cursor += 2

    return None, False


def _segment_extremes(
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
) -> Tuple[float, float]:
    direction = bis[start_idx].direction
    window = bis[start_idx:end_idx + 1]
    same_direction_bis = [bi for bi in window if bi.direction == direction]
    reverse_direction_bis = [bi for bi in window if bi.direction != direction]

    if direction == BiDirection.UP:
        last_same_extreme = same_direction_bis[-1].high
        last_reverse_extreme = reverse_direction_bis[-1].low
    else:
        last_same_extreme = same_direction_bis[-1].low
        last_reverse_extreme = reverse_direction_bis[-1].high

    return last_same_extreme, last_reverse_extreme


def _same_direction_extends(
    direction: BiDirection,
    candidate_bi: Bi,
    reference_extreme: float,
) -> bool:
    if direction == BiDirection.UP:
        return candidate_bi.high > reference_extreme
    return candidate_bi.low < reference_extreme


def _reverse_breaks_last_reverse_extreme(
    direction: BiDirection,
    reverse_bi: Bi,
    last_reverse_extreme: float,
) -> bool:
    if direction == BiDirection.UP:
        return reverse_bi.low < last_reverse_extreme
    return reverse_bi.high > last_reverse_extreme


def _reverse_confirms_gap_break(
    direction: BiDirection,
    reverse_bi: Bi,
    next_reverse_bi: Bi,
) -> bool:
    if direction == BiDirection.UP:
        return next_reverse_bi.low < reverse_bi.low
    return next_reverse_bi.high > reverse_bi.high


def _resolve_theory_candidate_end_idx(
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
) -> Optional[int]:
    if end_idx <= start_idx:
        return None

    direction = bis[start_idx].direction
    candidate_indices = [idx for idx in range(start_idx, end_idx + 1) if bis[idx].direction == direction]
    if not candidate_indices:
        return None

    def candidate_key(idx: int) -> Tuple[float, float, int]:
        bi = bis[idx]
        if direction == BiDirection.UP:
            return (bi.high, bi.low, -bi.bi_id)
        return (-bi.low, -bi.high, bi.bi_id)

    return max(candidate_indices, key=candidate_key)


def _resolve_theory_segment_extent(
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
) -> int:
    if end_idx <= start_idx:
        return end_idx

    direction = bis[start_idx].direction
    reverse_indices = [idx for idx in range(start_idx + 1, end_idx + 1) if bis[idx].direction != direction]
    feature_break = _evaluate_theory_stop(bis, reverse_indices, direction)
    if feature_break is not None:
        theory_end_idx, _break_idx, _stop_reason = feature_break
        if theory_end_idx >= start_idx:
            return min(end_idx, theory_end_idx)

    theory_candidate_idx = _resolve_theory_candidate_end_idx(bis, start_idx, end_idx)
    if theory_candidate_idx is not None and theory_candidate_idx > start_idx:
        return min(end_idx, theory_candidate_idx)

    return end_idx


def _build_segment(
    segment_id: int,
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
    is_confirmed: bool,
    *,
    last_same_extreme: float,
    last_reverse_extreme: float,
    break_bi_id: Optional[int],
    stop_reason: str,
) -> Segment:
    window = bis[start_idx:end_idx + 1]
    start_bi = window[0]
    end_bi = window[-1]
    start_price = start_bi.low if start_bi.direction == BiDirection.UP else start_bi.high
    end_price = end_bi.high if end_bi.direction == BiDirection.UP else end_bi.low
    theory_candidate_idx = _resolve_theory_candidate_end_idx(bis, start_idx, end_idx)
    theory_candidate_end_bi = bis[theory_candidate_idx] if theory_candidate_idx is not None else end_bi
    theory_candidate_end_price = theory_candidate_end_bi.high if theory_candidate_end_bi.direction == BiDirection.UP else theory_candidate_end_bi.low
    return Segment(
        segment_id=segment_id,
        direction=start_bi.direction,
        start_bi_id=start_bi.bi_id,
        end_bi_id=end_bi.bi_id,
        start_ts=start_bi.start_ts,
        end_ts=end_bi.end_ts,
        start_price=start_price,
        end_price=end_price,
        high=max(bi.high for bi in window),
        low=min(bi.low for bi in window),
        norm_bar_range=(start_bi.norm_bar_range[0], end_bi.norm_bar_range[1]),
        bi_ids=[bi.bi_id for bi in window],
        is_confirmed=is_confirmed,
        theory_candidate_end_bi_id=theory_candidate_end_bi.bi_id,
        theory_candidate_end_ts=theory_candidate_end_bi.end_ts,
        theory_candidate_end_price=theory_candidate_end_price,
        last_same_extreme=last_same_extreme,
        last_reverse_extreme=last_reverse_extreme,
        break_bi_id=break_bi_id,
        stop_reason=stop_reason,
    )


def _merge_segments_same_direction(
    previous: Segment,
    current: Segment,
    bis: List[Bi],
) -> Segment:
    start_idx = previous.bi_ids[0]
    end_idx = current.bi_ids[-1]
    window = bis[start_idx:end_idx + 1]
    start_bi = window[0]
    end_bi = window[-1]
    merged_ids = previous.bi_ids + [bi_id for bi_id in current.bi_ids if bi_id not in previous.bi_ids]
    start_price = start_bi.low if start_bi.direction == BiDirection.UP else start_bi.high
    end_price = end_bi.high if end_bi.direction == BiDirection.UP else end_bi.low
    theory_candidate_idx = _resolve_theory_candidate_end_idx(bis, previous.bi_ids[0], current.bi_ids[-1])
    theory_candidate_end_bi = bis[theory_candidate_idx] if theory_candidate_idx is not None else end_bi
    theory_candidate_end_price = theory_candidate_end_bi.high if theory_candidate_end_bi.direction == BiDirection.UP else theory_candidate_end_bi.low
    return Segment(
        segment_id=previous.segment_id,
        direction=previous.direction,
        start_bi_id=previous.start_bi_id,
        end_bi_id=current.end_bi_id,
        start_ts=previous.start_ts,
        end_ts=current.end_ts,
        start_price=start_price,
        end_price=end_price,
        high=max(bi.high for bi in window),
        low=min(bi.low for bi in window),
        norm_bar_range=(previous.norm_bar_range[0], current.norm_bar_range[1]),
        bi_ids=merged_ids,
        is_confirmed=current.is_confirmed,
        theory_candidate_end_bi_id=theory_candidate_end_bi.bi_id,
        theory_candidate_end_ts=theory_candidate_end_bi.end_ts,
        theory_candidate_end_price=theory_candidate_end_price,
        last_same_extreme=current.last_same_extreme,
        last_reverse_extreme=current.last_reverse_extreme,
        break_bi_id=current.break_bi_id,
        stop_reason=current.stop_reason,
        is_reclaimed=True,
        absorbed_segment_ids=list(dict.fromkeys([*previous.absorbed_segment_ids, current.segment_id, *current.absorbed_segment_ids])),
    )


def _find_later_initial_segment_window(
    bis: List[Bi],
    start_idx: int,
    *,
    strict_segment_rules: bool = False,
) -> Optional[Tuple[int, int]]:
    for candidate_start_idx in range(start_idx + 1, len(bis) - 2):
        candidate_window = bis[candidate_start_idx:candidate_start_idx + 3]
        if _forms_initial_segment(candidate_window, strict_segment_rules=strict_segment_rules):
            return candidate_start_idx, candidate_start_idx + 2
    return None


def _evaluate_theory_stop(
    bis: List[Bi],
    reverse_indices: List[int],
    direction: BiDirection,
) -> Optional[Tuple[int, int, str]]:
    """理论主路径：先只看特征序列分型，避免早于理论判定就进入兜底分支。"""
    return _feature_sequence_break(bis, reverse_indices, direction)


def _extend_segment(
    bis: List[Bi],
    start_idx: int,
    *,
    anchor_idx: Optional[int] = None,
    strict_segment_rules: bool = False,
    enable_gap_false_defer: bool = True,
    enable_fallback_reverse_break: bool = True,
    enable_same_direction_fallback: bool = True,
) -> Optional[Tuple[int, bool, Optional[int], str, Optional[int]]]:
    if start_idx + 2 >= len(bis):
        return None

    initial = bis[start_idx:start_idx + 3]
    break_idx: Optional[int] = None
    is_confirmed = False

    if _forms_initial_segment(initial, strict_segment_rules=strict_segment_rules):
        seed_start_idx = start_idx
        seed_end_idx = start_idx + 2
        direction = initial[0].direction
        cursor = start_idx + 3
    else:
        if anchor_idx is None or anchor_idx != start_idx:
            return None

        fallback_seed = _find_later_initial_segment_window(
            bis,
            start_idx,
            strict_segment_rules=strict_segment_rules,
        )
        if fallback_seed is None:
            return None

        seed_start_idx, seed_end_idx = fallback_seed
        direction = bis[seed_start_idx].direction
        cursor = seed_start_idx + 3

    end_idx = seed_end_idx
    reverse_indices = [seed_start_idx + 1]

    last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
    pending_gap_break_idx: Optional[int] = None
    # 冲突规则：一旦缺口再分辨先触发 False（先破第一笔起点），
    # 当前线段后续不再接受 gap 候选的 True 翻案，避免同形态窗口漂移。
    gap_false_locked = False
    defer_next_reverse_break = False

    while cursor < len(bis):
        reverse_bi = bis[cursor]
        if reverse_bi.direction == direction:
            if enable_same_direction_fallback:
                break_bi_id = reverse_bi.bi_id
                stop_reason = "unexpected_same_direction"
                break
            break_bi_id = reverse_bi.bi_id
            stop_reason = "exhausted_confirmed_bis"
            break

        reverse_indices.append(cursor)
        is_first_transition_round = cursor == seed_end_idx + 1
        segment_first_bi = bis[seed_start_idx]

        transition_state = _evaluate_transition_state(bis, cursor, direction)
        allow_fallback_reverse_break = not (
            is_first_transition_round and transition_state == TransitionState.PENDING
        )
        if (
            is_first_transition_round
            and transition_state == TransitionState.PENDING
            and cursor + 2 >= len(bis)
            and _breaks_first_bi_start(direction, reverse_bi, segment_first_bi)
        ):
            break_idx = cursor
            is_confirmed = False
            break_bi_id = reverse_bi.bi_id
            stop_reason = "transition_pending"
            break

        prev_same_dir_idx = cursor - 1
        prev_prev_same_dir_idx = cursor - 3
        hits_non_extending_same_direction_pair = (
            prev_same_dir_idx >= start_idx
            and prev_prev_same_dir_idx >= start_idx
            and bis[prev_same_dir_idx].direction == direction
            and bis[prev_prev_same_dir_idx].direction == direction
            and (
                (direction == BiDirection.UP and bis[prev_same_dir_idx].high <= bis[prev_prev_same_dir_idx].high)
                or (direction == BiDirection.DOWN and bis[prev_same_dir_idx].low >= bis[prev_prev_same_dir_idx].low)
            )
        )

        if cursor + 1 >= len(bis):
            should_defer_break = defer_next_reverse_break
            if should_defer_break:
                defer_next_reverse_break = False
            else:
                feature_break = _evaluate_theory_stop(bis, reverse_indices, direction)
                if feature_break is not None:
                    end_idx, break_idx, stop_reason = feature_break
                    is_confirmed = True
                    break_bi_id = bis[break_idx].bi_id
                    break

            if (
                enable_fallback_reverse_break
                and allow_fallback_reverse_break
                and _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme)
            ):
                break_idx = cursor
                is_confirmed = True
                break_bi_id = reverse_bi.bi_id
                stop_reason = "reverse_break"
                break

            break_bi_id = reverse_bi.bi_id
            stop_reason = "exhausted_confirmed_bis"
            break

        same_dir_bi = bis[cursor + 1]
        if same_dir_bi.direction != direction:
            if enable_same_direction_fallback:
                break_bi_id = same_dir_bi.bi_id
                stop_reason = "same_direction_slot_not_filled"
                break
            break_bi_id = same_dir_bi.bi_id
            stop_reason = "exhausted_confirmed_bis"
            break

        if not gap_false_locked:
            gap_candidate_idx = _gap_feature_sequence_candidate(bis, reverse_indices, direction)
            pending_gap_break_idx = _replace_gap_candidate(
                pending_gap_break_idx,
                gap_candidate_idx,
            )

            if pending_gap_break_idx is not None:
                evaluated_gap_break_idx = pending_gap_break_idx
                should_defer_after_local_gap_false = (
                    enable_gap_false_defer
                    and evaluated_gap_break_idx == cursor
                    and cursor + 4 < len(bis)
                )
                gap_state, is_delayed_true, resolved_end_idx, resolved_break_idx, resolved_stop_reason = (
                    _evaluate_gap_candidate_state(
                        bis,
                        pending_gap_break_idx,
                        should_defer_after_local_gap_false=should_defer_after_local_gap_false,
                    )
                )
                if gap_state == GapCandidateState.CONFIRMED:
                    # theory 模式下不延迟：缺口分型再分辨通过即确认；
                    # practical 下延迟给 weak_down_rebound -> reverse_break 兑现。
                    should_defer_down_weak_gap = (
                        enable_fallback_reverse_break
                        and direction == BiDirection.DOWN
                        and pending_gap_break_idx == cursor
                        and same_dir_bi.low >= last_same_extreme
                    )
                    if should_defer_down_weak_gap:
                        pass
                    else:
                        end_idx = resolved_end_idx
                        break_idx = resolved_break_idx
                        is_confirmed = True
                        break_bi_id = bis[break_idx].bi_id
                        stop_reason = resolved_stop_reason
                        break
                if gap_state in {GapCandidateState.INVALIDATED, GapCandidateState.DEFERRED}:
                    reclaimed_idx = None
                    if gap_state == GapCandidateState.INVALIDATED and not defer_next_reverse_break:
                        reclaimed_idx = _reclaims_transition_back_to_prior_segment(bis, cursor, direction)
                    if reclaimed_idx is not None:
                        end_idx = reclaimed_idx
                        last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
                        reverse_indices = [
                            idx
                            for idx in range(start_idx, end_idx + 1)
                            if bis[idx].direction != direction
                        ]
                        pending_gap_break_idx = None
                        gap_false_locked = False
                        cursor = reclaimed_idx + 1
                        continue
                    if gap_state == GapCandidateState.DEFERRED:
                        if direction == BiDirection.UP:
                            last_reverse_extreme = reverse_bi.low
                            last_same_extreme = same_dir_bi.high
                        else:
                            last_reverse_extreme = reverse_bi.high
                            last_same_extreme = same_dir_bi.low
                        end_idx = cursor + 1
                        defer_next_reverse_break = True
                        reverse_indices = [idx for idx in reverse_indices if idx > cursor]
                        cursor += 2
                        continue
                    pending_gap_break_idx = None
                    gap_false_locked = True
                    invalidated_after_deferred_gap = defer_next_reverse_break
                    defer_next_reverse_break = False
                    if (
                        not invalidated_after_deferred_gap
                        and
                        enable_fallback_reverse_break
                        and allow_fallback_reverse_break
                        and _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme)
                    ):
                        break_idx = cursor
                        is_confirmed = True
                        break_bi_id = reverse_bi.bi_id
                        stop_reason = "reverse_break"
                        break
                    if cursor + 2 < len(bis):
                        if direction == BiDirection.UP:
                            last_reverse_extreme = reverse_bi.low
                            last_same_extreme = same_dir_bi.high
                        else:
                            last_reverse_extreme = reverse_bi.high
                            last_same_extreme = same_dir_bi.low
                        end_idx = cursor + 1
                        cursor += 2
                        continue
                    end_idx = cursor + 1
                    break_bi_id = same_dir_bi.bi_id
                    stop_reason = "same_direction_not_extending"
                    break

        reclaimed_idx = None
        if not gap_false_locked:
            reclaimed_idx = _reclaims_transition_back_to_prior_segment(bis, cursor, direction)
        if reclaimed_idx is not None:
            end_idx = reclaimed_idx
            last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
            reverse_indices = [
                idx
                for idx in range(start_idx, end_idx + 1)
                if bis[idx].direction != direction
            ]
            pending_gap_break_idx = None
            gap_false_locked = False
            cursor = reclaimed_idx + 1
            continue

        if hits_non_extending_same_direction_pair:
            if defer_next_reverse_break:
                defer_next_reverse_break = False
            elif enable_fallback_reverse_break and allow_fallback_reverse_break:
                break_idx = cursor
                is_confirmed = True
                break_bi_id = reverse_bi.bi_id
                stop_reason = "reverse_break"
                break

        should_defer_break = defer_next_reverse_break
        if should_defer_break:
            defer_next_reverse_break = False
        else:
            feature_break = _evaluate_theory_stop(bis, reverse_indices, direction)
            if feature_break is not None:
                end_idx, break_idx, stop_reason = feature_break
                is_confirmed = True
                break_bi_id = bis[break_idx].bi_id
                break

        if should_defer_break:
            pass
        elif (
            enable_fallback_reverse_break
            and allow_fallback_reverse_break
            and _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme)
        ):
            break_idx = cursor
            is_confirmed = True
            break_bi_id = reverse_bi.bi_id
            stop_reason = "reverse_break"
            break

        if direction == BiDirection.UP:
            if same_dir_bi.high <= last_same_extreme:
                if cursor + 2 < len(bis):
                    next_reverse_bi = bis[cursor + 2]
                    candidate_feature_break = _evaluate_theory_stop(
                        bis,
                        reverse_indices + [cursor + 2],
                        direction,
                    )
                    if candidate_feature_break is not None:
                        end_idx, break_idx, stop_reason = candidate_feature_break
                        is_confirmed = True
                        break_bi_id = bis[break_idx].bi_id
                        break
                    if not gap_false_locked:
                        gap_candidate_idx = _gap_feature_sequence_candidate(
                            bis,
                            reverse_indices + [cursor + 2],
                            direction,
                        )
                        pending_gap_break_idx = _replace_gap_candidate(
                            pending_gap_break_idx,
                            gap_candidate_idx,
                        )
                        if pending_gap_break_idx is not None:
                            gap_state, is_delayed_true, resolved_end_idx, resolved_break_idx, resolved_stop_reason = (
                                _evaluate_gap_candidate_state(
                                    bis,
                                    pending_gap_break_idx,
                                    should_defer_after_local_gap_false=False,
                                )
                            )
                            if gap_state == GapCandidateState.CONFIRMED:
                                should_defer_down_weak_gap = (
                                    direction == BiDirection.DOWN
                                    and pending_gap_break_idx == cursor
                                    and same_dir_bi.low >= last_same_extreme
                                )
                                if should_defer_down_weak_gap:
                                    pass
                                else:
                                    end_idx = resolved_end_idx
                                    break_idx = resolved_break_idx
                                    is_confirmed = True
                                    break_bi_id = bis[break_idx].bi_id
                                    stop_reason = resolved_stop_reason
                                    break
                            if gap_state in {GapCandidateState.INVALIDATED, GapCandidateState.DEFERRED}:
                                reclaimed_idx = None
                                if gap_state == GapCandidateState.INVALIDATED and not defer_next_reverse_break:
                                    reclaimed_idx = _reclaims_transition_back_to_prior_segment(bis, cursor, direction)
                                if reclaimed_idx is not None:
                                    end_idx = reclaimed_idx
                                    last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
                                    reverse_indices = [
                                        idx
                                        for idx in range(start_idx, end_idx + 1)
                                        if bis[idx].direction != direction
                                    ]
                                    pending_gap_break_idx = None
                                    gap_false_locked = False
                                    cursor = reclaimed_idx + 1
                                    continue
                                if gap_state == GapCandidateState.DEFERRED:
                                    if direction == BiDirection.UP:
                                        last_reverse_extreme = reverse_bi.low
                                        last_same_extreme = same_dir_bi.high
                                    else:
                                        last_reverse_extreme = reverse_bi.high
                                        last_same_extreme = same_dir_bi.low
                                    end_idx = cursor + 1
                                    defer_next_reverse_break = True
                                    reverse_indices = [idx for idx in reverse_indices if idx > cursor]
                                    cursor += 2
                                    continue
                                pending_gap_break_idx = None
                                gap_false_locked = True
                                invalidated_after_deferred_gap = defer_next_reverse_break
                                defer_next_reverse_break = False
                                if (
                                    not invalidated_after_deferred_gap
                                    and enable_fallback_reverse_break
                                    and allow_fallback_reverse_break
                                    and _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme)
                                ):
                                    break_idx = cursor
                                    is_confirmed = True
                                    break_bi_id = reverse_bi.bi_id
                                    stop_reason = "reverse_break"
                                    break
                                end_idx = cursor + 1
                                cursor += 2
                                continue
                    if (
                        next_reverse_bi.direction != direction
                        and enable_fallback_reverse_break
                        and allow_fallback_reverse_break
                        and _reverse_breaks_last_reverse_extreme(direction, next_reverse_bi, last_reverse_extreme)
                    ):
                        break_idx = cursor
                        is_confirmed = True
                        break_bi_id = next_reverse_bi.bi_id
                        stop_reason = "reverse_break"
                        break
                if enable_same_direction_fallback:
                    break_bi_id = same_dir_bi.bi_id
                    stop_reason = "same_direction_not_extending"
                    break
                break_bi_id = same_dir_bi.bi_id
                stop_reason = "exhausted_confirmed_bis"
                break
            last_reverse_extreme = reverse_bi.low
            last_same_extreme = same_dir_bi.high
        else:
            if same_dir_bi.low >= last_same_extreme:
                if cursor + 2 < len(bis):
                    next_reverse_bi = bis[cursor + 2]
                    if defer_next_reverse_break:
                        defer_next_reverse_break = False
                    else:
                        candidate_feature_break = _evaluate_theory_stop(
                            bis,
                            reverse_indices + [cursor + 2],
                            direction,
                        )
                        if candidate_feature_break is not None:
                            end_idx, break_idx, stop_reason = candidate_feature_break
                            is_confirmed = True
                            break_bi_id = bis[break_idx].bi_id
                            break
                    if not gap_false_locked:
                        gap_candidate_idx = _gap_feature_sequence_candidate(
                            bis,
                            reverse_indices + [cursor + 2],
                            direction,
                        )
                        pending_gap_break_idx = _replace_gap_candidate(
                            pending_gap_break_idx,
                            gap_candidate_idx,
                        )
                        if pending_gap_break_idx is not None:
                            gap_state, is_delayed_true, resolved_end_idx, resolved_break_idx, resolved_stop_reason = (
                                _evaluate_gap_candidate_state(
                                    bis,
                                    pending_gap_break_idx,
                                    should_defer_after_local_gap_false=False,
                                )
                            )
                            if gap_state == GapCandidateState.CONFIRMED:
                                should_defer_down_weak_gap = (
                                    enable_fallback_reverse_break
                                    and direction == BiDirection.DOWN
                                    and pending_gap_break_idx == cursor
                                    and same_dir_bi.low >= last_same_extreme
                                )
                                if should_defer_down_weak_gap:
                                    pass
                                else:
                                    end_idx = resolved_end_idx
                                    break_idx = resolved_break_idx
                                    is_confirmed = True
                                    break_bi_id = bis[break_idx].bi_id
                                    stop_reason = resolved_stop_reason
                                    break
                            if gap_state in {GapCandidateState.INVALIDATED, GapCandidateState.DEFERRED}:
                                reclaimed_idx = None
                                if gap_state == GapCandidateState.INVALIDATED and not defer_next_reverse_break:
                                    reclaimed_idx = _reclaims_transition_back_to_prior_segment(bis, cursor, direction)
                                if reclaimed_idx is not None:
                                    end_idx = reclaimed_idx
                                    last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
                                    reverse_indices = [
                                        idx
                                        for idx in range(start_idx, end_idx + 1)
                                        if bis[idx].direction != direction
                                    ]
                                    pending_gap_break_idx = None
                                    gap_false_locked = False
                                    cursor = reclaimed_idx + 1
                                    continue
                                if gap_state == GapCandidateState.DEFERRED:
                                    if direction == BiDirection.UP:
                                        last_reverse_extreme = reverse_bi.low
                                        last_same_extreme = same_dir_bi.high
                                    else:
                                        last_reverse_extreme = reverse_bi.high
                                        last_same_extreme = same_dir_bi.low
                                    end_idx = cursor + 1
                                    defer_next_reverse_break = True
                                    reverse_indices = [idx for idx in reverse_indices if idx > cursor]
                                    cursor += 2
                                    continue
                                pending_gap_break_idx = None
                                gap_false_locked = True
                                invalidated_after_deferred_gap = defer_next_reverse_break
                                defer_next_reverse_break = False
                                if (
                                    not invalidated_after_deferred_gap
                                    and enable_fallback_reverse_break
                                    and allow_fallback_reverse_break
                                    and _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme)
                                ):
                                    break_idx = cursor
                                    is_confirmed = True
                                    break_bi_id = reverse_bi.bi_id
                                    stop_reason = "reverse_break"
                                    break
                                end_idx = cursor + 1
                                cursor += 2
                                continue
                    weak_down_rebound = (
                        pending_gap_break_idx == cursor
                        and same_dir_bi.low >= last_same_extreme
                    )
                    if (
                        enable_fallback_reverse_break
                        and
                        next_reverse_bi.direction != direction
                        and (
                            (weak_down_rebound and _reverse_confirms_gap_break(direction, reverse_bi, next_reverse_bi))
                            or (
                                not weak_down_rebound
                                and _reverse_breaks_last_reverse_extreme(direction, next_reverse_bi, last_reverse_extreme)
                                and allow_fallback_reverse_break
                            )
                        )
                    ):
                        if strict_segment_rules and cursor - 1 >= start_idx:
                            # Strict mode aligns down-branch break anchoring with up-branch behavior:
                            # current segment stops at the last same-direction bi, and the next segment
                            # starts from the first reverse bi.
                            end_idx = cursor - 1
                            break_idx = cursor
                        else:
                            end_idx = cursor + 1
                            break_idx = cursor + 2
                        is_confirmed = True
                        break_bi_id = next_reverse_bi.bi_id
                        stop_reason = "reverse_break"
                        break
                if enable_same_direction_fallback:
                    break_bi_id = same_dir_bi.bi_id
                    stop_reason = "same_direction_not_extending"
                    break
                break_bi_id = same_dir_bi.bi_id
                stop_reason = "exhausted_confirmed_bis"
                break
            last_reverse_extreme = reverse_bi.high
            last_same_extreme = same_dir_bi.low

        end_idx = cursor + 1
        cursor += 2

    else:
        break_bi_id = None
        stop_reason = "exhausted_confirmed_bis"

    return end_idx, is_confirmed, break_idx, stop_reason, break_bi_id


def identify_segments(
    bis: List[Bi],
    *,
    bootstrap_mode: str = DEFAULT_SEGMENT_BOOTSTRAP_MODE,
    bootstrap_skip_confirmed_bis: int = 0,
    strict_segment_rules: bool = DEFAULT_STRICT_SEGMENT_RULES,
    termination_mode: str = DEFAULT_SEGMENT_TERMINATION_MODE,
) -> List[Segment]:
    """
    识别线段。

    spec_id: SPEC.SEGMENT.CORE / SPEC.SEGMENT.IMPLEMENTATION（见 docs/chanlun/segment-spec.md 与 segment-implementation-guide.md）。
    第一阶段规则对应 docs/chanlun/chanlun-rule-spec.md 6.1-6.5：
    - 输入可传入全量笔序列，但实现内部只使用已确认笔
    - 至少 3 笔，方向交替，首尾笔同向
    - 同向笔必须持续推进，反向笔不得破坏最近关键低/高点
    - 被反向笔有效破坏时，线段终结并确认为已完成线段
    - 若尾部尚未被有效反向笔破坏，则保留一个未确认尾段

    可选锚定参数：
        - 默认值 bootstrap_mode=prefer_earlier_start：当前函数默认会枚举候选起点，
            对每个可行候选试跑首段并按工程启发式打分，再在接近最优的候选里优先更靠左起点
        - bootstrap_mode=auto：扫描候选起点并直接选择得分最高的首段种子
        - bootstrap_mode=prefer_earlier_start：在接近 auto 最优质量的候选中优先更靠左起点
    - bootstrap_mode=first_valid_seed：从最左侧开始寻找首个合法三笔种子
    - bootstrap_mode=skip_left_edge：先跳过左侧若干已确认笔，再寻找首个合法三笔种子
    - strict_segment_rules=True（默认）：额外要求“前三笔同向推进”，并合并同向相邻线段

        说明：
        - 这里记录的是函数级默认值；当前部分调用方会按周期覆写该参数
        - 例如当前报表/发布链路会对 1m 显式改用 first_valid_seed，以减少首段锚点右移
        - prefer_earlier_start 的评分逻辑属于工程启发式，不应视为严格理论公式
    """
    _validate_bootstrap_config(bootstrap_mode, bootstrap_skip_confirmed_bis)
    _validate_termination_mode(termination_mode)
    bis = _confirmed_bis(bis)

    if len(bis) < 3:
        return []

    practical_mode, effective_bootstrap_mode, effective_strict_segment_rules = _resolve_execution_profile(
        termination_mode=termination_mode,
        bootstrap_mode=bootstrap_mode,
        strict_segment_rules=strict_segment_rules,
    )

    segments: List[Segment] = []
    segment_id = 0
    enable_gap_false_defer = practical_mode
    enable_fallback_reverse_break = practical_mode
    enable_same_direction_fallback = practical_mode
    index = _resolve_bootstrap_start_index(
        bis,
        bootstrap_mode=effective_bootstrap_mode,
        bootstrap_skip_confirmed_bis=bootstrap_skip_confirmed_bis,
    )

    if effective_strict_segment_rules and effective_bootstrap_mode == SEGMENT_BOOTSTRAP_PREFER_EARLIER_START:
        probe = _extend_segment(
            bis,
            index,
            strict_segment_rules=True,
            enable_gap_false_defer=enable_gap_false_defer,
            enable_fallback_reverse_break=enable_fallback_reverse_break,
            enable_same_direction_fallback=enable_same_direction_fallback,
        )
        if probe is None:
            index = 0

    anchor_idx: Optional[int] = None
    while index <= len(bis) - 3:
        current_enable_gap_false_defer = enable_gap_false_defer and not segments
        result = _extend_segment(
            bis,
            index,
            anchor_idx=anchor_idx,
            strict_segment_rules=effective_strict_segment_rules,
            enable_gap_false_defer=current_enable_gap_false_defer,
            enable_fallback_reverse_break=enable_fallback_reverse_break,
            enable_same_direction_fallback=enable_same_direction_fallback,
        )
        if result is None:
            index += 1
            anchor_idx = None
            continue

        end_idx, is_confirmed, break_idx, stop_reason, break_bi_id = result
        effective_end_idx = end_idx
        if termination_mode == SEGMENT_TERMINATION_MODE_THEORY and not is_confirmed:
            effective_end_idx = _resolve_theory_segment_extent(bis, index, end_idx)

        last_same_extreme, last_reverse_extreme = _segment_extremes(bis, index, effective_end_idx)
        candidate = _build_segment(
            segment_id,
            bis,
            index,
            effective_end_idx,
            is_confirmed,
            last_same_extreme=last_same_extreme,
            last_reverse_extreme=last_reverse_extreme,
            break_bi_id=break_bi_id,
            stop_reason=stop_reason,
        )

        if effective_strict_segment_rules and segments and segments[-1].direction == candidate.direction:
            segments[-1] = _merge_segments_same_direction(segments[-1], candidate, bis)
        else:
            segments.append(candidate)
            segment_id += 1

        if not is_confirmed:
            if termination_mode == SEGMENT_TERMINATION_MODE_THEORY:
                index = effective_end_idx + 1
                anchor_idx = None
                continue
            later_seed = _find_later_initial_segment_window(
                bis,
                effective_end_idx,
                strict_segment_rules=effective_strict_segment_rules,
            )
            if later_seed is not None:
                later_seed_start_idx = later_seed[0]
                later_probe = _extend_segment(
                    bis,
                    later_seed_start_idx,
                    anchor_idx=later_seed_start_idx,
                    strict_segment_rules=effective_strict_segment_rules,
                    enable_gap_false_defer=False,
                    enable_fallback_reverse_break=enable_fallback_reverse_break,
                    enable_same_direction_fallback=enable_same_direction_fallback,
                )
                if later_probe is not None and later_probe[1]:
                    index = later_seed_start_idx
                    anchor_idx = later_seed_start_idx
                    continue
            break

        if break_idx is not None:
            index = break_idx
            anchor_idx = break_idx
        else:
            index = end_idx + 1
            anchor_idx = None

    return segments