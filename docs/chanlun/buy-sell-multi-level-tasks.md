# 买卖点与多级别联立任务拆解

本页统一承接“一二三类买卖点严格确认”“多级别联立 review 模板”“买卖点差异表”和相关消费收口任务。

## 关联总表条目

- 一类买卖点严格确认
- 二类买卖点严格确认
- 三类买卖点严格确认
- `src/chanlun/analysis.py` 买卖点逻辑差异表
- 一二三类买卖点标准案例包
- 多级别联立 review 模板
- confirmed / pending / auxiliary 三态统一（买卖点部分）

## 当前 epic 看板

| ID | 任务 | 状态 | 依赖 | 完成定义 |
| --- | --- | --- | --- | --- |
| BS1 | 当前实现 vs 严格理论差异表 | 完成 | `analysis.py` 现状梳理 | 每条 buy / sell 规则都能标出“严格一致 / 工程近似 / 待实现” |
| BS2 | 一类买卖点严格确认 | 完成 | `zhongshu`, `trend-divergence` 稳定 | 最近中枢、离开段、背驰绑定关系明确且可自动判定 |
| BS3 | 二类买卖点严格确认 | 完成 | BS2 | 能严格绑定 1 类点后的首次确认性回抽 |
| BS4 | 三类买卖点严格确认 | 完成 | BS2 | 能严格绑定最近中枢后的首次回抽与级别边界 |
| BS5 | 多级别联立与消费降级规则 | 进行中 | BS2-BS4 | 高一级方向、操作级别、执行级别和 pending / auxiliary 降级文案一致 |
| BS6 | 标准案例包与回归闸门 | 进行中 | BS1-BS5 | 一二三类点与区间套样例可 review、可回归、可下游消费 |
| BS7 | 类二类买卖点（LB2 / LS2）严格确认 | 完成 | BS4（段级背驰口径稳定） | 同级别隔段背驰（A_i vs A_{i+2}）+ 回踩/反抽结束即生成，无前置一类点、不设破前低/前高 |
| BS8 | 类一类买卖点（LB1 / LS1）严格确认 | 完成 | BS2（一类点段级背驰口径稳定） | 盘整背驰（单中枢 range + ongoing_same_type）+ 离开段 vs 进入段创新低/高 + 力度衰减 + 反向转折即生成，标准一类点趋势门控缺席时补点 |

## 按任务类型看板

阅读方式：

- 文档任务：买卖点差异表、案例包、多级别 review 模板、消费降级规范。
- 测试任务：一二三类点回归、区间套样例回归、多级别降级核验。
- 代码任务：严格一二三类点确认、多级别联立规则、买卖点相关消费输出。
- 优先级：`高` 表示当前买卖点主线直接依赖；`中` 表示并行推进项；`低` 表示保留但不抢当前前置链路。

当前重点：

1. 文档 / 代码前置：当前实现 vs 严格理论差异表已补齐（BS1 完成），下一步按一类点 -> 二类点 -> 三类点顺序替换工程近似。
2. 测试：继续锁多级别联立与降级核验，避免高一级未确认却越级显示强确认。
3. 代码：在上游中枢和背驰更稳定后，再按一类点 -> 二类点 -> 三类点顺序收口。

### 文档任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| D1 | 当前实现 vs 严格理论差异表 | 高 | 逐条把 `buy_1/2/3`、`sell_1/2/3` 的现状与目标拆开 | 完成 | 差异表已落在 BS1 节，逐条绑定 `analysis.py::analyze_chanlun_signals` 行号，六条规则均标为「工程近似」并写出已严格绑定项与主要缺口。 |
| D2 | 标准案例包与 review 模板 | 中 | 补一二三类点正反例、区间套、小转大与多级别共振样例 | 进行中 | 已有骨架；当前已补前端可见级别的区间套/小转大卡片（真实 `600900 1m confirmed 3S`、真实 `002555 1m -> 5m` 候选观察链、`5m buy3 -> third_class_confirmed` 对照卡），但整体仍不足以让 reviewer 快速判断每类点的严格程度。 |
| D3 | 消费降级规范 | 中 | 统一 pending / auxiliary / confirmed 的文案分层 | 进行中 | 需要跟中枢、背驰两条上游链一起收口。 |

### 测试任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| T1 | 一二三类点回归闸门 | 中 | 为每类点建立正例、反例、易混淆例最小回归集 | 进行中 | 已有 buy_2/sell_2 正例；`2026-08-23` 补齐一买/一卖/三买/三卖正例、一买「仅触边不背驰」反例、三买「回抽回中枢」反例、二买「中继震荡破前低」易混淆例（`tests/test_chanlun_analysis.py`，共 7 个新用例，spec_id SPEC.BUY_SELL.CORE）。 |
| T2 | 多级别联立与降级核验 | 高 | 锁高一级未确认时下游不得越级显示强确认 | 进行中 | 这是消费层最容易误报强信号的区域。 |
| T3 | 区间套 / 小转大样例回归 | 中 | 给重点 review 样例绑定自动化锚点 | 进行中 | 依赖 BS2-BS5 的主实现逐步稳定。 |

### 代码任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| C1 | BS1 差异表对应到实现入口 | 高 | 把 `analysis.py` 中各类买卖点规则逐条映射出来 | 完成 | 六条 buy/sell 规则已逐条映射到 `analyze_chanlun_signals` 行号（L882-925），差异分类可溯源。 |
| C3 | BS5 多级别联立与消费降级 | 高 | 统一高一级方向、操作级别、执行级别与降级文案 | 进行中 | 这是当前消费层主要的实现收口点。 |
| C2 | BS2-BS4 一二三类点严格确认 | 中 | 先一类点，再二类点，再三类点逐级收口 | 进行中 | BS1 差异表已闭合，BS2 严格确认链（应然）已写入并钉住两个契约缺口（双边不对称、无转折确认），下一步做双边对称与转折确认代码收口。 |

## 任务拆分

<a id="bs1-diff-map"></a>
### BS1 当前实现 vs 严格理论差异表

所有规则入口都在 `src/chanlun/analysis.py::analyze_chanlun_signals`。差异三档口径：

- 严格一致：判定条件与 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) 的应然语义逐条对齐。
- 工程近似：绑定方向正确，但力度 / 首次回试 / 转折确认口径仍是工程近似。
- 待实现：理论要求尚未进入判定链。

