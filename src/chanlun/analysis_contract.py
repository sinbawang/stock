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


class SignalBasis(str, Enum):
    """买卖点依据枚举。"""

    BOTTOM_DIVERGENCE_NEAR_ZS_LOW = "bottom_divergence_near_zs_low"
    BUY1_PULLBACK_CONFIRMATION = "buy1_pullback_confirmation"
    LEAVE_ZS_THEN_PULLBACK_HOLDS_UPPER_EDGE = "leave_zs_then_pullback_holds_upper_edge"
    TOP_DIVERGENCE_NEAR_ZS_HIGH = "top_divergence_near_zs_high"
    SELL1_REBOUND_CONFIRMATION = "sell1_rebound_confirmation"
    LEAVE_ZS_THEN_REBOUND_FAILS_LOWER_EDGE = "leave_zs_then_rebound_fails_lower_edge"


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


SIGNAL_POINT_LABELS = {
    SignalPoint.BUY_1.value: "一买",
    SignalPoint.BUY_2.value: "二买",
    SignalPoint.BUY_3.value: "三买",
    SignalPoint.SELL_1.value: "一卖",
    SignalPoint.SELL_2.value: "二卖",
    SignalPoint.SELL_3.value: "三卖",
}


SIGNAL_BASIS_LABELS = {
    SignalBasis.BOTTOM_DIVERGENCE_NEAR_ZS_LOW.value: "中枢下沿附近出现底背驰",
    SignalBasis.BUY1_PULLBACK_CONFIRMATION.value: "一买后回抽确认，低点未再跌破前低",
    SignalBasis.LEAVE_ZS_THEN_PULLBACK_HOLDS_UPPER_EDGE.value: "离开中枢后回踩上沿未失守",
    SignalBasis.TOP_DIVERGENCE_NEAR_ZS_HIGH.value: "中枢上沿附近出现顶背驰",
    SignalBasis.SELL1_REBOUND_CONFIRMATION.value: "一卖后反抽确认，高点未再突破前高",
    SignalBasis.LEAVE_ZS_THEN_REBOUND_FAILS_LOWER_EDGE.value: "跌破中枢后反抽下沿失败",
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
        "structure_status": {
            member.value: (STRUCTURE_STATUS_LABELS[member.value], STRUCTURE_STATUS_NOTES[member.value])
            for member in StructureStatus
        },
        "precision_dynamic_grade": {
            member.value: (PRECISION_DYNAMIC_GRADE_LABELS[member.value], PRECISION_DYNAMIC_GRADE_NOTES[member.value])
            for member in PrecisionDynamicGrade
        },
    }
