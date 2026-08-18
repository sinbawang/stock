# 中枢核心理论规格

本文件定义中枢模块的核心理论口径，只回答“中枢严格上应该怎么定义、识别、表达”。

本文件不负责：

- 主辅消费规则
- 图表/报告冲突降级策略
- 原文逐课复核进度
- 案例库与图文化样例

中枢相关文档的推荐分层：

- [zhongshu-core-spec.md](zhongshu-core-spec.md): 中枢核心理论定义。
- [zhongshu-review-entry.md](zhongshu-review-entry.md): 中枢 review 单页入口。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 中枢/类中枢主辅消费与命名规范。
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md): 原文复核矩阵。
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md): 图文化样例库。

## 1. 当前定位

- 理论成熟度：高
- 当前实现完成度：中
- 当前文档完整度：中高

当前仓库里，中枢的理论定义已经相对清楚，但“标准中枢主实现”和“类中枢辅助实现”的收敛还没有完全结束。

## 2. 中枢在整体结构中的位置

- 中枢不是孤立价格盒子，而是走势类型的核心组织单元。
- 不通过中枢，趋势、盘整、背驰、一二三类买卖点都无法形成完整定义。
- 中枢必须放回同级别分解中理解，不能仅凭图上矩形形状给结论。

## 3. 中枢定义

严格定义下，中枢由至少 3 个连续次级别走势类型的重叠区间构成。

必须区分以下对象：

- 进入段
- 中枢本体内部三段及其后续扩展
- 离开段

红线：

- 不能把进入段直接算作中枢内部第一段。
- 不能把离开段直接并入中枢本体。
- 不能把“任意连续三笔重叠”直接等同于严格中枢。

## 4. 最小中枢

形成最小中枢的基本步骤：

1. 先有进入段，把走势带入潜在重叠区域。
2. 从进入段之后开始，连续 3 个次级别走势类型作为中枢本体候选。
3. 若这 3 段存在公共重叠，则形成最小中枢。

中枢区间：

- `zs_low = max(low1, low2, low3)`
- `zs_high = min(high1, high2, high3)`

并要求：

- `zs_low < zs_high`

严格要求：

- 这 3 段必须是进入段之后的连续 3 段。
- 相邻段方向必须交替。
- 进入段不计入中枢本体三段。

## 5. 扩展、延伸、扩张

### 5.1 扩展

- 后续同级别内部段继续与当前中枢区间重叠时，中枢在时间上延长。

### 5.2 延伸

- 同一中枢内部震荡继续发展，但仍属于同一中枢语义。

### 5.3 扩张

- 当结构升级到更高层级关系时，应按更高一级中枢解释。
- 不能把更高层级结构仍机械地视为原最小中枢的简单横向平移。

## 6. 中枢终结与破坏

- 中枢形成离开段后，若后续结构不再维持原中枢语义，原中枢结束。
- 中枢结束不能只凭价格越过边界机械判定。
- 是否终结，必须放回同级别分解中解释其离开性质和后续结构归属。

## 7. 中枢标准表达

一个标准中枢对象，建议至少区分：

- `entering_*`: 哪一段只是进入段。
- `core_*`: 哪些段属于中枢本体。
- `exit_*`: 哪一段被识别为离开段。
- `render_*`: 图上矩形如何画。
- `zone_mode`: 区间是否为固定区间或随扩展重算区间。

最少字段建议：

- `id`
- `structure_level`
- `entering_segment_id`
- `core_start_segment_id`
- `core_end_segment_id`
- `exit_segment_id`
- `zs_low`
- `zs_high`
- `is_terminated`
- `termination_mode`
- `zone_mode`

## 8. 图形表达要求

标准图形表达应区分：

- 进入段
- 中枢本体矩形
- 中枢扩展部分
- 离开段

图上至少应满足：

- 中枢矩形不从进入段起画。
- 中枢矩形只覆盖中枢本体内部段。
- 离开段单独表达，不并入中枢本体。
- 若采用固定区间画法，必须显式说明其为工程近似。

## 9. 与类中枢的边界

- 标准中枢是理论主口径。
- 类中枢是笔级近似辅助口径。
- 任何主辅消费、命名、冲突降级，不在本文件定义，统一交给 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。

## 10. 当前工程实现与理论差异

当前仓库的典型差异点主要包括：

- 当前工程中常以笔级近似路径先行，而不是标准中枢主输出先行。
- 当前部分实现采用固定区间矩形，而不是随扩展重算区间。
- 当前对中枢终结和后续扩展吸收的处理，仍有工程保守分支。

因此：

- 本文件定义“目标理论口径”。
- 当前实现差异应记录到任务清单或实现专题，不应反向污染本文件定义。

## 11. 维护建议

- 若改中枢理论定义，优先改本文件。
- 若改主辅消费和对外命名，优先改 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。
- 若改原文课次对应关系，优先改 [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)。
- 若补图示和案例，优先改 [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)。

## 12. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [zhongshu-review-entry.md](zhongshu-review-entry.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)