| 规则 | 实现入口（analysis.py） | 当前判定条件（工程口径） | 已严格绑定 | 主要工程近似 / 缺口 | 分类 |
| --- | --- | --- | --- | --- | --- |
| `buy_1` | `analyze_chanlun_signals` buy_1 段 | 线段级中枢：`segment_bottom_divergence`（离开段 vs 进入段创新低 + 力度衰减）+ 离开段末笔跌破下沿 + `_has_reverse_turn_after` 反向转折（信号锚点=离开段末笔 `_bi_by_id(exit_segment.end_bi_id)`）；笔级中枢回退 `bottom_divergence` | 最近中枢 + 离开段 + 段级背驰；力度、边界、转折均以离开段末笔为基准 | 笔级中枢（类中枢辅助链路）仍为 macd_sum_abs 衰减 | 严格一致 |
| `sell_1` | `analyze_chanlun_signals` sell_1 段 | 线段级中枢：`segment_top_divergence`（离开段 vs 进入段创新高 + 力度衰减）+ 离开段末笔越上沿 + `_has_reverse_turn_after` 反向转折（信号锚点=离开段末笔）；笔级中枢回退 `top_divergence` | 最近中枢 + 离开段 + 段级顶背驰；力度、边界、转折均以离开段末笔为基准 | 与 buy_1 对称：笔级中枢链路仍为 macd_sum_abs 衰减 | 严格一致 |
| `buy_2` | `analyze_chanlun_signals` buy_2 段 | 段级中枢：一买前置=`segment_bottom_divergence` + `latest_down.low > 离开段末笔.low`（不破前低）+ `_is_first_reverse_hold`（首次回抽锁定）+ `latest_up.bi_id > latest_down.bi_id` + `_renewed_beyond_previous`（再度走强须创新高）；笔级中枢回退笔级前置 | 绑定一买（段级）+ 不破前低（离开段末笔）+ 首次回抽锁定 + 再度走强（创新高） | 笔级中枢（类中枢辅助链路）仍为笔级口径 | 严格一致 |
| `buy_3` | `analyze_chanlun_signals` buy_3 段 | 段级中枢：向上离开段（核心起 high > zs_high）+ 紧随的向下回试段不破上沿（`_find_buy3_segment_leave_hold`，回试尚未成段时回退到笔级紧随回试笔）+ 回试后重新向上（存在其后向上笔）；信号锚点=首次回试低点；笔级中枢回退笔级离开+回试 | 离开中枢（向上）+ 首次回试不破上沿 + 回试后重新向上（不强制创新高，贴合第20课第三类买卖点定理） | 笔级中枢链路仍为笔级离开 | 严格一致 |
| `sell_2` | `analyze_chanlun_signals` sell_2 段 | 段级中枢：一卖前置=`segment_top_divergence` + `latest_up.high < 离开段末笔.high`（不破前高）+ `_is_first_reverse_hold`（首次反抽锁定）+ `latest_down.bi_id > latest_up.bi_id` + `_renewed_beyond_previous`（再度走弱须创新低）；笔级中枢回退笔级前置 | 绑定一卖（段级）+ 不破前高（离开段末笔）+ 首次反抽锁定 + 再度走弱（创新低） | 与 buy_2 对称：笔级中枢链路仍为笔级口径 | 严格一致 |
| `sell_3` | `analyze_chanlun_signals` sell_3 段 | 段级中枢：向下离开段（核心起 low < zs_low）+ 紧随的向上反抽段不破下沿（`_find_sell3_segment_leave_hold`，反抽尚未成段时回退到笔级紧随反抽笔）+ 反抽后重新向下（存在其后向下笔）；信号锚点=首次反抽高点；笔级中枢回退笔级离开+反抽 | 离开中枢（向下）+ 首次反抽不破下沿 + 反抽后重新向下（不强制创新低，贴合第20课第三类买卖点定理） | 与 buy_3 对称：笔级中枢链路仍为笔级离开 | 严格一致 |

口径汇总：

- 一二三类点的「最近中枢绑定」与「离开段 / 回抽方向」已严格对齐。
- 三类点（buy_3/sell_3）已绑定「离开 + 不回归 + 首次回试锁定 + 回试后重新向上 / 向下」，段级中枢链路上「离开」以向上 / 向下离开段为锚点，信号价格锚定在首次回试 / 反抽极值（不再强制创新高 / 新低，贴合第20课第三类买卖点定理）。
- 二类点（buy_2/sell_2）已绑定「一买 / 一卖前置 + 不破前低 / 前高 + 首次回抽锁定 + 再度走强 / 走弱（创新高 / 新低）」，段级中枢链路上「前置 + 不破前低/前高」以离开段末笔为锚点。
- 一类点（buy_1/sell_1）背驰三元组已绑定，线段级中枢链路上「离开段 vs 进入段」力度、边界、转折均已以离开段末笔为基准（`_bi_by_id(exit_segment.end_bi_id)`）。
- 工程近似集中在：笔级中枢（类中枢辅助链路）的力度衰减与笔级离开/回抽口径（辅助展示口径）。

验收：

- reviewer 能从差异表直接知道“当前哪里已严格、哪里只是近似”。
- 后续改买卖点逻辑时，能明确知道影响的是哪一类差异。

<a id="bs2-buy1"></a>
### BS2 一类买卖点严格确认

- 绑定最近标准中枢，而不是模糊使用辅助结构。
- 绑定离开段与背驰确认，明确何时只是预警、何时可确认。
- 为买点与卖点分别补对称样例，避免只实现单边。

严格确认链（应然，见 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) 2.2）：

1. 最近中枢绑定：`reference_zs_id` 必须指向最近标准中枢（非类中枢 / 辅助结构）。
2. 离开段确认：离开笔必须已确认（`is_confirmed=True`），且方向与中枢方向相反（向下离开 -> 一买，向上离开 -> 一卖）。
3. 背驰确认：离开段相对进入段力度衰减（严格力度比较口径，非 macd_sum_abs 近似）。
4. 转折确认：背驰后出现反向转折笔（一买需向上笔、一卖需向下笔）。
5. 证据字段：`departure_bi_id`、`reference_zs_id`、`divergence_decayed`、`turn_bi_id` 可回溯。

预警 vs 确认边界（当前实然）：

- `zs_monitor_alert=pre_breakout/pre_breakdown` 是预警层，不等价于 buy_1/sell_1 确认（已有 replay gate 锁定）。
- buy_1/sell_1 已要求「已确认离开笔 + `_has_reverse_turn_after` 反向转折确认」，未确认离开或无转折笔时不再触发一类点。
- 双边已对称：buy_1 用 `latest_down.is_confirmed`、sell_1 用 `latest_confirmed_up`（均已确认）。

待收口（按优先级）：

- 已全部落地：双边对称、转折确认、力度口径（线段级中枢按「离开段 vs 进入段」严格比较）均已收口。
  剩余为「中枢附近」笔级边界触碰口径与笔级中枢（类中枢辅助链路）的力度衰减，暂不作阻塞。

验收：

- 一类点结论可以回溯到“最近中枢 + 离开段 + 背驰”三元组。
- 消费端不会把辅助口径误显示成严格一类点。

<a id="bs3-buy2"></a>
### BS3 二类买卖点严格确认

- 明确二类点只能建立在已成立的一类点之后。
- 明确首次确认性回抽的窗口、失败条件和失效条件。
- 补“看起来像二类点但其实是中继震荡”的反例。

验收：

- 二类点不会脱离一类点单独出现。
- 回抽是否有效能用机器字段而不是人工二次解释。

<a id="bs4-buy3"></a>
### BS4 三类买卖点严格确认

