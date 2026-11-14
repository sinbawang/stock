---
spec_id: SPEC.BUY_SELL.CORE
status: stable
owner: chanlun
applyTo: src/chanlun/analysis.py
tests: tests/test_chanlun_analysis.py
---

# 买卖点与多级别联立规格

本文件定义以下高层消费与执行模块：

- 一二三类买卖点
- 区间套
- 小转大
- 多级别联立
- 操作级别与执行级别分工

这是缠论分析最容易出现“概念懂了，但代码和消费端口径不一致”的模块。

## 1. 当前定位

> 实然状态（完成度 / 收敛进度）见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)；
> 本文件只保留理论口径（应然）。

- 理论成熟度：中高
- 当前文档完整度：中低

## 2. 一二三类买卖点

### 2.1 总则

- 买卖点都依附于最近中枢和走势类型。
- 买卖点是结构结论，不是经验信号枚举。
- 任一买卖点都必须能回答“属于哪个最近中枢、位于哪个离开/回抽阶段”。

### 2.2 第一类买卖点

- 第一类买点：下跌走势在最后相关中枢附近出现背驰后，形成向上转折。
- 第一类卖点：上涨走势在最后相关中枢附近出现背驰后，形成向下转折。

核心是“背驰导致的转折”，不是单纯触边。

严格确认要件（应然）：

- 必须处于同级别趋势中：一买要求 `ongoing_type == down`，一卖要求 `ongoing_type == up`；
  盘整 / 中枢扩张（range）不产生一类点，只能给盘整背驰观察提示。
- 绑定最近标准中枢，且能回溯到「最近中枢 + 离开段 + 背驰」三元组。
- 离开段必须已确认（完成），并与中枢方向相反（向下离开 -> 一买，向上离开 -> 一卖）。
- 背驰必须离开段相对进入段力度衰减，且已出现反向转折笔（反向转折笔可为 effective 未确认尾笔——
  `2026-09-13` 用户决策「新笔不要求确认」，与二 / 三类口径对齐；离开段锚点仍须已确认）。
- 预警态（仅跌破 / 越界或仅背驰，尚未出现任何反向笔）不得标为严格一类点，只能列 `forming` 预备。
- 买卖两侧对称：一买与一卖的确认要件逐条对齐。

### 2.3 第二类买卖点

- 第二类买点：第一类买点出现后，第一次回试不破前低，再次恢复向上时形成。
- 第二类卖点：第一类卖点出现后，第一次反抽不破前高，再次恢复向下时形成。

核心是“转折后的第一次确认性回抽”。二类点依赖一类点，因此同样要求同级别趋势
（`ongoing_type == down/up`）。

### 2.4 第三类买卖点

- 第三类买点：向上离开中枢后，第一次回抽不重新跌回中枢上沿之下，再度走强时形成。
- 第三类卖点：向下离开中枢后，第一次反抽不重新站回中枢下沿之上，再度走弱时形成。

核心是“离开中枢后的首次不回归确认”。段级中枢下，离开与回抽均须为线段级别：
离开段 + 回踩线段同时成立才可报三买/三卖；回踩尚未成段时不得提前报点。

### 2.5 类一类买卖点（LB1 / LS1）

类一类买卖点是「盘整背驰」（而非趋势背驰）构成的、类似第一类买卖点的转折点。原文
（第27课「盘整背驰与历史性底部」）：「第一类买点肯定是趋势背驰构成的，而盘整背驰构成的
买点……在大级别里，这也构成一种类似第一类买点的买点……这时候就要用到这因为盘整背驰而
形成的**类第一类买点**了」；第65课亦言「严格来说，盘整背驰无所谓第一类买点，只是这样来
类比」。

标准一买 / 一卖要求同级别趋势（`ongoing_type == down/up`），因此盘整 / 中枢震荡（range）里
趋势门控缺席、标准一类点不出（§2.2 只给盘整背驰观察提示）。类一类点正是把这条「盘整背驰
观察提示」升级为可操作转折点：在最近中枢的中枢震荡 / 扩张结构里，离开段相对同向进入段出现
盘整背驰并反向转折时给点。

- 类一买（LB1）：最近中枢处于中枢震荡 / 盘整（`ongoing_type == range`，无同级别下跌趋势），
  向下离开段相对同向进入段出现盘整背驰——离开段跌破中枢下沿且创进入段前低但段级力度弱于
  进入段；离开段结束、出现向上反向转折笔时（可为未确认尾笔），在离开段低点生成类一买。
