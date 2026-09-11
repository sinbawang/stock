"""analysis 层机器可读契约（SDD 唯一事实源）。

覆盖 `analysis.py` 中除中枢字段族之外的展示契约：
- `signal_point`   买卖点信号（一买/二买/三买/一卖/二卖/三卖）
- `signal_basis`   买卖点依据
- `structure_status` 当前结构切分状态

约定与 `zhongshu_contract.py` 一致：`Enum` 是语义事实源，`*_LABELS` / `*_NOTES`
是它的展示投影；`analysis.py` 从本模块导入，不再维护第二份拷贝；
`tests/test_analysis_contract.py` 锁定完整性。
"""
from __future__ import annotations

from enum import Enum


class SignalPoint(str, Enum):
    """买卖点信号枚举（缠论一/二/三类买卖点）。"""

    BUY_1 = "buy_1"
    BUY_2 = "buy_2"
    BUY_3 = "buy_3"
    SELL_1 = "sell_1"
    SELL_2 = "sell_2"
    SELL_3 = "sell_3"
    # 类二类买卖点（LB2 / LS2）：同级别隔段背驰生成，无前置一类点、不设破前低/前高。
    BUY_2_LIKE = "buy_2like"
    SELL_2_LIKE = "sell_2like"
    # 类一类买卖点（LB1 / LS1）：盘整背驰（range 门控）构成的类第一类转折点。
    BUY_1_LIKE = "buy_1like"
    SELL_1_LIKE = "sell_1like"


class SignalBasis(str, Enum):
    """买卖点依据枚举。"""

    BOTTOM_DIVERGENCE_NEAR_ZS_LOW = "bottom_divergence_near_zs_low"
    BUY1_PULLBACK_CONFIRMATION = "buy1_pullback_confirmation"
    LEAVE_ZS_THEN_PULLBACK_HOLDS_UPPER_EDGE = "leave_zs_then_pullback_holds_upper_edge"
    TOP_DIVERGENCE_NEAR_ZS_HIGH = "top_divergence_near_zs_high"
    SELL1_REBOUND_CONFIRMATION = "sell1_rebound_confirmation"
    LEAVE_ZS_THEN_REBOUND_FAILS_LOWER_EDGE = "leave_zs_then_rebound_fails_lower_edge"
    GAP_SEGMENT_DIVERGENCE_PULLBACK_END = "gap_segment_divergence_pullback_end"
    GAP_SEGMENT_DIVERGENCE_REBOUND_END = "gap_segment_divergence_rebound_end"
    CONSOLIDATION_DIVERGENCE_REVERSE_LOW = "consolidation_divergence_reverse_low"
    CONSOLIDATION_DIVERGENCE_REVERSE_HIGH = "consolidation_divergence_reverse_high"


class SignalLifecycleState(str, Enum):
    """买卖点信号生命周期状态（spec §2.8）。

    `forming`：核心背驰 / 离开条件已成立、反向转折尚未确认，仅 watch 观察态，不得升 confirmed。
    `confirmed`：反向转折已确认，锚定已确认笔 / 线段，可操作确认态。
    `invalidated`：确认后成立前提被后续走势破坏，保留锚点与 `invalidated_reason`。
    """

    FORMING = "forming"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"


class SignalInvalidatedReason(str, Enum):
    """`confirmed → invalidated` 失效原因枚举（spec §2.8，买卖两侧对称）。"""

    FIRST_CLASS_EXTREME_BROKEN = "first_class_extreme_broken"
    SECOND_CLASS_PULLBACK_FAILED = "second_class_pullback_failed"
    THIRD_CLASS_REENTERED_ZS = "third_class_reentered_zs"
    CONSOLIDATION_DIVERGENCE_LOST = "consolidation_divergence_lost"
    GAP_DIVERGENCE_LOST = "gap_divergence_lost"


class StructureStatus(str, Enum):
    """当前结构切分状态枚举。"""

    ONGOING_SAME_TYPE = "ongoing_same_type"
    CANDIDATE_COMPLETED_WAITING_STABILITY = "candidate_completed_waiting_stability"
    COMPLETED_THEN_NEW_TYPE = "completed_then_new_type"