- 严格绑定最近中枢、离开后首次回抽、级别边界。
- 明确与二类点的分界，避免把普通回抽统称成三类点。
- 补“最近中枢变化后，旧三类点结论是否失效”的规则。

验收：

- 三类点有稳定的最近中枢绑定，不会随上游轻微漂移频繁换锚。
- 买卖点与中枢消费展示能说明“当前是严格确认、待确认还是辅助监视”。

<a id="bs5-multi-level-consumer"></a>
### BS5 多级别联立与消费降级规则

- 补高一级方向、操作级别、执行级别的统一模板。
- 明确当上游结构仍 pending 时，买卖点如何降级成 watch / auxiliary。
- 统一报告、小程序、tech.json 中的多级别说明文案。

验收：

- 同一案例在 review 文档、导出 JSON、消费展示中的级别语义一致。
- 不再出现高一级未确认、下游却直接显示强确认信号的冲突。

当前进展：

- 执行级别（区间套）已绑定上级别同级别结构消费等级：`build_lower_timeframe_precision_entry` 读取上级别 `same_level_consumption_level`，当上级别为 `auxiliary`（类中枢辅助）或 `pending`（待确认）时，次级别买卖点状态从 `actionable` 降级为 `watch`，并在 note 中标注「不按严格区间套执行」，避免低级别买卖点越级显示强确认；同时新增 `higher_consumption_level` / `higher_consumption_level_label` 两个字段，把上级别消费等级暴露到区间套 payload。
- 回归：`tests/test_chanlun_analysis.py` 新增 `test_build_lower_timeframe_precision_entry_downgrades_auxiliary_higher_level` / `test_build_lower_timeframe_precision_entry_downgrades_pending_higher_level` / `test_build_lower_timeframe_precision_entry_keeps_actionable_when_higher_confirmed` 三用例，锁住 auxiliary / pending 降级与 confirmed 保持 actionable 的三档语义。
- 86课动态判级已落地：`build_lower_timeframe_precision_entry` 新增 `dynamic_grade` / `dynamic_grade_label` 字段，按上级别中枢漂移方向（`structure_state.current_ongoing.type` 的 up / down / range）对次级别买卖点分级——震荡=「震荡机会」、上移中的卖点 / 下移中的买点=「警戒」、上移中的买点 / 下移中的卖点=「无操作价值」。契约枚举 `PrecisionDynamicGrade` 落在 `analysis_contract.py`，回归见 `test_analysis_contract.py::test_precision_dynamic_grade_enum_is_stable_and_complete` 与 `test_chanlun_analysis.py::test_build_lower_timeframe_precision_entry_dynamic_grade`（六象限 parametrize）。
- 第44课小转大必要条件已显式落地：`build_lower_timeframe_precision_entry` 新增 `small_to_large_status` / `small_to_large_status_label` / `small_to_large_status_note`，仅区分「小转大候选」与「最后一个次级别中枢已出现对应三类买卖点、必要条件已具备」，避免把必要条件误写成高级别已确认；`build_precision_window_display` 同步透出「小转大」行。回归见 `test_analysis_contract.py::test_small_to_large_status_enum_is_stable_and_complete`、`test_build_lower_timeframe_precision_entry_marks_small_to_large_candidate_without_buy3_sell3`、`test_build_lower_timeframe_precision_entry_marks_small_to_large_necessary_condition_when_buy3_sell3_exists`、`test_build_precision_window_display_includes_small_to_large_status`。
- 消费展示已接入：`build_precision_window_display` 的 `lines` 增加「判级」与「小转大」行并透出 `dynamic_grade` / `dynamic_grade_label` / `small_to_large_status*`；A/H mixed report、HK compact 文案与 miniapp bundle 均已透出该状态。回归链已覆盖三层：分析层（`tests/test_chanlun_analysis.py`）、mixed report（`tests/test_generate_a_share_single_mixed_report.py` / `tests/test_generate_h_share_single_mixed_report.py`）以及 miniapp summary/detail（`tests/test_build_miniapp_publish_bundle.py`，含 `002555/03690/600900` 三个真实 replay 观察样本与全文件回绿）。

<a id="bs6-case-gates"></a>
### BS6 标准案例包与回归闸门

- 一二三类点分别补正例、反例、易混淆例。
- 区间套、小转大、多级别共振与降级都要有可复核样例。
- 每类重点结论至少绑定一个自动化 regression 锚点。

验收：

- [buy-sell-multi-level-visual-example-library.md](buy-sell-multi-level-visual-example-library.md) 中的重点样例可被自动化回归支撑。
- 新增买卖点规则前后，最小回归集能及时暴露行为变化。

<a id="bs7-like-second-point"></a>
### BS7 类二类买卖点（LB2 / LS2）严格确认

理论口径见 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) §2.6。这里落设计、任务与测试用例。

#### 设计（design）

判定入口：`src/chanlun/analysis.py::analyze_chanlun_signals`，在标准二 / 三类点之后追加类二类点块。

数据依赖：`segments`（同级别线段序列）、`macd_points`（段级力度）、`current_zs`（最近中枢，用于依附）。

信号码 / 契约：新增 `buy_2like`（类二买）、`sell_2like`（类二卖），落 `analysis_contract.py` 的
`SignalPoint` 与 `SignalBasis`（依据码 `gap_segment_divergence_pullback_end` /
`gap_segment_divergence_rebound_end`）。信号码保持单下划线以复用现有
`_format_signal_point_name` / `format_signal_point_label` 往返归一化。

核心算法（类二买 LB2，类二卖 LS2 对称）：

1. 取同级别线段序列，以最后一个已确认线段 `A_{i+2}`（当下回踩 / 反抽段）为锚，全链相邻
   回取 `A_{i+1}`（反向段）与 `A_i`（同向段），末三段须为 `A_i(下)-A_{i+1}(上)-A_{i+2}(下)`
   （LS2 对称）。用全链相邻而非「已确认线段序列末三段」，避免中间未确认段被过滤后破坏隔段相邻。
2. 隔段背驰：`A_{i+2}` 段级 MACD 面积力度弱于 `A_i`（`strength(A_i) > 0` 且
   `strength(A_{i+2}) < strength(A_i)`）。**不要求** `A_{i+2}` 破前低 / 前高（贴合
   「不需要破前低/前高」）。
3. 回踩结束：`A_{i+2}` 末笔（`_bi_by_id(A_{i+2}.end_bi_id, bis)`）后
   `_has_reverse_turn_after(anchor, ...)` 出现反向转折。
4. 门控：仅在 `same_level_decomposition_mode == single_confirmed` 时给点；`pending` 状态只观察。
5. 生成：信号锚点 = `A_{i+2}` 末笔（回踩 / 反抽极值），`related_zs_id = current_zs.zs_id`。

去重与门控：