- 类一卖（LS1）：最近中枢处于中枢震荡 / 盘整（`ongoing_type == range`，无同级别上涨趋势），
  向上离开段相对同向进入段出现盘整背驰——离开段升破中枢上沿且创进入段前高但段级力度弱于
  进入段；离开段结束、出现向下反向转折笔时（可为未确认尾笔），在离开段高点生成类一卖。

与标准第一类买卖点的关键差异（应然）：

- 背驰口径不同：标准一类点是「趋势背驰」（`ongoing_type == down/up`），类一类点是「盘整背驰」
  （`ongoing_type == range`，中枢震荡 / 中枢扩张）。两者的力度比较对象一致——都是「离开段 vs
  同向进入段」（段级 MACD 面积衰减 + 离开段创进入段前低 / 前高），只是所处走势类型不同。
- 定位仍是「背驰导致的转折」本身：类一类点是转折点 / 背驰点本身（对应第一类点的操作意义），
  不是转折后的回抽确认（那是二类 / 类二类点）。
- 依附最近中枢：与其它买卖点一致，类一类点须能回答「属于哪个最近中枢、位于哪个离开段」。
- 中枢震荡门控（单中枢盘整 regime）：类一类点属「单中枢盘整」场景，仅在
  `ongoing_type == range` 且 `current_structure_status == ongoing_same_type`（单一中枢、语义清晰的
  中枢震荡）时给点；`candidate_completed_waiting_stability`（前段完成、新类型候选未确认）
  等过渡 / 待定态下最近中枢语义不清，只作观察，不发机械类一类点（§2.7）。注：range 走势
  在同级别分解里恒为 `single_active_zhongshu`（即 `dual_interpretation_pending`），故此处以
  `ongoing_same_type` 单中枢作为「盘整背驰」确认闸门，而非类二类点的 `single_confirmed`
  （后者为趋势 regime，至少两同向不重叠中枢）。

与标准一 / 二 / 三类点、类二类点去重（应然）：

- 与标准一类点互斥：同一离开段上标准一买 / 一卖已成立（趋势背驰）时，不再重复标记类一买 /
  类一卖（盘整背驰是趋势门控缺席时的放宽版本，趋势背驰为更强确认）。因 range 门控与 down/up
  门控互斥，二者不会命中同一 `ongoing_type`，去重主要防御未来门控放宽。
- 与类二类点（LB2 / LS2）区分：类二类点是「隔段 A_i vs A_{i+2}」盘整背驰、不要求破前低 /
  前高、不设 range 门控；类一类点要求 range 门控 + 「离开段 vs 进入段」创新低 / 新高的盘整背驰
  转折点。两者处于互斥 regime：类一类点在单中枢盘整（`ongoing_same_type` range），类二类点在
  趋势分解已确认（`single_confirmed`），不会同时命中；同一转折若标准一 / 二类点或类二类点
  已成立，则不重复标记类一类点。

### 2.6 类二类买卖点（LB2 / LS2）

类二类买卖点是「同级别分解」机械操作下的第二类机会（第一类是第三类买卖点）。它与
标准二类点同属「转折后首次确认性回抽 / 反抽」，但不要求前置一个标准第一类买卖点，
而是直接由同级别隔段背驰给出。因此在标准一类点因趋势门控（`ongoing_type`）而缺席时，
类二类点仍能捕获操作机会。

- 类二买（LB2）：同级别相邻两段同向下跌段 A_i 与 A_{i+2}（中间隔一段向上段 A_{i+1}）
  出现隔段背驰——A_{i+2} 段级力度弱于 A_i（不要求 A_{i+2} 破前低）；当 A_{i+2}
  （即当下回踩段）结束、出现向上反向转折时（可为未确认尾笔），直接在 A_{i+2} 低点生成类二买。
- 类二卖（LS2）：同级别相邻两段同向上涨段 A_i 与 A_{i+2}（中间隔一段向下段 A_{i+1}）
  出现隔段背驰——A_{i+2} 段级力度弱于 A_i（不要求 A_{i+2} 破前高）；当 A_{i+2}
  （即当下反抽段）结束、出现向下反向转折时（可为未确认尾笔），直接在 A_{i+2} 高点生成类二卖。

