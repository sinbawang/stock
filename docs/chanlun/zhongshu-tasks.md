# 中枢模块任务拆解

本页把“标准线段级中枢主实现”这个大 epic 拆成可执行任务。总表只保留进度；这里负责说明接下来还要做什么、依赖什么、做到什么算完成。

## 关联总表条目

- 标准线段级中枢主实现
- 类中枢与标准中枢字段完全拆分
- 中枢严格定义图示库
- `tech.json` 严格结构状态字段补齐
- confirmed / pending / auxiliary 三态统一（中枢部分）
- 小程序 / 报告端主辅口径显式展示

## 已完成收口

- 主批量发布链已锁定 `segment` 为标准中枢唯一主口径。
- `identify_zhongshu(..., structure_level="segment")` 已只吃已确认线段。
- 未确认尾段不再直接污染标准中枢主链；若线段链收缩回单个未确认尾段，标准中枢整体清空而不残留旧中心。
- `segment.is_reclaimed` / `absorbed_segment_ids` 已下沉到尾段解释层、`segments.csv` 和 miniapp `summary/detail`。
- 多组真实 fixture 的 bootstrap / gap / reclaim / reverse_break 边界已被 focused regression 锁住。

## 当前 epic 看板

| ID | 任务 | 状态 | 依赖 | 完成定义 |
| --- | --- | --- | --- | --- |
| ZS1 | 线段级标准中枢进入条件稳定 | 进行中 | `segment` S1-S3 | 同一组已确认线段总能得到同一组进入段、进入区间和首个标准中枢 |
| ZS2 | 完成 / 扩张 / 新中枢切换状态机 | 待完成 | ZS1 | 能稳定区分“原中枢继续扩张”与“原中枢完成后出现新中枢” |
| ZS3 | reclaim / 重写 / gap 交界统一 | 进行中 | `segment` S3 | 上游边界重算后，中枢不会残留旧区间，也不会漏清空 / 漂移 |
| ZS4 | 标准中枢 vs 类中枢字段完全拆分 | 进行中 | ZS1-ZS3 | 主链字段、辅助字段、消费展示全部能区分标准口径与辅助口径 |
| ZS5 | 输出与消费层三态收口 | 进行中 | ZS2, ZS4 | `confirmed / pending / auxiliary` 在 `tech.json`、报告、小程序中语义一致 |
| ZS6 | review 样例与真实回归闭环 | 进行中 | ZS1-ZS5 | 关键真实窗口都有图示、消费样例和 regression gate |

## 按任务类型看板

阅读方式：

- 文档任务：理论规格、review 入口、样例卡片、字段盘点、文档-测试映射。
- 测试任务：真实样本 gate、synthetic gate、focused regression、回放探测工具校验。
- 代码任务：中枢状态机、字段生成、消费输出、重写/清空规则这类直接改变结果的实现。
- 优先级：`高` 表示当前中枢主线直接卡住；`中` 表示主线并行收口项；`低` 表示保留但不是本轮第一落点。

当前重点：

1. 测试：找到真实 `1m pre_breakout` 样本，并补齐 `tech.json` 与 publish 双 gate。
2. 代码：优先推进 `ZS2` 完成 / 扩张 / 新中枢状态机，以及 `ZS3` reclaim / gap 交界统一。
3. 文档：把 `1m pre_breakout` 与 confirmed live 卡片接到第 92 课 review 主链路。

### 文档任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| D1 | review 入口与样例库 | 高 | 把 `1m pre_breakout` 与 confirmed live 卡片补进第 92 课链路 | 进行中 | `pre_breakdown` 主卡片已到位，`pre_breakout` 与 confirmed live 卡片仍缺。 |
| D3 | 文档-测试映射表 | 高 | 把 `1m pre_break*` 四条 gate 与 review 卡片一一对应 | 进行中 | `pre_breakdown` 双 gate 已落地，`pre_breakout` 仍缺真实样本。 |
| D2 | 主辅字段盘点与命名约束 | 中 | 继续把扁平字段的“主口径 / 辅口径”归属写死 | 进行中 | ZS4.1 已完成首版高风险字段盘点，剩余是约束继续前推到消费端文档。 |

### 测试任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| T2 | `1m pre_breakout` 真实样本链 | 高 | 找到真实样本并补齐 `tech.json` + publish gate | 待完成 | 当前只有 synthetic gate，没有真实落盘样本。 |
| T4 | `1m pre_break*` 探测工具 | 高 | 用 `--auto-find` 扫描缩短真实样本发现路径 | 进行中 | `build/probe_intraday_prebreak_sample.py` 已支持自动扫描，下一步是稳定跑候选标的。 |
| T1 | `1m pre_breakdown` 真实样本链 | 中 | 维持 `tech.json` / 文案 / publish 三层真实回归 | 进行中 | 独立真实 `tech.json` gate、文案回归、publish regression 都已落地。 |
| T3 | reclaim / gap / rewrite focused regressions | 中 | 继续锁复杂交界，不让旧中枢幽灵回归 | 进行中 | bootstrap / gap / reclaim / reverse_break 已有多组真实 fixture regression，复杂交界仍待补强。 |

### 代码任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| C1 | ZS1 进入条件稳定 | 高 | 锁定进入段 / 离开段边界与首次成立解释 | 进行中 | 输入 segment 资格已大体收口，边界解释与首次成立 focused regression 仍待补。 |
| C2 | ZS2 完成 / 扩张 / 新中枢状态机 | 高 | 把状态机从解释文本落到稳定机器字段 | 待完成 | 这是当前最核心的主实现缺口之一。 |
| C3 | ZS3 reclaim / 重写 / gap 交界统一 | 高 | 解决旧中枢残留、过早吞并与重算顺序漂移 | 进行中 | 属于当前代码层高优先 blocker。 |
| C4 | ZS4-ZS5 字段与消费收口 | 中 | 把主辅分轨、pending / confirmed / auxiliary 三态继续落到主产物 | 进行中 | `pre_breakdown` 链已打通，`pre_breakout` 与 confirmed live 卡片仍拖住整体收口。 |

## 里程碑视图

阅读方式：

- `ZSx` 表示 epic。
- `ZSx.y` 表示可以单独排期、单独 review、单独验收的阶段任务。
- 若某个 `ZSx.y` 未完成，原则上不要提前宣称对应 epic 已收口。

| 里程碑 | 目标 | 当前状态 | 主要产出 |
| --- | --- | --- | --- |
| ZS1.1 | 锁定标准中枢输入 segment 集 | 进行中 | 输入边界规则、首个中枢进入条件 |
| ZS1.2 | 锁定进入段 / 离开段边界 | 待完成 | 边界判定规则、segment -> zhongshu 解释页 |
| ZS1.3 | 锁定首次成立回归样例 | 待完成 | focused regression + review 示例 |
| ZS2.1 | 定义完成 / 扩张 / 新中枢状态图 | 待完成 | 状态机草图、字段草案 |
| ZS2.2 | 绑定再进入 / 回抽 / 区间重叠规则 | 待完成 | 判定顺序、冲突裁决规则 |
| ZS2.3 | 把状态机落到机器字段 | 待完成 | machine-readable 状态字段、消费契约 |
| ZS3.1 | 统一 reclaim / 吸收后的清空与重建 | 进行中 | 中枢重算顺序、旧中心清理规则 |
| ZS3.2 | 统一 gap defer / invalidated 交界 | 待完成 | gap 交界重算优先级 |
| ZS3.3 | 锁住复杂重写回归集 | 待完成 | focused regressions |
| ZS4.1 | 列清主产物混用字段 | 进行中 | 字段盘点表 |
| ZS4.2 | 完成标准中枢 / 类中枢命名拆分 | 进行中 | 字段命名表、降级约束 |
| ZS4.3 | 收口多消费端展示 | 进行中 | summary / report / miniapp 一致展示 |
| ZS5.1 | 收口中枢相关监视字段 | 进行中 | 字段定义、生成逻辑 |
| ZS5.2 | 收口三态文案与机器字段 | 进行中 | confirmed / pending / auxiliary 契约 |
| ZS5.3 | 补真实 `1m` 预警样本 | 进行中 | `1m` 发布样例与 review 卡片 |
| ZS6.1 | 补进入段 / 本体 / 离开段图示 | 待完成 | 图示案例 |
| ZS6.2 | 补主辅冲突与 pre_break 样例 | 待完成 | 对照案例页 |
| ZS6.3 | 样例与 regression 一一绑定 | 进行中 | 文档-测试映射表 |

## 任务拆分

### ZS1 线段级标准中枢进入条件稳定

目标：先把“哪些线段有资格组成标准中枢”说死，再讨论完成态和扩张态。

#### ZS1.1 锁定标准中枢输入 segment 集

- 明确标准中枢只基于已确认线段，不接受未确认尾段直接入场。
- 明确线段链被回收、合并、缩回单个未确认尾段时，中枢是否必须整体清空。
- 明确 `segment` 层 restart / overlap 修正对中枢输入集合的影响边界。

产出：

- 一份“标准中枢输入 segment 资格表”。
- 一组“必须清空 / 可以保留 / 必须重建”的判定规则。

#### ZS1.2 锁定进入段 / 离开段边界

- 明确进入段、离开段、重回中枢时的 segment 边界取值。
- 明确 segment 边界右移、左移时，首次成立中枢的区间如何同步变更。
- 明确“离开失败重新并回中枢”和“真正离开后形成新结构”的判定口径。

产出：

- 一页 `segment -> zhongshu` 边界解释说明。
- 一套进入段 / 离开段最小例子。

#### ZS1.3 锁定首次成立回归样例

- 补一页“segment 边界变化如何影响 zhongshu 首次成立”的 review 示例。
- 为首次成立补 focused regression，避免首个中枢成立位置漂移。
- 确保 repeated rebuild / publish 对首个标准中枢给出同一结果。

产出：

- focused regression fixture。
- review 示例页锚点。

验收：

- 同一窗口重复重算后，不会因为尾段解释变化得到不同首个标准中枢。
- `segment` 层的 restart / overlap 修正不会让中枢首区间无解释地左移或右移。

退出条件：

