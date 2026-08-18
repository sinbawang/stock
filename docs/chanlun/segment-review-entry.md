# 线段 review 入口

本页作为 `segment` 下一轮 review 的单页入口，目标不是重复现有规范，而是把 review 真正需要对照的四层信息压到同一个入口里：

1. 原文定义。
2. 当前实现口径。
3. `pending` / 重写 / 吸收 / 复用等高风险场景样例。
4. 下游消费字段映射与展示红线。

如需先看本轮文档增量而不是直接进入规范正文，可先读 [segment-review-diff-summary-2026-08.md](segment-review-diff-summary-2026-08.md)。

使用方式：

1. 先看本页第 1 节和第 2 节，确认“理论要求”和“当前实现”是否在讨论同一对象。
2. 再看第 3 节，确认当前分歧究竟来自尾部待确认、再分辨、还是结构重写。
3. 最后看第 4 节，判断这个差异应该先改代码、改文档，还是先限制消费端表达。

## 1. 原文定义入口

线段 review 的原文锚点优先使用以下几页：

1. [segment-original-review-matrix.md](segment-original-review-matrix.md)
2. [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)
3. `books/chanzhongshuochan_lessons/articles_md/lesson_062_教你炒股票62：分型、笔与线段的关系.md`
4. `books/chanzhongshuochan_lessons/articles_md/lesson_063_教你炒股票63：替代与确认的边界.md`
5. `books/chanzhongshuochan_lessons/articles_md/lesson_067_教你炒股票67：线段划分标准的再研究.md`
6. `books/chanzhongshuochan_lessons/articles_md/lesson_071_教你炒股票71：线段划分标准的再分辨.md`

当前 review 时应优先回答三件事：

- 起段三笔的公共重叠与特征序列约束是否满足。
- 终结是已确认完成，还是只是尾部候选。
- 第一/第二种情况和再分辨分支，是否真的足够把旧段判死或把旧段延续。

## 2. 当前实现入口

当前实现与契约入口：

1. [segment-implementation-guide.md](segment-implementation-guide.md)
2. [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
3. [segment-mode-consumer-examples.md](segment-mode-consumer-examples.md)
4. [segment-to-zhongshu-mode-protocol-draft.md](segment-to-zhongshu-mode-protocol-draft.md)

当前实现层 review 时，建议重点看这四个问题：

| review 问题 | 当前要点 | 常见漂移 |
| --- | --- | --- |
| 线段是否只建立在确认笔之上 | 未确认尾笔不应直接入段 | 候选尾笔被提前写成完成段 |
| 终结是否已有足够右侧确认 | `pending_confirmation` 应与 confirmed 分开 | 图上像结束，但结构上仍未闭合 |
| 再分辨是否只是最小闭环 | 71 课当前仍有工程近似边界 | 把“已实现主路径”误读成“完整严格实现” |
| `stop_reason` 是什么层级 | 它是消费契约，不是原文定义本身 | 下游反向把契约字段当理论结论 |

## 3. 高风险样例入口

这部分是下一轮 `segment` review 最该优先落地的样例清单。

### 3.1 尾部待确认

关注点：

- 当前尾部只是候选完成，还是已经形成确认终结。
- `segment_tail_interpretations` 是否仍包含 `pending_confirmation`。
- 消费端是否把待确认结构误写成“已完成走势”。

建议先补的样例类型：

1. 尾部停驻但右侧确认不足。
2. 尾部已有反向特征序列，但仍缺完整终结证据。
3. 图形视觉上像结束、结构上仍应保留 `pending` 的反例。

当前可直接进入 review 的现成案例：

1. [segment-visual-example-library.md](segment-visual-example-library.md) 第 6.5 节 `SZ.000651 30m` 尾部待确认样本。
2. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.9 节 `HK.00700 15m` 尾段 `exhausted_confirmed_bis` 未闭合样本。

### 3.2 再分辨与第二种情况

关注点：

- 67 课第二种情况是否已与普通直接分型终结区分开。
- 71 课 R1-R6 分支里哪些已经闭环，哪些仍是工程近似。
- 当前 gap/缺口场景是否会导致旧段误终结或误延续。

建议先补的样例类型：

1. 第一种情况与第二种情况并列对照。
2. 缺口导致必须再分辨的正例。
3. 再分辨后旧段延续、旧段终结两种对照例。

当前可直接进入 review 的现成案例：

1. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.6 节 `R6` 缺口再分辨延迟确认正例。
2. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.7 节 “先破第一笔起点，候选撤销并延续旧段”反例。
3. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.8 节 `SZ.000591 15m` 真实回归窗口。
4. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.9 节 `HK.00700 15m` 真实回归窗口。

### 3.3 重写、吸收、复用

关注点：

- 后续结构是否吸收了旧尾段。
- 某根尾部笔是否被更新结构复用成进入笔或连接笔。
- 线段边界右移后，下游是否还能稳定看懂“旧结论已被改写”。

建议先补的样例类型：

1. 旧线段候选终结后被右侧结构推翻。
2. 尾部笔被复用，导致原先边界重算。
3. 同一组图中先给出首次解释，再给出重写后的最终解释。

当前可直接进入 review 的现成案例：

1. [segment-visual-example-library.md](segment-visual-example-library.md) 第 8.6 节 `SZ.000651 30m` 中枢吸收导致线段解释重写样本。
2. [segment-visual-example-library.md](segment-visual-example-library.md) 第 8.7 节 中枢结构文本层已锁定同类重写说明的规范联动案例。

样例落点统一参考：

1. [segment-visual-example-library.md](segment-visual-example-library.md)
2. [segment-implementation-changelog.md](segment-implementation-changelog.md)

## 4. 下游消费字段映射

线段 review 不应只停留在“理论是否成立”，还要检查消费端会不会把观察态写成确认态。

当前优先看的字段和展示位如下：

| 消费位置 | 关键字段/对象 | 正确口径 | 红线 |
| --- | --- | --- | --- |
| `tech.json` 结构摘要 | `segment_tail_interpretations` | 有 `pending_confirmation` 时统一按待确认解释 | 不得仅凭结论文案升级为 confirmed |
| `tech.json` 同级别分解 | `same_level_decomposition_mode` | `dual_interpretation_pending` 时高层结构统一降级 | 不得默认当 `single_confirmed` |
| 报告技术要点 | `technical_focus_lines` | 允许写“候选完成待确认”“边界仍待右侧确认” | 不得压缩成“线段已完成” |
| 小程序详情技术卡片 | `pending` / `confirmed` 标签 | 先展示主结构状态，再展示观察态说明 | 不得把 pending 段和 confirmed 段渲染成同一颜色/同一图例 |
| 图表标注 | theory/practical 双模式段信息 | 主辅、确认/待确认分层显示 | 不得隐藏模式差异后只留单一结论 |

跨模块消费总表仍以 [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) 为准；本页只保留 `segment` 自己最容易误读的入口。

## 5. 本轮建议执行顺序

1. 先用第 6.5、7.8、7.9 节已有真实案例做第一轮 review。
2. 再用第 7.6、7.7 节规范回归案例核对 67/71 课理论边界。
3. 然后补充更多“重写 / 吸收 / 复用”真实案例，扩大第 8 节覆盖面。
4. 最后把这些样例反推回 `tech.json`、报告、小程序的字段与文案红线。

## 6. 关联文档

1. [segment-doc-map.md](segment-doc-map.md)
2. [segment-original-review-matrix.md](segment-original-review-matrix.md)
3. [segment-visual-example-library.md](segment-visual-example-library.md)
4. [segment-implementation-guide.md](segment-implementation-guide.md)
5. [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
6. [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)