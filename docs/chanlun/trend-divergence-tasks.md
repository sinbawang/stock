# 走势类型与背驰模块任务拆解

本页统一承接“严格同级别走势类型自动分解”“趋势背驰严格自动判定”“盘整背驰严格自动判定”以及对应案例、输出字段的执行拆解。

## 关联总表条目

- 严格同级别走势类型自动分解
- 趋势背驰严格自动判定
- 盘整背驰严格自动判定
- 背驰与盘整背驰标准案例包
- `tech.json` 严格结构状态字段补齐（走势类型 / 背驰相关部分）

## 当前 epic 看板

| ID | 任务 | 状态 | 依赖 | 完成定义 |
| --- | --- | --- | --- | --- |
| TD1 | 同级别走势类型自动分解主链 | 完成 | `segment`, `zhongshu` 稳定 | 给定同级别结构后，能稳定拆出盘整 / 趋势 / 过渡段，而不是只输出工程摘要 |
| TD2 | 趋势背驰严格判定 | 完成 | TD1 | 背驰判定可对应原文条件、最近中枢、离开段和力度比较 |
| TD3 | 盘整背驰严格判定 | 完成 | TD1 | 盘整背驰不再被趋势背驰或工程近似规则替代 |
| TD4 | 输出字段与消费解释收口 | 完成 | TD2, TD3 | `post_divergence_route`、`oscillation_rhythm_state` 等字段能稳定表达结构状态 |
| TD5 | 标准案例包与回归闸门 | 完成 | TD1-TD4 | 正例、反例、易混淆例都能自动化回归和文档 review |

## 按任务类型看板

阅读方式：

- 文档任务：走势类型定义、背驰案例库、字段语义与消费红线。
- 测试任务：走势类型 / 背驰 regression、过渡态样本、字段与文案核验。
- 代码任务：同级别走势类型自动分解、趋势背驰判定、盘整背驰判定与字段生成。
- 优先级：`高` 表示当前必须优先推进；`中` 表示主线并行项；`低` 表示保留但不抢当前实现前置条件。

当前重点：

1. 代码：先完成 `TD1` 同级别走势类型自动分解主链，这是背驰严格化的前置条件。
2. 测试：补走势类型主链 regressions，避免 repeated rebuild 下类型链漂移。
3. 文档：继续把严格结论、工程近似和监视提示分层写清，并补过渡态案例。

### 文档任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| D1 | 走势类型 / 背驰规格与差异说明 | 中 | 把严格结论、工程近似、监视提示继续分层写清 | 进行中 | 已补 [trend-divergence-spec.md](trend-divergence-spec.md) §11「应然↔实然逐条对应」，把走势类型/趋势背驰/盘整背驰/类背驰/背驰后去向/指标地位/震荡节奏逐条映射到 machine-readable 字段并标注三层。 |
| D2 | 背驰案例包与图示库 | 中 | 补正例、反例、易混淆例，尤其是过渡态样本 | 进行中 | 已补 [trend-divergence-visual-example-library.md](trend-divergence-visual-example-library.md) §9「正例/反例/易混淆例（数值化卡片）」；真实过渡态样本仍受锚点漂移阻塞。 |

### 测试任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| T1 | 走势类型主链 regressions | 高 | 锁 repeated rebuild 下的类型链不漂移 | 进行中 | TD1 主链已成型，已有 `type_chain` 单例、空集与复杂前缀链回归（`2026-08-23` 补 `test_build_structure_state_type_chain_folds_multiple_completed_runs`，锁 up->down->range 三 run 折叠）。 |
| T2 | 趋势背驰 / 盘整背驰回归 | 中 | 为正例、反例、易混淆例建立最小自动化锚点 | 进行中 | 趋势/盘整背驰正例 + 反例（离开段未突破 / 未试探边界）均已落地；`2026-08-23` 补「趋势 vs 盘整分轨互斥」回归（`test_analyze_chanlun_signals_trend_and_range_divergence_tracks_are_mutually_exclusive`），锁同一结构不会同时 active 两条背驰轨。 |
| T3 | 字段与消费核验 | 中 | 核验 `post_divergence_route`、`oscillation_rhythm_state` 不被误升为 confirmed | 完成 | `post_divergence_route` 已按 `strict` 输出，非严格背驰回落到 `last_zs_extension`。 |

### 代码任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| C1 | TD1 同级别走势类型自动分解主链 | 高 | 形成 machine-readable 的稳定类型链 | 完成 | `type_chain` 已落地并锁回归；过渡段由 `transition_state` 表达。 |
| C2 | TD2 趋势背驰严格判定 | 中 | 绑定最近中枢、离开段与力度比较 | 完成 | `divergence.trend` 已补 `strict / reference_zs_id / departure_confirmed / strength_comparison`。 |
| C3 | TD3 盘整背驰严格判定 | 中 | 建立独立于趋势背驰的判定入口 | 完成 | `divergence.range` 已补 `strict / reference_zs_id / touches_boundary / strength_comparison`。 |
| C4 | TD4 输出字段与消费解释收口 | 中 | 统一严格结论、预警、监视字段的边界 | 完成 | `post_divergence_route` 改为按 `strict` 输出；60m 报告文案区分“确认/迹象/无”。 |