- reviewer 能明确回答“为什么这个中枢从这里开始”。
- 自动化回归能锁住首个中枢的进入段和区间。

<a id="zs2-state-machine"></a>
### ZS2 完成 / 扩张 / 新中枢切换状态机

目标：把“中枢还在、刚完成、还是已经换成新中枢”拆成统一状态机，而不是分散在解释文本里。

#### ZS2.1 定义完成 / 扩张 / 新中枢状态图

- 定义何时判定“原中枢继续扩张”，何时判定“原中枢已完成”。
- 定义哪些事件只会改变中枢区间，哪些事件会切换到新中枢。
- 画出最小状态图，避免后续实现仍按 case-by-case 补丁推进。

产出：

- 中枢状态图草案。
- 术语表：扩张、完成、监视中、新中枢候选。

#### ZS2.2 绑定再进入 / 回抽 / 区间重叠规则

- 定义离开段之后的回抽、再进入、区间重叠对状态切换的影响。
- 明确“重新进入原中枢”与“在原中枢之后生成新中枢”的裁决顺序。
- 明确 pending 监视态是否允许继续向下游暴露强结论。

产出：

- 判定顺序清单。
- 典型冲突案例表。

#### ZS2.3 把状态机落到机器字段

- 把“完成态”与“监视态 / pending 态”拆成稳定 machine-readable 字段。
- 明确下游只能消费哪些强状态，哪些只能显示成 watch / pending。
- 同步定义状态变化时 summary / publish 层应该如何表现。

产出：

- 状态字段草案。
- 消费契约草案。

验收：

- 标准中枢完成、扩张、新中枢三种状态不会互相复用同一字段解释。
- 下游买卖点绑定最近中枢时，不再因为完成态漂移而改绑到不同中枢。

退出条件：

- reviewer 能明确回答“这个中枢现在到底是完成、扩张还是监视中”。
- 下游绑定最近中枢时，不再依赖额外人工解释。

<a id="zs3-rewrite-gap"></a>
### ZS3 reclaim / 重写 / gap 交界统一

目标：把最容易漂移的交界条件收口，避免中枢层继续残留“旧中心幽灵”。

#### ZS3.1 统一 reclaim / 吸收后的清空与重建

- 明确当上游线段被 reclaim、吸收或边界重算时，中枢层如何清空、重建或保留。
- 明确“旧中枢整体废弃”和“旧中枢区间重算”之间的裁决规则。
- 约束中枢层不能沿用已失效 segment chain 的缓存结果。

产出：

- 中枢重算顺序清单。
- 旧中心清理规则。

#### ZS3.2 统一 gap defer / invalidated 交界

- 统一“gap 候选失效但重写成立”“gap false defer 落地后再进入下一轮”的中枢重算顺序。
- 明确何时先清空旧中枢，何时允许等待下一轮结构落定后再重建。
- 明确这一路径上 pending / confirmed 是否允许临时共存。

产出：

- gap 交界优先级清单。
- pending / confirmed 共存红线。

#### ZS3.3 锁住复杂重写回归集

- 补 focused regressions，专门锁定“旧中枢不得残留”和“新中枢不得被过早吞掉”两类错误。
- 把 repeated rebuild / publish 纳入最小回归集，避免只在单次本地运行正确。
- 至少绑定一组 overlap/reuse 和一组 deferred->invalidated 真实窗口。

产出：

- focused regression 清单。
- 真实窗口映射表。

验收：

- 复杂线段重写后，中枢列表不会混入基于旧 segment chain 的幽灵中心。
- 相同真实窗口在 repeated rebuild / publish 中能保持同一标准中枢结果。

退出条件：

- 复杂交界问题不再靠人工删缓存或解释历史结果来兜底。
- regression gate 能直接指出是哪类交界又漂了。

### ZS4 标准中枢 vs 类中枢字段完全拆分

目标：让 reviewer 和消费者不再猜“这个字段说的是标准中枢还是类中枢”。

#### ZS4.1 列清主产物混用字段

- 列出主产物里所有混用标准中枢与类中枢的字段。
- 标出每个字段当前的来源、消费方、误用风险。
- 明确哪些字段已经是主口径，哪些仍是历史兼容字段。

产出：

- 字段盘点表。
- 风险等级清单。

当前结论（首版）：

- 数组层命名已经基本分轨，真正高风险的不在 `zhongshus` / `lei_zhongshus` 本身，而在一批未显式带来源命名空间的扁平字段。
- 当前实现里 `structure_state`、`same_level_decomposition_mode`、`post_divergence_route`、`oscillation_rhythm_state`、`zs_monitor_*` 这批字段，都是沿 `zhongshus -> current_zs` 主口径链生成；但双轨规范又允许同类语义挂到 `zhongshus` 与 `lei_zhongshus` 对象里，消费端若不显式写“主口径 / 辅口径”，就会把它们误读成“中枢总称字段”。
- 因此 ZS4 的真正收口重点不是重命名 `zhongshus`，而是给扁平字段补“来源归属”和“冲突时谁优先”的稳定约束。

字段盘点表（首版）：

| 字段 / 字段组 | 当前主要来源 | 目标归类 | 当前风险 | 下一动作 |
| --- | --- | --- | --- | --- |
| `zhongshus` | 标准中枢主数组 | 标准中枢主口径 | 风险低。命名已清楚，但仍可能在文本里被和辅助口径混称。 | 继续保持为所有主结论默认来源。 |
| `lei_zhongshus` | 类中枢辅助数组 | 类中枢辅助口径 | 风险中。字段名清楚，但报告 / 卡片文案仍可能直接简称“中枢”。 | 在消费端统一显示“类中枢 / 辅助”。 |
| `zhongshus_theory` / `zhongshus_practical` | 标准中枢双模式输出 | 标准中枢主口径的 theory / practical 分层 | 风险中。容易和 `lei_zhongshus_*` 一起被看成同层多数组。 | 明确它们是“同一主口径的双模式”，不是主辅分轨。 |
| `lei_zhongshus_theory` / `lei_zhongshus_practical` | 类中枢双模式输出 | 类中枢辅助口径的 theory / practical 分层 | 风险中。容易和标准中枢双模式并列后被误读成等权主输出。 | 在图表 / JSON 文档中强调“辅助双模式”。 |
| `structure_state.*` | 当前由 `build_structure_state(raw_bars, zhongshus)` 生成 | 扁平主口径字段 | 风险高。字段名不带 `zhongshu`，消费端容易把它当成“总结构事实”，忽略其当前只绑定标准中枢链。 | 在字段契约里补“来源=标准中枢主链”。 |
| `same_level_decomposition_mode` | 当前主运行链扁平输出 | 扁平主口径字段 | 风险高。语义属于中枢 / 走势分解 gate，但名称未体现它默认跟随主口径。 | 补字段归属说明，并规定辅口径不得用它升级 confirmed。 |
| `post_divergence_route` | 当前主运行链扁平输出 | 扁平主口径字段 | 风险高。消费端最容易把它直接解读为结构确认，且双轨规范允许数组内也携带同名字段。 | 明确“顶层字段默认主口径；数组内同名字段必须分轨解释”。 |
| `route_level_from` / `route_level_to` | 跟随 `post_divergence_route` 扁平输出 | 扁平主口径上下文字段 | 风险中高。若不写清来源，容易被类中枢去向字段借壳复用。 | 与 `post_divergence_route` 一起归档为主口径上下文。 |
| `recomposition_applied` | 规格已定义，落地主链仍待继续收口 | 待定的主口径解释字段 | 风险中。尚未稳定主产物时最容易被不同入口各自解释。 | 在真正落主产物前，不允许被消费端当必备字段。 |
| `oscillation_rhythm_state` | 当前主运行链扁平输出 | 扁平主口径下的辅助监视字段 | 风险高。字段位置是顶层，容易被误读成独立结论；字段语义又是辅助监视。 | 保留顶层输出，但明确它只能辅助解释主口径。 |
| `zs_monitor_midline` / `zs_monitor_zn_series` / `zs_monitor_bias` / `zs_monitor_alert` | 当前主运行链扁平输出 | 扁平主口径下的监视字段 | 风险高。名字带 `zs`，但不区分标准 / 类中枢；双轨规范又允许数组内携带同类字段。 | 规定顶层 `zs_monitor_*` 默认只代表主口径监视；辅口径若存在，必须挂在 `lei_zhongshus[*]` 内解释。 |
| `summary.conclusion` / `summary.note` / `analysis_text` / `advice_text` 中的中枢结论句 | 文本层，多由主链字段回填 | 文本载体，不是独立结构字段 | 风险高。最容易把辅助口径、watch、pending 美化成主口径 confirmed。 | 为每类文本句补“引用哪个结构字段”的映射说明。 |
| `zhongshus_bi` / `segment_based_zhongshu` 等历史命名 | 历史命名残留风险 | 禁止继续对外扩散 | 风险中。会让 reviewer 无法快速判断到底是标准中枢还是类中枢。 | 继续列为禁名，不再新增任何对外入口。 |

风险等级清单（按优先级）：

1. 最高风险：`structure_state.*`、`same_level_decomposition_mode`、`post_divergence_route`、`zs_monitor_*`。这些字段当前实际跟随标准中枢主链，但名字本身没有写明“主口径”，最容易被消费端或 review 文案混成“中枢总称字段”。
2. 次高风险：`oscillation_rhythm_state`、`route_level_from/to`、文本摘要结论。它们容易被拿来越级解释主状态，或者被借去为辅助口径背书。
3. 中风险：`zhongshus_theory/practical` 与 `lei_zhongshus_theory/practical`。命名本身不算错，但没有补足“主辅”和“theory/practical”是两套正交维度的说明。
4. 低风险：`zhongshus`、`lei_zhongshus` 本体数组名。核心问题不是名字，而是消费者有没有按主辅分层展示。

#### ZS4.2 完成标准中枢 / 类中枢命名拆分

- 逐项明确哪些字段只能表达标准中枢，哪些只能表达辅助类中枢，哪些必须双轨并存。
- 统一命名、降级策略和缺省展示顺序。
- 明确是否需要为历史字段保留兼容层。

产出：

- 命名对照表。
- 降级与兼容策略。