与标准二类点的关键差异（应然）：

- 无前置一类点：不要求先有标准一买 / 一卖，只要求同级别隔段背驰（A_i vs A_{i+2}）。
- 不设「破前低 / 前高」约束：隔段背驰只比较 A_i 与 A_{i+2} 的段级力度衰减，A_{i+2}
  是否创新低 / 新高一律不作要求（这正是类二类点相对标准一 / 二 / 三类点能多捕获机会之处）。
- 不设「再度走强 / 走弱（创新高 / 新低）」二次确认：回踩 / 反抽结束（出现反向转折笔）
  即刻生成，不等待其后重新突破。
- 隔段背驰须为同级别线段口径：A_{i+2} 取最后一个已确认线段（当下回踩 / 反抽段），
  全链相邻回取 A_{i+1}（反向段）与 A_i（同向段）；力度以线段级 MACD 面积衰减为准。
- 依附最近中枢：与其它买卖点一致，类二类点须能回答「属于哪个最近中枢」。
- 同级别分解须已确认：仅在 `same_level_decomposition_mode == single_confirmed` 时给点；
  `dual_interpretation_pending`（单一 / 无确认中枢、候选待定、震荡待方向）下最近中枢语义
  不清，只作观察，不发机械类二类点（§2.7）。
- 与标准二类点去重：同一转折上若标准二买 / 二卖已成立，则不再重复标记类二买 / 类二卖
  （标准点为更强确认，类二点为其放宽版本）。

### 2.7 关系约束

- 第二类点与第三类点可能在特定结构下重合。
- 若最近中枢语义不清，买卖点不能给严格确认，只能给观察提示。
- 类中枢路径不得单独提升为严格确认买卖点。

### 2.8 信号生命周期与实时预备态

> 覆盖标准一 / 二 / 三类点与类一 / 类二类点。设计与失效条件落地细节见
> [signal-realtime-lifecycle-design.md](signal-realtime-lifecycle-design.md)，任务见
> [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md) RS0-RS5。

每个买卖点具备生命周期状态 `forming（预备 / 观察）→ confirmed（确认）→ invalidated（失效）`。

#### 2.8.1 以锚点段（`anchor_segment`）统一 forming / confirmed（应然）

所有买卖点——同级别分解机械操作常用的类二 / 类三（LB2 / LS2、三买 / 三卖），一般的一 / 二类
（一买 / 一卖、二买 / 二卖），以及盘整背驰的类一（LB1 / LS1）——的 `forming` 与 `confirmed`
除各自的**基本条件**（共同条件：背驰 / 离开 / 隔段力度衰减 + 中枢绑定，见下表）外，均以**锚点段
`anchor_segment`**（定义该点的离开 / 回踩 / 反抽线段）统一刻画，口径对称、跨帧单调（不 repaint）：

- `forming`（预备 / 观察）：`anchor_segment` 的**尾笔**（`anchor_segment.tail_bi`）已确认。
  仍只作 watch 档观察态，不得升为 confirmed，也不得被下游二次摘要成确认买卖点。
  - `forming_at` / `detected_at` = `anchor_segment.tail_bi.confirmed_at`（锚点段尾笔的确认时刻）。
- `confirmed`（确认）：`anchor_segment` 整体已确认（反向线段确认），是可操作确认态
  （仍受多级别降级约束，且须满足 §3.3 repaint 红线：只锚定已确认笔 / 线段）。
  - `confirmed_at` = `anchor_segment.confirmed_at`（锚点段的确认时刻）。
- **类一（盘整背驰）例外**：`confirmed` 条件放松为 `anchor_segment.tail_bi 已确认` **且** `回中枢
  （back_to_center，价格重回中枢区间 [ZD, ZG]，定义见 §2.8.2）`。
  - `confirmed_at` = `max(back_to_center_at, anchor_segment.tail_bi.confirmed_at)`。
- `invalidated`（失效）：`forming` 或 `confirmed` 之后其成立前提被后续走势破坏。保留原信号锚点、
  `invalidated_at` / `invalidated_price` 与 `invalidated_reason`，供撤单 / 失效提示消费，不再作可操作
  确认态。逐点类型的**失效条件 / `invalidated_at` 公式 / reason 枚举值**见 §2.8.1 生命周期表后三列、
  §2.8.4 六字段口径，以及
  [signal-realtime-lifecycle-design.md](signal-realtime-lifecycle-design.md) §3.2 / §3.2.1。

