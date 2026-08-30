from pathlib import Path

import pytest

from chanlun.segment import StopOutcomeCategory, classify_stop_reason
from tests.segment_regression_support import identify_segments_from_csv, load_bis_from_csv


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    {
        "name": "000591-day",
        "csv_path": ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20210914_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break"},
        "min_segments": 3,
        "min_confirmed": 2,
        "min_preprocessing": 0,
    },
    {
        "name": "000591-1m",
        "csv_path": ROOT / "data" / "reports" / "000591" / "1m" / "analyze" / "000591_1m_20260810_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_gap_fractal", "reverse_break", "same_direction_not_extending"},
        "min_segments": 3,
        "min_confirmed": 2,
        "min_preprocessing": 0,
    },
    {
        "name": "000591-5m",
        "csv_path": ROOT / "data" / "reports" / "000591" / "5m" / "analyze" / "000591_5m_20260715_to_20260828.csv",
        "expected_stop_reasons": {"reverse_break"},
        "min_segments": 2,
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
        "csv_path": ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260319_to_20260828.csv",
        "expected_stop_reasons": {"reverse_break", "feature_sequence_gap_fractal", "feature_sequence_fractal"},
        "min_segments": 6,
        "min_confirmed": 5,
        "min_preprocessing": 0,
    },
    {
        "name": "00700-1m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "1m" / "analyze" / "00700_1m_20260814_to_20260828.csv",
        "expected_stop_reasons": {"reverse_break", "same_direction_not_extending"},
        "min_segments": 2,
        "min_confirmed": 1,
        "min_preprocessing": 1,
    },
    {
        "name": "00700-5m",
        "csv_path": ROOT / "data" / "reports" / "00700" / "5m" / "analyze" / "00700_5m_20260722_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"},
        "min_segments": 8,
        "min_confirmed": 6,
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
        "csv_path": ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260319_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "exhausted_confirmed_bis"},
        "min_segments": 5,
        "min_confirmed": 4,
        "min_preprocessing": 1,
    },
    {
        "name": "03690-1m",
        "csv_path": ROOT / "data" / "reports" / "03690" / "1m" / "analyze" / "03690_1m_20260814_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break", "same_direction_not_extending"},
        "min_segments": 12,
        "min_confirmed": 10,
        "min_preprocessing": 1,
    },
    {
        "name": "03690-5m",
        "csv_path": ROOT / "data" / "reports" / "03690" / "5m" / "analyze" / "03690_5m_20260722_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"},
        "min_segments": 10,
        "min_confirmed": 10,
        "min_preprocessing": 0,
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
        "expected_stop_reasons": {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"},
        "min_segments": 2,
        "min_confirmed": 1,
        "min_preprocessing": 0,
    },
    {
        "name": "300124-1m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "1m" / "analyze" / "300124_1m_20260810_to_20260828.csv",
        "expected_stop_reasons": {"exhausted_confirmed_bis", "feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"},
        "min_segments": 18,
        "min_confirmed": 17,
        "min_preprocessing": 1,
    },
    {
        "name": "300124-5m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "5m" / "analyze" / "300124_5m_20260715_to_20260828.csv",
        "expected_stop_reasons": {"feature_sequence_fractal", "reverse_break", "same_direction_not_extending"},
        "min_segments": 6,
        "min_confirmed": 5,
        "min_preprocessing": 1,
    },
    {
        "name": "300124-60m",
        "csv_path": ROOT / "data" / "reports" / "300124" / "60m" / "analyze" / "300124_60m_20260213_to_20260618.csv",
        "expected_stop_reasons": {"exhausted_confirmed_bis", "reverse_break"},
        "min_segments": 4,
        "min_confirmed": 3,
        "min_preprocessing": 1,
    },
]