命名拆分原则：

1. `zhongshu` 与 `lei_zhongshu` 是主辅维度；`theory` 与 `practical` 是模式维度。两者必须正交表达，不得混成一套命名规则。
2. 数组字段优先承担“对象归属”表达；顶层扁平字段优先承担“当前主结论”表达。
3. 只要字段会被下游直接拿来写结论、预警或买卖点，它默认必须先绑定标准中枢主口径；辅口径只能以显式命名或内嵌对象方式出现。
4. 若某字段允许主辅双轨并存，则顶层版本默认代表主口径，辅口径版本必须挂在 `lei_zhongshus[*]` 或明确的 `lei_` 命名空间下。

命名对照表（首版）：

| 字段类别 | 推荐主口径命名 | 推荐辅口径命名 | 是否允许双轨并存 | 备注 |
| --- | --- | --- | --- | --- |
| 标准中枢对象数组 | `zhongshus` | 不适用 | 否 | 这是主口径对象容器，不需要再加 `segment_` 前缀。 |
| 类中枢对象数组 | 不适用 | `lei_zhongshus` | 否 | 必须显式保留 `lei_` 前缀。 |
| 标准中枢双模式数组 | `zhongshus_theory` / `zhongshus_practical` | 不适用 | 否 | 表示同一主口径的两种模式，不是主辅并列。 |
| 类中枢双模式数组 | 不适用 | `lei_zhongshus_theory` / `lei_zhongshus_practical` | 否 | 只能解释辅助结构，不得被消费端默认为主输出。 |
| 标准中枢对象内基础字段 | `id`、`structure_level=segment`、`start_segment_id`、`end_segment_id`、`zs_low`、`zs_high` | 不适用 | 否 | 只允许出现在 `zhongshus[*]`。 |
| 类中枢对象内基础字段 | 不适用 | `id`、`structure_level=bi`、`start_bi_id`、`end_bi_id`、`zs_low`、`zs_high` | 否 | 只允许出现在 `lei_zhongshus[*]`。 |
| 顶层主结构状态字段 | `structure_state.*` | 不建议单独设顶层辅版本 | 否 | 顶层 `structure_state` 默认只代表标准中枢主链。 |
| 顶层主口径分解 gate | `same_level_decomposition_mode` | 不建议单独设顶层辅版本 | 条件允许 | 若辅口径也要表达，优先挂到 `lei_zhongshus[*].same_level_decomposition_mode`。 |
| 顶层主口径去向字段 | `post_divergence_route`、`route_level_from`、`route_level_to` | 不建议单独设顶层辅版本 | 条件允许 | 顶层永远先解释主口径；辅口径若存在，必须内嵌到辅数组对象里。 |
| 顶层主口径监视字段 | `zs_monitor_midline`、`zs_monitor_zn_series`、`zs_monitor_bias`、`zs_monitor_alert` | 不建议单独设顶层辅版本 | 条件允许 | 顶层 `zs_monitor_*` 默认只代表主口径监视。 |
| 顶层辅助节奏字段 | `oscillation_rhythm_state` | 不建议单独设顶层辅版本 | 条件允许 | 它是辅助监视字段，但当前仍默认跟随主口径链输出。 |
| 对象内附加解释字段 | `zhongshus[*].post_divergence_route` 等 | `lei_zhongshus[*].post_divergence_route` 等 | 是 | 允许双轨并存，但消费者必须显式标主辅来源。 |
| 文本主结论字段 | `summary.conclusion`、`analysis_text` 中的中枢主结论句 | `summary.note` 或辅助说明句 | 否 | 文本主结论默认引用 `zhongshus` 路径。 |
| 历史兼容禁名 | 禁止新增 `segment_based_zhongshu`、`zhongshus_bi` | 禁止新增 | 否 | 只允许在迁移说明中被提及，不得作为新产物字段。 |

默认归属规则：

- 顶层字段默认归主口径：`structure_state.*`、`same_level_decomposition_mode`、`post_divergence_route`、`route_level_from/to`、`oscillation_rhythm_state`、`zs_monitor_*` 只要出现在顶层，就默认代表标准中枢主链。
- 辅口径字段默认内嵌：类中枢若也要表达同类信息，优先写到 `lei_zhongshus[*]` 对象内，而不是再造一组平行顶层扁平字段。
- 文本默认主结论优先：`summary.conclusion`、买卖点标题、预警卡片标题都必须优先解释主口径；辅口径只能放进 `note`、附注、辅助卡片或图例二层说明。
- 双模式不等于双口径：`theory/practical` 只回答“同一口径怎么算”，不回答“主结论从哪条口径来”。

降级与兼容策略（首版）：

| 场景 | 处理策略 | 禁止做法 |
| --- | --- | --- |
| 顶层字段只有主口径版本，辅口径也有内部结果 | 顶层继续只暴露主口径；辅口径放进 `lei_zhongshus[*]` 或辅助文本。 | 新增一组无前缀顶层平行字段，制造第二套“主字段幻觉”。 |
| 主辅都要表达同名附加语义 | 允许在 `zhongshus[*]` 与 `lei_zhongshus[*]` 内对象级并存。 | 在顶层把辅口径字段覆盖主口径字段。 |
| 顶层主口径字段缺失 | 一律按 `unknown` / 降级处理，并保留字段缺失说明。 | 因为辅口径有值，就把顶层字段补写成主口径已确认。 |
| `same_level_decomposition_mode=dual_interpretation_pending` | 所有高层结论统一降级为 pending/watch。 | 因辅口径更激进就升级为 confirmed。 |
| `zs_monitor_alert` 只有辅口径预警 | 只允许输出“类中枢提示，未触发主预警”。 | 直接把辅口径预警升格成主预警或 3B/3S 确认。 |
| 旧接口仍使用历史字段名 | 允许短期保留读兼容，不允许继续写新产物。 | 在新 JSON、文档、UI 中继续扩散历史命名。 |

兼容层策略：

1. 读兼容可以暂留，写兼容要尽快收口。也就是旧入口可以继续识别 `segment_based_zhongshu` 一类历史命名，但新产物、新文档、新消费层不再输出它们。
2. 任何新增字段必须在进入主产物前先归类到三类之一：`主口径顶层字段`、`辅口径对象内字段`、`主辅对象内双轨字段`。
3. 若未来确实需要顶层辅口径摘要，必须显式命名为 `lei_*`，而不是复用主口径扁平字段名。
4. 兼容层只解决“旧字段还能读”，不解决“旧字段还能继续作为主规范写法”。

缺省展示顺序：

1. 先显示 `zhongshus` 主结论或其顶层主口径字段。
2. 再显示 `lei_zhongshus` 辅助解释。
3. 若主辅冲突，固定输出“中枢主口径优先”。
4. theory / practical 只在需要解释分支差异时展开，不得抢到主辅分层之前。

<a id="zs43-consumer-output"></a>
#### ZS4.3 收口多消费端展示

- 同步收口 `summary/tech.json`、报告、小程序、导出产物里的命名与降级策略。
- 明确主口径 / 辅口径 / 降级解释在 UI 和 JSON 中的最小显示要求。
- 补一组“同案三栏对照”作为长期回归样本。

产出：

- 多消费端展示对照。
- 最小显示规范。

最小显示规范（首版）：

| 消费位 | 必须显示什么 | 可选显示什么 | 绝对红线 |
| --- | --- | --- | --- |
| `tech.json` 顶层 | `zhongshus` 主口径；主口径状态字段；必要的 `pending/confirmed/auxiliary` 语义 | `lei_zhongshus`、附加监视字段、辅助说明文本 | 不得只保留辅助口径却省略主口径来源。 |
| `summary.conclusion` | 主口径结论或主口径观察态结论 | 冲突说明、等待条件 | 不得把辅口径、预警态、节奏态改写成确认买卖点。 |
| 报告结构段 | 先写中枢主结论，再写类中枢辅助说明 | theory / practical 分支差异、风险附注 | 不得让辅助结论覆盖主结论顺序。 |
| 小程序首页卡片 | 轻量状态标签 + 主结论短句 | 更新时间、主口径来源提示 | 缺结构字段时不得默认打 `confirmed`。 |
| 小程序详情技术概览 | 主结构状态、pending gate、必要时补辅口径说明 | 级别映射、风险等待条件 | 不得把 `dual_interpretation_pending` 渲染成确定性方向。 |
| 小程序预警卡片 | `watch/pending` 级预警说明 | 主辅冲突附注、等待确认条件 | 不得把预警卡片标题写成 confirmed 3B/3S。 |
| 图表图例 / 标注 | `zhongshus` 与 `lei_zhongshus` 分层图例；pending 单独标注 | theory / practical 分层、segment 双模式说明 | 不得把类中枢、pending、confirmed 混成同色同标签。 |
| 导出 / 发布 JSON | 主口径字段、辅口径字段、状态字段分别可机读 | 文本摘要、图表引用、发布层派生标签 | 不得只剩文本结论，没有可定位的主结构字段。 |

按字段类别的显示要求：

| 字段类别 | `tech.json` | 报告 | 小程序 | 图表 / 导出 |
| --- | --- | --- | --- | --- |
| `zhongshus` | 必须保留 | 必须作为主结论来源 | 必须优先消费 | 必须主图例显示 |
| `lei_zhongshus` | 建议保留 | 只作辅助说明 | 可在详情页或附注显示 | 必须与主口径分层 |
| `structure_state.*` | 有则优先机读 | 可翻译为“已完成 / 进行中 / 切换中” | 详情页优先展示 | 可作悬浮说明，不代替对象图例 |
| `same_level_decomposition_mode` | 必须参与状态降级 | 必须体现在语气降级 | 必须影响标签级别 | 可作附注，不直接画成买卖点 |
| `post_divergence_route` + `route_level_*` | 保留去向候选和级别映射 | 可写“观察期 / 待级别闭合” | 预警或结构卡片可显示 | 不得单独画成 confirmed 反转 |
| `oscillation_rhythm_state` | 仅作辅助字段 | 仅作节奏说明 | 轻量辅助标签 | 不得覆盖主结构颜色 |
| `zs_monitor_*` | 保留主口径监视状态 | 必须保留“未确认”措辞 | 统一按 watch/pending | 可画风险边界，不得画 confirmed 3B/3S |
| 文本摘要 (`analysis_text` / `advice_text`) | 只能解释结构字段 | 允许展开 | 可做可读性补充 | 不得替代 machine-readable 主字段 |