统一生命周期表（`anchor_segment` 为各行「基本条件」列标注的锚点段；`forming` / `confirmed` 公式
除类一外同构）。表后三列为**失效三要素**：触发条件、`invalidated_at` 公式与 `invalidated_reason` 枚举值
（枚举定义见 `src/chanlun/analysis_contract.py::SignalInvalidatedReason`）：

| 买卖点类型 | 预期收益简介 | 基本条件（forming / confirmed 共同，含锚点段 `anchor_segment`） | forming 条件 | `forming_at` / `detected_at` 公式 | confirmed 条件 | `confirmed_at` 公式 | invalidated 条件 | `invalidated_at` 公式 | `invalidated_reason` 枚举值 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一买 / 一卖 | 趋势背驰转折起点，博反转第一波；空间最大、风险最高 | 同级别趋势（down→一买 / up→一卖）+ 绑定最近标准中枢 + **离开段**（=`anchor_segment`）对同向进入段趋势背驰（创进入段前低 / 前高 + 段级力度衰减）+ 离开段破中枢下 / 上沿 | `anchor_segment.tail_bi` 已确认 | `anchor_segment.tail_bi.confirmed_at` | `anchor_segment` 已确认 | `anchor_segment.confirmed_at` | 离开段极值被后续有效跌破 / 升破（一买 `low < anchor_segment.low`；一卖 `high > anchor_segment.high`） | 失效判据**首次成立**的那根 K 线 `ts`（判定帧内自上一帧末 bar 起逐根回扫；实现暂取判定帧末 bar，见 §2.8.4） | `first_class_extreme_broken` |
| 二买 / 二卖 | 一类点后首次确认性回抽 / 反抽；风险低于一类、空间仍大 | 绑定一买 / 一卖前置 + 首次回抽 / 反抽不破前低 / 前高 + 再度走强 / 走弱；**回抽 / 反抽段**（=`anchor_segment`） | `anchor_segment.tail_bi` 已确认 | `anchor_segment.tail_bi.confirmed_at` | `anchor_segment` 已确认 | `anchor_segment.confirmed_at` | 首次确认性回抽失败：回抽破前低 / 反抽破前高（二买 `latest_down.low < payload.price`；二卖 `latest_up.high > payload.price`） | 同上 | `second_class_pullback_failed` |
| 三买 / 三卖（同级别分解机械第一类机会） | 离开中枢后首次不回归、趋势延续；确定性高、空间中等 | 向上 / 向下离开中枢 + 首次回试 / 反抽不重新跌回 / 站回中枢沿 + 回试后重新走强 / 走弱；**回试 / 反抽段**（=`anchor_segment`） | `anchor_segment.tail_bi` 已确认 | `anchor_segment.tail_bi.confirmed_at` | `anchor_segment` 已确认 | `anchor_segment.confirmed_at` | 回试 / 反抽重新回到**该点自己所属中枢**（买三 `latest_down.low < related_zs_high`；卖三 `latest_up.high > related_zs_low`；边沿取点确认时固化的 `related_zs_low/high`） | 同上 | `third_class_reentered_zs` |
| 类一买 / 类一卖（LB1 / LS1，盘整背驰） | 盘整背驰转折；震荡区间转折机会，空间≈中枢震荡幅度 | 最近中枢 `ongoing_type == range` 且 `ongoing_same_type`（单中枢盘整）+ **离开段**（=`anchor_segment`）对同向进入段盘整背驰（破中枢沿 + 创进入段前低 / 前高 + 段级力度衰减） | `anchor_segment.tail_bi` 已确认 | `anchor_segment.tail_bi.confirmed_at` | `anchor_segment.tail_bi` 已确认 **且** 回中枢（`back_to_center`，价格重回 `[ZD, ZG]` 中枢区间，定义见 §2.8.2）〔放松〕 | `max(back_to_center_at, anchor_segment.tail_bi.confirmed_at)` | 盘整背驰前提消失（离开段 vs 进入段力度关系反转）或 range 门控退出（锚点门控 `buy1like_anchor` / `sell1like_anchor` 变 `None`） | 同上 | `consolidation_divergence_lost` |
| 类二买 / 类二卖（LB2 / LS2，同级别分解机械第二类机会） | 同级别隔段背驰的回踩 / 反抽确认；类似二类的机械补点，空间中等 | `same_level_decomposition_mode == single_confirmed` + 同级别隔段背驰（A_i vs A_{i+2} 段级力度衰减，不要求破前低 / 前高）+ **A_{i+2}（当下回踩 / 反抽段）**（=`anchor_segment`） | `anchor_segment.tail_bi` 已确认 | `anchor_segment.tail_bi.confirmed_at` | `anchor_segment` 已确认 | `anchor_segment.confirmed_at` | 隔段背驰前提消失（A_{i+2} 力度不再弱于 A_i；锚点门控 `buy2like_anchor` / `sell2like_anchor` 变 `None`）或同级别分解退出 `single_confirmed` | 同上 | `gap_divergence_lost` |

