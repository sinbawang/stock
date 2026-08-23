"""中枢模块机器可读契约（SDD 唯一事实源）。

spec_id: SPEC.ZHONGSHU.DUAL_TRACK（见 docs/chanlun/zhongshu-dual-track-spec.md）。

本模块是中转/消费层四个字段族的唯一事实源：
- `transition_state`  中枢同级别走势转场阶段（ZS2 契约）
- `consumption_level` 同级别结构消费等级（ZS5 三态：auxiliary/pending/confirmed）
- `zs_monitor_alert`  中枢监视预警信号（ZS5.1 契约）
- `zs_monitor_bias`   中枢偏向监视（ZS5.1 契约）

约定：
- `Enum` 是语义事实源，`*_LABELS` / `*_NOTES` 是它的展示投影。
- `analysis.py` 从本模块导入这些字典，不再维护第二份拷贝。
- `tests/test_zhongshu_contract.py` 锁定「枚举完整性 / label-note 非空 / 契约函数投影一致」，
  防止契约与实现静默脱节。
"""
from __future__ import annotations

from enum import Enum


class ZhongshuTransitionState(str, Enum):
    """中枢同级别走势转场阶段（标准中枢主链，ZS2 契约）。"""

    NONE = "none"
    SAME_TYPE_EXTENSION = "same_type_extension"
    CANDIDATE_NEW_TYPE = "candidate_new_type"
    ONGOING_NEW_TYPE = "ongoing_new_type"


class ConsumptionLevel(str, Enum):
    """同级别结构消费等级（ZS5 三态契约）。"""

    AUXILIARY = "auxiliary"
    PENDING = "pending"
    CONFIRMED = "confirmed"


class ZhongshuMonitorAlert(str, Enum):
    """中枢监视预警信号（ZS5.1 契约）。

    `none` 是"当前无预警"的稳定态；`pre_breakout` / `pre_breakdown`
    只允许按 watch/pending 消费，不得直接升格为 confirmed 三买/三卖。
    """

    NONE = "none"
    PRE_BREAKOUT = "pre_breakout"
    PRE_BREAKDOWN = "pre_breakdown"


class ZhongshuMonitorBias(str, Enum):
    """中枢偏向监视（ZS5.1 契约）。

    注：无中枢时的初始态是 `None`（非本枚举成员），表示"尚无中枢可判偏向"；
    本枚举只覆盖有中枢时的 strong/weak/neutral 三档。
    """

    STRONG = "strong"
    WEAK = "weak"
    NEUTRAL = "neutral"


TRANSITION_STATE_LABELS = {
    ZhongshuTransitionState.NONE.value: "无转场",
    ZhongshuTransitionState.SAME_TYPE_EXTENSION.value: "同型延伸",
    ZhongshuTransitionState.CANDIDATE_NEW_TYPE.value: "新走势候选",
    ZhongshuTransitionState.ONGOING_NEW_TYPE.value: "新走势进行中",
}


TRANSITION_STATE_NOTES = {
    ZhongshuTransitionState.NONE.value: "当前还不能从已完成前段稳定推出新的同级别走势转场。",
    ZhongshuTransitionState.SAME_TYPE_EXTENSION.value: "当前仍按前一走势类型的同类延伸处理。",
    ZhongshuTransitionState.CANDIDATE_NEW_TYPE.value: "前段走势已完成，但当前新走势仍处候选待确认阶段。",
    ZhongshuTransitionState.ONGOING_NEW_TYPE.value: "前段走势已完成，当前新的同级别走势类型正在运行中。",
}


CONSUMPTION_LEVEL_LABELS = {
    ConsumptionLevel.AUXILIARY.value: "仅辅助观察",
    ConsumptionLevel.PENDING.value: "待确认消费",
    ConsumptionLevel.CONFIRMED.value: "已确认消费",
}


CONSUMPTION_LEVEL_NOTES = {
    ConsumptionLevel.AUXILIARY.value: "当前还没有稳定的同级别中枢主结构，只能按辅助观察信号消费。",
    ConsumptionLevel.PENDING.value: "当前已有结构线索，但还不能直接升级为同级别强确认结论。",
    ConsumptionLevel.CONFIRMED.value: "当前同级别结构已具备稳定消费基础，可直接按主结构结论解释。",
}


ZS_MONITOR_ALERT_LABELS = {
    ZhongshuMonitorAlert.NONE.value: "无预警",
    ZhongshuMonitorAlert.PRE_BREAKOUT.value: "向上预警",
    ZhongshuMonitorAlert.PRE_BREAKDOWN.value: "向下预警",
}


ZS_MONITOR_BIAS_LABELS = {
    ZhongshuMonitorBias.STRONG.value: "偏强",
    ZhongshuMonitorBias.WEAK.value: "偏弱",
    ZhongshuMonitorBias.NEUTRAL.value: "中性",
}


def _project_enum(enum_cls, labels, notes):
    return {member.value: (labels[member.value], notes[member.value]) for member in enum_cls}


def get_zhongshu_contract() -> dict[str, dict[str, tuple[str, str]]]:
    """返回机器可读的中枢契约投影。

    结构：`{字段族: {code: (label, note)}}`，与 segment 的 `get_stop_reason_contract()`
    同属"代码是唯一事实源、Markdown 是其投影"的 SDD 约定。
    """
    return {
        "transition_state": _project_enum(
            ZhongshuTransitionState, TRANSITION_STATE_LABELS, TRANSITION_STATE_NOTES
        ),
        "consumption_level": _project_enum(
            ConsumptionLevel, CONSUMPTION_LEVEL_LABELS, CONSUMPTION_LEVEL_NOTES
        ),
        "zs_monitor_alert": {
            member.value: (ZS_MONITOR_ALERT_LABELS[member.value], "")
            for member in ZhongshuMonitorAlert
        },
        "zs_monitor_bias": {
            member.value: (ZS_MONITOR_BIAS_LABELS[member.value], "")
            for member in ZhongshuMonitorBias
        },
    }
