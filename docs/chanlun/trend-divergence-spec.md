# 走势类型与背驰规格

本文件定义高层结构模块，覆盖：

- 走势类型
- 类背驰
- 盘整背驰
- 趋势背驰
- 背驰后的结构去向
- 中枢震荡阶段的解释边界

这是当前仓库里“不确定性最高、最需要和原文持续对照”的模块之一。

## 1. 当前定位

> 实然状态（完成度 / 收敛进度）见 [trend-divergence-tasks.md](trend-divergence-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)；
> 本文件只保留理论口径（应然）。

- 理论成熟度：中高
- 当前文档完整度：中

## 2. 走势类型

走势类型属于同级别分解后的结构结果，不是若干笔或若干线段的简单标签。

同级别走势类型至少分为：

- 上涨
- 下跌
- 盘整

约束：

- 必须先完成同级别分解，再谈走势类型。
- 不允许脱离中枢单独定义趋势或盘整。
- 价格新高新低本身，不足以单独定义趋势。

## 3. 背驰总定义

背驰是同级别结构完成某一离开动作后，价格创新而力度不能同步创新的结构性现象。

严格前提：

- 必须说明比较对象属于哪两个同级别离开动作。
- 必须说明它们依附的是哪个最近中枢。
- 力度比较只能在同级别语义下进行。

## 4. 趋势背驰

- 趋势背驰发生在趋势末端。
- 核心不是“指标变弱”，而是最后一段同向离开结构相对前一同向离开结构力度衰减。
- 趋势背驰后，结构解释必须回到有限分支，不能无限叙述。

## 5. 盘整背驰

- 盘整背驰发生在同一中枢震荡或围绕同一中枢的同级别波动中。
- 比较对象是同一中枢语义下、同方向的两次离开或试探动作。
- 后一次虽然触及更极端价格或再次测试边界，但力度弱于前一次，才可称为盘整背驰。

## 6. 类背驰

类背驰可以作为工程观察提示，但不能天然升级为严格背驰确认。

适用约束：

- 若尚未完成严格同级别分解，只能输出 `observation` 或 `pending` 语义。
- 类背驰不得绕过最近中枢和离开动作定义，直接替代趋势背驰或盘整背驰。
- 下游消费端必须区分“严格背驰确认”和“类背驰提示”。

## 7. 背驰后的结构去向

背驰后只允许回到有限结构分支：

- 最后中枢继续扩展
- 演化为更大级别盘整
- 演化为更大级别反趋势

这个限制用于避免“见背驰就判反转”的过度简化。

## 8. 指标的地位

- MACD、均线、量能只能辅助解释力度衰减。
- 指标不能脱离走势分解，独立定义背驰。
- 指标与结构冲突时，以结构主结论为准。

## 9. 实然指引（不承担规格职责）

> 本文件只定义“应然”。当前工程实现状态见 [trend-divergence-tasks.md](trend-divergence-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)。

历史实然摘要（保留作背景，不再更新）：

- 曾有 `structure_state` 和 `divergence` 输出框架。
- 曾有背驰相关工程语义。
- 严格“走势类型分解 -> 背驰确认 -> 结构去向”完整自动链路曾未完全闭环。

## 10. 维护建议

- 若要改“走势类型”“背驰”“盘整背驰”定义，优先改本文件。
- 若只是补充中枢主辅消费约束，优先改 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。
- 若只是补充图文化案例，不要把案例堆进本文件，转去样例库或案例包。

## 11. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [trend-divergence-original-review-matrix.md](trend-divergence-original-review-matrix.md)
- [trend-divergence-visual-example-library.md](trend-divergence-visual-example-library.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)