三处展示位最小对照规则：

1. 去向候选：`tech.json` 保留 `post_divergence_route + route_level_from/to + pending gate`；报告写“观察期 / 待级别闭合”；小程序只显示 `pending/watch`。
2. 节奏监视：`tech.json` 保留 `oscillation_rhythm_state`；报告只写“节奏偏弱 / 平衡”；小程序只显示 `auxiliary` 或轻量观察标签。
3. 预警未确认：`tech.json` 保留 `zs_monitor_alert + 未确认说明`；报告写“出现预警，但未确认三买/三卖”；小程序只显示 `watch/pending`。
4. 主辅冲突：`tech.json` 同时保留 `zhongshus` 与 `lei_zhongshus`；报告必须写“主口径优先”；图表必须分层显示，禁止同色合并。

当前发布层差距（需要后续收口）：

- `detail.json` 一侧仍偏向 `same_level_decomposition.*` 这类旧分组，而不是统一外露 `structure_state.*`、`same_level_decomposition_mode` 等扁平主入口。
- 发布层已经出现 machine-readable pending 证据，但 schema 和页面显示还没有完全按同一命名收口。
- 图表资产当前更接近 `charts/*.json` 驱动，而不是旧文档里偏图片化的示例，后续展示规范需要明确以结构化图表 JSON 为主。
- 文本层 confirmed 风险仍高，尤其容易把“预警前态”“辅助口径更激进”“节奏偏弱”偷换成强确认结论。

当前建议的消费收口顺序：

1. 先统一 `tech.json/detail.json` 的主口径字段名和 pending gate。
2. 再统一报告文案模板，保证主结论永远先于辅助说明。
3. 然后统一小程序标签体系，把 `confirmed / pending / auxiliary` 固定成三档。
4. 最后统一图表图例和导出 JSON，让对象层和文本层不再互相打架。

验收：

- reviewer 不需要靠上下文猜字段到底是标准中枢还是类中枢。
- 消费端能显式显示“主口径 / 辅口径 / 降级解释”。

退出条件：

- 新增字段时可以立刻归类到标准 / 类中枢 / 双轨并存之一。
- 已有消费者不再混读两个口径。

### ZS5 输出与消费层三态收口

目标：把中枢相关字段从“能显示”推进到“严格程度、状态、文案都一致”。

#### ZS5.1 收口中枢相关监视字段

- 收口 `zs_monitor_alert`、`zs_monitor_midline`、`zs_monitor_bias`、`same_level_decomposition_mode`、`post_divergence_route`、`oscillation_rhythm_state` 的严格口径。
- 明确哪些字段表达事实状态，哪些字段表达观察路线或风险提示。
- 明确工程近似阈值仍存在的字段，避免被误读成严格结论。

产出：

- 字段定义表。
- 严格结论 / 监视提示分类表。

分类原则：

1. 能单独支撑“已确认 / 已完成 / 主口径确认”的，才算严格结论字段。
2. 只能决定“先降级为观察 / 待确认”的，归为 pending gate 或降级 gate。
3. 只表达方向倾向、节奏、预警、风险边界的，一律归为监视字段。
4. 只要底层算法仍依赖工程映射、阈值近似或样本不足，即使已落主链，也不能包装成严格理论已闭环。

字段分类表（首版）：

| 字段 | 当前字段角色 | 严格程度分类 | 推荐对外状态 | 当前主要风险 | 当前口径 |
| --- | --- | --- | --- | --- | --- |
| `structure_state.last_completed` | 已完成结构事实 | 严格结论字段 | `confirmed` | 与 `current_ongoing` 同型时，被误读成“旧走势完全切开、当前新走势也已成立”。 | 只能说明上一段已完成，不自动确认当前新段。 |
| `structure_state.current_ongoing` | 当前进行结构事实 | 进行中事实字段 | `pending` | 把 `candidate_completion` 或 ongoing 当 confirmed。 | 一律按观察态处理，直到同级别完成条件闭合。 |
| `structure_state.relationship` | last/current 关系解释 | 关系解释字段 | `disambiguation_only` | 把 `same_type_extension`、`completed_then_new_type` 直接翻译成已确认转折。 | 只解释关系，不单独产出信号等级。 |
| `same_level_decomposition_mode` | 同级别分解降级 gate | pending gate | `confirmed_or_pending_gate` | 当前工程映射被误读成“严格唯一分解已完成”。 | `dual_interpretation_pending` 时必须统一降级；`single_confirmed` 也只代表当前工程口径已收敛，不等于全部理论缺口关闭。 |
| `post_divergence_route` | 背驰后去向候选 | 观察路线字段 | `pending_or_context` | 看见 `higher_level_reverse_trend` 就直接认定反转确认。 | 只说明当前候选去向，不单独说明结构已完成。 |
| `route_level_from` / `route_level_to` | 去向级别上下文 | 上下文字段 | `context_only` | 被当成“级别已经切换完成”的证据。 | 只补级别解释，不能独立提升结论强度。 |
| `oscillation_rhythm_state` | 中枢震荡节奏监视 | 辅助监视字段 | `auxiliary` | 用工程力度比替代严格走势类型或买卖点确认。 | 只作节奏强弱解释，不得覆盖主结构结论。 |
| `zs_monitor_midline` | 中枢中轴监视量 | 监视字段 | `pending_or_auxiliary` | 数值一旦出现，就被当成结构已确认的硬阈值。 | 只作监视参考，需要和 `zs_monitor_alert`、主结构状态联动解释。 |
| `zs_monitor_zn_series` | 中枢震荡序列监视量 | 监视字段 | `pending_or_auxiliary` | 监视序列被直接拿去替代买卖点链条。 | 只保留为震荡监视证据，不单独驱动 confirmed。 |
| `zs_monitor_bias` | 中枢偏向监视 | 监视字段 | `pending_or_auxiliary` | `strong/weak/neutral` 被误读成趋势已确认。 | 只表达当前偏向，不表达完成态。 |
| `zs_monitor_alert` | 中枢预警信号 | 预警字段 | `pending_or_auxiliary` | 只因字段落盘，就被写成 confirmed 3B/3S。 | 只能按 watch/pending 消费，必须保留“未确认”。 |
| `recomposition_applied` | 重组/再组合说明 | 工程解释字段 | `context_only` | 被当成严格理论结构重构已经闭环的证明。 | 当前更接近工程说明字段，进入主产物前不得抬成强结论。 |

严格结论 / 监视提示分类表（首版）：

| 分类 | 包含字段 | 允许说什么 | 不允许说什么 |
| --- | --- | --- | --- |
| 严格结论字段 | `structure_state.last_completed`；必要时主口径 `zhongshus` 已确认事实 | `已完成`、`主口径确认` | 不得顺手把当前 ongoing、新段、预警一起升级为 confirmed。 |
| 进行中事实字段 | `structure_state.current_ongoing` | `进行中`、`待闭合`、`观察中` | 不得写成 `已确认趋势`、`已确认买卖点`。 |
| 关系解释字段 | `structure_state.relationship` | `同型延伸`、`结构切换后运行中`、`关系未定` | 不得单独生成 confirmed/pending 标签。 |
| 降级 gate | `same_level_decomposition_mode` | `待确认`、`双解释 pending`、`当前先降级` | 不得把 gate 字段反过来包装成严格理论完成证明。 |
| 去向候选字段 | `post_divergence_route`、`route_level_from/to` | `更大级别盘整候选`、`反趋势候选`、`待级别闭合` | 不得写成 `反转已确认`、`更高级别趋势已成立`。 |
| 辅助监视字段 | `oscillation_rhythm_state`、`zs_monitor_midline`、`zs_monitor_zn_series`、`zs_monitor_bias` | `节奏偏弱`、`中轴附近震荡`、`偏强/偏弱监视` | 不得替代主结构或买卖点确认。 |
| 预警字段 | `zs_monitor_alert` | `出现预警`、`关注突破/破位风险`、`仍待确认` | 不得写成 `确认三买/三卖`。 |
| 工程说明字段 | `recomposition_applied` | `当前存在重组/再组合说明` | 不得当成严格理论判定完成的证据。 |

当前工程近似风险表：

| 字段 | 当前近似来源 | 收口前红线 |
| --- | --- | --- |
| `same_level_decomposition_mode` | 仍基于当前 `structure_state.current_structure_status` 与 `confirmation_basis` 的工程确定性映射 | 不得把 `single_confirmed` 直接宣传成严格同级别唯一分解已完全闭环。 |
| `post_divergence_route` | 仍基于现有 divergence 与尾中枢延伸语义的工程候选映射 | 不得把候选去向当成最终结构确认。 |
| `oscillation_rhythm_state` | 仍基于最近同方向确认笔 `macd_sum_abs` 力度比的工程近似 | 不得把它替代严格 `A_i/A_{i+2}` 节奏引擎结论。 |
| `zs_monitor_*` | 当前已有主链实现，但 `1m` 真实落盘样本与部分场景覆盖仍不足 | 不得因为字段能生成，就默认所有级别和场景都已理论收口。 |
| `recomposition_applied` | 仍偏协议 / 解释层，未形成统一稳定主产物语义 | 不得在消费端被当成必备结构字段。 |

使用规则：

1. 任何文案只要引用 `zs_monitor_*`、`oscillation_rhythm_state` 或 `post_divergence_route`，都必须同步判断是否需要保留 `待确认 / 观察` 语气。
2. 只有 `structure_state.last_completed` 与主口径 `zhongshus` 的已确认事实，才允许作为“确认类”文案的直接证据。
3. `same_level_decomposition_mode` 首先是降级器，不是升级器。它最重要的作用是阻止过度确认，而不是帮文案找理由升格。
4. 若字段缺失，一律按 `unknown` 或降级处理，不允许用相邻辅助字段补齐成 confirmed。

<a id="zs52-tristate-output"></a>
#### ZS5.2 收口三态文案与机器字段

