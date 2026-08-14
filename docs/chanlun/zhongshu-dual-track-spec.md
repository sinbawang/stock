# 中枢/类中枢双轨规范

本页用于给实现、图表、报告三方提供统一术语和主辅消费规则。

## 1. 术语定义

- 中枢：标准中枢，基于线段识别，主口径。
- 类中枢：笔级近似中枢，基于已确认笔识别，辅口径。

## 2. 主辅关系

- 走势类型判定以中枢为主。
- 一二三类买卖点判定以中枢为主。
- 类中枢仅用于兼容、回溯和辅助解释。
- 主辅冲突时，以中枢结论为准，类中枢降级为观察提示。

## 3. 输出命名约束

- 标准中枢数组：`zhongshus`
- 类中枢数组：`lei_zhongshus`
- 禁止用 `zhongshus_bi` 或 `segment_based_zhongshu` 这类历史命名继续对外扩散。

可选模式分层：

- `zhongshus_theory` / `zhongshus_practical`
- `lei_zhongshus_theory` / `lei_zhongshus_practical`

## 4. 图表与报告要求

- 图表必须把中枢与类中枢分层渲染，且图例显式命名。
- 报告结构段必须先给“中枢主结论”，再给“类中枢辅助结论”。
- 买卖点文本必须标注主判定来源为中枢。
- 若主辅冲突，必须输出冲突说明，不允许静默覆盖。

## 5. 最小字段建议

中枢对象建议最少包含：

- `id`
- `structure_level = segment`
- `start_segment_id`
- `end_segment_id`
- `zs_low`
- `zs_high`
- `is_terminated`
- `termination_mode`

类中枢对象建议最少包含：

- `id`
- `structure_level = bi`
- `start_bi_id`
- `end_bi_id`
- `zs_low`
- `zs_high`
- `is_terminated`
- `termination_mode`

## 6. 迁移建议

1. 先保持类中枢输出不删，新增中枢主输出。
2. 再让报告和图表优先读取中枢，类中枢改为辅助展示。
3. 最后把旧接口中的“中枢”字样逐步迁移到“类中枢”，避免误导。

## 7. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [segment-to-zhongshu-mode-protocol-draft.md](segment-to-zhongshu-mode-protocol-draft.md)
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
- [../analysis/combined-analysis-output-spec.md](../analysis/combined-analysis-output-spec.md)

## 8. 附加字段契约（第29/36/38/39/92课）

当输出接入“背驰后三级去向 + 同级别分解 + 中枢震荡监视器”时，`zhongshus` 与 `lei_zhongshus` 均可携带以下字段：

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

建议值域（与主规范对齐）：

- `post_divergence_route`: `last_zs_extension | higher_level_range | higher_level_reverse_trend`
- `same_level_decomposition_mode`: `single_confirmed | dual_interpretation_pending`
- `oscillation_rhythm_state`: `balanced | up_bias | down_bias | pending`
- `zs_monitor_bias`: `strong | weak | neutral`
- `zs_monitor_alert`: `none | pre_breakout | pre_breakdown`

缺失字段处理：

- 字段缺失时一律按 `unknown` 语义降级，不得默认映射为 `none` 或 `single_confirmed`。
- 降级时必须保留“当前为字段缺失降级”说明，避免下游误判为确认状态。

## 9. 主辅冲突优先级表

| 冲突场景 | 主结论来源 | 辅助结论处理 | 对外输出要求 |
| --- | --- | --- | --- |
| `zhongshus` 与 `lei_zhongshus` 对去向结论不一致 | `zhongshus` | `lei_zhongshus` 降级为辅助提示 | 必须输出“中枢主口径优先” |
| 主口径 `same_level_decomposition_mode=dual_interpretation_pending` | `zhongshus` | 辅助口径不得升级为确认买卖点 | 建议语气降级为“观察/等待确认” |
| 主口径 `zs_monitor_alert=none`，辅口径出现预警 | `zhongshus` | 可记录辅助预警但不升格主风险 | 输出“类中枢提示，未触发主预警” |
| 主口径有 `pre_breakout/pre_breakdown` 预警，辅口径无预警 | `zhongshus` | 辅口径缺失不抵消主预警 | 必须保留主预警并提示待确认 |

## 10. 买卖点消费红线

- 一二三类买卖点的 `confirmed_signal` 只能由 `zhongshus` 路径产生。
- `lei_zhongshus` 只能产出 `auxiliary_signal`，不得单独把状态提升为 `confirmed_signal`。
- 当 `same_level_decomposition_mode=dual_interpretation_pending` 时，无论主辅是否同向，都只能输出 `pending_signal`。
- 指标信号（MACD/均线/量能）只可作为解释附注，不得覆盖以上主辅判定链路。
