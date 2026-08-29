---
spec_id: SPEC.SEGMENT.CORE
status: stable
owner: chanlun
applyTo: src/chanlun/segment.py
tests: tests/test_segment.py, tests/test_segment_rediscrimination_matrix.py, tests/test_segment_regression_suite.py
---

# 线段理论规格

本文件定义线段模块的严格理论口径（应然），只回答「线段严格上应该怎么起段、扩展、终结、表达尾段」。

- 实然（当前实现怎么画）见 [segment-implementation-guide.md](segment-implementation-guide.md)。
- 原文逐课复核见 [segment-original-review-matrix.md](segment-original-review-matrix.md)。
- 理论 vs 实现差异见 [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)。

## 1. 当前定位

- 理论成熟度：中高（67 课主路径稳定，71 课完整再分辨仍待收敛）。
- 实然状态（完成度 / 收敛进度）见 [segment-tasks.md](segment-tasks.md) 与 diff-matrix；本文件只保留理论口径。

## 2. 输入口径

- 线段不直接从 K 线生成，基于**已确认笔**序列生成。
- 未确认尾笔不参与线段起段、扩展或终结判断。
- 底层分型、笔必须按 [base-structure-spec.md](base-structure-spec.md) 稳定后才能进入线段层。

## 3. 起段定义

一条线段至少需要 3 笔，且这 3 笔必须同时满足：

- 方向交替；
- 第 1 笔与第 3 笔同向；
- 前三笔存在公共重叠区间；
- 第 3 笔相对第 1 笔持续推进：
  - 向上线段：第 3 笔高点高于第 1 笔高点；
  - 向下线段：第 3 笔低点低于第 1 笔低点。

不满足上述条件的三笔，不能构成线段起点。

## 4. 段内扩展

线段按「两笔一组」扩展：先来一笔反向回撤笔，再来一笔同向推进笔。只有同向笔继续创出新高/新低，线段才允许延长：

- 向上线段：新的同向上笔高点必须高于前一个同向上笔高点；
- 向下线段：新的同向下笔低点必须低于前一个同向下笔低点。

若同向笔未继续推进，线段在当前已有位置停住。

## 5. 终结定义

线段终结优先级：先看反向特征序列是否形成可直接确认的顶/底分型；未形成时才退回「反向笔破坏最近关键低/高点」的判定。

### 5.1 直接特征序列分型终结

反向特征序列先按非包含思路标准化（只处理同一条反向序列内部包含，相邻特征元素按序列方向合并），再判断分型：

- 向上线段：抽取段内向下笔为反向特征序列；连续三个反向元素形成顶分型且前两元素无缺口，则线段在该顶分型高点处终结。
- 向下线段：抽取段内向上笔为反向特征序列；连续三个反向元素形成底分型且前两元素无缺口，则线段在该底分型低点处终结。

对应状态码：`feature_sequence_fractal`。

### 5.2 缺口第二种情况（71 课再分辨）

若反向特征序列分型的第一、第二元素之间存在缺口，不立刻终结旧线段：

- 将该分型对应的反向笔记为**待确认转折点**，并视为新序列第一笔；
- 若后续同向第三笔**先破第一笔终点**，则确认新线段成立，旧线段在原分型极值处终结（`feature_sequence_gap_fractal`）；
- 若后续反向笔**先破第一笔起点**，则视为旧线段延续，撤销该候选分界点；
- 若先经历至少一轮「弱同向未突破」，再由更晚一轮同向强推进确认终结，则记为 `feature_sequence_gap_fractal_delayed_true`。

> 78 课补充（两种情况的第二特征序列）：