- 明确 `confirmed / pending / auxiliary` 在 `summary/tech.json` 与发布产物中的文案与机器字段。
- 统一报告、小程序、导出 JSON 的状态措辞。
- 补一组 pending / auxiliary 典型反例，避免全部样例都偏 confirmed 稳态。

产出：

- 三态字段契约。
- 多端文案对照表。

三态契约原则：

1. 机器字段先判级，文案只能跟随机器字段降级或解释，不能反向升级。
2. `confirmed` 只能来自主口径已确认事实，不能由预警字段、辅助字段或执行层字段单独生成。
3. `pending` 用于“结构仍在进行 / 存在双解释 / 只到预警不达确认”的场景。
4. `auxiliary` 用于“有解释价值，但不足以决定主结论”的场景。
5. 字段缺失时一律按 `unknown -> pending/auxiliary` 降级，不允许补脑成 `confirmed`。

三态字段契约（首版）：

| 状态 | 允许的机器字段来源 | `tech.json` 推荐表达 | 报告推荐措辞 | 小程序推荐标签 | 导出 / 发布 JSON 约束 |
| --- | --- | --- | --- | --- | --- |
| `confirmed` | `structure_state.last_completed`；主口径 `zhongshus` 已确认事实；必要时明确标注的工程 `fallback_confirmed` | 保留主口径字段与确认依据；摘要可写“已确认/已完成” | `主口径确认`、`已完成`、`当前按 ... 确认处理` | `confirmed` | 必须能回溯到主口径字段，不得只剩文本结论。 |
| `pending` | `structure_state.current_ongoing`；`same_level_decomposition_mode=dual_interpretation_pending`；`zs_monitor_alert`；未闭合去向候选；线段 pending | 保留 ongoing / pending gate / 预警字段，并在摘要中显式写“待确认/观察” | `观察`、`待确认`、`等待结构闭合`、`出现预警但未确认` | `pending` 或 `watch` | 不得被导出层二次摘要成 confirmed signal。 |
| `auxiliary` | `lei_zhongshus`；`oscillation_rhythm_state`；`precision_entry.nested_from`；指标解释附注 | 保留辅助字段，但不得覆盖主状态字段 | `辅助提示`、`辅助观察`、`执行层说明` | `auxiliary` | 必须与主口径分层，不得冒充主状态。 |

三态到字段的最小映射：

| 字段 / 字段组 | 默认状态 | 可否升级 | 升级条件 | 红线 |
| --- | --- | --- | --- | --- |
| `structure_state.last_completed` | `confirmed` | 否 | 不需要升级，它本身就是已完成事实 | 不得顺带确认当前 ongoing。 |
| `zhongshus` 当前已确认主事实 | `confirmed` | 否 | 需有主口径已确认事实链 | 不得被类中枢反向覆盖。 |
| `structure_state.current_ongoing` | `pending` | 否 | 只有在后续闭合后，才转由新的确认字段接棒 | 不得把 ongoing 文案直接写成完成。 |
| `same_level_decomposition_mode=dual_interpretation_pending` | `pending` | 否 | 无 | 它是降级器，不是升级器。 |
| `same_level_decomposition_mode=single_confirmed` | `confirmed_candidate_gate` | 条件允许 | 仍需配合主口径结构事实 | 不得单凭这个 gate 宣称严格理论完全收口。 |
| `post_divergence_route` | `pending` | 否 | 无 | 只能表示去向候选，不能单独推出确认趋势。 |
| `zs_monitor_alert` | `pending` | 否 | 无 | 不得单独推出 confirmed 3B/3S。 |
| `oscillation_rhythm_state` | `auxiliary` | 否 | 无 | 不得替代结构确认。 |
| `lei_zhongshus` | `auxiliary` | 否 | 无 | 不得单独升级为 confirmed。 |
| `precision_entry.status=actionable` | `auxiliary_or_execution` | 条件允许 | 仅可提升执行层动作提示，不可提升主结构状态 | 不得单独升级主结论 confirmed。 |

多端文案对照表（首版）：

| 状态 | `summary.conclusion` / `advice_text` | 报告标题或结论句 | 小程序标签 | 图表 / 卡片说明 |
| --- | --- | --- | --- | --- |
| `confirmed` | `已确认`、`已完成`、`当前按三卖确认处理` | `主口径确认`、`当前按 ... 确认处理` | `confirmed` | 可用强标签，但必须和 pending/auxiliary 视觉分层。 |
| `pending` | `观察`、`待确认`、`等待离开后确认`、`出现预警但未确认` | `当前仍在观察期`、`等待结构闭合` | `pending` / `watch` | 必须保留“未确认”或“观察中”说明。 |
| `auxiliary` | `辅助提示`、`节奏偏弱`、`执行层说明` | `类中枢辅助视图`、`仅作辅助观察` | `auxiliary` | 只能作为二层说明，不可占据主标题。 |

典型反例约束：

| 错误场景 | 正确状态 | 正确写法 | 错误写法 |
| --- | --- | --- | --- |
| 只有 `zs_monitor_alert=pre_breakdown` | `pending` | `出现向下预警，但当前不构成确认三卖` | `确认三卖` |
| `same_level_decomposition_mode=dual_interpretation_pending` | `pending` | `当前先按观察/等待确认处理` | `方向已经确认` |
| 只有 `oscillation_rhythm_state=down_bias` | `auxiliary` | `节奏偏弱，先维持观察` | `趋势已转空` |
| 只有 `lei_zhongshus` 给出更激进去向 | `auxiliary` | `类中枢提示更激进方向，仅作辅助` | `主结论同步确认` |
| `precision_entry.status=actionable` 但高级别未闭合 | `auxiliary_or_pending` | `执行层可跟踪，但受上级别约束` | `已确认买入/卖出` |

实施顺序：

1. 先统一 `tech.json` 与 `detail.json` 的状态字段读法，禁止不同入口各自发明 `confirmed/pending/auxiliary`。
2. 再统一报告模板，把 `confirmed`、`pending`、`auxiliary` 的固定措辞写进生成逻辑。
3. 然后统一小程序标签，只保留三档主标签，避免页面各自扩展语义。
4. 最后统一导出 / 发布 JSON 的状态透传，确保二次摘要不会把 `pending` 写成 `confirmed`。

#### ZS5.3 补真实 `1m` 预警样本

- 补真实 `1m` 预警样本，避免只有 `30m/day` 级别的较稳定样例。
- 优先补 pre_break、pending、completed_then_new_type 这类过渡态。
- 把 `1m` 样例同步接入 review 文档和发布产物核验。

产出：

- `1m` 主样例列表。
- 发布产物核验清单。

当前样本判断：

- `1m` 并不是完全没样本，当前已经有 4 个稳定消费锚点，分别覆盖 watch/pending、completed_then_new_type、预警前态代理、confirmed。
- 真正缺的不是“再找一个 `1m` 文件”，而是“正式落盘的 `1m pre_breakout/pre_breakdown` 主链样本”和“与之配套的发布 / 测试锚点”。
- 因此 ZS5.3 应按三层推进：先承认已有锚点，再单列未落正式字段链的缺口，最后单列自动化与发布核验缺口。

`1m` 主样例列表（当前已稳定）：

| 场景 | 当前主锚点 | 当前状态 | 当前用途 |
| --- | --- | --- | --- |
| watch / pending | `HK.02357 1m range ongoing` | 已稳定 | 约束“已有中枢但结构未完成”不得升级确认。 |
| completed_then_new_type | `HK.01339 1m completed_then_new_type` | 已稳定 | 约束“前段已完成”不等于“当前新段已确认”。 |
| pre-warning proxy | `SH.601328 1m pre-warning proxy` | 已稳定但仍属代理 | 约束“风险迹象已出现”不等于“正式 pre_break* 已落盘”。 |
| confirmed | `SZ.000651 1m confirmed 3S` | 已稳定 | 作为 `1m` confirmed 场景对照锚点。 |

样本缺口矩阵（首版）：

| 缺口类别 | 当前现状 | 还缺什么 | 优先级 | 下一动作 |
| --- | --- | --- | --- | --- |
| 已有消费锚点 | 当前已有 4 个真实 `1m` 锚点 + 1 个 confirmed regression reference，可覆盖 watch/pending、completed_then_new_type、正式 `pre_breakdown`、pre-warning proxy 与 confirmed reference 最小闭环 | 还缺同场景多案例对照，尤其是多个 pending / 预警前态反例与真实 confirmed live 卡片 | 中 | 先不扩张数量，优先把缺正式 `pre_breakout` 链和 confirmed live 卡片的问题补齐。 |
| 正式 `1m pre_breakdown` 落盘样本 | `data/reports/000651/1m/tech.json` 已出现真实 `zs_monitor_alert=pre_breakdown`，`SH.601328 1m` 继续保留为预警前态代理 | 补一条与之配套的 review 主卡片，并继续补更多同类样本 | 最高 | 先以 `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_real_1m_pre_breakdown_sample` 锁住真实 `tech.json -> summary/detail` 链。 |
| 正式 `1m pre_breakout` 落盘样本 | 当前 `30m` 有 `SZ.002594 pre_breakout`，且已用 `build/probe_intraday_prebreak_sample.py` 回放否定 `00981 / 00728 / 06088` 三组高优先窗口；`1m` 仍没有正式落盘样本 | 至少 1 个真实 `1m` `zs_monitor_alert=pre_breakout` 落盘样本 | 最高 | 下一步改为扩历史窗口或生成新样本，不再重复把 `00981 / 00728 / 06088` 当前已测窗口当首选候选。 |
| `1m` 预警未确认 -> confirmed 对照链 | 当前已有真实 `1m pre_breakdown` 落盘样本 + `1m confirmed 3S` reference gate，但 `pre_breakout` 方向仍缺真实样本，confirmed 方向也仍缺 live 页内卡片 | 一组“正式 `pre_break*` -> 回中枢未确认”与“一组 `pre_break*` 后确认链闭合”的 `1m` 对照 | 高 | 继续补 `1m pre_breakout` 真实样本，并把 confirmed reference 往 live 页内卡片推进。 |
| 发布产物锚点 | 文档已确认 `30m pre_breakdown/pre_breakout -> published summary/detail` 有回归锚点；`1m pre_breakdown` 也已有真实样本 publish regression，`1m pre_breakout` 仍缺真实锚点 | `1m summary/detail/miniapp` 的双边正式预警字段核验 | 高 | 对称补齐 `1m pre_breakout` 的真实 `tech.json -> publish summary/detail` 核验链。 |
| 自动化测试锚点 | `1m pre_breakdown` 已有独立真实 `tech.json` gate + 真实 publish regression，`1m pre_breakout` 仍只有 synthetic gate | 至少再补一条真实 `1m pre_breakout` regression / publish gate | 高 | 测试侧继续按一上/一下对称补齐真实样本锚点。 |
| review 卡片锚点 | 真实 `SZ.000651 1m pre_breakdown` 已接管向下预警主位，`SH.601328 1m` 已降为代理说明卡片 | 真实 `1m pre_breakout` 卡片与真实 confirmed live 卡片 | 中高 | 在样例库与消费对照页继续补 `1m pre_breakout` 主卡片，并把 confirmed reference 升级成 live 卡片。 |