## 任务拆分

<a id="td1-route-chain"></a>
### TD1 同级别走势类型自动分解主链

- 明确走势类型分解的输入边界：使用哪些已确认 segment、如何绑定最近标准中枢。
- 明确“盘整延续”“趋势延续”“完成后转入新类型”的切换条件。
- 产出 machine-readable 的同级别走势类型结果，而不是只留人工解释。

验收：

- 同一窗口在 repeated rebuild 中不会切出不同走势类型链。
- 下游背驰、买卖点模块能引用稳定的走势类型结果，而不是重新各自猜一遍。

当前进展：

- 已新增 [trend-type-decomposition.md](trend-type-decomposition.md)，写死输入边界（confirmed segments → segment 中枢 → live runs）、切换条件（盘整延续 / 趋势延续 / 完成后转入新类型 / 重吸收）与 machine-readable 输出契约。
- `build_structure_state(...)` 已新增 `type_chain` 字段：`[{type, status, zs_count, start_zs_id, end_zs_id}]`，与 `last_completed` / `current_ongoing` 严格一致（completed 段取自 `last_completed`，ongoing 段取自 `current_ongoing`），早前 run 按 run 粒度折叠为 completed；过渡段继续由 `relationship.transition_state` 表达。
- 已新增 `tests/test_chanlun_analysis.py::test_build_structure_state_type_chain_matches_last_completed_and_ongoing` 与 `test_build_structure_state_type_chain_single_and_empty`，锁住 up→range 拆出 completed up + ongoing range、单中枢与空集三档真值。
- `2026-08-23` 补复杂前缀链回归 `tests/test_chanlun_analysis.py::test_build_structure_state_type_chain_folds_multiple_completed_runs`：构造 up（zs1->zs2 终结）→ down（zs4->zs5 终结）→ range（zs7 ongoing）三个 run（中间用被更大扩张吸收的中枢分隔），锁住 `type_chain` 把两个历史 run 按 run 粒度折叠为 completed（`up(2)`、`down(2)`），保留当前 `ongoing range(1)`，且 `last_completed` 指向最近 completed run（down）。

<a id="td2-trend-divergence"></a>
### TD2 趋势背驰严格判定

- 补趋势背驰所需的力度比较、离开段确认、最近中枢绑定规则。
- 区分“工程化 divergence 提示”与“严格趋势背驰确认”。
- 明确趋势背驰触发后的后续路线字段。

验收：

- 每个趋势背驰结论都能回溯到明确的走势类型、最近中枢和力度对比。
- 消费端不会把工程预警字段直接当作严格趋势背驰结论。

当前进展：

- `build_divergence_state(...)` 的 `divergence.trend` 已补 machine-readable 严格判定字段：
  `strict`（严格趋势背驰确认，需趋势 + 最近中枢绑定 + 离开段突破 + 力度衰减）、
  `reference_zs_id`（最近中枢绑定）、`departure_confirmed`（离开段是否突破 ZG/ZD）、
  `strength_comparison`（`candidate_bi_id / candidate_strength / reference_bi_id / reference_strength / decayed`）。
- 已新增 `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_marks_trend_divergence_as_higher_level_reverse_trend` 断言补上 `strict/reference_zs_id/departure_confirmed/strength_comparison`，并新增
  `test_analyze_chanlun_signals_trend_divergence_without_departure_confirmation_is_not_strict`，锁住“力度衰减但离开段未突破 → 工程提示，非严格背驰”的区分。
- 消费端读取 `strict` 决定是否按严格背驰结论措辞，归 TD4 收口。

<a id="td3-range-divergence"></a>
### TD3 盘整背驰严格判定

- 单列盘整背驰输入条件，避免落回趋势背驰逻辑复用。
- 补“盘整内离开段 / 回抽段 / 再次离开段”之间的判定关系。
- 为容易误判成“普通震荡”或“趋势背驰”的场景补反例。

验收：

- 盘整背驰有独立字段、独立样例和独立 regression。
- reviewer 能清楚区分“盘整背驰缺失”与“只是工程近似提示”。

当前进展：

- `build_divergence_state(...)` 的 `divergence.range` 已补独立 machine-readable 判定字段：
  `strict`（盘整背驰严格确认，需盘整 + 最近中枢绑定 + 试探边界 + 力度衰减）、
  `reference_zs_id`、`touches_boundary`（同方向试探是否触及 ZG/ZD，`>=` / `<=`）、
  `strength_comparison`（与趋势背驰同构的力度对比详情）。
