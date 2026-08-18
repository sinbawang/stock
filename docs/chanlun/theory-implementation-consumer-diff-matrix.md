# 理论定义 / 当前实现 / 下游消费 总差异总表（第一版）

本页作为跨模块 review 入口，用来统一回答五个问题：

1. 严格缠论理论在该模块中的主定义是什么。
2. 当前仓库已经实际实现了什么。
3. 下游报告、小程序、`tech.json`、图表消费的又是哪一层语义。
4. 三者之间当前差异主要在哪里。
5. 下一步应优先补理论、实现，还是消费契约。

使用原则：

- 理论定义不能被当前实现反向改写。
- 当前实现不能被下游消费文案自动美化成“已严格完成”。
- 下游消费若引用辅助口径、观察态、工程近似，必须显式标注。

## 1. 阅读方式

建议按以下顺序使用本页：

1. 先定位模块。
2. 看“严格理论主定义”。
3. 看“当前实现主口径”。
4. 看“下游消费现状”。
5. 最后看“主要差异”和“优先动作”。

若需要模块细节，跳转到对应专题文档，不要把本页扩写成新的巨型总 spec。

## 2. 总览矩阵

| 模块 | 严格理论主定义 | 当前实现主口径 | 下游消费现状 | 差异状态 | 优先动作 |
| --- | --- | --- | --- | --- | --- |
| 基础结构 | 先包含处理，再标准 K，再严格分型，再成笔确认。 | 已有较稳定主链路，文档和工程口径相对一致。 | 主要作为上游基础输入，被下游间接消费。 | 低 | 继续补边界反例，维持冻结口径。 |
| 线段 | 必须依附笔与特征序列/再分辨逻辑确认终结。 | 已形成稳定工程闭环，67 课主路径与 71 课最小闭环可运行。 | 图表、报告、导出字段已依赖 `stop_reason`、`is_confirmed`、theory/practical 双模式。 | 中 | 补 67/71 正反例；继续区分理论定义与工程契约。 |
| 标准中枢 | 必须区分进入段、本体、离开段，以线段级中枢为主口径。 | 当前主运行链路仍较多依赖类中枢或工程替代结构。 | 下游已有主辅区分框架，但主输出尚未完全切回标准中枢。 | 高 | 优先补标准线段级中枢主实现与字段收敛。 |
| 类中枢/辅助中枢 | 不是严格中枢本体，只能作辅助观察和消费降级。 | 已有稳定字段与使用场景。 | 部分报告/图表依赖其做辅助提示。 | 中 | 继续强化命名与展示红线，防止升级为主结论。 |
| 走势类型 | 必须建立在同级别分解和中枢关系上。 | 当前主要输出结构状态摘要，未形成完整严格递归分解。 | 下游可消费 `structure_state` 一类摘要字段。 | 高 | 优先补严格同级别自动分解主链路。 |
| 趋势背驰 | 必须比较同级别趋势离开段，并绑定最近中枢。 | 有工程化 divergence 输出，但不等于严格趋势背驰。 | 下游可能已展示 divergence/背驰提示。 | 高 | 单列严格趋势背驰判定链和输出字段。 |
| 盘整背驰 | 必须回到同一中枢语义下解释两次离开/试探关系。 | 当前最容易被工程近似替代。 | 下游若直接展示，误读风险较高。 | 高 | 单列盘整背驰严格主口径与反例集。 |
| 一类买卖点 | 必须依附背驰导致的结构转折。 | `buy_1/sell_1` 更接近工程规则。 | 下游可已有买卖点信号展示。 | 高 | 建立 1 类点严格确认链和字段证据。 |
| 二类买卖点 | 必须是 1 类点后的第一次确认性回抽。 | 当前仍偏工程化。 | 下游若直接显示 2B/2S，需格外谨慎。 | 高 | 补与 1 类点绑定的首次回抽判定。 |
| 三类买卖点 | 必须绑定最近中枢和首次不回归回试。 | 文档已较清楚，代码仍未完全严格绑定。 | 下游可能已有 3B/3S 近似表达。 | 中高 | 收敛到最近中枢 + 首次回试的硬约束。 |
| 多级别联立 | 高级别定方向，低级别提精度；低级别不得推翻高级别未完成结构。 | 已有框架性文档与部分消费约束。 | 报告/小程序侧仍可能混用观察态和确认态。 | 中高 | 统一 confirmed/pending/auxiliary 三态和展示文案。 |