按任务拆分的推进顺序：

1. `ZS5.3.a` 先锁定“当前 4 个 `1m` 锚点各自负责哪一类状态”，避免后续补样本时把既有锚点职责打乱。
2. `ZS5.3.b` 已先用真实 `000651 1m pre_breakdown` 样本补上正式落盘缺口，后续把它升级进 review 主卡片。
3. `ZS5.3.c` 继续对称补正式 `1m pre_breakout` 落盘样本，避免只有单边预警链；当前缓存里 `00981 / 00728 / 06088` 首轮高优先窗口已回放否定。
4. `ZS5.3.d` 在 `pre_breakdown` 已有真实 publish regression 的基础上，再把 `pre_breakout` 的 `tech.json`、`summary/detail`、小程序消费标签补齐到同等状态。
5. `ZS5.3.e` 最后补 review 卡片和 regression 映射，把代理样本降级成“过渡态说明”，不再充当正式预警链主锚点。

`ZS5.3` 分任务 checklist：

#### ZS5.3.a 锁定现有 `1m` 锚点职责

目标：先把当前 4 个 `1m` 样本的职责冻结，避免后续新增正式预警样本时把既有锚点语义冲掉。

固定职责表（首版）：

| 锚点 | 主职责 | 可承担的次职责 | 禁止替代的职责 | 维护说明 |
| --- | --- | --- | --- | --- |
| `HK.02357 1m range ongoing` | watch / pending 主锚点 | 单中枢盘整进行中、无确认买卖点、`relationship.kind=undetermined` 的观察态说明 | 不得替代 completed_then_new_type、正式预警、confirmed 样本 | 若后续仍是“单中枢 + 结构未完成”，继续保留为 watch/pending 首选锚点。 |
| `HK.01339 1m completed_then_new_type` | completed_then_new_type 主锚点 | “前段已完成、当前新段运行中”的结构切换说明 | 不得替代单中枢 watch/pending、正式预警、confirmed 样本 | 若后续出现更清晰的结构切换样本，可替换；但必须继续承担“完成后新段进行中而未确认”的职责。 |
| `SH.601328 1m pre-warning proxy` | 预警前态代理主锚点 | 顶背驰迹象已出现、等待离开中枢、风险迹象未进入正式字段链的过渡说明 | 不得替代正式 `pre_breakdown`、正式 `pre_breakout`、confirmed 样本 | 一旦正式 `1m pre_break*` 样本落盘，它必须降级成“代理/过渡样本”，不再承担正式预警主锚点。 |
| `1m confirmed 3S` regression reference | confirmed 对照锚点 | `1m` confirmed 三卖回归输出、与 pending/预警样本对照 | 不得替代 watch/pending、completed_then_new_type、预警未确认样本，也不得冒充当前 live `tech.json` | 当前先由具名 regression reference gate 承担 confirmed 对照角色；后续仍需补真实 live 卡片。 |

职责冻结规则：

1. 四个真实样本 + 一个 confirmed regression reference 当前各自只承担一种主职责，不允许一个样本同时充当“观察态”和“正式预警”两类主锚点。
2. 在正式 `1m pre_breakdown/pre_breakout` 样本补齐前，`SH.601328 1m` 只能写成 `pre-warning proxy` 或“预警前态代理”，不得偷换成正式预警链样本。
3. 若后续替换锚点，必须保持“职责不变、样本可换”的原则：替换的是具体标的，不是场景定义。
4. 任何文档或消费页只要引用这四个 `1m` 锚点，都应优先沿用本表职责，不得因为文案方便临时改场景归类。

输入：

- `HK.02357 1m`
- `HK.01339 1m`
- `SH.601328 1m`
- `SZ.000651 1m`

完成定义：

- 四个真实样本 + 一个 confirmed regression reference 各自只承担一种主状态职责：watch/pending、completed_then_new_type、正式 `pre_breakdown`、pre-warning proxy、confirmed 对照。
- `SH.601328 1m` 被明确标记为代理样本，而不是正式 `pre_break*` 样本。

输出：

- 一张固定职责表。
- 一条“不得混改既有锚点职责”的维护规则。

阻塞条件：

- 若某已有锚点在最新产物中状态已变化，需要先决定是换锚点还是更新职责定义。

#### ZS5.3.b 补正式 `1m pre_breakdown` 落盘样本

目标：补出至少一个真实 `1m` 下破预警样本，让 `zs_monitor_alert=pre_breakdown` 在 `1m` 主链上真正落盘。

输入：

- 候选真实 `1m` 标的 / 窗口
- 当前 `SH.601328 1m` 代理样本
- 已有 `30m/60m pre_breakdown` 对照样本

完成定义：

- 本地 `data/reports/<symbol>/1m/tech.json` 能稳定看到正式 `zs_monitor_alert=pre_breakdown`。
- 同一产物里仍保留主口径字段与“未确认”语义，未误升为 confirmed 3S。

输出：

- 一个正式 `1m pre_breakdown` 样本锚点。
- 对应的最小消费说明。

阻塞条件：

- 若 `1m` 主链没有真实落盘而只有解释文本，不能算完成。

<a id="zs53c-pre-breakout-sample"></a>
#### ZS5.3.c 补正式 `1m pre_breakout` 落盘样本

目标：对称补齐 `1m` 上破预警样本，避免 `ZS5.3` 只收口下破一边。

输入：

- 候选真实 `1m` 标的 / 窗口
- 当前 `30m pre_breakout` 对照样本

完成定义：

- 本地 `data/reports/<symbol>/1m/tech.json` 能稳定看到正式 `zs_monitor_alert=pre_breakout`。
- 消费文案保持“预警未确认”，不误写成 confirmed 3B。

输出：

- 一个正式 `1m pre_breakout` 样本锚点。
- 与 `pre_breakdown` 对称的消费约束。

阻塞条件：

- 若只能找到解释文本而没有正式字段落盘，不算正式样本补齐。

<a id="zs53d-pre-breakout-publish"></a>
#### ZS5.3.d 补发布产物与消费核验链

目标：把正式 `1m pre_break*` 样本贯通到发布层，而不是只停在本地 `tech.json`。

输入：

- `ZS5.3.b`、`ZS5.3.c` 的正式样本
- 当前 `30m pre_break* -> summary/detail` 核验路径

完成定义：

- `summary/detail` 能看到 `watch/pending` 级 `1m` 预警展示。
- 小程序卡片 / 图表能显示“未确认”且与 confirmed `3S` 分层。

输出：

- 一条 `1m tech.json -> publish summary/detail -> miniapp` 核验链。
- 发布前核验清单增量项。

阻塞条件：

- 若发布层仍把 `1m pre_break*` 省略或改写成 confirmed，则不能进入下一步。

<a id="zs53e-review-gate-map"></a>
#### ZS5.3.e 补 review 卡片与 regression 映射

目标：把正式 `1m pre_break*` 样本接入 review 页和自动化锚点，同时让代理样本回退成过渡说明。

入口映射表（首版）：

| 入口类型 | 目标入口 | 正式 `1m pre_break*` 样本接入方式 | 代理样本处理方式 | 完成标志 |
| --- | --- | --- | --- | --- |
| review 总入口 | `zhongshu-review-entry.md` 第 92 课监视器预警与确认链对照区 | 把正式 `1m pre_breakdown` / `pre_breakout` 提升为 `1m` 主预警锚点，与 `SZ.000651 1m confirmed 3S` 同页对照 | `SH.601328 1m` 降为“预警前态代理/补充说明” | review 入口不再用代理样本充当 `1m` 正式预警链主锚点。 |
| 页内案例库 | `zhongshu-visual-example-library.md` 第 4 节 | 新增正式 `1m pre_breakdown`、`1m pre_breakout` 卡片，明确“预警未确认 -> 回中枢 / 确认失败 / 后续确认链” | 保留 `SH.601328 1m` 作为“尚未进入正式字段链”的前态卡片 | 第 4 节同时拥有 `1m` 正式预警卡片和 confirmed 对照卡片。 |
| 消费对照页 | `zhongshu-consumer-display-examples.md` 第 4 节与第 7 节 | 用正式 `1m pre_break*` 样本替换“仅代理闭环”描述，补 `tech.json` / 报告 / 小程序三处并排对照 | 代理样本移到“预警前态/待离开中枢”说明位 | 消费页不再依赖代理样本假装正式预警字段已落盘。 |
| 总任务 / 进度说明 | `chanlun-spec-tasks.md` 与 `zhongshu-review-diff-summary-2026-08.md` | 把“`1m` 真实落盘样本仍缺”改成“已补正式 `1m pre_break*` 样本 + 剩余缺口” | 继续保留代理样本历史说明，但不再计入正式缺口 | 进度页能明确区分“正式样本已补”与“代理样本历史作用”。 |
| 发布核验入口 | `summary/detail`、miniapp publish 样例链 | 为正式 `1m pre_break*` 样本补一条发布产物截图/JSON 对照入口 | 代理样本不再承担发布预警字段验证职责 | 发布核验页能直接看到 `1m` 正式预警字段。 |
| regression / publish gate | 新增或补强 `1m pre_breakdown`、`1m pre_breakout` 自动化锚点 | 每个正式样本至少绑定一条 regression 或 publish gate，并能回链到对应 review 卡片 | 代理样本若保留，只能作负例或过渡说明，不作为正式 gate 代表 | 一上/一下两条 `1m pre_break*` gate 均已建立。 |