class PrecisionDynamicGrade(str, Enum):
    """86课：次级别买卖点相对大级别中枢漂移方向的操作意义分级。"""

    OSCILLATION_OPPORTUNITY = "oscillation_opportunity"
    WARNING = "warning"
    NO_OPERATIONAL_VALUE = "no_operational_value"


class SmallToLargeStatus(str, Enum):
    """小转大状态：仅区分候选与必要条件已具备，不直接宣称大级别已确认。"""

    CANDIDATE = "candidate"
    THIRD_CLASS_CONFIRMED = "third_class_confirmed"


SIGNAL_POINT_LABELS = {
    SignalPoint.BUY_1.value: "一买",
    SignalPoint.BUY_2.value: "二买",
    SignalPoint.BUY_3.value: "三买",
    SignalPoint.SELL_1.value: "一卖",
    SignalPoint.SELL_2.value: "二卖",
    SignalPoint.SELL_3.value: "三卖",
    SignalPoint.BUY_2_LIKE.value: "类二买",
    SignalPoint.SELL_2_LIKE.value: "类二卖",
    SignalPoint.BUY_1_LIKE.value: "类一买",
    SignalPoint.SELL_1_LIKE.value: "类一卖",
}


SIGNAL_BASIS_LABELS = {
    SignalBasis.BOTTOM_DIVERGENCE_NEAR_ZS_LOW.value: "中枢下沿附近出现底背驰",
    SignalBasis.BUY1_PULLBACK_CONFIRMATION.value: "一买后回抽确认，低点未再跌破前低",
    SignalBasis.LEAVE_ZS_THEN_PULLBACK_HOLDS_UPPER_EDGE.value: "离开中枢后回踩上沿未失守",
    SignalBasis.TOP_DIVERGENCE_NEAR_ZS_HIGH.value: "中枢上沿附近出现顶背驰",
    SignalBasis.SELL1_REBOUND_CONFIRMATION.value: "一卖后反抽确认，高点未再突破前高",
    SignalBasis.LEAVE_ZS_THEN_REBOUND_FAILS_LOWER_EDGE.value: "跌破中枢后反抽下沿失败",
    SignalBasis.GAP_SEGMENT_DIVERGENCE_PULLBACK_END.value: "同级别隔段背驰，回踩结束即生成（无需前置一买、不破前低）",
    SignalBasis.GAP_SEGMENT_DIVERGENCE_REBOUND_END.value: "同级别隔段背驰，反抽结束即生成（无需前置一卖、不破前高）",
    SignalBasis.CONSOLIDATION_DIVERGENCE_REVERSE_LOW.value: "盘整背驰（离开段 vs 进入段），离开段结束向上转折即生成（趋势门控缺席时补点）",
    SignalBasis.CONSOLIDATION_DIVERGENCE_REVERSE_HIGH.value: "盘整背驰（离开段 vs 进入段），离开段结束向下转折即生成（趋势门控缺席时补点）",
}


SIGNAL_LIFECYCLE_STATE_LABELS = {
    SignalLifecycleState.FORMING.value: "预备",
    SignalLifecycleState.CONFIRMED.value: "确认",
    SignalLifecycleState.INVALIDATED.value: "已失效",
}


SIGNAL_LIFECYCLE_STATE_NOTES = {
    SignalLifecycleState.FORMING.value: "背驰/离开条件已成立、反向转折待确认，仅按 watch 观察，不构成确认买卖点。",
    SignalLifecycleState.CONFIRMED.value: "反向转折已确认、锚定已确认笔/线段，可操作确认态（仍受多级别降级约束）。",
    SignalLifecycleState.INVALIDATED.value: "确认后成立前提被后续走势破坏，按失效/撤单处理，不再作可操作确认态。",
}


SIGNAL_INVALIDATED_REASON_LABELS = {
    SignalInvalidatedReason.FIRST_CLASS_EXTREME_BROKEN.value: "离开段极值被有效跌破/升破",
    SignalInvalidatedReason.SECOND_CLASS_PULLBACK_FAILED.value: "回抽/反抽破前低/前高，首次确认性回抽失败",
    SignalInvalidatedReason.THIRD_CLASS_REENTERED_ZS.value: "首次回试/反抽重新跌回/站回中枢",
    SignalInvalidatedReason.CONSOLIDATION_DIVERGENCE_LOST.value: "盘整背驰前提消失或 range 门控退出",
    SignalInvalidatedReason.GAP_DIVERGENCE_LOST.value: "隔段背驰前提消失或同级别分解退出 single_confirmed",
}


