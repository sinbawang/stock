# 中枢重算顺序与旧中心清理规则

本页锁定 `identify_zhongshu(..., structure_level="segment")` 的重算顺序与旧中心清理规则，
是 ZS3.1 的交付说明。输入资格见 [zhongshu-input-qualification.md](zhongshu-input-qualification.md)，
进入/离开边界见 [segment-zhongshu-boundary.md](segment-zhongshu-boundary.md)。

## 1. 核心原则

中枢层**不缓存**任何基于 segment chain 的结果。每次调用都从当前最终线段链全量重算。
因此“旧中枢幽灵”的根源只能在线段层：只要上游 `identify_segments` 的最终链正确，
中枢层就不会残留基于旧 chain 的中心。

## 2. 重算顺序清单

生产链路（`scripts/batch_prepare_chanlun_reports.py`）的固定顺序：

1. `raw_bars` → `clean_bars` → `normalize_bars`
2. `identify_fractals` → `filter_consecutive_fractals`
3. `identify_bis(...)`
4. `identify_segments(...)`（`1m` 用 `first_valid_seed`，其余用 `prefer_earlier_start`）
5. `identify_zhongshu(segments, structure_level="segment")` —— **主口径**
6. `identify_zhongshu(confirmed_bis, structure_level="bi")` —— 辅助口径（类中枢）

中枢层消费的是第 4 步产出的**最终**线段链，不消费任何中间态、pending 缓存或重算快照。
`restart` / `overlap` / `reclaim` / `reverse_break` 修正全部在线段层完成，中枢层只做“读最终链 + 重建”。

## 3. 旧中心清理 / 裁决规则

| 情况 | 裁决 | 说明 |
| --- | --- | --- |
| 线段链被 reclaim / 合并 / 缩回单个未确认尾段 | **整体废弃（清空）** | `_primary_segment_items` 裁到空，`identify_zhongshu` 返回 `[]`，不保留旧中心对象 |
| 旧中心被后续更大扩张重吸收（相邻中心 exit→entering 复用 + 区间重叠） | **不物理删除，标记重吸收** | `_mark_reabsorbed_lineage` 把前一已终结中心标 `superseded_by_zs_id` / `is_reabsorbed_by_larger_expansion=True`，沿重叠 successor 链传递塌缩 |
| 正常重建 | **全量重算** | 无缓存残留，同一窗口重复重算结果一致 |

裁决口径：

- “整体废弃”对应“旧 segment chain 已失效”：链缩回后旧中心失去存在依据，必须清空而非保留。
- “区间重算/重吸收”对应“旧中心仍在链内，只是语义被更大扩张吸收”：保留对象但标记失效，
  供下游按 lineage 解释，而不是把中间中心误吞成更晚中心的前驱。
- 二者不得混用：链失效用清空，链内重吸收用标记。

## 4. 回归锚点

- 整体废弃：`tests/test_zhongshu.py::test_identify_segment_zhongshu_recomputes_to_empty_after_same_direction_reclaim`、
  `test_identify_segment_zhongshu_recomputes_to_empty_after_reverse_break_reclaim`
- 重吸收标记：`tests/test_zhongshu.py::test_overlapping_followup_center_marks_previous_as_reabsorbed`、
  `test_reabsorbed_lineage_does_not_collapse_across_non_overlapping_final_successor`、
  `test_overlapping_followup_segment_center_marks_previous_as_reabsorbed`
- 真实空集真值：`tests/test_zhongshu_regression_real_fixtures.py`（`03690 30m`、`000591 60m long`、`300124 60m`）
- 重复重建确定性：`tests/test_zhongshu_regression_real_fixtures.py::test_repeated_rebuild_produces_identical_segments_zhongshus_and_structure_state`
