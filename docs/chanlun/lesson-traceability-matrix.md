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

## 覆盖课次（29 课，全部结构技术课）

说明：只收录「结构技术课」（分型/笔/线段/中枢/走势类型/背驰/买卖点）。心态、杂史、答疑、案例类课次（如 1-14、22-23、26、28、31、34、41-42、47-60、66-76、80、85、87、94-101、103-106）无 spec/code 锚点，不收录；尚未被任何 review 矩阵引用的技术课（如 15/19/30/46/54/79/81/82/84/89-91/93/99/104/107/108）见文末「待补课次」。

| 课次 | 标题 | 原文关键点（精确摘要） | spec 锚点 | design / task 锚点 | test 锚点 | code 锚点 | 覆盖状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 走势终完美 | 走势终完美；完成与未完成必须并存描述。 | [trend-divergence-spec §2](trend-divergence-spec.md)；[trend-type-decomposition](trend-type-decomposition.md) | [TD1](trend-divergence-tasks.md#td1-route-chain) | `build_structure_state` type_chain 回归 | `build_structure_state` / `type_chain` | 显式映射（zhongshu + trend-divergence 矩阵） |
| 18 | 走势类型、中枢定义 | 趋势、盘整定义依附中枢和同级别分解；中枢定理。 | [zhongshu-core-spec](zhongshu-core-spec.md)；[trend-divergence-spec §2](trend-divergence-spec.md) | [ZS2](zhongshu-tasks.md#zs2-state-machine) / [TD1](trend-divergence-tasks.md#td1-route-chain) | `test_zhongshu.py` 中枢定义回归 | `identify_zhongshu` / `build_structure_state` | 显式映射（zhongshu 矩阵） |
| 20 | 中枢级别扩张及第三类买卖点 | 中枢延伸 vs 级别扩张；中心定理；第三类买卖点首次回抽约束。 | [buy-sell-multi-level-spec §2.4](buy-sell-multi-level-spec.md)；[zhongshu-core-spec](zhongshu-core-spec.md) | [BS4](buy-sell-multi-level-tasks.md#bs4-buy3) | buy_3/sell_3 回归 | buy_3/sell_3 判定 | 显式映射（zhongshu + buy-sell 矩阵） |
| 21 | 买卖点分析的完备性 | 三类买卖点完备性；2 类与 3 类在特定条件下重合。 | [buy-sell-multi-level-spec §2.5](buy-sell-multi-level-spec.md) | [BS1 差异表](buy-sell-multi-level-tasks.md#bs1-diff-map) | buy/sell 回归 | buy_2/sell_2、buy_3/sell_3 | 显式映射（zhongshu + buy-sell 矩阵） |
| 24 | MACD 对背驰的辅助判断 | A/B/C 三段，B 中枢回拉 MACD 黄白线到 0 轴附近；C 段柱面积 < A 段 → 趋势背驰。盘整背驰两种情形：C 不破中枢必回跌；C 破中枢但力度弱则先出、回跌不回中枢构成第三类买点。背驰-买卖点定理：任一背驰必然制造某级别买卖点。 | [trend-divergence-spec §4/§5/§8](trend-divergence-spec.md)；[buy-sell-multi-level-spec §2.4](buy-sell-multi-level-spec.md) | [TD2/TD3](trend-divergence-tasks.md#td2-trend-divergence)；指标只作辅助的红线 | `test_analyze_chanlun_signals_marks_trend_divergence_*`、`..._range_divergence_*` | `build_divergence_state` / `_has_top_divergence` / `_has_bottom_divergence` | 显式映射（已补进 trend-divergence-original-review-matrix） |
| 25 | 吻，MACD、背驰、中枢 | 均线/MACD 是辅助工具，与中枢主定义完全不同，不得混用；趋势背驰后至少回跌到 B 段中枢；盘整背驰三种情况（含构成第三类买点）。 | [trend-divergence-spec §8](trend-divergence-spec.md)；[theory-implementation-consumer-diff-matrix](theory-implementation-consumer-diff-matrix.md) 指标辅助红线 | [zhongshu-original-review-matrix 第25课](zhongshu-original-review-matrix.md) | `test_build_structure_state_without_same_level_zhongshu_is_auxiliary_only`；节奏“只作辅助观察”文案回归 | `zs_monitor_*` 与 divergence 的主辅分离 | 显式映射（已有第25课条目） |
| 27 | 盘整背驰与历史性底部 | 趋势至少两中枢，背驰至少发生在第二中枢之后；第一中枢背驰只能算盘整背驰；盘整背驰构成二/三类买点；大级别盘整背驰常对应历史大底；精确大转折点寻找程序定理 = 逐级收缩区间套。 | [trend-divergence-spec §5](trend-divergence-spec.md)；[buy-sell-multi-level-spec §3](buy-sell-multi-level-spec.md) | [TD3](trend-divergence-tasks.md#td3-range-divergence)；[BS4](buy-sell-multi-level-tasks.md#bs4-buy3) | `test_analyze_chanlun_signals_range_divergence_*`；`build_lower_timeframe_precision_entry` 区间套用例 | `divergence.range`；`precision_entry.nested_from` | 显式映射（已补进 trend-divergence-original-review-matrix） |
| 29 | 转折的力度与级别 | 趋势背驰后只允许三级去向：最后中枢扩展 / 更大级别盘整 / 更高级别反趋势。 | [trend-divergence-spec §7](trend-divergence-spec.md) | [TD4](trend-divergence-tasks.md#td4-output-fields) | `post_divergence_route` 回归 | `_build_post_divergence_route` | 显式映射（zhongshu + trend-divergence 矩阵） |
| 33 | 走势的多义性 | 多义性来源：中枢延伸数量、模本精度、多种合理释义；中枢延伸一般不超过 5 段，6 段延伸即构成更大级别中枢；纯中枢角度可把背驰重述为离开力度比较。 | [trend-ambiguity-combination-law](trend-ambiguity-combination-law.md) | [TD1](trend-divergence-tasks.md#td1-route-chain)；中枢延伸数量约束 | `same_level_decomposition_mode` 多义降级回归 | `build_structure_state`；中枢延伸计数 | 显式映射（已补 trend-ambiguity-combination-law §2.4 + 核心原则延伸限制） |
| 35 | 给基础差的同学补补课 | 级别递归定义打破「中枢↔走势类型」循环定义；最低级别中枢 = 三笔同价位；三连续走势类型重叠构成高一级别中枢；走势分解定理一/二；买卖点级别定理（大级别买卖点必是次级别以下某一级别买卖点）。 | [base-structure-spec](base-structure-spec.md)；[trend-type-decomposition](trend-type-decomposition.md) | [TD1](trend-divergence-tasks.md#td1-route-chain)；级别递归 | `build_structure_state` type_chain 回归 | `normalize` / 级别层级定义 | 显式映射（已补 buy-sell-multi-level-spec §5 买卖点级别定理） |
| 36 | 走势类型连接结合性 | 结合律允许重组，但不能改写已确认结构事实；多义性不是含糊性。 | [trend-ambiguity-combination-law §2.1](trend-ambiguity-combination-law.md) | [TD1](trend-divergence-tasks.md#td1-route-chain) | `same_level_decomposition_mode` 回归 | `build_structure_state` | 显式映射（zhongshu + trend-divergence 矩阵） |
| 37 | 背驰的再分辨 | 无趋势无背驰；a+A+b+B+c 中 A、B 必须同级别；c 必为次级别且必含 B 的第三类买卖点，c 必创新高/新低；b 级别 ≤ c。 | [trend-divergence-spec §4](trend-divergence-spec.md) | [TD2](trend-divergence-tasks.md#td2-trend-divergence) | `test_analyze_chanlun_signals_marks_trend_divergence_*` | `divergence.trend.departure_confirmed` / `reference_zs_id` | 显式映射（已补矩阵 + spec §4 结构约束） |
| 38 | 走势类型连接的同级别分解 | 同级别分解具有唯一性；多义不等于任意。 | [trend-ambiguity-combination-law §2.2](trend-ambiguity-combination-law.md) | [TD1](trend-divergence-tasks.md#td1-route-chain) | `same_level_decomposition_mode` 回归 | `build_structure_state` | 显式映射（zhongshu + trend-divergence 矩阵） |
| 39 | 同级别分解再研究 | 中枢震荡内 Ai 与 Ai+2 力度比较（机械节奏）；节奏只服务监视。 | [chanlun-rule-spec](chanlun-rule-spec.md) 节奏附录；[trend-divergence-spec](trend-divergence-spec.md) | [TD4](trend-divergence-tasks.md#td4-output-fields) | `oscillation_rhythm_state` 回归 | `_build_oscillation_rhythm_state` | 显式映射（zhongshu + trend-divergence 矩阵） |
| 40 | 同级别分解的多重赋格 | Ai 与 Ai+2 盘整背驰演化出高一级别中枢；同级别分解可在多级别自动换档（赋格式多层操作）。 | [trend-ambiguity-combination-law §2.3](trend-ambiguity-combination-law.md) | [TD4](trend-divergence-tasks.md#td4-output-fields)；多级别联立 | `oscillation_rhythm_state` 回归 | `_build_oscillation_rhythm_state` | 显式映射（已补 trend-ambiguity-combination-law §2.5） |
| 43 | 有关背驰的补习课 | 背驰-转折定理；背驰级别 = 当下走势级别（必然拉回最后中枢）vs 背驰级别 < 当下走势级别（须先形成更大中枢）两种转折方式；走势类型分解原则（某级别走势不可能出现更大级别中枢）。 | [trend-divergence-spec §7](trend-divergence-spec.md)；[buy-sell-multi-level-spec §4](buy-sell-multi-level-spec.md) | [TD4](trend-divergence-tasks.md#td4-output-fields)；[BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | `post_divergence_route` 回归 | `_build_post_divergence_route` | 显式映射（已补进 trend-divergence-original-review-matrix，并补 spec §4 两种转折方式） |
| 44 | 小级别背驰引发大级别转折 | 小背驰-大转折定理：小级别顶/底背驰引发大级别转折的必要条件是最后一个次级别中枢出现第三类卖/买点（只有必要、无充分条件）。 | [buy-sell-multi-level-spec §4](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | 小转大降级模板回归（待补） | 多级别联立消费降级 | 显式映射（已补矩阵 + spec §4 必要条件） |
| 53 | 三类买卖点的再分辨 | 三类买卖点再分辨、小转大补位、级别切换原则。 | [buy-sell-multi-level-spec](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | buy/sell 回归 | buy_1..sell_3 判定 | 显式映射（zhongshu + buy-sell 矩阵） |
| 61 | 区间套定位标准图解 | 围绕同一中枢的任意两段都可比较力度；背驰段内逐级定位（背驰段的背驰段…）即区间套；第二类卖点可与某中枢第三类卖点重合。 | [buy-sell-multi-level-spec §3](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer)；precision_entry | `build_lower_timeframe_precision_entry` 回归 | `precision_entry.nested_from` | 显式映射（已补进 buy-sell-multi-level-original-review-matrix） |
| 62 | 分型、笔与线段的关系 | 线段必须建立在笔的结构稳定性之上，不能脱离分型、笔的确认链。 | [base-structure-spec](base-structure-spec.md)；[segment-spec](segment-spec.md) | [S1 线段主链](segment-tasks.md#s1-segment-bootstrap) | `test_segment.py` / `test_chanlun_analysis.py` | `fractal.py` / `bi.py` / `segment.py` | 显式映射（base-structure + segment 矩阵） |
| 63 | 替代与确认的边界 | 替代与确认影响线段起段、延伸、终结；候选态不得误写为已确认。 | [segment-spec](segment-spec.md) | [S2 确认态](segment-tasks.md#s2-confirmation) | `test_segment.py` 确认/未确认回归 | `segment.py`（`is_confirmed` / pending） | 显式映射（base-structure + segment 矩阵） |
| 65 | 再说分型、笔、线段 | 包含关系必须先统一处理，否则分型与结构漂移。 | [base-structure-spec](base-structure-spec.md) | 基础结构主链 | 包含/标准化回归 | `normalize.py` / `data/cleaner.py` | 显式映射（base-structure 矩阵） |
| 67 | 线段的划分标准 | 起段三笔公共重叠；反向特征序列分型；第一/第二种情况。 | [segment-spec](segment-spec.md) | [S1 线段主链](segment-tasks.md#s1-segment-bootstrap) | `test_segment.py` 第一/第二种情况回归 | `segment.py` | 显式映射（base-structure + segment 矩阵） |
| 71 | 线段划分标准的再分辨 | 第一二元素存在缺口时，通过再分辨决定旧段终结还是延续。 | [segment-spec](segment-spec.md) | [S3 重写/吸收](segment-tasks.md#s3-rewrite-gap) | `test_segment.py` 缺口再分辨回归 | `segment.py`（gap 再分辨） | 基本一致（工程近似但主路径闭环） |
| 78 | 继续说线段的划分 | 第二种情况第二特征序列的包含处理；缺口后 A+B+C 只能算一个线段。 | [segment-spec](segment-spec.md) | [S3 重写/吸收](segment-tasks.md#s3-rewrite-gap) | 吸收/合一回归 | `segment.py`（`absorbed_segment_ids`） | 基本一致（捷径蕴含分型判据；A+B+C 合一待显式对齐） |
| 83 | 笔-线段与线段-最小中枢 | 笔级最小中枢稳定性差，线段级更稳；中枢主口径选线段级。 | [zhongshu-dual-track-spec](zhongshu-dual-track-spec.md) | ZS 主辅分离 | 主辅分离回归 | `zhongshu.py`（`structure_level="segment"`） | 显式映射（zhongshu 矩阵） |
| 86 | 走势分析中必须杜绝一根筋思维 | 同一买卖点的操作意义随大级别位置（中枢上移/下移/震荡）而不同；趋势转折后第一段反弹卖点常即最后中枢第三类卖点，须动态分级。 | [buy-sell-multi-level-spec §5](buy-sell-multi-level-spec.md) | [BS5](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | 多级别联立消费降级回归 | 多级别联立消费降级 | 显式映射（已补 buy-sell-multi-level-spec §5 动态分级） |
| 92 | 中枢震荡的监视器 | 中枢震荡监视器（Z/Zn）用于强弱与变盘预警，不直接替代买卖点定义。 | [chanlun-rule-spec](chanlun-rule-spec.md) 监视器附录；[zhongshu-consumer-display-examples](zhongshu-consumer-display-examples.md) | ZS 消费收口 | `zs_monitor_*` 回归 | `zs_monitor_alert` / `zs_monitor_bias` | 显式映射（zhongshu 矩阵） |
| 102 | 再说走势必完美 | 走势必完美对应一种最强唯一分解（类比记数法）；级别依次升大；区间套是走势必完美的应用；任何高级别改变必须先由低级别开始；走势可完全分类。 | [trend-type-decomposition](trend-type-decomposition.md)；[trend-divergence-spec §2](trend-divergence-spec.md) | [TD1](trend-divergence-tasks.md#td1-route-chain) | `build_structure_state` type_chain 唯一性回归 | `build_structure_state` / `type_chain` | 显式映射（已补 trend-type-decomposition 理论根基） |

## 待补课次（技术课但尚未被任何 review 矩阵引用）

以下课次属于技术/结构范畴，但当前既无 review 矩阵行、也无 spec 条款，作为下一轮补课候选：

- 第15课：没有趋势，没有背驰（背驰前置原则，可与 37 课合并补）
- 第19课：学习缠中说禅技术分析理论的关键
- 第30课：缠中说禅理论的绝对性
- 第46课：每日走势的分类
- 第54课：一个具体走势的分析
- 第79课：分型的辅助操作
- 第81课：图例、更正及分型、走势类型的哲学本质
- 第82课：分型结构的心理因素
- 第84课：本 ID 理论一些必须注意的问题
- 第89/90课：中阴阶段的具体分析 / 结束时间辅助判断
- 第91/93/99课：走势结构的两重表里关系
- 第104课：几何结构与能量动力结构
- 第107课：如何操作短线反弹
- 第108课：何谓底部（月线中期走势演化）

## 覆盖缺口汇总（按优先级）

0. **矩阵范围（本轮扩至 29 课）**：覆盖全部结构技术课（分型/笔/线段/中枢/走势类型/背驰/买卖点）。仍有 15/19/30/46/54/79/81/82/84/89-91/93/99/104/107/108 等技术课未被任何 review 矩阵引用，见上文「待补课次」。
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