- 盘整背驰与趋势背驰通过 `ongoing_type` 分轨（`range` vs `up/down`），不复用趋势判定分支。
- 已新增 `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_marks_range_divergence_as_higher_level_range` 断言补上 `strict/reference_zs_id/touches_boundary/strength_comparison`，并新增
  `test_analyze_chanlun_signals_range_divergence_without_touching_boundary_is_not_strict`，锁住“力度衰减但未试探到边界 → 工程提示，非严格盘整背驰”的区分。

<a id="td4-output-fields"></a>
### TD4 输出字段与消费解释收口

- 收口 `post_divergence_route`、`oscillation_rhythm_state` 等字段的严格定义。
- 明确哪些字段表达“严格结论”，哪些字段只表达“监视 / 预警”。
- 补充 summary / publish / miniapp 对走势类型和背驰的文案策略。

验收：

- 字段命名、严格程度、展示文案三者一致。
- 消费端不会把 pending / watch 误展示成 confirmed 背驰。

当前进展：

- `_build_post_divergence_route(...)` 改为按 `divergence.trend.strict` / `divergence.range.strict` 输出：严格背驰才给 `higher_level_reverse_trend` / `higher_level_range`，工程提示回落到 `last_zs_extension`（最后中枢扩展观察）。
- 四个 60m 报告 / wechat 文案消费者（`run_cn_60m_*`、`run_hk_60m_*`）的“趋势背驰 / 盘整背驰”行改为三档：`确认`（strict）/ `迹象`（active 但非 strict）/ `无`。
- 已新增非严格路由断言：`test_analyze_chanlun_signals_trend_divergence_without_departure_confirmation_is_not_strict` 与 `test_analyze_chanlun_signals_range_divergence_without_touching_boundary_is_not_strict` 均锁定 `post_divergence_route == "last_zs_extension"`。

<a id="td5-case-gates"></a>
### TD5 标准案例包与回归闸门

- 为趋势背驰、盘整背驰分别补正例、反例、易混淆例。
- 案例与自动化回归一一对应，避免文档和代码各写各的。
- 绑定至少一组真实 `1m` 或 `5m` 过渡态样本，而不只看较稳态窗口。

验收：

- [trend-divergence-visual-example-library.md](trend-divergence-visual-example-library.md) 中每个重点结论都能找到自动化锚点。
- 新增背驰规则前后，最小回归集能及时指出行为变化。

当前进展 / 锚点漂移（2026-08-22 记录）：

- 已新增 [trend-divergence-visual-example-library.md](trend-divergence-visual-example-library.md) 第 8 节「案例 → 回归映射表」：趋势背驰正例/反例、盘整背驰正例/反例、趋势 vs 盘整分轨五条案例均绑定具名 pytest（`test_chanlun_analysis.py`）。
- 真实样本锚点依赖 `zhongshu` 模块的 `1m` 预警锚点；原 `000651 1m pre_breakdown` 锚点已漂移（见 [zhongshu-tasks.md](zhongshu-tasks.md) ZS5.3.b），当前数据+代码下已变成「三买 confirmed」。
- 已补背驰模块真实样本锚点（replay 驱动，见 `build/probe_intraday_prebreak_sample.py` 已暴露 `divergence_*` / `post_divergence_route` / `oscillation_rhythm_state` 字段）：
  - 趋势背驰（下跌非严格）：`000651 1m 2026-08-12 10:38` 与 `2026-08-14 10:57`（双锚点）
  - 趋势背驰（下跌严格）：`000591 day 2026-08-03`（`trend_active=True`、`trend_strict=True`、`higher_level_reverse_trend`）
  - 趋势背驰（上涨严格）：`601328 day 2025-06-24`
  - 趋势背驰（上涨非严格）：`300124 1m 2026-08-05 10:29`（`last_zs_extension`）
  - 盘整背驰（严格）：`000651 1m 2026-08-03 13:47`（`range_active=True`、`range_strict=True`、`touches_boundary=True`、`higher_level_range`）
  - 均由 `tests/test_chanlun_analysis.py` 的 replay gate 锁住。
- 趋势 / 盘整背驰真实样本已补齐（下/上、严格/非严格四个象限 + 盘整严格）。扫描工具：`build/scan_divergence_samples.py`。

## 当前 blocker

- TD1-TD5 已闭环：趋势背驰（下/上、严格/非严格）与盘整背驰（严格）真实样本均已补（replay 驱动，`000651` / `000591` / `601328` / `300124` 六锚点）。
- 剩余：背驰案例库与图示库正例/反例/易混淆例的进一步系统化绑定；更多级别/标的的样本广度（非阻塞）。

## 推荐执行顺序

1. 先做 TD1，把走势类型自动分解闭环补起来。
2. 再并行推进 TD2 和 TD3，分别收口趋势背驰与盘整背驰。
3. 最后做 TD4 和 TD5，把输出字段、案例和回归统一起来。