> 1. **分型左条件 ⟺ 捷径「先破终点」**：67课第二种情况要求「从该分型极值点开始的
>    反向笔序列的特征序列出现分型」。对该第二特征序列，分型的「中元素越过左元素」
>    左条件与 71课捷径「同向第三笔先破第一笔终点」在几何上严格等价——中元素低/高点
>    恰等于同向第三笔的终点，左元素低/高点恰等于缺口 pivot 的终点。因此捷径在左条件
>    处即确认，**早于**完整分型（完整分型还需「中元素越过右元素」），属急切近似而非
>    漏判；78课「严格按包含关系处理」的要求被捷径蕴含，无需在同一窗口内再判一次。
>    等价关系由 `test_78_second_feature_sequence_left_condition_equals_shortcut` 锁定。
> 2. **A+B+C 合一**：78课「线段 C 未成第二特征序列分型又直接新高/新低 → A+B+C 只算
>    一个线段」对应「缺口候选失效（先破第一笔起点）→ 旧段延续吸收 B」+「后续同方向
>    线段经 `_merge_segments_same_direction` 合流」，以 `is_reclaimed=True` 与
>    `absorbed_segment_ids` 记录吸收身份，由 `test_78_a_plus_b_plus_c_merge_marks_reclaim_metadata` 锁定。
> 3. **退化挂起**：若缺口后价格被夹在 `[pivot 低点, pivot 高点]` 内且无任何一笔越界，
>    则捷径与第二特征序列分型都无法形成（pivot 包含后续所有反向笔，特征序列被合并为
>    单元素），此时 `_rediscriminate_gap_break_detail` 返回 `None`（pending）是理论上
>    的正确行为，非缺陷。

> `feature_sequence_gap_fractal_delayed_true` 的「弱同向轮次」为工程扩展，非原文定义。

### 5.3 反向笔破坏关键点

- **直接破坏**：反向下/上笔跌破/突破当前线段最近关键低/高点，线段立即终结（`reverse_break`）。
- **震荡未破坏后二次确认**：反向笔未破坏关键点时旧段暂不终结；若后续同向笔未创新高/新低，且再下一根反向笔突破最近关键低/高点，则确认旧线段被破坏（`reverse_break_after_gap`），这根最早的反向笔作为新线段第一笔。

一旦发生有效破坏，前一线段标记 `is_confirmed=True`。

### 5.4 第一笔破坏前线段（71课第一种情况）

从转折点开始，第一笔反向笔就破坏前线段，且该笔延伸出三笔后第三笔破第一笔结束位置 → 新线段一定形成、前线段一定结束。

- 状态码：`first_bi_break_then_third_extends`（`theory_confirmed`）。
- 判定入口：`_first_bi_breaks_prior_segment_and_third_extends()`，仅在首个转折轮次、theory 模式触发。
- 若第三笔完全落在第一笔范围内（先破终点/先破起点未定），仍由 `transition_pending` / `_evaluate_transition_state()` 处理。

## 6. 未确认尾段

线段已满足起段条件并出现若干次正常推进，但尚未被有效反向破坏时，保留一个未确认尾段：

- `is_confirmed=False`；
- 图中仍绘制，表示「当前最后一段仍在进行中」。

## 7. theory / practical 双模式

- **theory**：只认严格几何终结（`feature_sequence_*` 系列），不把 fallback 反向破坏当确认。
- **practical**：允许消费 fallback 确认（`reverse_break`、`reverse_break_after_gap`）。

消费语义与状态码分类见 [segment-stop-reason-contract.md](segment-stop-reason-contract.md)。

## 8. 与其他模块的关系

- 上游：以 [base-structure-spec.md](base-structure-spec.md) 的已确认笔为输入。
- 下游：segment 级标准中枢（[zhongshu-core-spec.md](zhongshu-core-spec.md)）、走势类型、买卖点绑定。
- 边界：`bootstrap_mode`、窗口截断、工程评分属于实现层稳定性策略，不属于原文线段定义本身；`stop_reason` 是工程消费契约，不应反向当作理论定义。

## 9. 维护建议

- 线段理论定义变更：优先修改本文件。
- 实现口径变更：修改 [segment-implementation-guide.md](segment-implementation-guide.md)。
- 理论 vs 实现差异：记录到 [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) 与 [segment-tasks.md](segment-tasks.md)。
- 不得把「当前实现是…」写进本文件（应然/实然分离，见 [spec-change-protocol.md](spec-change-protocol.md)）。

## 10. 关联文档

- [segment-implementation-guide.md](segment-implementation-guide.md)：当前实现口径（实然）
- [segment-original-review-matrix.md](segment-original-review-matrix.md)：67/71/78 课原文逐课复核
- [segment-stop-reason-contract.md](segment-stop-reason-contract.md)：`stop_reason` 消费契约
- [segment-visual-example-library.md](segment-visual-example-library.md)：图文化示例库
- [segment-doc-map.md](segment-doc-map.md)：线段文档导航
- [segment-tasks.md](segment-tasks.md)：线段任务拆解
