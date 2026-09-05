# 同级别走势类型自动分解主链

本页锁定 TD1“同级别走势类型自动分解”的输入边界、切换条件与 machine-readable 输出，
是背驰严格判定（TD2/TD3）的前置契约。状态机细节见 [zhongshu-state-machine.md](zhongshu-state-machine.md)。

理论根基（第102课“再说走势必完美”）：走势必完美对应一种最强唯一分解（类比自然数的记数法），级别依次升大；
同级别分解的唯一性正是这一整体结构的直接推论，区间套则是它的重要应用。因此 TD1 的“唯一分解”不是工程妥协，
而是走势必完美在固定级别下的工程实现。

> 同级别分解的理论口径（应然）见 [same-level-decomposition-spec.md](same-level-decomposition-spec.md)。

## 1. 输入边界

走势类型分解的输入是**标准线段级中枢链**，链路固定为：

1. `identify_segments` 产出最终线段链（只消费 `is_confirmed` 段，未确认尾段被裁）。
2. `identify_zhongshu(segments, structure_level="segment")` 产出标准中枢链。
3. `_decompose_walk_types(zhongshus)` 消费**全部检出中枢**（严格同级别分解不做扩张重吸收裁剪，
   `superseded_by_zs_id` / `is_reabsorbed_by_larger_expansion` 标记只影响 CSV/调试，不影响分解），
   按相邻中枢关系唯一切分为走势类型块。

每个走势类型块对应一段同级别走势类型：

- 恰好一个中枢（相邻关系为 `range`：区间重叠或 GG/DD 回探扩张）→ `range`（盘整）。
  **连续多个 `range` 关系的中枢各自独立成一个盘整（§8.2），不折叠成 `zs_count>1` 的大盘整。**
- 相邻中枢同向、真不重叠（`_relation_kind` 判为 `up`/`down`）且 ≥2 个 → `up` / `down`（趋势）。

## 2. 切换条件

| 场景 | 判定 | 机器表现 |
| --- | --- | --- |
| 盘整（单中枢） | 相邻关系为 `range`（区间重叠或 GG/DD 回探扩张） | `range`，每盘整恰好 1 中枢 |
| 趋势 | ≥2 个连续同向、真不重叠中枢 | `up` / `down`，`zs_count>=2` |
| 完成后转入新类型 | 切出异类型或新盘整 | `last_completed` 非空，`transition_state=candidate_new_type`（ongoing 单中枢盘整）或 `ongoing_new_type`（ongoing 趋势） |
| 相邻重叠中枢 | 两中枢区间/波动重叠 | 各自独立成盘整（`盘整A + 盘整B`，§8.2），不合并、不算扩张升级 |

## 3. machine-readable 输出

`build_structure_state(...)` 现在输出两类 machine-readable 结果：

### 3.1 类型链 `type_chain`

- 结构：`[{type, status, zs_count, start_zs_id, end_zs_id, start_ts, end_ts}, ...]`
- 语义：把全部中枢按 `_decompose_walk_types` 唯一切分为走势类型块，除最后一段为 `ongoing` 外均为 `completed`。
- 与 `last_completed` / `current_ongoing` 严格一致：`current_ongoing` 为最后一块，
  `last_completed` 为倒数第二块（不足两块时为 `null`）。
- `type` 取值：`range` / `up` / `down`；`status` 取值：`completed` / `ongoing`。
- `start_ts` / `end_ts`：该类型段的起止时间（`end_ts` 对 `ongoing` 为 `null`），供结构图在
  每个类型段起点画走势类型分界虚竖线并标注 `range/up/down`（见
  `chanlun.visualization.Plotter._draw_structure_boundaries`）。

### 3.2 转场与消费等级

- `relationship.transition_state`：`none` / `candidate_new_type` / `ongoing_new_type`
  （严格同级别分解下 `same_type_extension` 不再由块相邻产生：延伸趋势本身即单一 ongoing 块）。
- `consumption_level`：`auxiliary` / `pending` / `confirmed`
  - 单中枢 ongoing 盘整（`single_active_zhongshu`）→ `pending` / `dual_interpretation_pending`
    （§3：盘整候选，切点未确认前不升级）。
  - 形成中的 ≥2 中枢趋势（`forming_next_same_level_zhongshu`）→ `confirmed`。
- 二者共同表达“当前盘整候选、趋势推进，还是完成后转入新类型”，下游背驰 / 买卖点应引用，
  不得各自重新猜一遍。

## 4. 稳定性保证

- `build_structure_state` 无缓存、无随机性，同一窗口 repeated rebuild 结果一致。
- 回归锚点：`tests/test_chanlun_analysis.py::test_build_structure_state_type_chain_matches_last_completed_and_ongoing`
  与 `test_build_structure_state_type_chain_single_and_empty`；真实窗口见
  `tests/test_zhongshu_regression_real_fixtures.py` 的 repeated rebuild 确定性 gate。

## 5. 后续细化（非本阶段 blocker）

- 单条链内多段类型切换（如 `up → range → up`）由 `_decompose_walk_types` 直接唯一切分：
  `range` 关系切开为独立盘整，连续同向 `up`/`down` 关系合并为一个趋势块；回归见
  `test_build_structure_state_type_chain_enumerates_in_run_type_switches`。
- 背驰严格判定（TD2/TD3）直接消费 `type_chain` / `current_ongoing.type` / 最近中枢。
