from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from chanlun.models import Bi, BiDirection


@dataclass(frozen=True)
class LessonBoundaryCase:
    name: str
    lesson: int
    bis: list[Bi]
    expected_first_stop_reason: str
    expected_first_confirmed: bool
    expected_min_segments_theory: int
    expected_min_segments_practical: int
    expected_first_stop_reason_practical: str | None = None


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


def get_lesson_boundary_cases() -> list[LessonBoundaryCase]:
    return [
        LessonBoundaryCase(
            name="lesson62-overlap-seed",
            lesson=62,
            bis=[
                _bi(0, BiDirection.UP, 120, 100),
                _bi(1, BiDirection.DOWN, 118, 105),
                _bi(2, BiDirection.UP, 119, 106),
            ],
            expected_first_stop_reason="exhausted_confirmed_bis",
            expected_first_confirmed=False,
            expected_min_segments_theory=1,
            expected_min_segments_practical=1,
        ),
        LessonBoundaryCase(
            name="lesson67-feature-fractal-break",
            lesson=67,
            bis=[
                _bi(0, BiDirection.UP, 120, 100),
                _bi(1, BiDirection.DOWN, 112, 104),
                _bi(2, BiDirection.UP, 125, 106),
                _bi(3, BiDirection.DOWN, 111, 105),
                _bi(4, BiDirection.UP, 126, 107),
                _bi(5, BiDirection.DOWN, 118, 108),
                _bi(6, BiDirection.UP, 130, 109),
                _bi(7, BiDirection.DOWN, 110, 102),
            ],
            expected_first_stop_reason="feature_sequence_fractal",
            expected_first_confirmed=True,
            expected_min_segments_theory=2,
            expected_min_segments_practical=2,
        ),
        LessonBoundaryCase(
            name="lesson71-transition-pending",
            lesson=71,
            bis=[
                _bi(0, BiDirection.UP, 100, 90),
                _bi(1, BiDirection.DOWN, 95, 85),
                _bi(2, BiDirection.UP, 105, 95),
                _bi(3, BiDirection.DOWN, 94, 80),
                _bi(4, BiDirection.UP, 96, 87),
            ],
            expected_first_stop_reason="transition_pending",
            expected_first_confirmed=False,
            expected_min_segments_theory=1,
            expected_min_segments_practical=1,
        ),
        LessonBoundaryCase(
            name="lesson78-gap-delayed-true",
            lesson=78,
            bis=[
                _bi(0, BiDirection.UP, 120, 100),
                _bi(1, BiDirection.DOWN, 108, 104),
                _bi(2, BiDirection.UP, 125, 106),
                _bi(3, BiDirection.DOWN, 112, 109),
                _bi(4, BiDirection.UP, 111.0, 110.0),
                _bi(5, BiDirection.DOWN, 110.8, 109.4),
                _bi(6, BiDirection.UP, 111.6, 109.0),
                _bi(7, BiDirection.DOWN, 110.0, 108.6),
                _bi(8, BiDirection.UP, 116.0, 109.0),
            ],
            # 缺口分型后的再分辨：下跌特征序列在 bi3 出现缺口（bi5.low=109.4 未破
            # bi3.low=109），先经一轮「弱同向未突破」，随后更晚同向强推进 bi7.low=108.6
            # 破 bi3.low=109 → 缺口分型延迟确认旧线段终结（71 课「先破终点/先破起点」
            # 再分辨主路径）。theory / practical 均落 `feature_sequence_gap_fractal_delayed_true`
            # 且 confirmed=True。见 docs/chanlun/segment-visual-example-library.md 7.6 R6。
            expected_first_stop_reason="feature_sequence_gap_fractal_delayed_true",
            expected_first_stop_reason_practical="feature_sequence_gap_fractal_delayed_true",
            expected_first_confirmed=True,
            expected_min_segments_theory=2,
            expected_min_segments_practical=2,
        ),
    ]