入口接线规则：

1. review 入口优先替换锚点顺序，不必先删除代理样本；正式样本先上主位，代理样本再降到补充位。
2. 消费对照页必须同时更新 `tech.json`、报告、小程序三处写法，避免只有样例库更新、消费页仍沿用代理描述。
3. regression / publish gate 必须能回链到 review 卡片；review 卡片也必须能指出对应哪条自动化锚点。
4. 正式 `1m pre_breakdown` 和 `1m pre_breakout` 必须成对接线，避免只收口单边入口。

最小映射结果：

- `zhongshu-review-entry.md`：`1m` 正式预警主锚点 + `1m confirmed 3S` 对照。
- `zhongshu-visual-example-library.md`：正式 `1m pre_break*` 卡片 + `SH.601328 1m` 前态代理卡片。
- `zhongshu-consumer-display-examples.md`：正式 `1m pre_break*` 三处展示对照。
- regression / publish gate：至少两条 `1m` 正式预警自动化锚点。

输入：

- `ZS5.3.b`、`ZS5.3.c` 的正式样本
- `SH.601328 1m` 代理样本
- 当前 review / consumer / regression 入口

完成定义：

- review 页能同页对照 `1m pre_break*` 与 `1m confirmed`。
- 至少一上/一下两条 `1m` regression / publish gate 已建立。
- `SH.601328 1m` 被降级成“预警前态代理/过渡样本”说明，不再占正式预警主锚点。

输出：

- review 卡片入口更新。
- regression 映射表。

阻塞条件：

- 若正式样本还没落盘，就不能用代理样本假装完成 review / regression 收口。

发布产物核验清单（首版）：

| 核验层 | 必须看到什么 | 当前状态 |
| --- | --- | --- |
| 本地 `data/reports/<symbol>/1m/tech.json` | 正式 `zs_monitor_alert=pre_breakout|pre_breakdown`；对应 pending 文案；主口径字段仍保留 | `pre_breakdown` 已有真实样本；`pre_breakout` 待补 |
| 发布 `summary/detail` | `watch/pending` 级预警展示，不误升为 confirmed | `30m` 已有；`1m pre_breakdown` 已有真实回归；`1m pre_breakout` 待补 |
| 小程序卡片 / 图表 | `1m` 预警卡片能显示“未确认”，且和 confirmed `3S` 明确分层 | `1m pre_breakdown` 已接线；`1m pre_breakout` 待补 |
| review 文档 | 正式 `1m pre_break*` 卡片与 confirmed 对照卡片能同页审阅 | `pre_breakdown` 已接线；`pre_breakout` 与 confirmed live 卡片仍待补 |
| 自动化回归 | 至少一上/一下两条 `1m pre_break*` 锚点 | `pre_breakdown` 真实回归已落地；`pre_breakout` 仍缺真实锚点 |

发布 / regression gate 占位表（首版）：

| gate 占位名 | 对应正式样本 | 最小断言 | 必须回链入口 | 当前状态 |
| --- | --- | --- | --- | --- |
| `1m-pre-breakdown-tech-json-gate` | 正式 `1m pre_breakdown` | `tech.json` 出现 `zs_monitor_alert=pre_breakdown`，且摘要仍是 pending/watch，不是 confirmed `3S` | `zhongshu-review-entry.md` 第 92 课 + `zhongshu-consumer-display-examples.md` 第 4 节 | 已落地真实样本 pytest + synthetic pytest |
| `1m-pre-breakdown-publish-gate` | 正式 `1m pre_breakdown` | `summary/detail`、小程序卡片、图表标签都能显示“向下预警未确认” | publish 核验样例链 + `zhongshu-visual-example-library.md` 第 4 节 | 已落地真实样本 pytest + synthetic pytest |
| `1m-pre-breakout-tech-json-gate` | 正式 `1m pre_breakout` | `tech.json` 出现 `zs_monitor_alert=pre_breakout`，且摘要仍是 pending/watch，不是 confirmed `3B` | `zhongshu-review-entry.md` 第 92 课 + `zhongshu-consumer-display-examples.md` 第 4 节 | 已落地 synthetic pytest，待真实样本 |
| `1m-pre-breakout-publish-gate` | 正式 `1m pre_breakout` | `summary/detail`、小程序卡片、图表标签都能显示“向上预警未确认” | publish 核验样例链 + `zhongshu-visual-example-library.md` 第 4 节 | 已落地 synthetic pytest，待真实样本 |
| `1m-confirmed-3s-reference-gate` | `SZ.000651 1m confirmed 3S` | confirmed `3S` 保持稳定，且消费端不会把它回退成 pending/watch 预警说明 | `zhongshu-review-entry.md` 第 92 课 + `zhongshu-consumer-display-examples.md` 第 7 节 | 已落地具名 pytest |
| `1m-proxy-negative-transition-gate` | `SH.601328 1m pre-warning proxy` | 风险前态仍不得输出正式 `zs_monitor_alert=pre_break*`，也不得被消费端升级成 confirmed | `zhongshu-visual-example-library.md` `4.4` + `zhongshu-consumer-display-examples.md` `7.6` | 已落地具名 pytest |

gate 收口规则：

1. 每个方向至少要同时有一条 `tech.json` gate 和一条 publish gate，不能只补本地字段断言。
2. gate 名称先按占位名维护，真正落测试时可映射到具体脚本或 pytest 用例，但文档中的四个占位角色不能缺。
3. 每条 gate 都必须能反向指出对应 review 卡片、消费对照页和发布核验入口，避免测试名存在但 reviewer 无法定位样本。
4. `SH.601328 1m` 不得占用上述四个 gate 的正式样本位置；若保留自动化校验，只能落到 `1m-proxy-negative-transition-gate` 这类 proxy negative / transition gate。

最小落地顺序：

1. 优先补 `1m-pre-breakout-tech-json-gate` 与 `1m-pre-breakout-publish-gate` 的真实样本，确认 `summary/detail` 与小程序没有把 pending/watch 偷换成 confirmed。
2. 然后把 `1m confirmed 3S` 从 regression reference 推进到真实 live 页内卡片。
3. 最后在 `ZS6.3` 的文档-测试映射里把 `pre_breakdown / pre_breakout` 四条 gate 与 review 卡片一一绑定。

退出条件细化：

- `1m` 不再只有代理预警样本；当前至少已有正式 `pre_breakdown` 真实落盘样本，后续补齐 `pre_breakout` 对称样本。
- 每个正式 `1m pre_break*` 样本都能在 `tech.json`、发布产物、review 页、自动化回归四层找到对应锚点。
- `SH.601328 1m` 可以回退成“预警前态代理 / 过渡样本”，而不再承担正式预警链主锚点职责。

验收：

- `1m / 5m / 30m / day` 四类入口至少各有稳定主样例可 review。
- 报告、小程序、导出 JSON 对同一中枢状态给出一致展示。

退出条件：

- 任意一个状态字段都能回答“严格结论还是监视提示”。
- `1m` 样例不再是 review 盲区。

### ZS6 review 样例与真实回归闭环

目标：让中枢 review 文档不只是说明页，而是能和自动化回归互相校验。

#### ZS6.1 补进入段 / 本体 / 离开段图示

- 继续补进入段 / 本体 / 离开段分层图。
- 每张图要标明当前状态、边界、最近上游线段和下游消费结论。
- 优先覆盖最容易误解的完成 / 扩张 / pending 过渡态。

产出：

- 分层图卡片。
- 图示字段说明。

<a id="zs62-review-cases"></a>
#### ZS6.2 补主辅冲突与 pre_break 样例

- 继续补真实 `1m pre_break*` 案例与主辅冲突样例。
- 至少补一组“标准中枢未确认但辅助口径已给预警”的对照案例。
- 至少补一组“完成后转入新中枢候选”的过渡样例。

产出：

- 主辅冲突样例页。
- pre_break 对照卡片。

#### ZS6.3 样例与 regression 一一绑定

- 为每类关键状态绑定最小 regression fixture，避免文档有了但代码无闸门。
- 为每个重点样例补“对应哪条 regression / 哪个发布核验脚本”。
- 为每个高风险 regression 补“对应哪页 review 示例”。

文档-测试映射表（首版）：

| 状态 / 场景 | review 主入口 | 页内样例 / 消费入口 | regression / publish gate | 绑定目标 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| `1m pre_breakdown` 正式预警未确认 | `zhongshu-review-entry.md` 第 92 课 | `zhongshu-visual-example-library.md` 第 4 节；`zhongshu-consumer-display-examples.md` 第 4 节 | `1m-pre-breakdown-tech-json-gate`；`1m-pre-breakdown-publish-gate` | review、消费页、发布层对“向下预警未确认”口径一致 | tech-json gate 与 publish gate 均已落地真实样本 pytest |
| `1m pre_breakout` 正式预警未确认 | `zhongshu-review-entry.md` 第 92 课 | `zhongshu-visual-example-library.md` 第 4 节；`zhongshu-consumer-display-examples.md` 第 4 节 | `1m-pre-breakout-tech-json-gate`；`1m-pre-breakout-publish-gate` | review、消费页、发布层对“向上预警未确认”口径一致 | tech-json / publish gate 已落地 synthetic pytest，真实样本待补 |
| `1m confirmed 3S` 确认链闭合 | `zhongshu-review-entry.md` 第 92 课 | `zhongshu-visual-example-library.md` `4.3`；`zhongshu-consumer-display-examples.md` 第 7 节 | `1m-confirmed-3s-reference-gate` -> `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_confirmed_3s_reference_anchor` | 作为 `1m pre_break*` 的 confirmed 对照锚点，不与 pending/watch 混写 | 已落地具名 pytest |
| `1m pre-warning proxy` 过渡态 | `zhongshu-review-entry.md` 第 92 课补充说明位 | `zhongshu-visual-example-library.md` `4.4`；`zhongshu-consumer-display-examples.md` `7.6` | `1m-proxy-negative-transition-gate` -> `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_keep_1m_proxy_as_transition_not_pre_breakdown_or_confirmed` | 约束消费端不得把风险前态升级成正式 `pre_break*` 或 confirmed | 已落地具名 pytest |
| `30m pre_breakout` 回中枢未确认 | `zhongshu-review-entry.md` 第 92 课 | `zhongshu-visual-example-library.md` `4.2`；`zhongshu-consumer-display-examples.md` 第 4 节 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_30m_pre_breakout_publish_anchor` | 作为 `1m` 正式预警链接入前的上级别已落地参考样本 | 已具名 |
| `30m -> day higher_level_range` 去向候选 | `zhongshu-review-entry.md` 第 29 课 | `zhongshu-visual-example-library.md` 第 2 节；`zhongshu-consumer-display-examples.md` 第 2 节 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_30m_pre_breakdown_publish_anchor` | 约束 `post_divergence_route` 只作 pending/watch 候选，不升级为 confirmed 趋势反转 | 已具名 |
| `5m down_bias` 节奏下偏弱 | `zhongshu-review-entry.md` 第 39 课 | `zhongshu-visual-example-library.md` 第 3 节；`zhongshu-consumer-display-examples.md` 第 3 节 | `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_down_bias_when_latest_up_strength_weakens_inside_zs` | 约束 `oscillation_rhythm_state` 只作节奏监视，不替代卖点确认链 | 已具名 |