- 若标准 `buy_2` 已在 `buy_points`，则不再追加 `buy_2like`（`sell` 侧对称）。
- 不设 `ongoing_type` 趋势门控（这正是类二类点相对标准一 / 二类点放宽、能多捕获机会之处）；
  但要求 `same_level_decomposition_mode == single_confirmed`（最近中枢语义已确认），
  `dual_interpretation_pending`（单/无确认中枢、震荡待方向）只观察不发点，保持与预警独立闸门一致。
- 不设「破前低 / 前高」与「再度走强 / 走弱创新高 / 新低」约束。

catalog 兼容：`buy_2like` / `sell_2like` 追加在固定 6 槽（buy_1..sell_3）之后（槽位 6 / 7），
保持既有按索引断言（catalog[1]=buy_2、catalog[4]=sell_2）稳定。

#### 任务（tasks）

| 类型 | 任务 | 状态 |
| --- | --- | --- |
| 文档 | 本节 + spec §2.6 理论口径 | 完成 |
| 代码 | `analysis_contract.py` 新增 `buy_2like` / `sell_2like` 枚举与 label / basis | 完成 |
| 代码 | `_find_lb2_gap_divergence` / `_find_ls2_gap_divergence` 辅助 + `analyze_chanlun_signals` 集成 | 完成 |
| 代码 | `build_signal_point_payloads` 透出类二类锚点与 catalog 槽位 | 完成 |
| 测试 | LB2 / LS2 正例 + 反例（无背驰 / 回踩未结束）+ 契约完整性 | 完成 |

#### 测试用例（test cases）

落 `tests/test_chanlun_analysis.py`（spec_id SPEC.BUY_SELL.CORE）：

- LB2 正例：`A_i(下)-A_{i+1}(上)-A_{i+2}(下)` 隔段背驰（`A_{i+2}` 创新低 + 力度衰减）+ 回踩末笔后
  出现向上转折 → `buy_2like ∈ buy_points`，catalog 槽位 basis=`gap_segment_divergence_pullback_end`。
- LB2 反例（无背驰）：`A_{i+2}` 力度不弱于 `A_i` → 不报 `buy_2like`。
- LB2 反例（回踩未结束）：`A_{i+2}` 末笔后无已确认向上转折笔 → 不报 `buy_2like`。
- LS2 正例：上跌上（`A_i(上)-A_{i+1}(下)-A_{i+2}(上)`）隔段顶背驰 + 反抽末笔后向下转折 →
  `sell_2like ∈ sell_points`。
- LS2 反例（无背驰）：`A_{i+2}` 力度不弱于 `A_i` → 不报 `sell_2like`。
- 契约完整性：`tests/test_analysis_contract.py` 的 `SignalPoint` / `SignalBasis` 完整集合更新。

验收：

- 在标准一类点因趋势门控缺席的结构里，类二类点仍能给出操作机会。
- 类二类点与标准二类点不重复标记；catalog 既有索引断言不被破坏。

<a id="bs8-like-first-point"></a>
### BS8 类一类买卖点（LB1 / LS1）严格确认

理论口径见 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) §2.5（第27 / 65 课“类第一类买点”）。
spec + design + tasks + testcases + code + 回归均已落地（`analysis_contract.py` / `analysis.py` /
`tests/test_chanlun_analysis.py` / `tests/test_analysis_contract.py`）。

#### 设计（design）

判定入口：`src/chanlun/analysis.py::analyze_chanlun_signals`，在标准一 / 二 / 三类点与类二类点块之后
追加类一类点块。

数据依赖（均已在 `analyze_chanlun_signals` 上游算好，无新增重算）：`segments`、`current_zs`、
`segment_bottom_divergence` / `segment_top_divergence`（「离开段 vs 进入段」段级背驰布尔量）、
`entering_segment` / `exit_segment`、`exit_end_bi`（离开段末笔）、`buy_signal_bi` / `sell_signal_bi`（段级
模式下已取为离开段末笔）、`ongoing_type`、`structure_state`。

信号码 / 契约：新增 `buy_1like`（类一买）、`sell_1like`（类一卖），落 `analysis_contract.py` 的
`SignalPoint` 与 `SignalBasis`（依据码 `consolidation_divergence_reverse_low` /
`consolidation_divergence_reverse_high`）。信号码保持单下划线以复用现有
`_format_signal_point_name` / `format_signal_point_label` 往返归一化（与 `buy_2like` 同口径）。

核心算法（类一买 LB1，类一卖 LS1 对称）：

1. 复用标准一买的「离开段 vs 进入段」段级背驰量：段级中枢下 `buy_divergence = segment_bottom_divergence`
   （`_has_segment_bottom_divergence`：离开段创新低 + 段级力度衰减），锤点 = 离开段末笔
   `buy_signal_bi`（= `exit_end_bi`），且 `buy_signal_bi.low <= current_zs.zs_low`（跌破下沿）。
2. 趋势门控改为 range：`ongoing_type == "range"`（中枢震荡 / 中枢扩张），而非标准一买的
   `== "down"`。这正是标准一买（`== "down"`）因趋势门控缺席的场景。
3. 反向转折：`_has_reverse_turn_after(buy_signal_bi, direction="down", bis)` 出现向上转折。
4. 门控：仅在单中枢中枢震荡（`ongoing_type == "range"` 且
   `structure_state["current_structure_status"] == "ongoing_same_type"`）时给点；
   `candidate_completed_waiting_stability` 等过渡态只观察。注：range 走势在同级别分解里
   恒为 `single_active_zhongshu`（即 `dual_interpretation_pending`），因此不能像 LB2/LS2 那样用
   `single_confirmed` 作门；改用 `ongoing_same_type` 单中枢作为「盘整背驰」确认闸门。
5. 生成：信号锤点 = 离开段末笔（离开段低点），`related_zs_id = current_zs.zs_id`。

（LS1 对称：`ongoing_type == "range"`、`sell_divergence = segment_top_divergence`、锤点 = `sell_signal_bi`
（离开段末笔）、`sell_signal_bi.high >= current_zs.zs_high`、`_has_reverse_turn_after(..., direction="up")`。）

笔级中枢回退：段级中枢缺失（`use_segment_divergence == False`）时回退笔级 `bottom_divergence` /
`top_divergence`（与标准一买笔级回退口径一致），锤点取 `latest_down` / `latest_confirmed_up`。

去重与门控：

- 与标准 `buy_1` 互斥：若 `buy_1` 已在 `buy_points` 则不追加 `buy_1like`（sell 侧对称）。因 `buy_1`
  门控是 `ongoing_type == down`、`buy_1like` 门控是 `== range`，两者不会同时命中同一 `ongoing_type`，
  去重主要防御未来门控放宽时重复。
- 与 `buy_2like`（LB2）区分：LB1 走「离开段 vs 进入段」 + range 门控；LB2 走「隔段 A_i vs
  A_{i+2}」。若同一离开段末笔已被 `buy_2like` 认领（`signal_bi_id` 相同），则不再重复标记 `buy_1like`。

catalog 兼容：`buy_1like` / `sell_1like` 追加在类二类槽位（槽 6=buy_2like、7=sell_2like）之后
（槽位 8=buy_1like、9=sell_1like），保持固定 6 槽（buy_1..sell_3）+ LB2/LS2（槽 6/7）的按索引断言稳定。

