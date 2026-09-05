# Chanlun Docs（缠论文档总入口）

分层阅读：**原文 → 规格(specs) → 设计(designs) → 任务(tasks) → 复核(review) → 支撑(样例/契约/协议)**。

## 0. 快速导航

| 想知道什么 | 看哪里 |
| --- | --- |
| 严格理论总纲（原文口径） | [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md) |
| 规则、模块边界、修改原则 | [chanlun-rule-spec.md](chanlun-rule-spec.md) |
| 进度、优先级、待办 | [chanlun-spec-tasks.md](chanlun-spec-tasks.md) |
| 理论 / 实现 / 消费三层差异 | [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) |
| 某课对应哪里 | [lesson-traceability-matrix.md](lesson-traceability-matrix.md) |

## 1. 原文层

- `books/chanzhongshuochan_lessons/`：缠论原文课文（lesson_001 … lesson_108）。
- [lesson-traceability-matrix.md](lesson-traceability-matrix.md)：课程可追溯矩阵，课次 → spec/design/tasks/tests/code 五层锚点。

## 2. 规格层 specs（总入口：[chanlun-rule-spec](chanlun-rule-spec.md) / [chanlun-strict-theory-spec](chanlun-strict-theory-spec.md)）

- [base-structure-spec.md](base-structure-spec.md)：基础结构（K线/包含/标准K/分型/笔）
- [segment-spec.md](segment-spec.md)：线段严格理论（应然）
- [zhongshu-core-spec.md](zhongshu-core-spec.md)：中枢核心理论
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)：中枢/类中枢主辅规范
- [same-level-decomposition-spec.md](same-level-decomposition-spec.md)：同级别分解理论口径（应然）
- [trend-divergence-spec.md](trend-divergence-spec.md)：走势类型 / 背驰 / 盘整背驰 / 背驰后去向
- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)：一二三类买卖点 / 区间套 / 小转大 / 多级别联立

## 3. 设计层 designs（总入口：[designs.md](designs.md)）

- 线段：[segment-implementation-guide](segment-implementation-guide.md)、[segment-doc-map](segment-doc-map.md)、[segment-zhongshu-boundary](segment-zhongshu-boundary.md)、[segment-to-zhongshu-mode-protocol-draft](segment-to-zhongshu-mode-protocol-draft.md)
- 中枢：[zhongshu-state-machine](zhongshu-state-machine.md)、[zhongshu-input-qualification](zhongshu-input-qualification.md)、[zhongshu-recompute-order](zhongshu-recompute-order.md)
- 走势类型/背驰：[trend-type-decomposition](trend-type-decomposition.md)、[trend-ambiguity-combination-law](trend-ambiguity-combination-law.md)

## 4. 任务层 tasks（总入口：[chanlun-spec-tasks](chanlun-spec-tasks.md)）

- [segment-tasks.md](segment-tasks.md)
- [zhongshu-tasks.md](zhongshu-tasks.md)
- [trend-divergence-tasks.md](trend-divergence-tasks.md)
- [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)

## 5. 复核层 review（总入口：[theory-implementation-consumer-diff-matrix](theory-implementation-consumer-diff-matrix.md) / [lesson-traceability-matrix](lesson-traceability-matrix.md)）

- 基础结构：[base-structure-original-review-matrix](base-structure-original-review-matrix.md)
- 线段：[segment-original-review-matrix](segment-original-review-matrix.md)、[segment-review-entry](segment-review-entry.md)、[segment-review-diff-summary-2026-08](segment-review-diff-summary-2026-08.md)
- 中枢：[zhongshu-original-review-matrix](zhongshu-original-review-matrix.md)、[zhongshu-review-entry](zhongshu-review-entry.md)、[zhongshu-review-diff-summary-2026-08](zhongshu-review-diff-summary-2026-08.md)
- 走势类型/背驰：[trend-divergence-original-review-matrix](trend-divergence-original-review-matrix.md)
- 买卖点：[buy-sell-multi-level-original-review-matrix](buy-sell-multi-level-original-review-matrix.md)

## 6. 支撑层（样例 / 契约 / 协议 / 变更）

- 示例库：[base-structure-visual-example-library](base-structure-visual-example-library.md)、[segment-visual-example-library](segment-visual-example-library.md)、[zhongshu-visual-example-library](zhongshu-visual-example-library.md)、[trend-divergence-visual-example-library](trend-divergence-visual-example-library.md)、[buy-sell-multi-level-visual-example-library](buy-sell-multi-level-visual-example-library.md)、[zhongshu-consumer-display-examples](zhongshu-consumer-display-examples.md)
- 样例包与回放：[sample-case-pack-2026-08-v1](sample-case-pack-2026-08-v1.md)、[sample-case-pack-2026-08-v2](sample-case-pack-2026-08-v2.md)、[rhythm-replay-log-template](rhythm-replay-log-template.md)、[rhythm-replay-log-2026-08-first-batch](rhythm-replay-log-2026-08-first-batch.md)、[rhythm-replay-log-2026-08-second-batch](rhythm-replay-log-2026-08-second-batch.md)
- 契约 / 协议：[segment-stop-reason-contract](segment-stop-reason-contract.md)、[segment-mode-consumer-examples](segment-mode-consumer-examples.md)、[spec-change-protocol](spec-change-protocol.md)
- 变更 / 安全：[segment-implementation-changelog](segment-implementation-changelog.md)、[segment-safety-checklist](segment-safety-checklist.md)
