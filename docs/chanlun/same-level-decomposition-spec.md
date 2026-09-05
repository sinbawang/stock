---
spec_id: SPEC.TREND_DIVERGENCE.SAME_LEVEL_DECOMPOSITION
status: stable
owner: chanlun
applyTo: src/chanlun/analysis.py
tests: tests/test_chanlun_analysis.py, tests/test_zhongshu_regression_real_fixtures.py
---

# 同级别分解规格

本文件定义固定级别下的同级别分解口径（应然）：如何把一条本级别走势唯一地分解为
「盘整 / 上涨 / 下跌」等本级别走势类型的连续连接，以及中枢形成、盘整候选、趋势形成、
盘整结束的判定顺序。

本文件不负责：

- 背驰 / 买卖点的严格判定（见 [trend-divergence-spec.md](trend-divergence-spec.md) 与
  [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)）。
- 中枢的严格定义与区间计算（见 [zhongshu-core-spec.md](zhongshu-core-spec.md)）。
- 多义性下的结合律重组（见 [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)）。
- 同级别分解的工程主链与 machine-readable 输出（见 [trend-type-decomposition.md](trend-type-decomposition.md)）。

同级别分解相关文档的推荐分层：

- [same-level-decomposition-spec.md](same-level-decomposition-spec.md)：同级别分解理论口径（本文，应然）。
- [trend-type-decomposition.md](trend-type-decomposition.md)：同级别走势类型自动分解主链（TD1，工程唯一分解）。
- [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)：走势多义性与结合律。
- [zhongshu-state-machine.md](zhongshu-state-machine.md)：中枢状态机实现细节。
- [trend-divergence-spec.md](trend-divergence-spec.md)：走势类型 / 背驰口径。

## 1. 当前定位

> 实然状态（完成度 / 收敛进度）见 [trend-divergence-tasks.md](trend-divergence-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)；
> 本文件只保留理论口径（应然）。

- 理论成熟度：高
- 当前文档完整度：中高

理论根基（第38/39课同级别分解唯一性 + 第102课“再说走势必完美”）：

- 走势必完美对应一种最强唯一分解（类比自然数的记数法），级别依次升大；
- 同级别分解是这一整体结构在固定级别下的唯一分解，不存在任何含糊乱分解的可能；
- 区间套是这一唯一分解的重要应用。

## 2. 基本对象

设当前分析级别为本级别，固定在该级别下做同级别分解，不引入“升级为高级别中枢”的递归视角。

- 次级别走势类型：构成本级别走势类型的基本段。
- 本级别中枢：至少三个连续次级别走势类型的重叠部分。
- 本级别盘整：只包含一个本级别中枢的已完成走势类型。
- 本级别上涨/下跌趋势：至少包含两个依次同向、彼此不重叠的本级别中枢的已完成走势类型。

任何本级别走势，都分解为盘整、上涨、下跌等本级别走势类型的连续连接：

```text
... -> 走势类型 -> 走势类型 -> 走势类型 -> ...
```

每个本级别走势类型至少包含三个次级别走势类型。

必须严格区分三个时点：

1. **中枢形成**：三个连续次级别走势存在共同重叠；
2. **具备盘整最低结构**：当前结构只有一个中枢，可能最终成为盘整；
3. **盘整完成得到确认**：后续结构已经给出可执行的同级别切点。

中枢形成不等于盘整已经完成。在切点得到确认前，不能把前三段先确认为盘整，再因后面出现第二个中枢而回溯改判为趋势。

## 3. 三段形成中枢和盘整候选

连续三个完成的次级别走势存在共同重叠：

```text
1-2-3
```

便形成一个本级别中枢，也满足本级别盘整的最低结构。此时应理解为：

> 此时得到的是盘整候选，不是已经确认完成的盘整。

后续结构可能给出两种结果：

- 确认切点，将该候选确认为一个盘整；
- 形成第二个同向、不重叠中枢，使整体发展为趋势。

## 4. 盘整候选继续延伸

形成中枢后，后续次级别走势继续围绕原中枢波动：