> **实现状态（2026-11-14）**：上表 `forming` / `confirmed` 公式为应然口径（统一 `anchor_segment`
> 的精确实现可后置）；**失效三列已确定并落地为代码判据**——逐点 reason 由
> `analysis._SIGNAL_INVALIDATION_REASON_BY_POINT` 静态映射，触发前提由
> `_signal_premise_broken`（价格）与 `_structural_premise_broken`（结构）判定。
> 类一的「盘整背驰前提消失」尚无结构判据（`_STRUCTURAL_GATE_BY_POINT` 未覆盖），当前只能由价格
> 近似触发，属已知缺口。
>
> **后续任务（可执行胜率）**：`forming` 事件与后续归宿已由 §2.8.5 + §2.8.4 六字段承载，
> 并落 CloudBase 文档数据库历史（design §6.2），据此统计从 `forming` 起算的**真实可执行胜率**
> （而非仅以 `confirmed` 回看），作为盘中更早入场档位的收益评估依据。

#### 2.8.2 类一「回中枢（`back_to_center`）」定义（应然）

类一（盘整背驰 LB1 / LS1）的 `confirmed` 比一 / 二 / 三类、类二多出一个「回中枢」放松条件。
其理论依据是第24课盘整背驰两种情形：**离开段破中枢但力度弱**时，价格**先出后回跌、重新回到
中枢区间**（而非「不回中枢」转第三类点）；盘整背驰构成的「类第一类点」正是这条「破沿即回」的
弱势离开反转。故类一不像标准一类点那样等反向线段整体走完才确认，而是以「尾笔确认 + 价格重新
回到中枢区间」作为盘整背驰成立的确认信号。

**中枢边沿口径**：沿用全文 ZG / ZD 约定——`ZG = related_zs_high`（中枢上沿）、
`ZD = related_zs_low`（中枢下沿）。两边沿在中枢前三笔重叠区固定后即固化到该点上
（`payload.related_zs_low` / `related_zs_high`，见 §RS0 增量7 / design §4.2.10），
跨帧稳定比较，不随尾部重切换人。

**定义（买卖对称）**：设 `anchor_segment` 为破沿的弱势离开段，反向转折后的回抽 / 反抽价格
重新进入中枢区间 `[ZD, ZG]` 即为「回中枢」：

- 类一买（LB1）：离开段向下跌破 `ZD`（创进入段前低但力度弱）；反向向上转折后，后续向上
  笔 / 段的**最高价 `high ≥ ZD`**（价格重新站回中枢下沿之上、回到中枢区间）→ `back_to_center` 成立。
- 类一卖（LS1）：离开段向上升破 `ZG`（创进入段前高但力度弱）；反向向下转折后，后续向下
  笔 / 段的**最低价 `low ≤ ZG`**（价格重新跌回中枢上沿之下、回到中枢区间）→ `back_to_center` 成立。

**`back_to_center_at`**：首次满足上述「价格重新进入中枢区间」条件的那根 K 线时间
（类一买取 `high` 首次 `≥ ZD` 的 bar；类一卖取 `low` 首次 `≤ ZG` 的 bar）。据此
`confirmed_at = max(back_to_center_at, anchor_segment.tail_bi.confirmed_at)`——两条件谁后满足以谁为准。

> 与三类点「不回中枢」互斥：类一要求离开后**回中枢**（弱势盘整背驰反转）；三买 / 三卖要求离开后
> 首次回试 / 反抽**不回中枢**（强势离开不回归）。同一离开段二者不会同时成立。