CROSS_CYCLE_GROUPS = {
    "000591": ["000591-day", "000591-1m", "000591-5m", "000591-60m"],
    "00700": ["00700-30m", "00700-1m", "00700-5m", "00700-60m"],
    "03690": ["03690-30m", "03690-1m", "03690-5m", "03690-60m"],
    "300124": ["300124-15m", "300124-1m", "300124-5m", "300124-60m"],
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
    "00700-1m",
    "300124-1m",
    "03690-1m",
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

    assert len(practical_segments) >= 4
    second = practical_segments[1]
    third = practical_segments[2]
    fourth = practical_segments[3]

    # effective_only 后该窗口不再含 overlap-reuse（下一段起点 < 上一段 break），
    # 改为干净的 restart 链：每段起点 == 上一段 break，且尾段为 pending 的 exhausted。
    assert second.direction.value == "down"
    assert second.start_bi_id == 5
    assert second.end_bi_id == 15
    assert second.break_bi_id == 16
    assert second.stop_reason == "reverse_break"
    assert third.direction.value == "up"
    assert third.start_bi_id == second.break_bi_id
    assert third.start_bi_id == 16
    assert third.break_bi_id == 21
    assert third.stop_reason == "reverse_break"
    assert fourth.direction.value == "down"
    assert fourth.start_bi_id == third.break_bi_id
    assert fourth.start_bi_id == 21
    assert fourth.break_bi_id == 26
    assert fourth.stop_reason == "exhausted_confirmed_bis"


def test_00700_5m_practical_keeps_mixed_stop_reasons_with_overlap_reuse_anchors() -> None:
    """00700 5m：锁住混合 stop_reason 链与 overlap-reuse 边界。

    effective_only 后 00700 5m 的 overlap-reuse 锚点迁移到：
    段 2 `down 6-8 break=11` 后段 3 `up 9-39` 起点 9 < break 11，
    段 12 `down 98-102 break=105` 后段 13 `up 103-105` 起点 103 < break 105：
    这两处都是「下一段在上一段 break 之前复用重叠区域」的 overlap-reuse 锚点，
    对应 S3 重写/吸收/复用输出口径不得漂移。
    """
    scenario = next(item for item in SCENARIOS if item["name"] == "00700-5m")
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    practical_segments = identify_segments_from_csv(csv_path, termination_mode="practical")

    assert len(practical_segments) >= 14
    seg2 = practical_segments[2]
    seg3 = practical_segments[3]
    seg12 = practical_segments[12]
    seg13 = practical_segments[13]

    # overlap-reuse #1: down 6-8 reverse_break break=11, next up 9-39 起点在 break 之前
    assert seg2.direction.value == "down"
    assert seg2.start_bi_id == 6
    assert seg2.end_bi_id == 8
    assert seg2.break_bi_id == 11
    assert seg2.stop_reason == "reverse_break"
    assert seg3.direction.value == "up"
    assert seg3.start_bi_id == 9
    assert seg3.start_bi_id == seg2.break_bi_id - 2
    assert seg3.end_bi_id == 39
    assert seg3.stop_reason == "feature_sequence_fractal"

    # overlap-reuse #2: down 98-102 reverse_break break=105, next up 103-105 起点在 break 之前
    assert seg12.direction.value == "down"
    assert seg12.start_bi_id == 98
    assert seg12.end_bi_id == 102
    assert seg12.break_bi_id == 105
    assert seg12.stop_reason == "reverse_break"
    assert seg13.direction.value == "up"
    assert seg13.start_bi_id == 103
    assert seg13.start_bi_id == seg12.break_bi_id - 2
    assert seg13.end_bi_id == 105
    assert seg13.stop_reason == "reverse_break"


def test_300124_5m_practical_keeps_mixed_stop_reasons_with_pending_middle_tail() -> None:
    """300124 5m：锁住混合 stop_reason 链与「历史中间段仍带 pending 停靠标签」。

    effective_only 后 300124 5m 的中间 pending 段迁移到：
    段 7 `up 50-62 same_direction_not_extending is_confirmed=False` 之后仍有
    已确认段 8/9（down 65-67、up 68-82），锁住「中间 pending 段在后续段存在时
    必须留在交替链中、不能被裁掉」的口径（否则该窗口会塌缩出错误的段集合）。
    """
    scenario = next(item for item in SCENARIOS if item["name"] == "300124-5m")
    csv_path = scenario["csv_path"]
    assert isinstance(csv_path, Path)
    assert csv_path.exists(), f"missing fixture csv: {csv_path}"

    practical_segments = identify_segments_from_csv(csv_path, termination_mode="practical")

    assert len(practical_segments) >= 9
    expected_head = [
        ("down", 5, 11, "reverse_break", True),
        ("up", 12, 18, "feature_sequence_gap_fractal", True),
        ("down", 19, 21, "feature_sequence_fractal", True),
        ("up", 22, 24, "feature_sequence_fractal", True),
        ("down", 25, 29, "feature_sequence_fractal", True),
        ("up", 30, 34, "reverse_break", True),
        ("down", 35, 49, "reverse_break", True),
        ("up", 50, 62, "same_direction_not_extending", False),
        ("down", 65, 67, "feature_sequence_fractal", True),
    ]
    for segment, (direction, start, end, reason, confirmed) in zip(practical_segments, expected_head):
        assert segment.direction.value == direction
        assert segment.start_bi_id == start
        assert segment.end_bi_id == end
        assert segment.stop_reason == reason
        assert segment.is_confirmed is confirmed