```text
1-2-3-4-5
```

在新的完整结构出现前，可以暂时把它作为一个盘整候选的延伸观察：

- 只有一个已明确的中枢，不能提前确认准确切点；
- 后面部分还不足以独立构成另一个本级别走势，不能提前确认准确切点。

## 5. 六段时如何判定

连续六个次级别走势完成，并且前后三段分别形成中枢候选时：

```text
1-2-3 | 4-5-6
候选A | 候选B
```

此时不能仅按编号直接切分，必须先比较两个中枢的位置关系。

### 5.1 同向且不重叠

若第二个中枢相对第一个中枢同向排列且不重叠，则整体满足趋势结构：

```text
Z1 -> Z2 = 上涨趋势或下跌趋势
```

前三段只形成了趋势中的第一个中枢候选，不能单独确认成盘整。

### 5.2 不满足趋势条件

若两个中枢重叠，或两者关系不满足同向、不重叠的趋势条件，本文件采用的固定级别机械分解可处理成：

```text
盘整A + 盘整B
```

这意味着：

- 到第六段完成时，才回看确认前一个盘整在第 3 段终点结束；
- 后一个盘整从该点开始；
- 两个盘整各有自己的中枢；
- 若两个中枢实际重叠，则整体不构成本级别趋势；
- 切点一经确认，后续结构不再回溯改变已经完成的盘整性质。

> 六段提供的是一个候选切分时点；判断顺序是先检查趋势条件，再确认盘整切点。
> 但不能只按照编号硬切。前后三段必须各自是三个连续、完成、存在共同重叠的次级别走势类型。

## 6. 延伸达到九段及以上

继续出现满足条件的三段结构时，仍按同一顺序逐组判断：先检查它是否与尚未完成走势中的前一中枢共同构成趋势；若不构成趋势，再确认盘整切分。

```text
1-2-3 | 4-5-6 | 7-8-9
盘整A | 盘整B | 盘整C
```

若各相邻中枢均不构成同向、不重叠的趋势关系，在固定同级别语境下可分解为多个本级别盘整的连接，不需要解释为高级别中枢：

- 六段在排除趋势结构后可分为两个盘整；
- 九段在逐次排除趋势结构后可分为三个盘整；
- 十二段可按同一判断顺序继续分解；
- 边界必须满足走势连续性，不能单凭数量机械编号。

## 7. 未完成走势何时形成趋势

关键不是总共有多少段，而是是否形成第二个不重叠的同向中枢：

```text
中枢 Z1 -> 同向离开 -> 中枢 Z2
```

如果满足：

```text
上涨：Z2 整体位于 Z1 上方
下跌：Z2 整体位于 Z1 下方
```

并且两个中枢没有规定意义上的重叠，则原来只有一个中枢的未完成走势发展为趋势：

```text
Z1 + Z2 -> 上涨趋势或下跌趋势
```

这时不能把第一个中枢候选先确认为已完成盘整，否则会破坏这套分解下的趋势识别。

## 8. 两个中枢的完整分类

### 8.1 后一中枢与前一中枢不重叠

```text
Z1      Z2
```

若依次同向排列：

- 向上排列：上涨趋势；
- 向下排列：下跌趋势。

### 8.2 两个中枢重叠

```text
Z1
  Z2
重叠部分存在
```

在本文件采用的固定级别机械分解约定中，可以确认候选切点并处理为：

```text
盘整 A + 盘整 B
```

不构成本级别趋势。

> “中枢扩张、形成高级别中枢”属于递归级别分析，当前语境不采用。

### 8.3 尚未形成第二个完整中枢

继续作为第一个未完成走势的延伸观察，不能预判第二个盘整或趋势。

## 9. 趋势的延伸和结束

形成两个不重叠同向中枢后，趋势已经成立：

```text
Z1 -> Z2 -> Z3 -> ...
```

继续产生同向、不重叠中枢，属于趋势延伸。

趋势背驰出现在最后一个中枢前后的同向运动比较中：

- 上涨趋势背驰：产生潜在一卖；
- 下跌趋势背驰：产生潜在一买。