轠额外：`src/chanlun/analysis.py` 类二类块注释引用的 `spec §2.5/§2.6` 在 spec 重编号后指向 类一类/类二类（§2.5/§2.6），继续成立；另在 code 阶段可顺手把类一类块注释锤到 spec §2.5。

#### 任务（tasks）

| 类型 | 任务 | 状态 |
| --- | --- | --- |
| 文档 | 本节 + spec §2.5 理论口径 | 完成 |
| 文档 | 测试用例规格（本节 #### 测试用例） | 完成 |
| 代码 | `analysis_contract.py` 新增 `buy_1like` / `sell_1like` 枚举与 label / basis | 完成 |
| 代码 | `analyze_chanlun_signals` 集成 range 门控盘整背驰类一类点块（含去重） | 完成 |
| 代码 | `build_signal_point_payloads` 透出类一类锤点与 catalog 槽位（8/9） | 完成 |
| 测试 | LB1 / LS1 正例 + 反例（门控=down/up 归标准一类点 / 无背驰 / 无反向转折 / candidate）+ 契约完整性 | 完成 |

#### 测试用例（test cases）

落 `tests/test_chanlun_analysis.py`（spec_id SPEC.BUY_SELL.CORE）：

- **LB1 正例**：单一最近中枢 + `ongoing_type == range` 且 `current_structure_status == ongoing_same_type`
  （单中枢中枢震荡）+ 向下离开（末笔）跌破 `zs_low` 且相对进入段创新低 + 力度衰减
  （`bottom_divergence` / `segment_bottom_divergence == True`）+ 离开末笔后出现向上反向转折 →
  `buy_1like ∈ buy_points`；catalog 槽位 `basis == consolidation_divergence_reverse_low`，
  `signal_bi_id` / `price` 锚在离开末笔低点。
- **LB1 反例（趋势门控 down）**：同背驰结构但 `ongoing_type == down`（两中枢不重叠不回探 → 下跌
  趋势）→ 报标准 `buy_1`，不报 `buy_1like`（趋势背驰归一买）。
- **LB1 反例（无背驰）**：离开段力度不弱于进入段（`segment_bottom_divergence == False`）→ 不报 `buy_1like`。
- **LB1 反例（无反向转折）**：离开段末笔后无向上转折笔（`_has_reverse_turn_after == False`）→ 不报 `buy_1like`。
- **LB1 门控反例**：前段已完成、当前为新类型候选未确认（`current_structure_status ==
  candidate_completed_waiting_stability`）→ 只观察，不报 `buy_1like`。
- **LS1 正例（对称）**：`ongoing_type == range` + 向上离开段升破 `zs_high` + `segment_top_divergence` +
  离开段末笔后向下反向转折 → `sell_1like ∈ sell_points`，`basis == consolidation_divergence_reverse_high`。
- **LS1 反例（无背驰）**：`segment_top_divergence == False` → 不报 `sell_1like`。
- **去重**：同一离开段末笔已被 `buy_2like` 认领（`signal_bi_id` 相同）时不重复标记 `buy_1like`。
- **契约完整性**：`tests/test_analysis_contract.py` 的 `SignalPoint` / `SignalBasis` 完整集合更新
  （`buy_1like` / `sell_1like` + 两个 basis）。

固定口（建议）：LB1/LS1 正例可用单中枢（range + `ongoing_same_type`）+ 笔级 / 段级背驰：
向下离开（末笔）跌破 `zs_low` 且 `bottom_divergence`/`segment_bottom_divergence == True`，随后反向转折笔；
趋势反例用两个不重叠下移中枢（`ongoing_type == down`）→ 归标准 `buy_1`；过渡态反例用
「完成块 + range 当前块」使 `current_structure_status == candidate_completed_waiting_stability`。

验收：

- 在盘整 / 中枢震荡（range）结构里，标准一类点因趋势门控缺席时，类一类点仍能给出「盘整背驰
  转折」操作机会。
- 类一类点与标准一 / 二类点、类二类点不重复标记；catalog 既有索引断言（buy_1..sell_2like）不被破坏。

## 当前 blocker

- 最近标准中枢和趋势 / 盘整背驰若未先稳定，买卖点严格确认会持续漂移。
- 当前消费端已有工程规则痕迹，必须先把差异表写清，再逐项替换。

## 推荐执行顺序

1. 先做 BS1，把“现状 vs 严格理论”差异表写清楚。
2. 再做 BS2-BS4，按一类点 -> 二类点 -> 三类点顺序收口。
3. 最后做 BS5-BS6，把多级别联立、消费降级和案例回归补齐。

---

## 下一批高 ROI 任务（待评审 backlog）

> 状态：**待评审（proposed）**。本节是「提升买卖点准确性与实时性」的下一批候选任务，
> 目标覆盖标准一 / 二 / 三类点与类一 / 类二类点。**尚未进入实现阶段**：按仓库
> [spec-change-protocol.md](spec-change-protocol.md) 五步流程，评审通过后再落 spec（应然）→ 契约 →
> 测试（红）→ 实现（绿）→ changelog。设计层细节见
> [signal-realtime-lifecycle-design.md](signal-realtime-lifecycle-design.md)（草案）。

### 现状快照（实然）

- 标准一 / 二 / 三类点与类一 / 类二类点判定链已落地（BS1-BS8 完成），锚定「已确认笔 + 反向转折」，
  段级中枢背驰用严格「离开段 vs 进入段」口径。
- 信号只有「不发 / 确认发」两态：无中间「预备态」，也无「确认后失效」回路——一个买卖点一旦写入
  报告，直到下一次全量重算前不会被撤销，即使价格随后创新低 / 新高破坏其前提。
- 多级别联立目前是**单向降级**（上级别 pending/auxiliary → 下级别降 watch）；缺**下级别 → 上级别
  的升级 / 确认**（小转大候选自动升级、区间套反向确认）。
- 每轮增量重算全量重跑信号，无「同一确认信号跨帧不得消失 / 翻转」的 repaint 回归护栏。

### 排序原则

- ROI = 覆盖点类型广度 × 误报 / 漏报下降幅度 ÷ 实现风险。跨所有点类型受益的横切项优先。
- 实时性与准确性同权：既要更早给出可操作信号，又不能引入 repaint（信号闪烁 / 事后撤销）。

### 看板（P0 最高）

