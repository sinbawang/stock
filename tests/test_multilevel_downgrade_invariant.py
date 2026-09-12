"""多级别联立降级红线（T2 / BS5 / C3）的不变量闸门。

背景
----
`buy-sell-multi-level-tasks.md` 的 T2 红线是：**锁高一级未确认时下游不得越级显示强确认**，
并称这是「消费层最容易误报强信号的区域」。原实现与该红线的锁定只有 4 个手挑样例
（`auxiliary` / `pending` / legacy-pending / `confirmed`），属举例覆盖而非不变量覆盖。

2026-09-12 核对时发现一个 **fail-open** 兜底：
`_build_same_level_consumption_level(structure_state)` 在三种显式降级信号之外**一律返回
`confirmed`**。也就是说，当 `structure_state` 同时缺 `current_structure_status` 与
`current_ongoing.confirmation_basis`（缺证据）时，消费等级被判成 `confirmed`，
多级别降级闸门直接失效——与 ZS5.2 三态契约原则第 5 条
（「字段缺失时一律按 `unknown -> pending/auxiliary` 降级，不允许补脑成 `confirmed`」）相悖。

可达性已实测：21 个冻结真实窗口 + 4 个冻结 `tech.json` 的这两个字段**全部存在**
（见 `build/probe_consumption_default.py`），且两个生产调用点
（`generate_a_share_single_mixed_report.py` / `generate_h_share_single_mixed_report.py`）
都传入完整 `analyze_chanlun_signals` 载荷。因此该缺陷当前是**潜在**的（未污染真实输出），
硬化后为行为中性；但该函数是**共享**消费等级的唯一兜底，且代码显式支持
「仅带 `structure_state` 的旧 payload」这条兼容路径，故必须 fail closed。

本文件用不变量覆盖替代举例覆盖：
1. 缺证据必须降级（fail closed），且不得影响有证据的正常档位；
2. 上级别未确认（`auxiliary` / `pending`）时，次级别状态在**全参数空间**内都不得为 `actionable`；
3. `small_to_large_status=higher_level_confirmed` 必须要求上级别自身 `confirmed`；
4. 反空转守卫：上级别 `confirmed` 时必须仍能出现 `actionable`，防止「一律降级」也能通过第 2 条。

spec_id: SPEC.BUY_SELL.CORE。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from chanlun.analysis import (
    _build_same_level_consumption_level,
    build_lower_timeframe_precision_entry,
)

UNCONFIRMED = ("auxiliary", "pending")
# 上级别消费等级的取值空间：三个正式档位 + 「字段缺失」。
CONSUMPTION_CASES = ("auxiliary", "pending", "confirmed", None)
# 触发上级别窗口的三条路径，覆盖 signal_points 与背驰两条分支。
TRIGGERS = ("signal", "trend_divergence")
SIDES = ("buy", "sell")
DRIFTS = ("up", "down", "range", None)


def _higher_signals(
    *,
    side: str,
    consumption: str | None,
    drift: str | None,
    trigger: str,
) -> dict[str, object]:
    point = f"{side}1"
    signals: dict[str, object] = {
        "buy_points": [point] if side == "buy" else [],
        "sell_points": [point] if side == "sell" else [],
        "current_zs": SimpleNamespace(
            end_ts=datetime(2026, 5, 10, 14, 0), zs_id=9, exit_bi_id=33, is_terminated=False
        ),
        "structure_state": {"current_ongoing": {"type": drift} if drift else {}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }
    if trigger == "signal":
        signals["signal_points"] = [
            {"point": point, "active": True, "time": "2026-05-10T14:30:00", "price": 10.2, "basis": "divergence"}
        ]
    elif trigger == "trend_divergence":
        signals["divergence"] = {
            "trend": {"active": True, "direction": "down" if side == "buy" else "up", "time": "2026-05-10T14:30:00"},
            "range": {"active": False},
        }
    if consumption is not None:
        signals["same_level_consumption_level"] = consumption
    return signals


def _lower_signals(*, side: str, with_point: bool = True) -> dict[str, object]:
    point = f"{side}2"
    entry = {"point": point, "active": True, "time": "2026-05-10T14:25:00", "price": 10.25, "basis": "pullback"}
    return {
        "buy_points": [point] if with_point and side == "buy" else [],
        "sell_points": [point] if with_point and side == "sell" else [],
        "signal_points": [entry] if with_point else [],
        "signal_catalog": [entry] if with_point else [],
        "structure_state": {"current_ongoing": {"type": "down"}},
        "divergence": {"trend": {"active": False}, "range": {"active": False}},
    }


def _build_entry(
    *,
    side: str,
    consumption: str | None,
    drift: str | None,
    trigger: str,
    with_point: bool = True,
) -> dict[str, object]:
    return build_lower_timeframe_precision_entry(
        _higher_signals(side=side, consumption=consumption, drift=drift, trigger=trigger),
        _lower_signals(side=side, with_point=with_point),
        lower_timeframe="5m",
        lower_timeframe_label="5M",
        pending_reverse_mode="effective_only",
    )


# --- 1. 消费等级兜底必须 fail closed ---


def test_consumption_level_fails_closed_when_evidence_missing() -> None:
    """ZS5.2 ¶5：缺证据不得补脑成 confirmed。"""
    assert _build_same_level_consumption_level({}) == "pending"
    assert _build_same_level_consumption_level({"current_ongoing": {}}) == "pending"
    assert _build_same_level_consumption_level({"current_structure_status": ""}) == "pending"
    assert _build_same_level_consumption_level({"current_ongoing": {"confirmation_basis": ""}}) == "pending"


def test_consumption_level_keeps_documented_downgrades() -> None:
    """三条显式降级信号仍按契约优先返回，不被新兜底影响。"""
    assert _build_same_level_consumption_level({"current_ongoing": {"confirmation_basis": "no_same_level_zhongshu"}}) == "auxiliary"
    assert _build_same_level_consumption_level({"current_structure_status": "candidate_completed_waiting_stability"}) == "pending"
    assert _build_same_level_consumption_level({"current_ongoing": {"confirmation_basis": "single_active_zhongshu"}}) == "pending"


def test_consumption_level_stays_confirmed_when_evidence_present() -> None:
    """反过度降级：有证据的正常结构必须仍是 confirmed。"""
    state = {
        "current_structure_status": "ongoing_same_type",
        "current_ongoing": {"type": "up", "confirmation_basis": "completed_then_new_type"},
    }

    assert _build_same_level_consumption_level(state) == "confirmed"


def test_precision_entry_downgrades_when_consumption_evidence_missing() -> None:
    """端到端：旧 payload 缺消费等级且 structure_state 缺证据时，不得保持 actionable。"""
    entry = _build_entry(side="buy", consumption=None, drift="up", trigger="signal")

    assert entry["higher_consumption_level"] == "pending", entry
    assert entry["status"] == "watch", entry
    assert "不按严格区间套执行" in entry["note"], entry


# --- 2. T2 红线不变量：上级别未确认 ⇒ 次级别不得 actionable ---


@pytest.mark.parametrize("trigger", TRIGGERS)
@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("consumption", CONSUMPTION_CASES)
@pytest.mark.parametrize("drift", DRIFTS)
def test_lower_level_never_actionable_when_higher_unconfirmed(
    trigger: str, side: str, consumption: str | None, drift: str | None
) -> None:
    """全参数空间覆盖，替代原先的 4 个手挑样例。"""
    entry = _build_entry(side=side, consumption=consumption, drift=drift, trigger=trigger)
    resolved = str(entry.get("higher_consumption_level") or "")

    # 缺证据时必须已降级，因此不应出现「未确认却仍 actionable」。
    if consumption is None:
        assert resolved == "pending", (trigger, side, drift, entry)
    if resolved in UNCONFIRMED:
        assert entry["status"] != "actionable", (trigger, side, consumption, drift, entry)


@pytest.mark.parametrize("trigger", TRIGGERS)
@pytest.mark.parametrize("side", SIDES)
def test_invariant_gate_is_not_vacuous(trigger: str, side: str) -> None:
    """反空转：`confirmed` 时必须仍能出现 actionable，否则「一律降级」也能通过上一条。"""
    entry = _build_entry(side=side, consumption="confirmed", drift="up", trigger=trigger)

    assert entry["status"] == "actionable", (trigger, side, entry)


# --- 3. 小转大红线 ---


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("consumption", CONSUMPTION_CASES)
def test_small_to_large_never_upgrades_without_confirmed_higher_level(
    side: str, consumption: str | None
) -> None:
    """第43/44课：高级别未闭环前，不得把小级别背驰升级为「大级别转折已启动」。"""
    entry = _build_entry(side=side, consumption=consumption, drift="up", trigger="signal")
    resolved = str(entry.get("higher_consumption_level") or "")

    if resolved != "confirmed":
        assert entry["small_to_large_status"] != "higher_level_confirmed", (side, consumption, entry)
        assert entry["small_to_large_reverse_confirm"] is None, (side, consumption, entry)