#### 2.8.3 上游重绘时 `forming` 事件的处理（2026-11-14 定稿）

`confirmed` 已有跨帧 repaint 护栏（只锚定已确认笔 / 线段、单调不翻转、消失须给证据，见 §3.3 红线与
[signal-realtime-lifecycle-design.md](signal-realtime-lifecycle-design.md) §3.4 `replay_confirmed_signal_lifecycle`）。
但 `forming` 锚在**进行中 / 未确认笔**上，上游（笔 / 线段 / 中枢）在后续帧**重绘（repaint）**时，
`forming` 的锚点、`anchor_segment` 乃至 `related_zs` 都可能移动或消失，故其跨帧口径与 `confirmed`
**不同**：

- `forming` 定位是 watch 档观察态、本就允许随上游重绘漂移，**不纳入** `confirmed` 的「禁止消失 /
  翻转」红线；但必须可审计地归入**四类跨帧归宿**：

  | 归宿 | 判定 | 记录 | 是否计入失效 |
  | --- | --- | --- | --- |
  | 顺延（`forming_reanchored`） | 同 `point` 仍有 forming，但 `signal_bi_id` 已换 | 只记审计事件，不产出 `invalidated` | 否 |
  | 兑现（`forming_confirmed`） | 同 `point` 在当前帧已 `confirmed`（锚点可换，属兑现 / 更替） | 正常升 confirmed，不产出 `invalidated` | 否 |
  | 失效（`forming_invalidated`） | 同锚点消失，**且**价格 / 结构前提已破坏（判据同 §2.8.5） | 产出 `lifecycle_state=invalidated` + `invalidated_reason` + `from_state=forming` | 是 |
  | 自然终止（`forming_dropped`） | 同锚点消失，但前提未破坏（纯重绘抹掉） | 只记审计事件，不产出 `invalidated` | 否 |

- `forming_at` / `forming_price` / `detected_at` 对同一 `point|time` 跨轮取**最早**值（沿用既有「尾部分型
  过滤导致后续帧轻微前移时不顶走首次检出」口径，见 design §4 检出时间修正），避免重绘把早期预警时刻顶走。
- 「记录所有 `forming` 事件算真实可执行胜率」（§2.8.1 后续任务）依赖此口径：重绘导致的 `forming`
  漂移 / 消失必须能与「真实兑现 / 失效」区分，否则胜率统计会被重绘噪声污染。

> **`forming` 缺位置条件（待完善）**：当前 `forming` 仅以「`anchor_segment.tail_bi` 已确认 + 基本
> 条件（背驰 / 离开 / 隔段力度衰减）」触发，**尚未加入价格位置约束**（例如离开段是否已真正破中枢沿 /
> 创前低前高到位、回踩 / 反抽是否落在合理价位带）。先记录此缺口，后续再完善 `forming` 的位置门控，
> 以减少重绘期的假预备。

Repaint 红线：

- `confirmed` 只能锚定已确认笔 / 线段；未确认笔只能承载 `forming`。
- 同一信号锚点（`signal_bi_id`）的 `confirmed` 在后续帧只能保持或转 `invalidated`，禁止凭空消失或
  方向翻转。

各点类型的 `confirmed → invalidated` 失效条件（买卖两侧对称；**触发前提**与 **reason 枚举值**、
`invalidated_at` 公式已对齐 §2.8.1 生命周期表后三列）：

- 一买 / 一卖：离开段极值被后续有效跌破 / 升破（背驰构成的转折被否定）→ `first_class_extreme_broken`。
- 二买 / 二卖：回抽 / 反抽破前低 / 前高（首次确认性回抽失败）→ `second_class_pullback_failed`。
- 三买 / 三卖：首次回试 / 反抽重新跌回 / 站回中枢（离开中枢的「不回归」前提被破坏）→
  `third_class_reentered_zs`；中枢边沿取**该点自己**的 `related_zs_low` / `related_zs_high`。
- 类一买 / 类一卖（LB1 / LS1）：盘整背驰前提消失（离开段 vs 进入段力度关系反转）或 range 门控退出 →
  `consolidation_divergence_lost`。
- 类二买 / 类二卖（LB2 / LS2）：隔段背驰前提消失（A_{i+2} 力度不再弱于 A_i）或同级别分解退出
  `single_confirmed` → `gap_divergence_lost`。

