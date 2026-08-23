---
spec_id: SPEC.SEGMENT.STOP_REASON
status: stable
owner: chanlun
applyTo: src/chanlun/segment.py
tests: tests/test_segment_rediscrimination_matrix.py, tests/test_segment.py
---

# 线段 stop_reason 接口契约

本页是线段 `stop_reason` 与 `stop_category` 的统一对外口径。

适用对象：

- 报表生成脚本
- miniapp 发布打包脚本
- 下游策略/前端消费方

代码入口：

- `src/chanlun/segment.py` 的 `get_stop_reason_contract()`

## 分类契约

当前按 `StopOutcomeCategory` 分组：

1. `theory_confirmed`
- `feature_sequence_fractal`
- `feature_sequence_gap_fractal`
- `feature_sequence_gap_fractal_delayed_true`

2. `fallback_confirmed`
- `reverse_break`
- `reverse_break_after_gap`

3. `pending`
- `unexpected_same_direction`
- `no_followup_same_direction`
- `same_direction_slot_not_filled`
- `same_direction_not_extending`
- `transition_pending`
- `exhausted_confirmed_bis`

4. `unknown`
- 空集合（仅用于未知码或空值兜底）

## 消费约定

1. 严格几何口径
- 优先消费 `theory_confirmed`

2. 实盘工程口径
- 可消费 `theory_confirmed + fallback_confirmed`
- 建议在展示层明确区分两类来源

3. 待确认状态
- `pending` 只表示结构待确认，不应当作已终结信号

## 稳定性要求

- 任一 `stop_reason` 只能属于一个 category（互斥）
- 新增 `stop_reason` 必须同步更新本页与回归测试

建议配套回归（现有）：

- `tests/test_segment_rediscrimination_matrix.py` 中 contract 相关断言
