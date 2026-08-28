# 中枢扩张与更大级别中枢判定（设计草案）

spec_id: SPEC.ZHONGSHU.EXPANSION（候选）
status: draft
owner: chanlun
applyTo: src/chanlun/zhongshu.py, src/chanlun/analysis.py

本文给出「中枢扩张 → 更大级别中枢 → 走势类型改判」的落地设计，锚点为 `03690 5m`
（窗口 `20260722→20260828`）。**本文只做设计，不改代码。**

关联：理论口径见 [zhongshu-core-spec.md](zhongshu-core-spec.md) §5-§6、
[trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)（draft）；
现状状态机见 [zhongshu-state-machine.md](zhongshu-state-machine.md)。

## 1. 问题陈述

`build_structure_state` 里走势类型由 `_relation_kind(previous, current)` 决定，只比较
**中枢区间 [ZD, ZG]**：

```python
def _relation_kind(previous, current):
    if current.zs_low > previous.zs_high:
        return "up"
    if current.zs_high < previous.zs_low:
        return "down"
    return "range"
```

它漏掉了**第 20 课**的点名场景：两个中枢**区间不重叠、但波动区间重叠** → 不是趋势，
而是更大级别中枢。

### 锚点：03690 5m

| 中枢 | 区间 [ZD, ZG] | 波动区间 [peak_low, peak_high] | 进入段 | 本体 |
| --- | --- | --- | --- | --- |
| ZS0 | [89.00, 91.35] | [88.70, 94.50] | S0 | S1..S6 |
| ZS1 | [92.05, 92.20] | [85.70, 96.45] | S7 | S8..S11 |

- 区间：ZS1.ZD=92.05 > ZS0.ZG=91.35 → 区间不重叠 → 现状判 `up`。
- 波动：`max(88.70, 85.70)=88.70 < min(94.50, 96.45)=94.50` → 波动区间重叠 `[88.70, 94.50]`。

当前输出：

```
current_ongoing.type = "up"（误）
confirmation_basis  = "forming_next_same_level_zhongshu"
zs_count = 2
```

## 2. 理论依据

- **第 20 课（中枢级别扩张）**：三个连续次级别走势的重叠区间不与前中枢重叠、但围绕该
  中枢的波动触及前中枢（或延伸）的波动区间 → 不能认为是趋势，而是产生一个更大级别中枢。
- **第 21 课**：中枢三态 = 延续 / 扩张 / 新生；扩张对应「更大级别中枢」，新生对应趋势。
- **第 33 课**：中枢延伸数量多义性（延伸 5 段内；6 段延伸 + 本体 3 段 = 9 段升级）。
- **第 36/38 课**：结合律与同级别分解唯一性。

## 3. 现状盘点

- `identify_zhongshu` 已算好 `peak_low / peak_high`（含延伸后更新），并随 `tech.json` 落盘。
- `_mark_reabsorbed_lineage` 只做「相邻已终止中枢 exit→entering 复用 + 区间重叠」的血缘
  标记，真实数据几乎不触发（`SCANNED 558 / MATCHED 0`），且它用「区间重叠」而非「波动重叠」。
- 因此「扩张」在机器层是**缺位**的：没有更大级别中枢对象，也没有走势类型改判。

## 4. 设计

分三个正交部分，可独立落地：

### 4.1 扩张判定（核心，改 `_relation_kind` 或新增并列判定）

给 `_relation_kind` 引入「波动区间重叠」的第二层判定：

```python
def _peaks_overlap(previous, current) -> bool:
    return max(previous.peak_low, current.peak_low) < min(previous.peak_high, current.peak_high)


def _relation_kind(previous, current):
    if current.zs_low > previous.zs_high:
        return "range" if _peaks_overlap(previous, current) else "up"   # 扩张 → 归入盘整
    if current.zs_high < previous.zs_low:
        return "range" if _peaks_overlap(previous, current) else "down"
    return "range"
```

语义：区间重叠=盘整；区间不重叠但波动重叠=**扩张（更大级别中枢，归 range）**；两者都不
重叠才是趋势。这样 `type_chain` / `current_ongoing.type` 自然改判，无需另开 type 值。

### 4.2 更大级别中枢对象（新增，独立输出，不改同级别主链）

新增 `identify_expanded_zhongshus(zhongshus) -> list[ExpandedZhongshu]`：

- 遍历相邻同级别中枢，当 `_peaks_overlap` 成立且区间不重叠时，把二者合并为一个
  `expanded` 对象。