背驰表示趋势具备结束条件；次级别转折完成后，才能确认趋势终点。趋势结束后，下一段只能重新分解为：

```text
反向趋势或盘整
```

## 10. 盘整背驰和盘整结束

盘整只有一个中枢，因此不存在严格的趋势背驰。

离开中枢的走势与进入中枢的同向走势力度减弱，可以称为盘整背驰，它只能提示：

```text
离开段可能结束
```

不能单独证明整个盘整已经结束，也不是严格的一类买卖点。

盘整候选的结束主要通过后续结构确认：

1. 后续形成第二个中枢后，先判断两个中枢是否满足趋势条件；
2. 若同向且不重叠，原结构发展为趋势，不把第一个中枢单独判为完成盘整；
3. 若不满足趋势条件，则按机械切分约定确认前一盘整结束；
4. 出现反向的完整本级别走势时，确认原盘整已在连接点结束。

## 11. 同级别分解决策表

| 后续结构 | 处理方式 |
| --- | --- |
| 三段重叠 | 形成中枢和盘整候选，尚未确认完成 |
| 后续尚未形成第二个完整中枢 | 继续观察未完成走势的延伸 |
| 第二个中枢同向且不重叠 | 整体发展为上涨或下跌趋势，不切开第一个中枢 |
| 第二个中枢与前中枢重叠 | 排除趋势后，可按约定确认为两个盘整 |
| 六段形成两组中枢但不满足趋势条件 | 确认候选切点，处理为盘整 + 盘整 |
| 九段逐组判断后均不构成趋势 | 可处理为三个盘整连接 |
| 趋势继续产生不重叠同向中枢 | 趋势延伸 |
| 最后中枢后发生趋势背驰并转折 | 趋势完成的确认依据 |
| 只有盘整背驰 | 候选转折，不能单独确认盘整结束 |

## 12. 口诀

> 三段成中枢，不等于盘整完成；新中枢先判趋势，再定盘整切点；同向不重叠成趋势，不满足趋势条件再分盘整；切点一经确认，不再回溯改判。

## 13. machine-readable 字段映射

本文件的应然口径在 `src/chanlun/analysis.py` 中的 machine-readable 载体（TD1 工程唯一分解主链）：

| 应然条文 | machine-readable 载体 | 值域 | 消费红线 |
| --- | --- | --- | --- |
| §2 走势类型分解 | `structure_state.type_chain` / `last_completed` / `current_ongoing` | `type: range / up / down`；`status: completed / ongoing` | 类型边界不得按编号硬切 |
| §5/§6 切分时点 | `relationship.transition_state` | `none / same_type_extension / candidate_new_type / ongoing_new_type` | 只表达是否切到新类型，不单独确认盘整/趋势 |
| §8 分解唯一性 | `same_level_decomposition_mode` | `single_confirmed / dual_interpretation_pending` | `dual_interpretation_pending` 统一降级为 pending/watch |
| §8 消费等级 | `same_level_consumption_level` | `auxiliary / pending / confirmed` | 三态不得混用 |

完整字段消费语义见 [trend-type-decomposition.md](trend-type-decomposition.md)、
[theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) 与
[zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。

## 14. 维护建议

- 若要改“同级别分解 / 盘整候选 / 趋势形成 / 切点确认”的理论口径，优先改本文件。
- 若只改工程主链的字段结构或 live-run 切分实现，优先改 [trend-type-decomposition.md](trend-type-decomposition.md)。
- 若涉及多义性 / 结合律重组，优先改 [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)。
- 若涉及中枢区间计算或重叠判定，优先改 [zhongshu-core-spec.md](zhongshu-core-spec.md)。

## 15. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [zhongshu-core-spec.md](zhongshu-core-spec.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- [trend-divergence-spec.md](trend-divergence-spec.md)
- [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)
- [trend-type-decomposition.md](trend-type-decomposition.md)
- [zhongshu-state-machine.md](zhongshu-state-machine.md)
- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)
- [lesson-traceability-matrix.md](lesson-traceability-matrix.md)