STRUCTURE_STATUS_LABELS = {
    StructureStatus.ONGOING_SAME_TYPE.value: "同类延伸中",
    StructureStatus.CANDIDATE_COMPLETED_WAITING_STABILITY.value: "候选完成待确认",
    StructureStatus.COMPLETED_THEN_NEW_TYPE.value: "已切入新走势",
}


STRUCTURE_STATUS_NOTES = {
    StructureStatus.ONGOING_SAME_TYPE.value: "当前仍优先按同一走势类型内部延伸处理，不抢先切分。",
    StructureStatus.CANDIDATE_COMPLETED_WAITING_STABILITY.value: "前段走势已具备完成候选，但边界仍待右侧结构确认稳定。",
    StructureStatus.COMPLETED_THEN_NEW_TYPE.value: "前段走势完成边界已相对稳定，当前按新的同级别走势类型处理。",
}


PRECISION_DYNAMIC_GRADE_LABELS = {
    PrecisionDynamicGrade.OSCILLATION_OPPORTUNITY.value: "震荡机会",
    PrecisionDynamicGrade.WARNING.value: "警戒",
    PrecisionDynamicGrade.NO_OPERATIONAL_VALUE.value: "无操作价值",
}


PRECISION_DYNAMIC_GRADE_NOTES = {
    PrecisionDynamicGrade.OSCILLATION_OPPORTUNITY.value: "大级别中枢震荡，次级别买卖点仅构成震荡机会。",
    PrecisionDynamicGrade.WARNING.value: "次级别买卖点与大级别中枢漂移方向相反，仅作警戒，不急于执行。",
    PrecisionDynamicGrade.NO_OPERATIONAL_VALUE.value: "次级别买卖点与大级别中枢漂移方向相同但已滞后，基本无新增操作价值。",
}


SMALL_TO_LARGE_STATUS_LABELS = {
    SmallToLargeStatus.CANDIDATE.value: "小转大候选",
    SmallToLargeStatus.THIRD_CLASS_CONFIRMED.value: "小转大必要条件已具备",
}


SMALL_TO_LARGE_STATUS_NOTES = {
    SmallToLargeStatus.CANDIDATE.value: "次级别转折已出现，但最后一个次级别中枢尚未见对应三类买卖点，当前只能按小转大候选观察。",
    SmallToLargeStatus.THIRD_CLASS_CONFIRMED.value: "最后一个次级别中枢已出现对应三类买卖点，仅说明小转大的必要条件已具备，仍不等于高级别转折充分确认。",
}


def get_analysis_contract() -> dict[str, dict[str, tuple[str, str]]]:
    """返回机器可读的 analysis 契约投影。

    结构：`{字段族: {code: (label, note)}}`（无 note 的字段族 note 为空串）。
    """
    return {
        "signal_point": {
            member.value: (SIGNAL_POINT_LABELS[member.value], "")
            for member in SignalPoint
        },
        "signal_basis": {
            member.value: (SIGNAL_BASIS_LABELS[member.value], "")
            for member in SignalBasis
        },
        "signal_lifecycle_state": {
            member.value: (SIGNAL_LIFECYCLE_STATE_LABELS[member.value], SIGNAL_LIFECYCLE_STATE_NOTES[member.value])
            for member in SignalLifecycleState
        },
        "signal_invalidated_reason": {
            member.value: (SIGNAL_INVALIDATED_REASON_LABELS[member.value], "")
            for member in SignalInvalidatedReason
        },
        "structure_status": {
            member.value: (STRUCTURE_STATUS_LABELS[member.value], STRUCTURE_STATUS_NOTES[member.value])
            for member in StructureStatus
        },
        "precision_dynamic_grade": {
            member.value: (PRECISION_DYNAMIC_GRADE_LABELS[member.value], PRECISION_DYNAMIC_GRADE_NOTES[member.value])
            for member in PrecisionDynamicGrade
        },
        "small_to_large_status": {
            member.value: (SMALL_TO_LARGE_STATUS_LABELS[member.value], SMALL_TO_LARGE_STATUS_NOTES[member.value])
            for member in SmallToLargeStatus
        },
    }
