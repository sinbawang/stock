"""中枢契约一致性测试（SDD：代码枚举是唯一事实源）。spec_id: SPEC.ZHONGSHU.DUAL_TRACK。

锁定 `zhongshu_contract.py` 四个字段族的枚举完整性、label/note 投影，
以及与 `analysis.py` 消费者字典的一致性。防止「契约声明了但实现不产出」这类
漂移（如 `reverse_break_after_gap` 曾出现的契约-行为脱节）。
"""
from __future__ import annotations

from chanlun import analysis
from chanlun.zhongshu_contract import (
    CONSUMPTION_LEVEL_LABELS,
    CONSUMPTION_LEVEL_NOTES,
    TRANSITION_STATE_LABELS,
    TRANSITION_STATE_NOTES,
    ZS_MONITOR_ALERT_LABELS,
    ZS_MONITOR_BIAS_LABELS,
    ConsumptionLevel,
    ZhongshuMonitorAlert,
    ZhongshuMonitorBias,
    ZhongshuTransitionState,
    get_zhongshu_contract,
)


def test_transition_state_enum_is_stable_and_complete() -> None:
    assert {member.value for member in ZhongshuTransitionState} == {
        "none",
        "same_type_extension",
        "candidate_new_type",
        "ongoing_new_type",
    }


def test_consumption_level_enum_is_stable_and_complete() -> None:
    assert {member.value for member in ConsumptionLevel} == {
        "auxiliary",
        "pending",
        "confirmed",
    }


def test_zs_monitor_alert_enum_is_stable_and_complete() -> None:
    assert {member.value for member in ZhongshuMonitorAlert} == {
        "none",
        "pre_breakout",
        "pre_breakdown",
    }


def test_zs_monitor_bias_enum_is_stable_and_complete() -> None:
    assert {member.value for member in ZhongshuMonitorBias} == {
        "strong",
        "weak",
        "neutral",
    }


def test_analysis_consumes_the_same_label_and_note_objects() -> None:
    """analysis.py 的展示字典必须直接来自契约模块，不得维护第二份拷贝。"""
    assert analysis.TRANSITION_STATE_LABELS is TRANSITION_STATE_LABELS
    assert analysis.TRANSITION_STATE_NOTES is TRANSITION_STATE_NOTES
    assert analysis.CONSUMPTION_LEVEL_LABELS is CONSUMPTION_LEVEL_LABELS
    assert analysis.CONSUMPTION_LEVEL_NOTES is CONSUMPTION_LEVEL_NOTES


def test_contract_projection_covers_all_codes_with_non_empty_labels() -> None:
    contract = get_zhongshu_contract()

    assert set(contract) == {
        "transition_state",
        "consumption_level",
        "zs_monitor_alert",
        "zs_monitor_bias",
    }

    for family, entries in contract.items():
        assert entries, f"{family} 契约为空"
        for code, (label, note) in entries.items():
            assert code, f"{family} 存在空 code"
            assert label, f"{family}.{code} label 为空"
            # transition_state / consumption_level 必须带 note；alert/bias 暂允许 note 为空。
            if family in {"transition_state", "consumption_level"}:
                assert note, f"{family}.{code} note 为空"


def test_alert_and_bias_labels_are_watch_only_semantics() -> None:
    """预警/偏向标签必须保持 watch/pending 语义，不得带 confirmed 措辞。"""
    assert ZS_MONITOR_ALERT_LABELS[ZhongshuMonitorAlert.NONE.value] == "无预警"
    assert ZS_MONITOR_ALERT_LABELS[ZhongshuMonitorAlert.PRE_BREAKOUT.value] == "向上预警"
    assert ZS_MONITOR_ALERT_LABELS[ZhongshuMonitorAlert.PRE_BREAKDOWN.value] == "向下预警"

    assert ZS_MONITOR_BIAS_LABELS[ZhongshuMonitorBias.STRONG.value] == "偏强"
    assert ZS_MONITOR_BIAS_LABELS[ZhongshuMonitorBias.WEAK.value] == "偏弱"
    assert ZS_MONITOR_BIAS_LABELS[ZhongshuMonitorBias.NEUTRAL.value] == "中性"

    assert all("确认" not in label for label in ZS_MONITOR_ALERT_LABELS.values())
    assert all("确认" not in label for label in ZS_MONITOR_BIAS_LABELS.values())