## 3. 分层定义

### 3.1 严格理论层

严格理论层回答“缠论原文语义上，这个对象到底是什么”。

文档锚点：

- 总纲：[chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- 基础结构：[base-structure-spec.md](base-structure-spec.md)
- 线段复核：[segment-original-review-matrix.md](segment-original-review-matrix.md)
- 中枢核心：[zhongshu-core-spec.md](zhongshu-core-spec.md)
- 走势类型与背驰：[trend-divergence-spec.md](trend-divergence-spec.md)
- 买卖点与多级别联立：[buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)

### 3.2 当前实现层

当前实现层回答“仓库今天到底算出了什么、图今天到底怎么画出来的”。

当前主锚点：

- 线段实现：[segment-implementation-guide.md](segment-implementation-guide.md)
- 线段契约：[segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 中枢主辅消费：[zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- 完成度与待办：[chanlun-spec-tasks.md](chanlun-spec-tasks.md)

### 3.3 下游消费层

下游消费层回答“报告、小程序、图表、`tech.json` 如何解释这些结构结果”。

当前主要风险：

1. 把工程近似输出写成严格理论确认。
2. 把辅助口径写成主口径。
3. 把 pending/观察态写成 confirmed。
4. 把 divergence 泛化为严格趋势背驰或盘整背驰。

### 3.4 字段级消费映射

这一层回答“具体字段到了 `tech.json`、联合报告、小程序时，应该按 confirmed、pending、auxiliary 的哪一档处理”。

#### 3.4.1 `tech.json` 字段状态矩阵

| 字段 | 当前来源层 | 推荐消费状态 | 当前约束 | 常见误读 | 正确消费方式 |
| --- | --- | --- | --- | --- | --- |
| `summary.conclusion` | 文本摘要层 | `pending_or_confirmed_text` | 可稳定读取，但本身不是 machine-readable 确认字段。 | 只看措辞就推断已确认买卖点。 | 必须结合结构字段或状态字段解释，不能单独当 confirmed signal。 |
| `summary.suggestion` | 文本摘要层 | `action_text_optional` | 可稳定读取，但属于建议文案，不是结构状态。 | 把建议文案当成结构判定结果。 | 只能作阅读提示，不能反推理论确认。 |
| `analysis_text` | 文本解释层 | `mixed_textual_state` | 当前仍是最广泛存在的解释载体。 | 从自由文本强行解析 confirmed/pending。 | 在结构字段缺失时可作说明来源，但不应单独驱动状态升级。 |
| `advice_text` | 文本建议层 | `action_text_optional` | 适合展示，不适合做严格结构判断。 | 把操作建议当成严格主结论。 | 仅作建议附文，不能覆盖主结构字段。 |
| `structure_state.last_completed` | 严格结构建议层 | `confirmed` | 若存在，应表示已完成走势类型。 | 与 `current_ongoing` 同型时误解为“旧走势完全切开”。 | 结合 `relationship.kind` 解读；同型延伸场景只表示“前段已确认片段”。 |
| `structure_state.current_ongoing` | 严格结构建议层 | `pending` | 若存在，应表达当前进行结构，不代表已完成。 | 把 `candidate_completion` 当 confirmed。 | 一律按 ongoing/观察态处理，直到同级别完成条件闭合。 |
| `structure_state.relationship` | 解释增强层 | `disambiguation_only` | 只用于解释 last/current 的关系。 | 把 `same_type_extension` 误读为新走势已确认。 | 仅作关系说明，不单独产出信号等级。 |
| `same_level_decomposition_mode` | 中枢/走势分解层 | `confirmed_or_pending_gate` | `single_confirmed | dual_interpretation_pending`。当前已按 `structure_state.current_structure_status` 与 `confirmation_basis` 的工程确定性接入真实主链，并已用于 `advice_text` 降级。 | 把当前工程映射误读为严格同级别唯一分解已完成。 | 当前只能视为“工程 pending gate”；`dual_interpretation_pending` 时所有高层结论降级为 pending/watch，仍不等于严格递归分解。 |
| `post_divergence_route` | 背驰后去向层 | `pending_or_confirmed_context` | 只说明去向，不单独说明已确认。当前已按现有 `divergence.trend/range` 与尾中枢延伸语义接入真实主链，并配套 `route_level_from/to` 透传到 `summary/tech.json/publish`。 | 把当前工程有限分支映射误读为严格背驰后三级去向自动分解已完成，或看见 `higher_level_reverse_trend` 就直接认定反转确认。 | 当前只能作为“工程去向候选”；仍需级别闭合与结构确认，消费端一律按 pending/watch 处理。 |
| `oscillation_rhythm_state` | 节奏监视层 | `auxiliary` | `balanced | up_bias | down_bias | pending`。当前已按最近同方向确认笔的 `macd_sum_abs` 力度比工程接入 `src -> summary/tech.json -> advice_text -> miniapp publish` 主链。 | 把当前工程力度比映射误读为严格 `A_i/A_{i+2}` 节奏引擎已完整实现，或用节奏字段代替走势类型确认。 | 当前只作辅助监视与文案解释；缺中枢、缺足够同向历史或阈值不稳时一律按 `pending/auxiliary` 降级，不得覆盖主结构结论。 |
| `zs_monitor_alert` | 已接入主运行链的中枢监视层 | `pending_or_auxiliary` | 规范值域是 `none | pre_breakout | pre_breakdown`。当前 `src -> summary/tech.json -> advice_text -> miniapp publish` 已有稳定实现锚点，并已补 `30m pre_breakdown/pre_breakout` 发布链回归；`1m` 真实落盘样本仍未补齐。 | 因字段已有实现，就误读为可单独推出 confirmed 3B/3S。 | 只能按 watch/pending 消费；当前已与 `zs_monitor_midline`、`zs_monitor_bias`、`same_level_decomposition_mode` 联动，但仍不得独立升级为 confirmed。 |
| `precision_entry.status` | 次级别执行层 | `execution_pending_or_actionable` | 当前值如 `standby | watch | actionable`。 | 把 `actionable` 当高级别 confirmed。 | 仅表示执行层时机状态，必须受高级别主结构约束。 |
| `precision_entry.nested_from` | 区间套绑定层 | `auxiliary_context` | 解释低级别信号绑定来源。 | 低级别窗口反向覆盖高级别结构。 | 只做来源解释，不改变主级别确认状态。 |
| `zhongshus` | 标准中枢主口径 | `confirmed_or_pending_main` | 主口径来源。 | 与 `lei_zhongshus` 混写为同一层。 | 对外主结论默认引用它。 |
| `lei_zhongshus` | 类中枢辅助口径 | `auxiliary` | 只能作辅助，不得单独升级。 | 文案里直接简称“中枢”。 | 明示“类中枢/辅助”，不得单独产出 confirmed signal。 |

#### 3.4.2 报告文本字段映射

| 文本块 | 推荐状态 | 允许用途 | 禁止用途 |
| --- | --- | --- | --- |
| `结论：观察/待确认...` | `pending` | 作为风险观察、等待确认提示。 | 改写成确认买卖点标题。 |
| `结论：出现预警...` | `pending` | 作为中枢监视或背驰后去向预警。 | 省略“待确认”后直接发成 confirmed 信号。 |
| `说明：类中枢结论仅为辅助...` | `auxiliary` | 保留辅口径存在感和解释价值。 | 让辅助文案覆盖主口径结论。 |
| `建议：暂按 watch/pending 管理...` | `pending` | 提醒执行层降级。 | 被二次摘要成“建议买入/卖出已确认”。 |
| `建议：等待离开-首次回抽不回中枢...` | `pending` | 表达 3B/3S 等候条件。 | 在条件未满足时提前升级三类点。 |

#### 3.4.3 小程序展示映射

| 页面位置 | 推荐展示来源 | 推荐状态映射 | 红线 |
| --- | --- | --- | --- |
| 首页卡片摘要 | `summary.conclusion` + 更新时间 | `confirmed`、`pending`、`auxiliary` 仅作轻量标签，不展开复杂理论词。 | 缺少结构字段时，不得默认打 `confirmed` 标签。 |
| 单股详情-技术面概览 | `analysis_text` + `structure_state.*` + `same_level_decomposition_mode` | 先显示主结构状态，再显示观察态/辅助态说明。 | 不得把 `dual_interpretation_pending` 渲染成确定性方向。 |
| 单股详情-预警卡片 | `zs_monitor_alert`、`post_divergence_route` | 统一按 `watch/pending` 处理。 | 预警卡片标题不得出现 confirmed buy/sell。 |
| 单股详情-执行层卡片 | `precision_entry` | 仅标执行层 `standby/watch/actionable`，并附“受上级别约束”。 | `actionable` 不得单独升级为主结论 confirmed。 |
| 图表图例/标注 | `zhongshus`、`lei_zhongshus`、segment 双模式信息 | 主辅分层显示，pending 单独标注。 | 不得把类中枢、pending 段和 confirmed 段混成同一图例。 |

#### 3.4.4 三态统一规则

| 状态 | 可来源字段/信号 | 允许对外文案 | 不允许的升级 |
| --- | --- | --- | --- |
| `confirmed` | `structure_state.last_completed`；`same_level_decomposition_mode=single_confirmed`；主口径 `zhongshus` 确认；线段 `theory_confirmed`；必要时实践层 `fallback_confirmed` 明示为工程确认 | `已确认`、`已完成`、`主口径确认` | 不得由 `lei_zhongshus`、`zs_monitor_alert`、`precision_entry.actionable` 单独产生 |
| `pending` | `structure_state.current_ongoing`；`dual_interpretation_pending`；`zs_monitor_alert`；线段 `pending`；预警文本；未闭合背驰后去向 | `观察`、`待确认`、`预警`、`等待结构闭合` | 不得改写成买卖点已确认、趋势已反转；若 `zs_monitor_alert` 尚未实现落盘，不得自行补齐字段后再升级口径 |
| `auxiliary` | `lei_zhongshus`；`oscillation_rhythm_state`；`precision_entry.nested_from`；指标解释附注 | `辅助提示`、`辅助观察`、`执行层说明` | 不得覆盖主结构结论，不得独立升级为 confirmed |

## 4. 当前最重要的差异带

### 4.1 线段已较强，线段级中枢仍偏弱

- 当前仓库在线段工程闭环上已经明显强于标准中枢主实现。
- 这会导致“底层段已稳定，但中枢主口径仍未完全接上”的阶段性错位。

### 4.2 高层结构最大问题不是没文档，而是没闭环自动判定

- 走势类型、趋势背驰、盘整背驰、1/2/3 类买卖点的核心缺口，不再是定义没写，而是严格主链路没闭环。

### 4.3 下游消费的主要风险是过度确认

- 一旦把辅助口径、工程近似、观察态写成确认结论，会让文档和实现差异被前端文案掩盖。

### 4.4 当前最缺的是字段级统一，而不是抽象原则

- confirmed/pending/auxiliary 的原则已经散见于线段、中枢、联合输出文档。
- 真正缺口是把这些原则压成字段级映射，供 `tech.json`、报告、小程序复用同一套解释。

## 5. review 时的使用模板

每次 review 一个模块时，建议至少写出这五栏：

- 理论定义：原文要求什么。
- 当前实现：代码今天做到了什么。
- 下游消费：报告/图表/字段今天怎么写。
- 差异结论：是文档差异、实现差异，还是消费差异。
- 下一动作：先补 spec、补代码，还是补展示红线。

## 6. 建议优先级

1. 先补标准线段级中枢主实现，把底层稳定结构接到中枢主口径上。
2. 再补严格同级别走势类型自动分解。
3. 然后拆开趋势背驰、盘整背驰、一二三类买卖点的严格确认链。
4. 最后统一 `tech.json`、报告、小程序的 confirmed/pending/auxiliary 展示语义。
5. 若新增字段或页面卡片，先回写本页 3.4 的字段级矩阵，再扩展消费端。

## 7. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md)
- [segment-doc-map.md](segment-doc-map.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