| ID | 任务 | 类别 | 优先级 | 覆盖点类型 | ROI 理由 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| RS0 | 信号生命周期与 repaint 安全契约 | 准确性 + 实时 | P0 | 1/2/3 + 类一 / 类二 | 横切全部点类型；补「确认→失效」回路 + 跨帧不翻转护栏，直接降低事后被打脸的假信号 | 完成（契约 + confirmed + 跨帧 invalidated/repaint + 管道 + 发布前闸门） |
| RS1 | 实时「预备态」（imminent / forming）分层 | 实时 | P1 | 1/2/3 + 类一 / 类二 | 把「背驰已现、待转折确认」升级为 watch 档可操作提示，盘中更早预警且不 repaint | 完成（1/2/3 + 类一 / 类二 forming 均已落地并双边回归） |
| RS2 | 多级别双向联立（小转大自动升级 + 区间套反向确认） | 准确性 | P2 | 1/2/3（尤其 3 类 / 类二） | 现只单向降级；补下级别→上级别确认，减少高级别转折漏报 | 完成（小转大升级 higher_level_confirmed + 区间套反向确认 + 回归） |
| RS3 | 收口既有「工程近似」（笔级中枢级别收敛 / 二类首次回抽窗口 / 三类回中枢失效） | 准确性 | P3 | 1/2/3 | 关闭 BS1 差异表遗留近似，降低边界假信号 | 完成（item1 级别收敛 + item2 首次回抽窗口均已落地 / item3 由 RS0 覆盖） |
| RS4 | 增量重算稳健性（跳空 / 停牌 / overlap 失配） | 实时 / 性能 | P3 | 全部（数据层） | 保证极端行情下缓存不污染信号，避免全量回退降级 | 完成（跨帧不连续检测 + 回退全量重抓 + 回归） |
| RS5 | 消费交付：发布包透传 + 小程序「买卖点」页面渲染 | 交付 | P1（随 RS0/RS1） | 1/2/3 + 类一 / 类二 | RS0/RS1 若不透传到发布包与前端，页面上看不到任何变化；此项确保改动真正落到用户可见面 | 完成（发布包 + 前端 + invalidated 帧序管道全链已落地并回归；invalidated 仅在真实跨帧失效事件时非空） |

### RS0 信号生命周期与 repaint 安全契约（P0）

- 目标（应然，待写入 spec）：为每个买卖点定义状态机 `forming(观察) → confirmed(确认) → invalidated(失效)`，
  并给出各点类型的**失效条件**（如：一买 confirmed 后离开段低点被有效跌破、二买回抽破前低、
  三买回试重新跌回中枢、类一 / 类二对应背驰前提被破坏）。
- 实时红线：`confirmed` 只允许锚定在已确认笔 / 线段上；同一 `signal_bi_id` 的 `confirmed` 信号在后续
  帧不得凭空消失或翻转方向，只能进入 `invalidated`（并保留证据字段）。
- 交付物：契约枚举（`SignalLifecycleState` 或等价）+ `analyze_chanlun_signals` 输出附带每点
  `lifecycle_state` / `invalidated_reason`；bar-by-bar replay 回归护栏。
- 验收：重放真实样本（1m/5m/30m/day）时，confirmed 信号集合单调（只增或转 invalidated），无闪烁。

进展（增量1，2026-09-11）：

- 契约已落地：`analysis_contract.py` 新增 `SignalLifecycleState`（forming/confirmed/invalidated）与
  `SignalInvalidatedReason`（5 类失效原因）枚举 + label/note 投影 + `get_analysis_contract` 两个新字段族；
  回归 `tests/test_analysis_contract.py`（新增枚举完整性 + label 稳定性 + 投影覆盖）。
- confirmed 基线已落地：`_build_signal_point_detail` 追加 `lifecycle_state` / `invalidated_reason`
  两个字段（additive，不破坏既有 catalog 索引与消费）；已确认 active 点统一带 `lifecycle_state=confirmed`。
- 待续：`invalidated` 状态发射（§3.2 各点失效条件的实际判定）+ 跨帧 bar-by-bar repaint 回归护栏
  （需回放帧序列 / 前帧状态）。这两项为 RS0 增量2。

进展（增量2，2026-09-11）：

- invalidation 定性为跨帧概念并落地回放护栏：`analysis.py::replay_confirmed_signal_lifecycle(frames)`
  按时间序比较多帧 confirmed 集合，产出 `invalidated`（附 `invalidated_reason`）、`repaint_violations`
  与 `timeline`。单帧快照恒按最新结构判定，前提破坏时确认点自然不发，故失效态由多帧比较得出，
  同时兜住「confirmed 只能保持或转 invalidated、不得凭空消失」的 spec §2.8 repaint 红线。
- 各点失效前提 `_signal_premise_broken` 按 §3.2 分族：一 / 二 / 类一 / 类二用「买点新低跌破 / 卖点新高
  升破信号价」；三类用「回抽 / 反抽重新回到中枢（买三回落 zs_high 之下、卖三反抽 zs_low 之上）」。
- 回归：`tests/test_chanlun_analysis.py` 新增 4 用例（一买新低失效、repaint 违规兜底、confirmed 跨帧保持、
  三买回中枢失效）。
- 待续：把回放护栏接入真实 1m/5m/30m/day 帧序列的自动化闸门（当前为纯 synthetic 帧单元测试）。

进展（增量3 real-frame 管道落盘，2026-09-11）：

- 采用「逐次运行 / 刷新为相邻帧」模型（而非单运行 O(n²) 前缀回放）：`analysis.py::to_lifecycle_frame`
  从单帧输出提取可持久化压缩帧（confirmed 锦点 + 前提比较标量）；`derive_signal_lifecycle_transitions`
  跨相邻两帧推导 `invalidated_points` 与 `repaint_violations`。
- `build_signal_summary_fields(signals, *, previous_frame=None)` 新增 `invalidated_points` /
  `signal_repaint_violations` / `lifecycle_frame`（本帧压缩帧写回 tech.json.summary，供下一运行对比）。
- 管道：`batch_prepare_chanlun_reports.py` 写 tech.json 前读上一份 tech.json.summary.lifecycle_frame
  作 previous_frame 传入 `build_technical_summary`（tech.json 即帧存，无新增 store）。
- 发布包 + 前端：`build_latest_signal_summary` 透出 invalidated 列表 + 「买卖点失效：…」文本行；
  两处技术卡透出 `invalidated_points`；westock buyPoints 页枚举 invalidated 成行并渲染「已失效」角标。
- 回归：`tests/test_chanlun_analysis.py` 4 新用例（to_lifecycle_frame / derive 跨帧失效 / 首帧空 /
  summary 透出）+ `tests/test_build_miniapp_publish_bundle.py` invalidated 文本行用例；共 210 用例回绿。
- 发布前闸门已落地：`tests/test_signal_repaint_gate.py` 扫描 `data/reports/**` 全部 tech.json，断言
  `summary.signal_repaint_violations` 恒空（spec §2.8 repaint 红线）；注册为 `run_segment_safety_gates.py`
  的 `signal-lifecycle` 闸门（无本地报告时跳过，与 segment regression 一致）。

### RS1 实时「预备态」分层（P1）

- 目标（应然，待写入 spec）：把现有 `zs_monitor_alert`（pre_breakout / pre_breakdown）泛化为**每类买卖点**
  的 `forming` 预备态：满足「背驰 / 离开 / 隔段力度衰减」但尚未出现反向转折确认时，给 `forming`
  档（watch），明确标注「待转折确认，非确认点」。
