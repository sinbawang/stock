# 课程可追溯矩阵（Lesson Traceability Matrix）

本页回答一个问题：**缠论原文的每一课，在仓库里有没有对应的 spec / design / task / test / code 锚点，以及当前覆盖到什么程度。**

用途与边界：

- 本页只做「课次 → 五层锚点」的双向索引，不重复写定义；定义以各 `*-spec.md` 为准。
- `覆盖状态` 分三档：
  - `显式映射`：文档里直接引用了该课次，且 spec/design 有对应条款。
  - `部分覆盖`：概念已在 spec/design/code 落地，但课次未被显式引用，存在“实现已做、原文未挂”的断链。
  - `缺口`：既无显式引用，也无明确 spec 条款承接。
- 本页与各模块 `*-original-review-matrix.md` 互补：矩阵讲「原文 vs 口径对照」，本页讲「原文 → 实现 → 消费」的全链路可追溯。

## 阅读方式

从左到右：

`课次 → 原文关键点 → spec 锚点 → design/task 锚点 → test 锚点 → code 锚点 → 覆盖状态`

## 首轮聚焦课次（第 24/25/27/33/35/37/40/43/44/61/86/102 课）

| 课次 | 标题 | 原文关键点（精确摘要） | spec 锚点 | design / task 锚点 | test 锚点 | code 锚点 | 覆盖状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | MACD 对背驰的辅助判断 | A/B/C 三段，B 中枢回拉 MACD 黄白线到 0 轴附近；C 段柱面积 < A 段 → 趋势背驰。盘整背驰两种情形：C 不破中枢必回跌；C 破中枢但力度弱则先出、回跌不回中枢构成第三类买点。背驰-买卖点定理：任一背驰必然制造某级别买卖点。 | [trend-divergence-spec §4/§5/§8](trend-divergence-spec.md)；[buy-sell-multi-level-spec §2.4](buy-sell-multi-level-spec.md) | [TD2/TD3](trend-divergence-tasks.md#td2-trend-divergence)；指标只作辅助的红线 | `test_analyze_chanlun_signals_marks_trend_divergence_*`、`..._range_divergence_*` | `build_divergence_state` / `_has_top_divergence` / `_has_bottom_divergence` | 显式映射（已补进 trend-divergence-original-review-matrix） |
| 25 | 吻，MACD、背驰、中枢 | 均线/MACD 是辅助工具，与中枢主定义完全不同，不得混用；趋势背驰后至少回跌到 B 段中枢；盘整背驰三种情况（含构成第三类买点）。 | [trend-divergence-spec §8](trend-divergence-spec.md)；[theory-implementation-consumer-diff-matrix](theory-implementation-consumer-diff-matrix.md) 指标辅助红线 | [zhongshu-original-review-matrix 第25课](zhongshu-original-review-matrix.md) | `test_build_structure_state_without_same_level_zhongshu_is_auxiliary_only`；节奏“只作辅助观察”文案回归 | `zs_monitor_*` 与 divergence 的主辅分离 | 显式映射（已有第25课条目） |
| 27 | 盘整背驰与历史性底部 | 趋势至少两中枢，背驰至少发生在第二中枢之后；第一中枢背驰只能算盘整背驰；盘整背驰构成二/三类买点；大级别盘整背驰常对应历史大底；精确大转折点寻找程序定理 = 逐级收缩区间套。 | [trend-divergence-spec §5](trend-divergence-spec.md)；[buy-sell-multi-level-spec §3](buy-sell-multi-level-spec.md) | [TD3](trend-divergence-tasks.md#td3-range-divergence)；[BS4](buy-sell-multi-level-tasks.md#bs4-buy3) | `test_analyze_chanlun_signals_range_divergence_*`；`build_lower_timeframe_precision_entry` 区间套用例 | `divergence.range`；`precision_entry.nested_from` | 显式映射（已补进 trend-divergence-original-review-matrix） |
| 33 | 走势的多义性 | 多义性来源：中枢延伸数量、模本精度、多种合理释义；中枢延伸一般不超过 5 段，6 段延伸即构成更大级别中枢；纯中枢角度可把背驰重述为离开力度比较。 | [trend-ambiguity-combination-law](trend-ambiguity-combination-law.md) | [TD1](trend-divergence-tasks.md#td1-route-chain)；中枢延伸数量约束 | `same_level_decomposition_mode` 多义降级回归 | `build_structure_state`；中枢延伸计数 | 显式映射（已补 trend-ambiguity-combination-law §2.4 + 核心原则延伸限制） |
| 35 | 给基础差的同学补补课 | 级别递归定义打破「中枢↔走势类型」循环定义；最低级别中枢 = 三笔同价位；三连续走势类型重叠构成高一级别中枢；走势分解定理一/二；买卖点级别定理（大级别买卖点必是次级别以下某一级别买卖点）。 | [base-structure-spec](base-structure-spec.md)；[trend-type-decomposition](trend-type-decomposition.md) | [TD1](trend-divergence-tasks.md#td1-route-chain)；级别递归 | `build_structure_state` type_chain 回归 | `normalize` / 级别层级定义 | 显式映射（已补 buy-sell-multi-level-spec §5 买卖点级别定理） |
| 37 | 背驰的再分辨 | 无趋势无背驰；a+A+b+B+c 中 A、B 必须同级别；c 必为次级别且必含 B 的第三类买卖点，c 必创新高/新低；b 级别 ≤ c。 | [trend-divergence-spec §4](trend-divergence-spec.md) | [TD2](trend-divergence-tasks.md#td2-trend-divergence) | `test_analyze_chanlun_signals_marks_trend_divergence_*` | `divergence.trend.departure_confirmed` / `reference_zs_id` | 显式映射（已补矩阵 + spec §4 结构约束） |
| 40 | 同级别分解的多重赋格 | Ai 与 Ai+2 盘整背驰演化出高一级别中枢；同级别分解可在多级别自动换档（赋格式多层操作）。 | [trend-ambiguity-combination-law §2.3](trend-ambiguity-combination-law.md) | [TD4](trend-divergence-tasks.md#td4-output-fields)；多级别联立 | `oscillation_rhythm_state` 回归 | `_build_oscillation_rhythm_state` | 显式映射（已补 trend-ambiguity-combination-law §2.5） |
| 43 | 有关背驰的补习课 | 背驰-转折定理；背驰级别 = 当下走势级别（必然拉回最后中枢）vs 背驰级别 < 当下走势级别（须先形成更大中枢）两种转折方式；走势类型分解原则（某级别走势不可能出现更大级别中枢）。 | [trend-divergence-spec §7](trend-divergence-spec.md)；[buy-sell-multi-level-spec §4](buy-sell-multi-level-spec.md) | [TD4](trend-divergence-tasks.md#td4-output-fields)；[BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | `post_divergence_route` 回归 | `_build_post_divergence_route` | 显式映射（已补进 trend-divergence-original-review-matrix，并补 spec §4 两种转折方式） |
| 44 | 小级别背驰引发大级别转折 | 小背驰-大转折定理：小级别顶/底背驰引发大级别转折的必要条件是最后一个次级别中枢出现第三类卖/买点（只有必要、无充分条件）。 | [buy-sell-multi-level-spec §4](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | 小转大降级模板回归（待补） | 多级别联立消费降级 | 显式映射（已补矩阵 + spec §4 必要条件） |
| 61 | 区间套定位标准图解 | 围绕同一中枢的任意两段都可比较力度；背驰段内逐级定位（背驰段的背驰段…）即区间套；第二类卖点可与某中枢第三类卖点重合。 | [buy-sell-multi-level-spec §3](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer)；precision_entry | `build_lower_timeframe_precision_entry` 回归 | `precision_entry.nested_from` | 显式映射（已补进 buy-sell-multi-level-original-review-matrix） |
| 86 | 走势分析中必须杜绝一根筋思维 | 同一买卖点的操作意义随大级别位置（中枢上移/下移/震荡）而不同；趋势转折后第一段反弹卖点常即最后中枢第三类卖点，须动态分级。 | [buy-sell-multi-level-spec §5](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | 多级别联立消费降级回归 | 多级别联立消费降级 | 显式映射（已补 buy-sell-multi-level-spec §5 动态分级） |
| 102 | 再说走势必完美 | 走势必完美对应一种最强唯一分解（类比记数法）；级别依次升大；区间套是走势必完美的应用；任何高级别改变必须先由低级别开始；走势可完全分类。 | [trend-type-decomposition](trend-type-decomposition.md)；[trend-divergence-spec §2](trend-divergence-spec.md) | [TD1](trend-divergence-tasks.md#td1-route-chain) | `build_structure_state` type_chain 唯一性回归 | `build_structure_state` / `type_chain` | 显式映射（已补 trend-type-decomposition 理论根基） |

## 覆盖缺口汇总（按优先级）

1. **高 · 断链补齐（已补）**：24/27/37/43/44/61 六课已补进对应 `*-original-review-matrix.md` 行。
2. **高 · 真实缺口（已补 spec）**：33/35/37/43/44 五课的 spec 条款已补（33 延伸限制、35 买卖点级别定理、37 结构约束、43 两种转折方式、44 必要条件）。
3. **中 · 显式化（已补）**：40/86/102 三课已补课次引用（40 §2.5、86 §5 动态分级、102 理论根基）。
4. **待办 · spec→test/code 落地**：本轮补的是「应然」条款，尚未补对应 pytest 回归与代码强制。建议按以下顺序落地：
   - 44 课必要条件：补「小背驰未出现三卖 → 不判大级别转折」反例回归。
   - 37 课结构约束：补「A/B 不同级别 → 盘整背驰」反例回归。
   - 33 课延伸限制：补中枢延伸计数回归。
   - 35/86：补多级别联立判级回归。

## 口径澄清（避免误读）

- `zhongshu-original-review-matrix.md` 写「首轮 12 课规范对齐已闭环」，指的是**文档层首轮复核闭环**，不是「严格自动化实现已完成」。
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md) 里的「严格理论自动化实现 47% / 综合 60%」才是面向**代码落地**的进度口径。
- 二者并存不矛盾：文档复核快于实现；本页把「课次是否显式映射」与「概念是否已落地」拆成两列，就是为了消除“已闭环 vs 47%”的阅读歧义。

## 维护规则

- 新增/修订某一课的 spec 条款后，在本页对应行回填锚点与状态。
- 若某课概念已落地但未显式引用，优先在对应 `*-original-review-matrix.md` 补引用，而不是只改本页状态。
- 课次 → test 锚点优先写具名 pytest 函数，避免行号漂移。
