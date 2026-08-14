# 线段到中枢模式传递协议（草案）

本草案定义：当中枢层消费线段结果时，如何处理 `termination_mode=theory/practical` 的语义传递，并统一“中枢/类中枢”命名。

术语约定：

- 中枢：标准中枢，基于线段识别，作为主口径。
- 类中枢：基于笔的近似实现，作为辅助口径。

## 1. 目标

- 避免中枢层把 `pending` 误当作已终结结构。
- 保证 theory/practical 两条线段口径在中枢层可并行对照。
- 为后续中枢实现提供稳定输入契约。
- 统一对外命名：主输出叫“中枢”，笔级输出叫“类中枢”。

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

## 4. 双轨输出建议（中枢主、类中枢辅）

推荐输出两套中枢快照：

- `zhongshus`: 标准中枢主输出（segment-based）
- `lei_zhongshus`: 类中枢辅助输出（bi-based）

每条路径都可再分 theory/practical 视图，例如：

- `zhongshus_theory` / `zhongshus_practical`
- `lei_zhongshus_theory` / `lei_zhongshus_practical`

并在汇总层明确显示差异来源，防止混读。

主辅消费规则：

- 走势类型、一二三类买卖点默认消费 `zhongshus`。
- `lei_zhongshus` 仅用于兼容与辅助解释，不得覆盖主结论。
- 若主辅冲突，对外文本必须明确“主口径采用中枢”。

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

## 7. 结构状态附加字段传递（第29/36/38/39/92课）

为对齐主规则文档新增条款，建议中枢消费层在双轨输出之外，再透传一组“结构解释附加字段”：

- `post_divergence_route`
- `route_level_from`
- `route_level_to`
- `same_level_decomposition_mode`
- `recomposition_applied`
- `oscillation_rhythm_state`
- `zs_monitor_midline`
- `zs_monitor_zn_series`
- `zs_monitor_bias`
- `zs_monitor_alert`

传递原则：

- theory 管道只消费 theory 终结链上的附加字段快照。
- practical 管道可消费 theory+fallback 终结链上的附加字段快照。
- `pending` 线段对应字段只能进入“观察态缓存”，不能触发“已完成中枢”或“已完成走势类型”状态切换。

主辅一致性约束：

- `zhongshus` 的附加字段为主字段，`lei_zhongshus` 只能作为辅助解释。
- 若主辅字段冲突，对外报告必须保留主口径，并在解释句中注明“类中枢辅助视图存在差异”。
- 任何情况下不得用 `lei_zhongshus` 的 `zs_monitor_alert` 覆盖 `zhongshus` 的风险提示。

下游消费约束：

- 当 `same_level_decomposition_mode=dual_interpretation_pending` 时，买卖点模块必须输出“待确认”而非“已确认触发”。
- 当 `post_divergence_route=higher_level_reverse_trend` 且 `zs_monitor_alert=pre_breakdown|pre_breakout` 时，可输出“高风险观察”标签，但仍需等待确认条件。
- 字段缺失按 unknown 处理，不得默认映射为 `single_confirmed` 或 `none`。