- 覆盖：一类（背驰已现待转折）、二类（回抽未破前低但未再走强）、三类（离开中枢首次回试进行中）、
  类一 / 类二（盘整 / 隔段背驰已现待反向转折）。
- 红线：`forming` 不得被下游二次摘要成 confirmed；与 RS0 的状态机同源。
- 验收：盘中样本能在 confirmed 前 N 根给出 `forming`，且 `forming → confirmed / invalidated` 转移可回溯。

进展（增量1，2026-09-11）：

- 已落地一类 / 类一预备态：`analyze_chanlun_signals` 在「背驰 + 离开成立但 `_has_reverse_turn_after`
  未成立」时产出 `forming`，写入独立 `forming_points`（不进 buy_points/sell_points/signal_points/
  signal_catalog，保持既有 confirmed 消费与 catalog 索引契约不变）。覆盖 buy_1/sell_1（趋势门控）与
  buy_1like/sell_1like（range 单中枢盘整背驰）；反向转折确认后自动升 confirmed 且不重复计数。
- 回归：`tests/test_chanlun_analysis.py` 新增 confirmed 生命周期用例 + buy_1/sell_1/buy_1like 三个
  forming 正例（spec §2.8）。
- 待续：二类 / 三类回抽预备态（回抽进行中）+ 类二（隔段背驰待反向转折）预备态为 RS1 增量2；
  发布包透传 + 小程序渲染为 RS5。

进展（增量2，2026-09-11）：

- 二类 / 三类 / 类二预备态已落地：`analyze_chanlun_signals` 的 forming 块补 buy_2/sell_2（一类前置 +
  首次回抽 / 反抽不破前低 / 前高、待再度走强 / 走弱）、buy_3/sell_3（离开中枢 + 首次回踩 / 反抽守边界、
  尚未 renew）、buy_2like/sell_2like（同级别隔段背驰 anchor、反向转折待确认）；均只进 `forming_points`，
  不写 buy_points/sell_points/catalog，反向转折确认后自动升 confirmed。
- 回归：`tests/test_chanlun_analysis.py` forming 正例现覆盖双边——一类（buy_1/sell_1）、类一（buy_1like）、
  二类（buy_2/sell_2）、三类（buy_3/sell_3）、类二（buy_2like/sell_2like），共 9 个 forming 用例。
- 注：级别收敛后 bi-level 中枢的一 / 二类 forming 仍作「仅观察」保留（forming = 观察态，非确认点，
  与 RS3 item1「无点 / 仅观察」口径一致）。发布包透传 + 小程序渲染仍归 RS5。

### RS2 多级别双向联立（P2）

- 目标（应然，待写入 spec §3/§4/§5 增补）：在现有单向降级基础上补**升级 / 确认**方向——
  当最后一个次级别中枢出现对应三类买卖点（`small_to_large_status == 必要条件已具备`）且高级别结构
  闭环时，把高级别「小转大候选」升级为「已确认转折」；区间套支持低级别执行确认反向标注高级别时机。
- 红线（第35 / 43 / 44 课）：必要条件 ≠ 充分条件；高级别未闭环前只标候选，不得越级确认。
- 验收：跨级别样本（如 30m 主结构 + 5m/1m 执行）中，升级只在必要条件 + 高级别闭环双满足时发生。

进展（2026-09-11）：

- 已落地升级方向：`analysis.py::_build_small_to_large_status` 新增 `higher_level_confirmed` 档，
  仅当次级别必要条件已具备（最后中枢对应三类点）+ 高级别结构闭环（`_higher_level_structure_closed`：
  `current_structure_status == completed_then_new_type` + `same_level_consumption_level == confirmed`
  + 新走势方向与 side 一致）双满足时升级，未闭环停在候选 / 必要条件已具备，兜住「必要≠充分」红线。
- 区间套反向确认：`_build_small_to_large_reverse_confirm` 仅在 `higher_level_confirmed` 时回填
  `small_to_large_reverse_confirm = {active, basis, higher_structure_status, note}` 并把 note 追加进
  精确入场 `note`；契约 `SmallToLargeStatus.HIGHER_LEVEL_CONFIRMED`（label「小转大已确认转折」）。
- 回归：`tests/test_chanlun_analysis.py`（buy/sell 升级正例 + 结构未闭环反例）、
  `tests/test_analysis_contract.py`（新增枚举完整性 + label/note）。

### RS3 收口既有工程近似（P3）

- 笔级中枢（类中枢辅助链路）级别收敛（原「力度口径」条已否）：笔级中枢比线段级低半级，用它兜底
  产出**操作级别**一 / 二类点属级别混用（买卖点级别 = 中枢级别，见 spec §2.1 与第53 / 81课「级别
  显微镜」原则）。因此收口方向不是把 `macd_sum_abs` 改成段级严格力度口径（那只是打磨一个级别本就
  不自洽的近似），而是**级别收敛**：段级中枢（`current_zs.structure_level == segment`）成型前，操作
  级别只给「无点 / 仅观察」，笔级中枢结构仅下沉到执行级别 / 区间套作次级别精确定位，不冒充操作级别
  信号。落点＝`analyze_chanlun_signals` 里 `use_segment_divergence == False` 分支不再直接发一 / 二类点。
- 二类点首次回抽窗口：`_is_first_reverse_hold` 增补「首次确认性回抽」的窗口 / 失败 / 失效条件，
  而非仅「不破前低 / 前高」。
- 三类点回中枢失效：回试中途重新跌回 / 站回中枢时自动置 `invalidated`（与 RS0 状态机联动）。
- 验收：
  - item 1 —— BS1 差异表「笔级中枢回退」相关行从「工程近似（笔级冒充操作级别）」改判为
    「级别正确：笔级仅供执行级别 / 区间套」；`use_segment_divergence == False` 时操作级别不再直接发
    一 / 二类点，补「段级中枢未成型 → 操作级别无点 / 仅观察」回归。
  - item 2 / item 3 —— 对应 BS1 差异表行从「工程近似」收敛为「严格一致」，并补易混淆反例回归。

进展（2026-09-11）：

- item 3（三类回中枢失效）已由 RS0 跨帧 `_signal_premise_broken` / `THIRD_CLASS_REENTERED_ZS` 基本覆盖。
- item 2（二类首次回抽窗口）已落地：`analysis.py::_is_first_reverse_hold` 从「仅更早的不破前低 / 前高
  回抽占用窗口」扩到「anchor 之后、candidate 之前出现任意同向回试笔（含破位失败态）即判窗口已占用 /
  失败」，candidate 不再是首次确认性回抽即不补二类点。回归：`tests/test_chanlun_analysis.py` 新增 4 个
  `_is_first_reverse_hold` 单测（首个回抽接受 / 更早不破位占用 / 更早破位失败 / 二卖对称破位失败）；
  既有二买正例、首次回抽锁定、破前低易混淆例、二卖对称例全绿。
