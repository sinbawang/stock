# 同级别走势类型自动分解主链

本页锁定 TD1“同级别走势类型自动分解”的输入边界、切换条件与 machine-readable 输出，
是背驰严格判定（TD2/TD3）的前置契约。状态机细节见 [zhongshu-state-machine.md](zhongshu-state-machine.md)。

理论根基（第102课“再说走势必完美”）：走势必完美对应一种最强唯一分解（类比自然数的记数法），级别依次升大；
同级别分解的唯一性正是这一整体结构的直接推论，区间套则是它的重要应用。因此 TD1 的“唯一分解”不是工程妥协，
而是走势必完美在固定级别下的工程实现。

## 1. 输入边界

走势类型分解的输入是**标准线段级中枢链**，链路固定为：

1. `identify_segments` 产出最终线段链（只消费 `is_confirmed` 段，未确认尾段被裁）。
2. `identify_zhongshu(segments, structure_level="segment")` 产出标准中枢链。
3. `_split_live_zhongshu_runs(...)` 按 `superseded_by_zs_id` / `is_reabsorbed_by_larger_expansion`
   把中枢链切成 live runs（剔除被更大扩张重吸收的中心）。

每个 live run 对应一段同级别走势类型：

- 单个中枢，或相邻中枢区间重叠 → `range`（盘整）
- 相邻中枢同向不重叠 → `up` / `down`（趋势）

## 2. 切换条件

| 场景 | 判定 | 机器表现 |
| --- | --- | --- |
| 盘整延续 | 相邻中枢区间重叠，或只有单个中枢 | `range`，`transition_state=none` 或 `same_type_extension` |
| 趋势延续 | 相邻中枢同向不重叠，持续创新高 / 新低 | `up` / `down`，`transition_state=same_type_extension` |
| 完成后转入新类型 | 中枢区间不再重叠、切出异类型 | `last_completed` 非空，`transition_state=candidate_new_type` 或 `ongoing_new_type` |
| 旧中心被更大扩张重吸收 | exit→entering 复用 + 区间重叠 | 归入 `same_type_extension`，不算独立完成 |

## 3. machine-readable 输出

`build_structure_state(...)` 现在输出两类 machine-readable 结果：

### 3.1 类型链 `type_chain`

- 结构：`[{type, status, zs_count, start_zs_id, end_zs_id, start_ts, end_ts}, ...]`
- 语义：把 live runs 拆成 `completed` 段（历史已终结类型）+ 最后一段 `ongoing`。
- 与 `last_completed` / `current_ongoing` 严格一致：completed 段来自 `last_completed`，
  ongoing 段来自 `current_ongoing`，早于 `last_completed` 的 run 按 run 粒度折叠为 completed。
- `type` 取值：`range` / `up` / `down`；`status` 取值：`completed` / `ongoing`。
- `start_ts` / `end_ts`：该类型段的起止时间（`end_ts` 对 `ongoing` 为 `null`），供结构图在
  每个类型段起点画走势类型分界虚竖线并标注 `range/up/down`（见
  `chanlun.visualization.Plotter._draw_structure_boundaries`）。

### 3.2 转场与消费等级

- `relationship.transition_state`：`none` / `same_type_extension` / `candidate_new_type` / `ongoing_new_type`
- `consumption_level`：`auxiliary` / `pending` / `confirmed`
- 二者共同表达“当前处于盘整延续、趋势延续，还是完成后转入新类型”，下游背驰 / 买卖点应引用，
  不得各自重新猜一遍。

## 4. 稳定性保证

- `build_structure_state` 无缓存、无随机性，同一窗口 repeated rebuild 结果一致。
- 回归锚点：`tests/test_chanlun_analysis.py::test_build_structure_state_type_chain_matches_last_completed_and_ongoing`
  与 `test_build_structure_state_type_chain_single_and_empty`；真实窗口见
  `tests/test_zhongshu_regression_real_fixtures.py` 的 repeated rebuild 确定性 gate。

## 5. 后续细化（非本阶段 blocker）

- 单个 run 内部多段类型切换（如 `up → range → up`）的完整前缀枚举：当前 `type_chain` 只展开到
  `last_completed` + `current_ongoing`，更早的段内细分由 `type_chain` 的 completed 前缀按 run 粒度折叠。
- 背驰严格判定（TD2/TD3）直接消费 `type_chain` / `current_ongoing.type` / 最近中枢。
