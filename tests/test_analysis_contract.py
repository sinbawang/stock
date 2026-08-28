"""analysis 契约一致性测试（SDD：代码枚举是唯一事实源）。spec_id: SPEC.CHANLUN.RULE。

锁定 `analysis_contract.py` 的 signal_point / signal_basis / structure_status
三个字段族的枚举完整性、label/note 投影，以及与 `analysis.py` 消费者字典的
一致性（`is` 同一对象，杜绝第二份拷贝）。
"""
from __future__ import annotations

from chanlun import analysis
from chanlun.analysis_contract import (
    PRECISION_DYNAMIC_GRADE_LABELS,
    PRECISION_DYNAMIC_GRADE_NOTES,
    SIGNAL_BASIS_LABELS,
    SIGNAL_POINT_LABELS,
    STRUCTURE_STATUS_LABELS,
    STRUCTURE_STATUS_NOTES,
    PrecisionDynamicGrade,
    SignalBasis,
    SignalPoint,
    StructureStatus,
    get_analysis_contract,
)


def test_signal_point_enum_is_stable_and_complete() -> None:
    assert {member.value for member in SignalPoint} == {
        "buy_1",
        "buy_2",
        "buy_3",
        "sell_1",
        "sell_2",
        "sell_3",
    }


def test_signal_basis_enum_is_stable_and_complete() -> None:
    assert {member.value for member in SignalBasis} == {
        "bottom_divergence_near_zs_low",
        "buy1_pullback_confirmation",
        "leave_zs_then_pullback_holds_upper_edge",
        "top_divergence_near_zs_high",
        "sell1_rebound_confirmation",
        "leave_zs_then_rebound_fails_lower_edge",
    }


def test_structure_status_enum_is_stable_and_complete() -> None:
    assert {member.value for member in StructureStatus} == {
        "ongoing_same_type",
        "candidate_completed_waiting_stability",
        "completed_then_new_type",
    }


def test_precision_dynamic_grade_enum_is_stable_and_complete() -> None:
    assert {member.value for member in PrecisionDynamicGrade} == {
        "oscillation_opportunity",
        "warning",
        "no_operational_value",
    }


def test_analysis_consumes_the_same_label_and_note_objects() -> None:
    """analysis.py 的展示字典必须直接来自契约模块，不得维护第二份拷贝。"""
    assert analysis.SIGNAL_POINT_LABELS is SIGNAL_POINT_LABELS
    assert analysis.SIGNAL_BASIS_LABELS is SIGNAL_BASIS_LABELS
    assert analysis.STRUCTURE_STATUS_LABELS is STRUCTURE_STATUS_LABELS
    assert analysis.STRUCTURE_STATUS_NOTES is STRUCTURE_STATUS_NOTES


def test_contract_projection_covers_all_codes_with_non_empty_labels() -> None:
    contract = get_analysis_contract()

    assert set(contract) == {"signal_point", "signal_basis", "structure_status", "precision_dynamic_grade"}

    for family, entries in contract.items():
        assert entries, f"{family} 契约为空"
        for code, (label, note) in entries.items():
            assert code, f"{family} 存在空 code"
            assert label, f"{family}.{code} label 为空"
            # structure_status / precision_dynamic_grade 必须带 note；signal_point / signal_basis 暂允许 note 为空。
            if family in {"structure_status", "precision_dynamic_grade"}:
                assert note, f"{family}.{code} note 为空"


def test_signal_point_labels_follow_buy_sell_semantics() -> None:
    assert SIGNAL_POINT_LABELS[SignalPoint.BUY_1.value] == "一买"
    assert SIGNAL_POINT_LABELS[SignalPoint.BUY_2.value] == "二买"
    assert SIGNAL_POINT_LABELS[SignalPoint.BUY_3.value] == "三买"
    assert SIGNAL_POINT_LABELS[SignalPoint.SELL_1.value] == "一卖"
    assert SIGNAL_POINT_LABELS[SignalPoint.SELL_2.value] == "二卖"
    assert SIGNAL_POINT_LABELS[SignalPoint.SELL_3.value] == "三卖"
