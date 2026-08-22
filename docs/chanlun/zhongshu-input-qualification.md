# 标准中枢输入 segment 资格表

本页锁定 `identify_zhongshu(..., structure_level="segment")` 的输入资格口径，
是 ZS1.1 的交付说明。进入段 / 离开段边界见 [segment-zhongshu-boundary.md](segment-zhongshu-boundary.md)。

## 1. 核心原则

标准中枢只基于**已确认线段**成立，未确认尾段不得直接入场。
资格裁剪只发生在链尾：`identify_zhongshu` 调用前先执行 `_primary_segment_items`，
从末尾往前裁掉连续未确认段，保留最后一个已确认段及其之前的所有段。

## 2. segment 资格表

| 线段位置 | 状态 | 是否进入中枢输入 | 规则 |
| --- | --- | --- | --- |
| 链尾 | `is_confirmed=False` | 否 | 从末尾往前连续裁掉未确认段 |
| 链中间 | `is_confirmed=False`（pending stop 标签） | 是 | 后面已有 confirmed 段时保留，仍属于交替链的一部分 |
| 任意位置 | `is_confirmed=True` | 是 | 正常参与 |
| 全部未确认 / 缩回单个未确认尾段 | — | 否（整体清空） | 裁剪后不足 5 段，无中枢 |

> 为什么未确认尾段不能作为本体第三段？
>
> `is_confirmed=False` 不是“这段不存在”，而是“这段的终点还没封口”：它的 `end_bi_id`、
> `high`、`low` 之后仍可能被延伸、回收或边界重算。中枢区间由本体前三段固定
> （`zs_low/zs_high`），若第三段未确认，区间就会随尾段重算而漂移，违背 ZS1
> “同一窗口重复重算得到同一标准中枢”的承诺。因此即使未确认尾段方向已经明确、
> 甚至价格已经越过本体第一段，也必须在它确认后再判断是否成立。
>
> 另注：当前实现还要求输入至少 5 段（进入段 + 本体三段 + 至少 1 段用于离开段判定），
> 所以“进入段 + 3 本体段”的 4 段最小中枢在尚未出现离开候选前也不会立即成立，属于工程保守分支。
> 严格理论口径下，3 段重叠即可形成最小中枢，本实现的“已确认 + 固定区间”是稳定性优先的工程取舍。

## 3. 必须清空 / 可以保留 / 必须重建

| 情况 | 判定 | 说明 |
| --- | --- | --- |
| 线段链被回收 / 合并 / 缩回单个未确认尾段 | **必须清空** | `_primary_segment_items` 裁到空，`identify_zhongshu` 返回 `[]`，不残留旧中心 |
| 中间历史段带 pending stop 标签、其后已有 confirmed 段 | **可以保留** | 中间 pending 段是已实现的交替链一部分，裁掉会扭曲链序并吞掉合法中枢 |
| `segment` 层 restart / overlap 修正导致边界重算 | **必须重建** | 上游 chain 变化后按新 chain 重算，不得沿用旧 segment chain 缓存 |
| 尾段未确认但前面仍有足够 confirmed 段 | **保留前面，只裁尾** | 裁掉尾段后若仍 ≥5 段，中枢照常成立 |

## 4. 最小例子

### 4.1 尾段未确认被裁掉，仍成立

| 段 | 方向 | high | low | confirmed |
| --- | --- | --- | --- | --- |
| 0 | DOWN | 110 | 98 | 是 |
| 1 | UP | 106 | 100 | 是 |
| 2 | DOWN | 104 | 101 | 是 |
| 3 | UP | 103 | 102 | 是 |
| 4 | DOWN | 102 | 96 | 是 |
| 5 | UP | 103.5 | 101.8 | 否（尾段） |

- 段 5 未确认 → 裁掉；段 0-4 仍构成 `进入=0, 本体=[1,2,3], 离开=4` 的完整中枢。

### 4.2 缩回单个未确认尾段 → 清空

- 若线段链最终只缩回 1 个未确认段，`_primary_segment_items` 裁到空 → 无中枢。

## 5. 与 segment 层关系

- 标准中枢输入只认 `identify_segments` 产出的最终线段链，不认中间态的 pending / 重算缓存。
- `restart` / `overlap` / `reclaim` / `reverse_break` 修正都在线段层完成，中枢层只消费最终链结果。
- 因此“旧中枢幽灵”应在线段层被阻止，中枢层不额外做跨链回滚。

## 6. 回归锚点

- `tests/test_zhongshu.py`：
  - `test_identify_segment_zhongshu_ignores_unconfirmed_tail_segment`
  - `test_identify_segment_zhongshu_keeps_historical_pending_segments_before_confirmed_follow_on`
  - `test_identify_segment_zhongshu_trims_only_unconfirmed_tail_and_still_forms`
  - `test_identify_segment_zhongshu_ignores_transition_pending_tail_from_segment_pipeline`
  - `test_identify_segment_zhongshu_recomputes_to_empty_after_same_direction_reclaim`
  - `test_identify_segment_zhongshu_recomputes_to_empty_after_reverse_break_reclaim`
