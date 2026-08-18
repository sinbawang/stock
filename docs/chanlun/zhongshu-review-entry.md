# 中枢 review 入口

本页作为 `zhongshu` 下一轮 review 的单页入口，目标不是重复中枢规范正文，而是把 review 真正需要对照的四层信息压到同一个入口里：

1. 原文定义与课次锚点。
2. 当前理论主口径与主辅消费口径。
3. 高风险案例入口。
4. 下游消费字段与展示红线。

使用方式：

1. 先看第 1 节，确认当前讨论的是“标准中枢理论定义”还是“类中枢辅助口径”。
2. 再看第 2 节，确认当前实现与消费规则有没有把两者混写。
3. 再看第 3 节，判断当前分歧究竟来自中枢扩展、级别扩张、三级去向，还是预警未确认。
4. 最后看第 4 节，判断这个差异应该先改 spec、改实现，还是先限制消费端表达。

## 1. 原文定义入口

中枢 review 的原文锚点优先使用以下几页：

1. [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
2. [zhongshu-core-spec.md](zhongshu-core-spec.md)
3. `books/chanzhongshuochan_lessons/articles_md/lesson_017_教你炒股票17：走势终完美.md`
4. `books/chanzhongshuochan_lessons/articles_md/lesson_018_教你炒股票18：不被面首的雏男是不完美的。.md`
5. `books/chanzhongshuochan_lessons/articles_md/lesson_020_教你炒股票20：缠中说禅走势中枢级别扩张及第三类买卖点.md`
6. `books/chanzhongshuochan_lessons/articles_md/lesson_021_教你炒股票21：缠中说禅买卖点分析的完备性.md`
7. `books/chanzhongshuochan_lessons/articles_md/lesson_029_教你炒股票29：转折的力度与级别.md`
8. `books/chanzhongshuochan_lessons/articles_md/lesson_038_教你炒股票38：走势类型连接的同级别分解.md`
9. `books/chanzhongshuochan_lessons/articles_md/lesson_039_教你炒股票39：同级别分解再研究.md`
10. `books/chanzhongshuochan_lessons/articles_md/lesson_092_教你炒股票92：中枢震荡的监视器.md`

当前 review 时应优先回答三件事：

- 当前对象是不是严格中枢本体，而不是进入段、离开段或笔级近似盒子。
- 当前变化属于中枢延伸、扩展，还是已经升级到级别扩张。
- 当前输出是 confirmed 主结论，还是 watch/pending 的监视、去向或辅助解释。

## 2. 当前实现与消费入口

当前实现与消费规则入口：

1. [zhongshu-core-spec.md](zhongshu-core-spec.md)
2. [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
3. [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)
4. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)

当前实现层 review 时，建议重点看这四个问题：

| review 问题 | 当前要点 | 常见漂移 |
| --- | --- | --- |
| 是否把进入段算进中枢本体 | 进入段只负责带入，不应并入本体三段 | 图上矩形从进入段起画 |
| 是否把类中枢混成主中枢 | 主口径优先 `zhongshus`，辅口径单列 `lei_zhongshus` | 文案里直接把类中枢简称为中枢 |
| 扩展与扩张是否分清 | 扩展仍属原中枢语义，扩张已涉及更高层级解释 | 把更高一级结构仍当成原盒子平移 |
| 预警/去向是否越级确认 | `zs_monitor_*`、`post_divergence_route` 只作 watch/pending | 预突破/预破位直接写成 confirmed 3B/3S |

## 3. 高风险样例入口

### 3.1 中枢定理与扩展/扩张

关注点：

- 当前是中枢延伸、扩展，还是级别扩张。
- 中枢矩形有没有错误覆盖进入段或离开段。
- 主口径是否仍能稳定解释“同一中枢”与“更高一级中枢”。

当前可直接进入 review 的现成案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1 节第 18/20 课中枢定理与扩张示例，现已内嵌 `SZ.000651 30m` 中枢扩张候选真实卡片。
2. [sample-case-pack-2026-08-v1.md](sample-case-pack-2026-08-v1.md) 与 [sample-case-pack-2026-08-v2.md](sample-case-pack-2026-08-v2.md) 中的 `30m / 5m / day映射` 样例优先；`60m` 当前只保留为补充锚点。

### 3.2 背驰后三级去向与级别切换

关注点：

- 背驰后是否严格落在“最后中枢扩展 / 更大级别盘整 / 更高级别反趋势”三分法内。
- `route_level_from -> route_level_to` 是否表达清楚。
- 是否把去向候选越级写成已确认反转。

当前可直接进入 review 的现成案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 2 节第 29 课背驰后三级去向示例，现优先使用 `SZ.000651 30m -> day`，`HK.00700 60m` 作为补充对照。
2. [sample-case-pack-2026-08-v2.md](sample-case-pack-2026-08-v2.md) 中 `higher_level_range`、`higher_level_reverse_trend` 等已填充案例。

### 3.3 震荡节奏与监视器预警

关注点：

- `A_i / A_{i+2}` 阈值只用于节奏监视，不直接确认买卖点。
- `pre_breakout / pre_breakdown` 与 confirmed 3B/3S 是否严格分开。
- 若主口径仍是 `dual_interpretation_pending`，是否已做消费降级。

当前可直接进入 review 的现成案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 3 节第 39 课节奏示例，现优先使用 `SH.601318 5m down_bias`；`HK.01024 15m balanced` 暂作补充对照。
2. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4 节第 92 课监视器预警与确认链对照示例，现优先使用 `SZ.002594 30m pre_breakout` 与 `SZ.000651 1m confirmed 3S`；`SH.601328 1m` 暂作 `1m` 预警前态代理样本，`HK.01024 60m pre_breakdown` 暂作补充对照。
3. [rhythm-replay-log-2026-08-first-batch.md](rhythm-replay-log-2026-08-first-batch.md) 与 [rhythm-replay-log-2026-08-second-batch.md](rhythm-replay-log-2026-08-second-batch.md)。

当前级别取样原则：尽可能优先使用 `1m / 5m / 30m / day`。本轮已稳定覆盖 `1m / 5m / 30m / day映射`，其中 `HK.02357 1m` 已可作为 watch/pending 场景锚点，`HK.01339 1m` 已可作为 completed_then_new_type 场景锚点，`SH.601328 1m` 已可作为预警前态代理锚点，`SZ.000651 1m` 已可作为 confirmed 场景锚点。

## 4. 下游消费字段映射

中枢 review 不应只停留在“理论是否成立”，还要检查消费端会不会把辅助态、观察态写成确认态。

当前优先看的字段和展示位如下：

| 消费位置 | 关键字段/对象 | 正确口径 | 红线 |
| --- | --- | --- | --- |
| `tech.json` 中枢主口径 | `zhongshus` | 默认作为主结论来源 | 不得与 `lei_zhongshus` 混写 |
| `tech.json` 类中枢辅口径 | `lei_zhongshus` | 只能作辅助观察或降级解释 | 不得独立升级为 confirmed |
| 去向解释 | `post_divergence_route` | 只作去向候选与级别说明 | 不得直接推出反转已确认 |
| 震荡监视 | `oscillation_rhythm_state` | 只作节奏强弱监视 | 不得替代中枢主结论 |
| 预警监视 | `zs_monitor_alert` | 统一按 watch/pending 处理 | 不得渲染为 confirmed 3B/3S |
| 小程序/报告文案 | 主口径 + 降级标签 | 主口径优先，观察态显式标注 | 不得省略 pending/auxiliary 说明 |

跨模块消费总表仍以 [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) 为准；本页只保留 `zhongshu` 自己最容易误读的入口。

若要直接看 `zhongshu` 专用的 `tech.json / 报告 / 小程序` 展示差异示例，优先看 [zhongshu-consumer-display-examples.md](zhongshu-consumer-display-examples.md)。

## 5. 本轮建议执行顺序

1. 先从 [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1 至第 4 节开始做第一轮 review，这四节现在都已有页内真实卡片。
2. 再核对 [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md) 的课次边界，确认 strict 理论与当前工程口径没有混写。
3. 然后把样例里的主辅冲突、预警未确认、三级去向继续反推回 `tech.json`、报告和小程序展示红线。

## 6. 关联文档

1. [zhongshu-core-spec.md](zhongshu-core-spec.md)
2. [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
3. [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
4. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)
5. [zhongshu-consumer-display-examples.md](zhongshu-consumer-display-examples.md)
6. [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)
7. [sample-case-pack-2026-08-v1.md](sample-case-pack-2026-08-v1.md)
8. [sample-case-pack-2026-08-v2.md](sample-case-pack-2026-08-v2.md)
9. [zhongshu-review-diff-summary-2026-08.md](zhongshu-review-diff-summary-2026-08.md)