现有具名入口与未来落点建议：

| 角色 | 当前已具名入口 / 建议落点 | 说明 |
| --- | --- | --- |
| `30m pre_breakdown` publish 参考 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_30m_pre_breakdown_publish_anchor` | 已覆盖 `summary/detail` 中“向下预警未确认”“去向候选”“节奏监视”三类输出。 |
| `30m pre_breakout` publish 参考 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_30m_pre_breakout_publish_anchor` | 已覆盖 `summary/detail` 中“向上预警未确认”“去向候选”“节奏监视”三类输出。 |
| 预警字段生成 | `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_pre_breakdown_when_close_presses_lower_zs_edge` | 当前最接近未来 `1m-pre-breakdown-tech-json-gate` 的字段生成断言入口。 |
| 节奏字段生成 | `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_balanced_rhythm_when_latest_same_direction_ratio_is_neutral`；`tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_down_bias_when_latest_up_strength_weakens_inside_zs` | 当前 `balanced/down_bias` 两个节奏状态都有独立字段断言。 |
| 预警文案降级 | `tests/test_zhongshu_structure_text.py::test_build_advice_keeps_pre_breakdown_as_pending_watch` | 当前最接近未来 publish / 文案 gate 的 pending/watch 口径断言入口。 |
| publish 文案脚本落点 | `scripts/build_miniapp_publish_bundle.py` | 现已负责把 `zs_monitor_alert`、`post_divergence_route`、`oscillation_rhythm_state` 转成 summary/detail 的技术焦点行。 |
| 报告文案脚本落点 | `scripts/batch_prepare_chanlun_reports.py` | 现已负责把 `pre_breakout/pre_breakdown`、节奏监视写入报告文案，适合作为未来 `1m` 报告 gate 的实现入口。 |
| `1m-pre-breakdown-tech-json-gate` 建议落点 | `tests/test_chanlun_analysis.py` + `tests/test_zhongshu_structure_text.py` | 先锁字段生成，再锁 pending/watch 文案，不要只测其中一层。 |
| `1m-pre-breakdown-tech-json-gate` 已落地 | `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_pre_breakdown_when_close_presses_lower_zs_edge` + `tests/test_build_signal_summary_fields_preserves_pre_breakdown_pending_gate` + `tests/test_chanlun_analysis.py::test_real_1m_pre_breakdown_sample_preserves_independent_tech_json_gate` | 当前已同时用 synthetic 字段断言和真实 `000651 1m tech.json` 样本锁住 `pre_breakdown` 进入 summary 字段时仍保持 pending/watch 语义。 |
| `1m-pre-breakdown-publish-gate` 建议落点 | `tests/test_build_miniapp_publish_bundle.py` | 未来应仿照现有 `30m` publish anchor，加一条 `1m` 未确认向下预警链。 |
| `1m-pre-breakdown-publish-gate` 已落地 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_pre_breakdown_publish_gate` | 当前已用 synthetic `1m tech.json` 锁住 publish 层“向下预警未确认”口径。 |
| `1m-pre-breakdown-publish-gate` 真实样本入口 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_real_1m_pre_breakdown_sample` | 当前已直接读取 `data/reports/000651/1m/tech.json`，锁住真实 `tech.json -> summary/detail` 的 pending/watch 语义。 |
| `1m-pre-breakout-tech-json-gate` 建议落点 | `tests/test_chanlun_analysis.py` + `tests/test_zhongshu_structure_text.py` | 与 `pre_breakdown` 对称，先锁字段，再锁消费降级。 |
| `1m-pre-breakout-tech-json-gate` 已落地 | `tests/test_chanlun_analysis.py::test_analyze_chanlun_signals_emits_pre_breakout_when_close_presses_upper_zs_edge` + `tests/test_chanlun_analysis.py::test_build_signal_summary_fields_preserves_pre_breakout_pending_gate` | 当前已用 synthetic 字段断言锁住 `pre_breakout` 进入 summary 字段时仍保持 pending/watch 语义。 |
| `1m-pre-breakout-publish-gate` 建议落点 | `tests/test_build_miniapp_publish_bundle.py` | 未来应仿照现有 `30m` publish anchor，加一条 `1m` 未确认向上预警链。 |
| `1m-pre-breakout-publish-gate` 已落地 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_pre_breakout_publish_gate` | 当前已用 synthetic `1m tech.json` 锁住 publish 层“向上预警未确认”口径，下一步只差真实落盘样本接入。 |
| `1m-pre-breakout` 样本探测工具 | `build/probe_intraday_prebreak_sample.py` | 现已支持手工 cutoff 回放与 `--auto-find` 全窗口扫描，可对现有 `1m raw_csv` 直接验证某个时间点是否真的生成 `zs_monitor_alert=pre_breakout/pre_breakdown`。 |
| `1m-pre-breakout` 首轮回放结论 | `build/probe_00981_1m.json`、`build/probe_00728_1m.json`、`build/probe_06088_1m.json` | 当前已回放否定 `00981 / 00728 / 06088` 的首轮高优先窗口；这些窗口分别落在 `buy_3 + pending` 或“尚未形成中枢”状态，没有产生真实 `pre_breakout`。 |
| `1m-confirmed-3s-reference-gate` 已落地 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_confirmed_3s_reference_anchor` | 已锁定 `SZ.000651 1m confirmed 3S` 不会被 pending/watch 文案吞掉。 |
| `1m-proxy-negative-transition-gate` 已落地 | `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_keep_1m_proxy_as_transition_not_pre_breakdown_or_confirmed` + `tests/test_zhongshu_structure_text.py::test_build_advice_keeps_pre_breakdown_as_pending_watch` | publish 层显式约束 proxy negative；文案层继续复用 pending/watch 降级断言风格。 |

首版绑定规则：

1. `ZS5.3.e` 的四条正式 `1m pre_break*` gate 是本表的最高优先级空位，后续补样本时必须先填这两行，再扩展别的状态。
2. `1m confirmed 3S` 与 `1m pre-warning proxy` 必须继续保留在表里，分别承担“confirmed 对照”和“代理负例/过渡态”角色，不能因正式样本补齐而消失。
3. 每一行都必须同时能回答三件事：review 从哪进、消费页看哪处、自动化 gate / publish 核验看哪条；如果已有具名 pytest，优先写成具名 pytest，而不是继续保留抽象描述。
4. 若某行只有样例没有 gate，应保留“已接线，gate 待补”；若只有 gate 没有 review 入口，则不能算收口完成。

下一轮补齐顺序：

1. 先把 `1m pre_breakout` 的真实落盘样本、publish gate、tech-json gate 对称补齐；优先扩历史窗口或换新标的，而不是重复尝试已回放否定的 `00981 / 00728 / 06088` 首轮窗口。
2. 再把 `1m confirmed 3S` 从 regression reference 推进到真实 live 页内卡片。
3. 最后把 `已接线` 的现有 `30m`、`5m` 行继续扩成可直接点到具体脚本或用例名的完整映射表。

产出：

- 文档-测试映射表。
- 高风险样例锚点清单。

验收：

- [zhongshu-review-entry.md](zhongshu-review-entry.md) 可以独立带 reviewer 走完“理论 -> 当前实现 -> 消费展示 -> 风险点”。
- 每个高风险状态至少有一个真实窗口和一个自动化回归锚点。

退出条件：

- reviewer 可以从文档直接跳到样例、测试、消费产物。
- 代码回归失败时，能快速定位受影响的是哪一类中枢状态。

## 当前 blocker

- 复杂 reclaim / 重写 与 gap 再分辨交界仍未彻底统一。
- 标准中枢完成态若不先稳定，后续买卖点绑定会继续漂移。
- 真实 `1m` 预警样本仍偏少，消费侧 review 容易只看到稳态、不看到过渡态。

## 推荐执行顺序

1. 先跟随 [segment-tasks.md](segment-tasks.md) 收口上游边界。
2. 再做 ZS1-ZS3，先把标准中枢主状态机稳定下来。
3. 然后做 ZS4-ZS5，收口字段和消费展示。
4. 最后补 ZS6，把样例、文档、回归闭环做完整。

## 当前建议从这里开工

如果下一轮要继续推进，建议按下面顺序直接开 task，而不是再从 epic 级别重想一遍：

1. `ZS1.2`：先把进入段 / 离开段边界规则写死。
2. `ZS3.2`：再把 gap defer / invalidated 交界的中枢重算顺序写死。
3. `ZS2.1`：在上面两个边界稳定后，补完成 / 扩张 / 新中枢状态图。
4. `ZS4.1`：开始盘点当前主产物里还混用标准中枢与类中枢的字段。