- item 1 重定方向（2026-09-11）：原「笔级力度改段级严格口径」被否——笔级中枢冒充操作级别买卖点是
  级别混用，改力度口径不能纠正级别问题。收口改为**级别收敛**并已落地：`analyze_chanlun_signals` 的
  buy_1/sell_1/buy_2/sell_2 发点统一增加 `use_segment_divergence` 门控，段级中枢（`structure_level ==
  segment` + 有 segments）未成型时操作级别不发一 / 二类点（仅观察）；笔级背驰量仍计算供执行级别 /
  区间套。回归：笔级一 / 二买 / 一 / 二卖正例转为级别收敛反例（bi-level 不发一 / 二类点）；新增 /
  迁移段级 buy_2/sell_2 正例（显式 Segment，锁段级回抽窗口）；buy_1/buy_1like 去重门控反例改用段级构造。
  注：三类 / 类一 / 类二点的笔级回退链路级别收敛不在本增量，待后续单独评估。

### RS4 增量重算稳健性（P3）

- 目标：`infer_incremental_start` / `_fetch_with_optional_local_store` 在跳空 / 停牌 / overlap 失配时，
  检测本地缓存与增量窗口不连续并安全回退，避免污染下游信号。
- 验收：构造跳空 / 停牌 fixture，断言缓存不连续时触发受控全量回补且信号一致。

进展（2026-09-11）：

- 已落地：`local_bar_store.detect_incremental_discontinuity(local_rows, remote_rows)` —— 远端增量最早一根
  严格晚于本地缓存末根时判定为跳空 / 停牌 / 源漂移不连续（两段之间有空洞）。
- `_fetch_with_optional_local_store`：仅在增量档（`local_covers_target`）且检测到不连续时，回退到
  `requested_start` 全量窗口重抓再合并，并在 `local_store.incremental_fallback` 与 tech.json summary 透出该标记；
  正常回抽 / 填缺（远端最早根 ≤ 本地末根）不受影响，无误回退。
- 回归：`tests/test_local_bar_store.py`（跳空正例 + 连续 / 填缺 / 空集反例）、
  `tests/test_batch_prepare_chanlun_reports.py::test_fetch_with_optional_local_store_falls_back_to_full_on_incremental_gap`
  （跨帧跳空触发全量回抓3合并用全量数据）；现有健康增量用例不回退（无假阳性）。

### RS5 消费交付：发布包透传 + 小程序「买卖点」页面渲染（P1，随 RS0/RS1）

> RS0/RS1 的计算层字段若不经此项交付，用户在小程序「买卖点」页面看不到任何变化。买卖点
> 主要展示面就是该页面，故此项与 RS0/RS1 同优先级并行。

- **发布包透传层**（本仓库 `scripts/build_miniapp_publish_bundle.py`）：`normalize_signal_point`
  （现仅透出 `point/label/time/price/active/basis`）与 `build_latest_signal_summary` 增补
  `lifecycle_state` / `invalidated_reason` / `forming` 字段；`forming` 预备态点也要进入 bundle
  （现被 `active` 过滤丢弃）。初期可先复用现有 `zs_monitor_alert` 文本行样式，把预备态以
  「买卖点预备：…待转折确认」文本行快速透出，再逐步做成结构化字段。
- **前端渲染层**（`c:/sandbox/sinba/westock/`，**独立仓库，不在当前工作区**）：「买卖点」页面
  按 `lifecycle_state` 渲染三态——`forming` 显「预备 / 观察」角标（watch）、`confirmed` 正常展示、
  `invalidated` 显「已失效」标记并带 `invalidated_reason`；红线：`forming` 不得渲染成确认点。
- 依赖：RS0（`lifecycle_state` 契约）、RS1（`forming` 语义）先定型；发布包与前端按同一契约对齐。
- 验收：同一真实样本在分析层、发布包、前端「买卖点」页面三处状态语义一致；`forming → confirmed /
  invalidated` 转移在页面上可见且不 repaint；回归覆盖发布包透传（`tests/test_build_miniapp_publish_bundle.py`）。

进展（发布包透传已落地，2026-09-11）：

- `scripts/build_miniapp_publish_bundle.py`：`normalize_signal_point` 现透出 `lifecycle_state` /
  `invalidated_reason`；`build_latest_signal_summary` 新增 `forming` 列表 + 「买卖点预备：…（待转折
  确认，非确认点）」文本行；两处技术卡（`build_technical_section` 与摘要卡）透出 `forming_points`。
  报告 JSON 侧 `summary` 由 `build_signal_summary_fields` 带出 `forming_points` 与生命周期标签的
  `signal_points`，全链贯通。
- 回归：`tests/test_build_miniapp_publish_bundle.py` 新增 forming 文本行 + `normalize_signal_point`
  生命周期字段两用例；报告生成 / 分析 / 契约 / 发布包共 198 用例回绿。
- 待续（westock 独立仓库）：「买卖点」页面按 `lifecycle_state` 渲染 forming（预备 / 观察角标）、
  confirmed（正常）、invalidated（已失效 + `invalidated_reason`）三态；红线：forming 不得渲染成确认点。

进展（前端已落地，2026-09-11）：

- `westock/miniprogram/services/publishViewService.js`：`buildSectionBuyPoints` / `buildSectionSellPoints`
  新增枚举 `forming_points`（与已确认点同类型去重）；`buildPointRowFromEntry` 透出 `lifecycleState` /
  `lifecycleLabel` / `invalidatedReason` / `isLike`；`loadBuyPointView` 把这些字段带入 buyRows/sellRows。
  顺手补 类一买 / 类一卖（B1L/S1L）类型映射（之前 `buy_1like` 会误归为一买）。
- `westock/miniprogram/pages/buyPoints/index.wxml` + `index.wxss`：类型列渲染生命周期角标
  （forming=预备、invalidated=已失效），`.lifecycle-badge-*` 样式；invalidated 行加删除线弱化。
- 验证：node 语法检查 + `buildSectionBuyPoints/Sell` 逻辑烟雾（forming/confirmed/去重/B1L/S1L）均通过。
- invalidated 帧序管道已全链贯通（2026-09-11 核验）：`batch_prepare_chanlun_reports.py` 写 tech.json 前读上一份
  `summary.lifecycle_frame` 作 `previous_frame` 传入 `build_signal_summary_fields` → 跨相邻帧推导
  `invalidated_points`；`build_miniapp_publish_bundle.py::build_latest_signal_summary` 透出 `invalidated` 列表 +
  「买卖点失效：…」文本行，`normalize_signal_point` 带 `lifecycle_state` / `invalidated_reason`；前端 buyPoints
  页渲染「已失效」角标。invalidated 集仅在真实跨帧失效事件（confirmed 点前提被后续走势破坏）时非空，
  故页面平时不显示失效行属正常。回归：`tests/test_build_miniapp_publish_bundle.py::test_build_latest_signal_summary_surfaces_invalidated_line`。

> 评审出口：请 reviewer 就 (1) P0/P1 是否值得优先于继续收口 BS5/BS6，(2) 状态机的失效条件口径，
> (3) 预备态是否单列契约字段，三点确认后再进入实现阶段。