#### 2.8.4 信号记录的时间与价格六字段（2026-11-14 新增）

每个买卖点信号记录除既有 `time`（锚点笔尾）/ `price`（锚点极值）外，另带**三组「事件时间 + 事件
K 线收盘价」**字段，统一口径为「**事件发生那根 K 线的收盘价**」（非锚点极值，非跑批时刻）：

| 字段 | 含义 | 取值公式 | 跨轮保留 |
| --- | --- | --- | --- |
| `forming_at` | 预备条件成立（结构检出）时刻 | `anchor_bi.confirmed_ts`（= 现行 `detected_at`，同一时刻的显式别名） | 取**最早** |
| `forming_price` | `forming_at` 那根 K 线的收盘价 | `close(bar @ forming_at)` | 随 `forming_at` |
| `confirmed_at` | 首次进入 `confirmed` 的结构时刻 | 现行口径：`anchor_segment.confirmed_at` / 类二 `as_of` / 反向转折笔 `end_ts` | 取**最早** |
| `confirmed_price` | `confirmed_at` 那根 K 线的收盘价 | `close(bar @ confirmed_at)` | 随 `confirmed_at` |
| `invalidated_at` | 失效判据**首次成立**的 K 线时间 | 判定帧内自上一帧末 bar 之后逐根回扫，首次命中即取该 bar `ts`；无可回扫窗口时取判定帧末 bar | 终态保留 |
| `invalidated_price` | `invalidated_at` 那根 K 线的收盘价 | `close(bar @ invalidated_at)` | 终态保留 |

口径约定：

- **K 线时间 → 收盘价解析**：优先精确匹配 `bar.ts == 事件时刻`；否则取 `bar.ts ≤ 事件时刻` 的最后一根；
  窗口内无更早 bar 时取第一根；仍无法解析则为 `null`（fail closed，**不得**用锚点极值或当前价冒充）。
- **不变量**：`confirmed_at ≥ forming_at`；`invalidated_at ≥ confirmed_at`（`forming → invalidated` 直转时
  `invalidated_at ≥ forming_at`，`confirmed_at` 为空）。