- 字段建议：
  - `expanded_id`
  - `sub_zs_ids: [previous.zs_id, current.zs_id]`
  - `expanded_low / expanded_high`（区间公式见 §6 待定）
  - `peak_low / peak_high`（= 两段波动的并集或重叠）
  - `level = "higher"`（显式区别于同级别）
- 消费端把 `expanded_zhongshus` 与同级别 `zhongshus` 并列输出，图上用更粗/半透明矩形表达。

### 4.3 走势类型改判与消费

- `build_structure_state` 用改后的 `_relation_kind` 计算 `type`；扩张自动落到 `range`。
- 保留 `same_level_consumption_level`：扩张落 `range` 后仍按同级别主链三态消费，
  新增的 `expanded` 对象只作「更大级别震荡」展示，**不得**反向改写同级别买卖点结论。

### 4.4 数据流

```
segments → identify_zhongshu（不变，同级别）
        → identify_expanded_zhongshus（新增，输出更大级别对象）
        → build_structure_state（_relation_kind 改判 + type_chain）
        → tech.json（zhongshus + expanded_zhongshus + structure_state）
        → 图表/报告/小程序（同级别矩形 + 更大级别半透明矩形）
```

## 5. 03690 5m 锚点 before / after

| 维度 | before（现状） | after（本设计） |
| --- | --- | --- |
| `_relation_kind(ZS0, ZS1)` | `up`（区间不重叠） | `range`（波动重叠 → 扩张） |
| `current_ongoing.type` | `up` | `range` |
| `type_chain` | `[{type: "up", zs_count: 2}]` | `[{type: "range", zs_count: 2}]` |
| 扩张对象 | 无 | 1 个 `expanded`：sub=[ZS0, ZS1]，zone≈[88.70, 94.50] |
| 背驰分轨 | 趋势背驰轨 | 盘整背驰轨（`divergence.range`） |
| 同级别中枢 | ZS0、ZS1（不变） | ZS0、ZS1（不变） |

## 6. 待定决策（需评审拍板）

1. **更大级别区间公式**：
   - (a) 两段波动区间重叠 `[88.70, 94.50]`；
   - (b) 两段 zone 的并集 `[89.00, 92.20]`；
   - (c) 按第 33 课 9 段升级重切后重算。
   建议先落 (a)（最直接、与判定一致）。
2. **type 取值**：扩张归 `range`（推荐，复用现有分轨）vs 新增 `expanded` 类型（语义更精确但
   需改消费端）。建议先归 `range`。
3. **`_relation_kind` 是否原地改**：原地改（推荐，type_chain 自然正确）vs 保留原函数、在
   `build_structure_state` 里加 override（隔离改动但需额外穿透字段）。建议原地改。

## 7. 下游影响

- `divergence.trend` / `divergence.range` 分轨：03690 会从趋势轨切到盘整轨。
- 一类点（buy_1/sell_1）背驰三元组：参考中枢口径不变，但「趋势背驰 vs 盘整背驰」措辞变化。
- `same_level_decomposition_mode` / `consumption_level`：扩张落 `range` 后仍为 `confirmed`，
  但 `transition_state` 可能从 `none` 变为 `same_type_extension`（待实测）。

## 8. 测试计划

1. **03690 5m 真实锚点**：断言 `current_ongoing.type == "range"`、`expanded_zhongshus`
   存在且 `sub_zs_ids == [0, 1]`、`expanded zone == [88.70, 94.50]`（按 §6.1a）。
2. **synthetic**：
   - 区间重叠 → `range`（不变）。
   - 区间不重叠 + 波动重叠 → 新增 `range`（扩张，非 up/down）。
   - 区间不重叠 + 波动不重叠 → `up`/`down`（趋势，不变）。
3. **回归**：`tests/test_zhongshu.py`、`tests/test_zhongshu_regression_real_fixtures.py`、
   `tests/test_chanlun_analysis.py` 现有用例必须不漂移（改 `_relation_kind` 前先跑基线）。

## 9. 与既有口径的边界

- 本设计**不改** `identify_zhongshu` 的「重叠优先 + 固定前三段区间」主链（§10.1 冻结）。
- 本设计**不动** `_mark_reabsorbed_lineage` 的血缘语义（那是「exit→entering 复用」的口径，
  与「波动重叠」正交）；后续可评估两者合并，但不在本设计范围。
