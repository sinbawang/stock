# 线段 review 增量摘要（2026-08）

本页用于总结本轮 `segment` 文档整理相对于前一阶段的实际增量，目标不是重复规范正文，而是回答三件事：

1. 这轮到底新增了哪些 review 入口和案例材料。
2. 哪些高风险场景已经从“抽象 TODO”推进成“可直接 review 的案例”。
3. 当前还缺什么，下一步最值得补哪里。

## 1. 本轮新增内容

### 1.1 入口层

本轮新增或显著强化了以下入口：

1. [segment-review-entry.md](segment-review-entry.md)
   用途：把原文定义、当前实现、高风险样例和下游消费红线压到单页入口。
2. [segment-original-review-matrix.md](segment-original-review-matrix.md)
   用途：已从“只列后续动作”推进到“直接回链具体案例入口”。
3. [segment-visual-example-library.md](segment-visual-example-library.md)
   用途：已从纯模板页推进到“模板 + 规范回归案例 + 真实回归窗口案例”。

### 1.2 样例层

本轮把 `segment` 最容易漂移的三类场景都建立了可 review 骨架：

1. `pending_confirmation` vs `confirmed`
2. 67课第二种情况 vs 71课再分辨
3. 重写 / 吸收 / 复用

### 1.3 真实案例层

本轮不再停留在抽象模板，已经补入以下已验证案例：

1. `SZ.000651 30m`
   - 尾部待确认真实样本
   - 中枢吸收导致线段解释重写样本
2. `SZ.000591 15m`
   - 真实回归窗口，已写入连续 landmarks
3. `HK.00700 15m`
   - 真实回归窗口，已写入连续 landmarks
4. `R6` 再分辨正例
   - 规范回归 fixture，延迟确认终结
5. “先破第一笔起点”反例
   - 规范回归 fixture，候选撤销并延续旧段

## 2. 关键增量对照

| 主题 | 之前状态 | 当前状态 |
| --- | --- | --- |
| review 入口 | 优先级和专题分散在多个文档中 | 已有 [segment-review-entry.md](segment-review-entry.md) 作为单页入口 |
| 原文矩阵 | 主要是课次对照和泛化后续动作 | 63/67/71 课已直接回链到案例页 |
| 样例库 | 以抽象模板为主 | 已包含模板、规范回归案例、真实回归窗口 |
| 待确认案例 | 只有原则和字段红线 | 已有 `SZ.000651 30m` 真实样本 |
| 再分辨案例 | 主要依赖测试名和实现说明 | 已有 `R6`、撤销候选反例、`000591 15m`、`00700 15m` 入口 |
| 重写/吸收案例 | 只有概念性说明 | 已有 `SZ.000651 30m` 复用/吸收样本 |

## 3. 当前最有价值的现成入口

如果现在就开始做 `segment` review，建议按以下顺序读取：

1. [segment-review-entry.md](segment-review-entry.md)
2. [segment-original-review-matrix.md](segment-original-review-matrix.md)
3. [segment-visual-example-library.md](segment-visual-example-library.md) 第 6.5 节 `SZ.000651 30m`
4. [segment-visual-example-library.md](segment-visual-example-library.md) 第 7.6 至 7.9 节
5. [segment-visual-example-library.md](segment-visual-example-library.md) 第 8.6 节 `SZ.000651 30m`

## 4. 仍未完成的缺口

本轮虽然把入口和案例骨架搭起来了，但还有几块没有真正收敛：

1. 67课“第二种情况”仍缺完整实盘截图式案例，只能先靠真实回归窗口和规范回归 fixture 支撑。
2. 71课 R1-R5 仍未逐条补成案例卡，目前只有 `R6` 正例和“先破起点”反例最清晰。
3. “重写 / 吸收 / 复用”目前仍以 `SZ.000651 30m` 为主，样本覆盖面偏窄。
4. 还没有把这些案例反推成统一的图表标注规则或小程序显示差异示例。

## 5. 下一步建议

最合理的下一步不是继续扩模板，而是继续填真实案例和截图说明：

1. 先把 67/71 课对应的 `000591 15m` 或 `00700 15m` 补成带关键笔序说明的完整案例卡。
2. 再补 1 到 2 个“重写 / 吸收 / 复用”的真实窗口，避免该类场景只依赖单个样本。
3. 然后再把这些案例映射回 `tech.json`、报告和小程序的展示红线，形成真正的消费闭环。

## 6. 关联文档

1. [segment-doc-map.md](segment-doc-map.md)
2. [segment-review-entry.md](segment-review-entry.md)
3. [segment-original-review-matrix.md](segment-original-review-matrix.md)
4. [segment-visual-example-library.md](segment-visual-example-library.md)
5. [segment-implementation-guide.md](segment-implementation-guide.md)
6. [segment-implementation-changelog.md](segment-implementation-changelog.md)
