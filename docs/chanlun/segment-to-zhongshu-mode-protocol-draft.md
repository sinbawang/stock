# 线段到中枢模式传递协议（草案）

本草案定义：当中枢层消费线段结果时，如何处理 `termination_mode=theory/practical` 的语义传递。

## 1. 目标

- 避免中枢层把 `pending` 误当作已终结结构。
- 保证 theory/practical 两条线段口径在中枢层可并行对照。
- 为后续中枢实现提供稳定输入契约。

## 2. 上游输入契约

中枢层至少需要以下字段：

- `stop_reason`
- `stop_category`
- `is_theory_confirmed_stop`
- `is_fallback_confirmed_stop`
- `is_pending_stop`
- `is_confirmed`

字段来源约束：

- 优先使用 [segment-stop-reason-contract.md](segment-stop-reason-contract.md) 的分类口径。
- 不允许下游自行重算 `stop_category` 分组规则。

## 3. 模式传递规则

1. theory 管道
- 仅将 `theory_confirmed` 线段作为中枢终结输入。
- `fallback_confirmed` 在 theory 管道视为待确认信息，不触发中枢终结。

2. practical 管道
- 可同时接受 `theory_confirmed + fallback_confirmed` 作为终结输入。
- `pending` 仍只作为观察态，不触发中枢终结。

3. pending 统一规则
- 任何模式下，`pending` 均不作为中枢完成信号。

## 4. 双管道输出建议

推荐输出两套中枢快照：

- `zhongshu_theory`: 严格几何口径
- `zhongshu_practical`: 实盘可执行口径

并在汇总层明确显示差异来源，防止混读。

## 5. 回归建议

- 线段层：
  - `tests/test_segment_regression_suite.py`
  - `tests/test_segment_lesson_boundary_fixtures.py`
- 消费层：
  - `tests/test_segment_consumer_mode_smoke.py`

后续如落地中枢实现，需补：

- theory/practical 同样本下中枢数量与边界差异回归
- pending 输入不触发中枢完成的负向用例

## 6. 待定项

- 中枢层是否在 API 输出里同时暴露双模式快照。
- 发布包是否默认携带双模式中枢字段，或按开关输出。
- 中枢层是否复用线段层的 `stop_outcome_bucket` 作为中间状态。