- **倒挂夹紧（2026-11-14）**：`confirmed_at` 与 `forming_at` 取自**不同结构层**，二者无天然单调关系——
  三类点的 `forming_at` 取锚点笔 `confirmed_ts`（笔级确认可能被后续更极值的反向分型推迟），
  `confirmed_at` 取锚点段的破坏笔确认（段级确认可能**早于**其末端笔的笔级确认）。点只有在
  「锚点笔已确认 + 锚段已确认」同时成立时才可能发射，故**点级**确认不得早于点级检出：
  倒挂时把 `confirmed_at` 夹紧到 `forming_at`，并按同一根事件 K 线重算 `confirmed_price`。
  实测（13 个冻结真实 fixture / 19 个 confirmed 点）修前 5 个倒挂（全为 `sell3`，最大倒挂约 1 天），修后 0。`
- **forming 行**：`confirmed_at` / `confirmed_price` / `invalidated_*` 均为空（尚未发生）。
- **confirmed 行**：`invalidated_*` 为空。
- **invalidated 行**：`forming_at` / `forming_price` / `confirmed_at` / `confirmed_price` 保留历史值。
- `lifecycle_state` 为**当前态**；三组字段是**迁移历史**，同一 `point` 被更晚信号更替（`superseded`）时
  旧记录不得篡改，新记录重新计时。

#### 2.8.5 `forming → invalidated` 转移（2026-11-14 新增）

`forming` 不是只能顺延或兑现：**其成立前提被破坏时，同样转 `invalidated`**（否则早期预警的误报
无法被度量，也无法统计真实可执行胜率）。判定口径：

- **前提判据与 `confirmed → invalidated` 同源**（复用 `_signal_premise_broken` / `_structural_premise_broken`，
  仅把锚点价格换成 forming 载荷自己的 `price`）：
  - 价格：一 / 二 / 类一 / 类二——买点 `latest_down.low < forming.price`、卖点 `latest_up.high > forming.price`；
    三类——买三 `latest_down.low < related_zs_high`、卖三 `latest_up.high > related_zs_low`。
  - 结构：类二锚点门控 / 三类 hold 段消失（同 §2.8.1）。
- **reason 与 `invalidated_premise`**：reason 沿用该点类型枚举（见 §2.8.1），`invalidated_premise` 取
  `price` / `structure`，并额外携带 `from_state = forming`。
- **不与 repaint 红线冲突**：`forming` 失效不算 repaint 违规；但同一 `point` + 同一锚点一旦
  `forming → invalidated`，其后**不得**再回到 forming / confirmed（否则记 `reconfirm_after_invalidated`）；
  同 `point` 换新锚点重新形成不受限（属「顺延 / 新信号」）。
- **阈值缺口（已知）**：当前不设 forming 有效期 TTL。若后续要加，必须新增独立 reason
  （如 `forming_expired`）以区分「前提被破坏」与「超时未兑现」，不得复用上面五个枚举值。

## 3. 区间套

区间套的作用是：

- 高一级给方向和结构位置。
- 当前操作级别给买卖点与风险边界。
- 更低一级给执行节奏、确认窗口和进退精度。

红线：

- 低级别买点不能单独推翻高级别未完成结构。
- 低级别只能提高时机精度，不能直接改写高级别主方向。

## 4. 小转大

小转大应理解为：

- 次级别结构先完成转折。
- 该转折随后被更高级别结构吸收、确认，演化为高级别转向的一部分。

它不是“低级别一有信号，高级别必转”。

严格要求：

- 必须明确低级别转折发生在哪里。
- 必须明确高级别确认依赖哪个结构闭环。
- 若高级别尚未确认，只能表述为“可能的小转大候选”。

两种转折方式（第43课“有关背驰的补习课”）：

- 背驰级别 = 当下走势级别：转折必然至少拉回该走势最后一个中枢（跌破/升破对应极值）。
- 背驰级别 < 当下走势级别：转折须先形成更大级别中枢，不必然直接回到原中枢；须以最后次级别中枢出现第三类买卖点为必要条件。

必要条件（第44课“小级别背驰引发大级别转折”）：

- 小级别顶背驰引发大级别向下的必要条件是：该级别走势的最后一个次级别中枢出现第三类卖点。
- 小级别底背驰引发大级别向上的必要条件是：该级别走势的最后一个次级别中枢出现第三类买点。
- 该条件只是必要、不是充分：出现对应第三类买卖点并不必然导致大级别转折。
- 在对应第三类买卖点未出现之前，不得把小级别背驰升级为“大级别转折已启动”。

## 5. 多级别联立

多级别联立的推荐分工：

- 高级别：方向、结构位置、是否临近关键中枢或关键背驰。
- 操作级别：一二三类买卖点、风险位、观察位。
- 执行级别：区间套确认、入场节奏、再确认窗口。

买卖点级别定理（第35课）：

- 大级别的买卖点，必然是次级别以下某一级别的买卖点（不一定是次级别）。
- 反向推论：低级别买卖点出现，不代表高级别买卖点成立；只有低级别转折被高级别结构吸收确认，才升级为高级别买卖点。

动态分级（第86课“杜绝一根筋”）：

- 同一买卖点的操作意义随大级别位置而不同：大级别中枢上移中的小级别卖点只是警戒，大级别中枢下移中的小级别卖点基本无操作价值，大级别中枢震荡中的小级别买卖点只构成震荡机会。
- 禁止用一个固定公式对同一买卖点给出恒等结论；必须结合当下大级别结构动态判级。

## 6. 实然指引（不承担规格职责）

> 本文件只定义“应然”。当前工程实现状态（已落地部分与未闭环缺口）见
> [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)。

历史实然摘要（保留作背景，不再更新）：

- 曾有部分 buy/sell 工程规则。
- 曾有部分低级别精确执行字段。
- 严格“最近中枢 -> 背驰 -> 1/2/3 类点 -> 多级别确认/降级”主链路曾未完全闭环。

## 7. 维护建议

- 若要改一二三类买卖点定义，优先改本文件。
- 若要改多级别联立或区间套定义，也优先改本文件。
- 若只是补充当前代码差异，转写到任务清单或实现差异文档，不要把工程临时判断塞进严格定义段落。

## 8. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [buy-sell-multi-level-original-review-matrix.md](buy-sell-multi-level-original-review-matrix.md)
- [buy-sell-multi-level-visual-example-library.md](buy-sell-multi-level-visual-example-library.md)
- [trend-divergence-spec.md](trend-divergence-spec.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md)
