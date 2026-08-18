# 缠论规格与落地任务清单

本文件跟踪“严格缠论理论规格”在仓库中的文档化、复核和实现收敛进度。

约定：

- 完成百分比是面向“严格理论落地”的估算，不等于功能能不能跑。
- `已完成` 表示仓库中已有稳定文档、契约或实现支撑。
- `待完成` 表示仍存在理论缺口、实现缺口或 review 资料缺口。

## 1. 总体进度

| 维度 | 说明 | 完成度 |
| --- | --- | --- |
| 严格理论规格整理 | 术语、结构、review 路径是否成体系可读 | 82% |
| 原文逐课复核 | 是否已有逐课对照与差异记录 | 88% |
| 当前工程口径沉淀 | 现状实现、契约、样例是否可追踪 | 81% |
| 严格理论自动化实现 | 代码是否已按严格理论完整落地 | 47% |
| 综合进度 | 文档、复核、实现三者合并后的总体估算 | 60% |

说明：

- 文档层完成度高于实现层。
- 当前项目“能跑”不等于“已严格按原文完成”。
- 低于 50% 的模块，通常不是缺样例，而是缺严格自动判定链路。

## 2. 已完成任务

### 2.1 文档与术语层

- [x] 建立主规格 [chanlun-rule-spec.md](chanlun-rule-spec.md)，覆盖分型、笔、线段、中枢等主概念。
- [x] 建立严格目标规格 [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)，把理论目标与当前实现拆开。
- [x] 建立跨模块 [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)，统一沉淀理论/实现/消费三层差异。
- [x] 为基础结构模块补齐“原文复核矩阵 + 图文化示例库”配套文档。
- [x] 建立中枢核心理论规格 [zhongshu-core-spec.md](zhongshu-core-spec.md)，把中枢理论定义与主辅消费/案例文档拆开。
- [x] 建立主辅消费规范 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。
- [x] 建立原文复核矩阵 [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)。
- [x] 建立中枢 review 单页入口 [zhongshu-review-entry.md](zhongshu-review-entry.md)，统一原文、样例、消费红线入口。
- [x] 建立中枢增量摘要 [zhongshu-review-diff-summary-2026-08.md](zhongshu-review-diff-summary-2026-08.md)，压缩本轮文档推进范围与剩余缺口。
- [x] 为走势类型/背驰模块补齐“原文复核矩阵 + 图文化示例库”配套文档。
- [x] 为买卖点/多级别联立模块补齐“原文复核矩阵 + 图文化示例库”配套文档。
- [x] 建立线段专题导航 [segment-doc-map.md](segment-doc-map.md)。
- [x] 为线段模块补齐“原文复核矩阵 + 图文化示例库”配套文档。

### 2.2 原文对照层

- [x] 完成第 17/18/20/21/25/29/36/38/39/53/83/92 课首轮复核框架。
- [x] 明确“基本一致”与“工程近似/待补”的区分，不再把两者混写成同一口径。
- [x] 明确中枢主口径为线段级，类中枢为笔级辅助口径。

### 2.3 工程现状沉淀层

- [x] 分型、笔、线段、类中枢已有工程主链路。
- [x] 线段终结、`stop_reason`、theory/practical 双模式已有契约和说明。
- [x] 发布/分析消费端已有主辅冲突与降级语义的基本约束。
- [x] 已沉淀样例包、图文化示例库、节奏回放模板。
- [x] 已为中枢沉淀 `1m / 5m / 30m / day映射` 优先的 review 与消费示例链，其中 `HK.02357 1m` 已作为 watch/pending 场景锚点接入，`HK.01339 1m` 已作为 completed_then_new_type 场景锚点接入，`SH.601328 1m` 已作为预警前态代理锚点接入，`SZ.000651 1m` 已作为 confirmed 场景锚点接入。

## 3. 待完成任务

### 3.1 P0 严格理论主链路

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 标准线段级中枢主实现 | 进行中 | 63% | 主批量发布链已进一步锁定 `segment` 为唯一主口径，并阻断旧 `bi` 级 `5m tech.json` 继续作为主产物复用；同时 `identify_zhongshu(..., structure_level="segment")` 已改为只吃已确认线段，未确认尾段不再直接污染标准中枢主链，且 reclaim/重写后若 segment 链被并回单个未确认尾段，标准中枢结果会整体清空而不残留旧中心。本轮又把 `segment.is_reclaimed` / `absorbed_segment_ids` 接入尾段解释层、`segments.csv` 和 miniapp `summary/detail` 消费口径，线段重写吸收不再只能靠 `bi_ids` 反推；并修掉一条具体的提前确认路径：当初始转折仍处于 `TransitionState.PENDING` 时，practical `reverse_break` 兜底不再提前把该段确认为 completed。同时 `auto` / `prefer_earlier_start` 在选首种子时，若更靠右候选起点落在更靠左且仍未确认的旧段未解决窗口里，现已不再把该 later confirmed 新段当成 bootstrap 最优候选；进一步地，首种子评分已去掉对三笔以上首段的额外长度奖励，而 practical 下的 `gap false defer` 也已从 bootstrap 模式中解耦，使 `first_valid_seed` / `auto` / `prefer_earlier_start` 在 `000591`、`300124`、`00700`、`03690` 共 7 组真实 fixture 上，首段起点、方向、`is_confirmed` 与 `stop_reason` 都已对齐，不再因为选种子模式不同而分叉。本轮继续修掉四条后续段边界漂移：当本地 gap 候选被判 `INVALIDATED` 并跳到下一轮时，segment extreme 现已同步前推，后续段不再拿旧极值误判“仍在延伸”；`00700-60m` 的 practical 第 3 段已因此回到与 theory 一致的 `feature_sequence_fractal`，不再被更晚的 `reverse_break` 抢跑确认。进一步地，`gap` 候选在同一轮被判 `INVALIDATED` 且 transition reclaim 已经成立时，`_extend_segment()` 现已优先走 reclaim；但若该 `INVALIDATED` 只是前一轮 local gap false `DEFERRED` 的落地结果，则会先锁定 `gap false`、保留后续 `reverse_break` 确认轮，而不会被 reclaim 或同轮 fallback 提前吞掉。围绕这条 deferred->invalidated 路径，现已同时补齐一条 focused unit test，专门锁住“latent reclaim 不能盖过 later reverse_break”的 restart 语义；配合 focused matrix tests、`tests/test_segment.py` synthetic coverage、以及真实 fixture regression gate，当前这一分支已稳定受控。除此之外，practical 主循环不再在首个未确认段处一刀切停止；若后面已经存在能独立走出 confirmed 段的新三笔种子，现在会继续扫描而不是过早把整条链冻结为单个 pending 尾段。这个实现收敛已把 `300124 15m` practical 从 `up 0->2 / down 3->5 pending` 推进为 `up 0->2 / down 3->9 reverse_break / up 10->18 reverse_break / down 19->21 feature_sequence_fractal / up 22->24 feature_sequence_fractal / down 25->29 pending`，同时也让 `000591-day` 当前 live 窗口 practical 不再人为残留一个尾部 preprocessing 段。与此同时，`tests/test_segment_regression_000591.py` 已把 `000591 60m` 的 real restart anchor 单独锁住：第一段 practical `break_bi_id=9` 必须与下一段 `start_bi_id=9` 对齐，不得漂移到更晚的 latent reclaim 候选；同文件还已把 `000591 60m long` 的中段 overlap/reuse 语义锁住：中间 `down` 段必须保持 `break_bi_id=17`，后续 `up` 段继续从 `15` 起并复用到 `17`，并已把 `000591-day` 的 live fixture 切到当前 `20210902_to_20260818` 窗口，防止旧路径失效后 day guard 脱靶；`tests/test_segment_regression_suite.py` 现又把 `300124 60m` 的 mixed overlap/restart 语义锁住：第二段 `up 4->8` practical `break_bi_id=11` 必须继续被后续 `down 9->11` 复用，而其后的 `reverse_break` 段又必须分别按 `12`、`17` 精确重启；同文件也已把 `00700 60m` 的对应 restart anchor 锁住：第 4 段 practical `break_bi_id=16` 必须与下一段 `start_bi_id=16` 对齐；`tests/test_segment_regression_03690.py` 则已同步到当前 `03690 30m` 真实窗口，并把超长 `up 13->31` practical 段的 `break_bi_id=32 -> next start_bi_id=32` restart anchor 锁进 dedicated regression，同时新增 `03690 60m` 的 overlap/reuse + preprocess-tail 锚点：首段 `down 0->2` practical `break_bi_id=5` 必须继续落在后续未确认 `up` 段窗口内，而尾段仍保持 `same_direction_not_extending` 未确认状态。当前主要缺口已进一步收敛到：更复杂的 reclaim/重写与 gap 再分辨交界仍未彻底统一，标准中枢的完成、扩张与后续买卖点绑定因此仍可能漂移。 |
| 严格同级别走势类型自动分解 | 待完成 | 25% | 文档已有方向，但代码仍未形成完整、稳定的自动分解闭环。 |
| 趋势背驰严格自动判定 | 待完成 | 20% | 当前有工程化 divergence 输出，但不是完整原文判定链。 |
| 盘整背驰严格自动判定 | 待完成 | 18% | 盘整背驰最容易被工程近似替代，需单列主口径实现。 |
| 一类买卖点严格确认 | 待完成 | 22% | 当前 buy_1/sell_1 更接近工程规则，不等于严格原文确认链。 |
| 二类买卖点严格确认 | 待完成 | 20% | 需绑定 1 类点后的首次确认性回抽语义。 |
| 三类买卖点严格确认 | 待完成 | 28% | 文档较清楚，但代码还需与最近中枢、首次回抽严格绑定。 |

### 3.2 P1 理论与工程对齐

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `chanlun-rule-spec` 与严格版差异标注 | 进行中 | 55% | 当前仍有部分段落把“现状”和“目标”写在一起。 |
| 理论/实现/消费三层总差异表 | 进行中 | 89% | 已补字段级矩阵，并为中枢新增 review 入口、消费示例页与同案三栏对照；本轮已把 `zs_monitor_alert`、`zs_monitor_midline`、`zs_monitor_bias`、`same_level_decomposition_mode`、`post_divergence_route`、`oscillation_rhythm_state` 接入 `src -> summary/tech.json -> publish` 主链，并补上 `route_level_from/to`、节奏辅助文案与 `30m` 发布回归锚点；当前差异已收敛到“`1m` 真实落盘样本不足、`oscillation_rhythm_state` 严格阈值仍是工程近似、少量剩余字段未形成稳定主产物”；后续主要剩更多反例、真实 `1m` 样本与剩余字段回写。 |
| `src/chanlun/analysis.py` 买卖点逻辑差异表 | 待完成 | 15% | 需要逐条标记当前 buy/sell 条件与严格理论的偏差。 |
| 类中枢与标准中枢字段完全拆分 | 进行中 | 45% | 文档已拆，输出字段与消费端仍需继续收敛。 |
| 主辅冲突样例库 | 进行中 | 50% | 已有框架，还缺足量正反例。 |

### 3.3 P1 review 资料层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 中枢严格定义图示库 | 进行中 | 77% | 已有 review 入口、增量摘要、页内真实卡片与消费对照，并补入 `1m` 预警前态代理样本；仍需继续补进入段/本体/离开段分层图及真实 `1m pre_break*` 案例。 |
| 线段严格定义案例库 | 进行中 | 58% | 已补复核矩阵与图示库骨架，仍需补 67/71 课正反例和 R1-R6 映射。 |
| 背驰与盘整背驰标准案例包 | 进行中 | 45% | 已有复核矩阵与图示库骨架，仍需补统一正例、反例、易混淆例。 |
| 一二三类买卖点标准案例包 | 进行中 | 48% | 已有复核矩阵与图示库骨架，仍需按最近中枢和级别填充案例。 |
| 多级别联立 review 模板 | 进行中 | 40% | 已有区间套/小转大图示骨架，仍需补高一级方向、操作级别、执行级别样例。 |

### 3.4 P2 输出与消费层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `tech.json` 严格结构状态字段补齐 | 进行中 | 76% | 已补字段级消费映射，并为中枢补入 `1m / 5m / 30m / day映射` 的真实 `tech.json` 示例；本轮已补上 `zs_monitor_alert`、`zs_monitor_midline`、`zs_monitor_bias`、`same_level_decomposition_mode`、`post_divergence_route`、`oscillation_rhythm_state` 的真实生成、`summary/tech.json` 落盘、`advice_text` pending/auxiliary 降级、`route_level_from/to` 级别映射，以及 `30m pre_breakdown/pre_breakout -> published summary/detail` 回归锚点；后续仍需补真实 `1m` 预警样本、节奏阈值精化与少量剩余结构字段。 |
| confirmed/pending/auxiliary 三态统一 | 进行中 | 68% | 已有统一字段级文档口径，并为中枢补入 confirmed、pending、auxiliary 的真实案例对照；剩余工作主要在真实消费端落实和回归。 |
| 小程序/报告端主辅口径显式展示 | 进行中 | 81% | 已完成真实发布包样本首轮审计，并新增中枢专用消费展示对照页与同案三栏示例；剩余工作主要是 UI 落地和回归校验。 |

## 4. 下一阶段建议顺序

建议按以下顺序推进，避免先修消费层再返工主结构：

1. 先补严格线段主链路。
2. 再补标准中枢与类中枢分离、扩张与完成判定。
3. 最后补趋势背驰、盘整背驰与一二三类买卖点严格确认。
4. 然后输出“理论 vs 当前实现”差异表，逐项压缩工程近似。
5. 最后统一 `tech.json`、报告和小程序展示口径。

当前排序理由如下：

- `segment` 是走势类型切分与后续中枢识别的直接结构边界；若线段完成条件、尾部确认、重写吸收口径未稳定，后续中枢与买卖点都会持续漂移。
- `zhongshu` 依赖上游线段边界稳定后才能明确“标准中枢 vs 类中枢”“扩张 vs 新中枢”“完成 vs 监视中”等核心状态，否则字段与消费层口径都会反复返工。
- `buy/sell points` 站在走势类型和中枢关系之上，最容易受上游结构漂移影响，因此应放在 `segment` 与 `zhongshu` 收敛之后集中严格化。

### 4.1 `segment` 下一步拆分

建议先把线段阶段拆成以下 3 个可直接执行的 review/实现项：

1. 线段成立与终结条件。
	目标：明确严格线段从哪些已确认笔开始计入，何时视为结束，哪些尾部延伸只能算候选而不能提前确认为完成。
2. `pending_confirmation` 与 `confirmed` 的统一判定。
	目标：统一当前 `segment_tail_interpretations`、同级别走势摘要、消费者文案中的确认状态，避免一处已确认、另一处仍写待确认。
3. 线段重写、吸收、复用时的输出口径。
	目标：把“旧线段被后续结构吸收”“尾部笔被复用”“边界右移重算”等情况稳定映射到 machine-readable 字段和 review 示例，避免后续中枢跟着漂移。

完成这 3 项后，再进入 `zhongshu` 会更稳，因为中枢的进入笔、离开笔、扩张边界与完成状态都直接依赖线段边界是否稳定。

本轮 `segment` review 入口：

- [segment-review-entry.md](segment-review-entry.md)
- 用途：统一原文定义、当前实现、`pending_confirmation` / 再分辨 / 重写吸收样例，以及下游字段红线。
- 当前进展：`segment-visual-example-library.md` 已从纯模板推进到“模板 + 规范回归案例 + 真实回归窗口案例”，现成入口包括 `SZ.000651 30m`、`SZ.000591 15m`、`HK.00700 15m`。

本轮 `zhongshu` review 入口：

- [zhongshu-review-entry.md](zhongshu-review-entry.md)
- 用途：统一原文定义、页内真实卡片、`tech.json` / 报告 / 小程序消费红线，以及 `1m / 5m / 30m / day映射` 的示例优先级。
- 当前进展：`zhongshu-visual-example-library.md` 第 1 至第 4 节均已进入页内可审状态；`zhongshu-consumer-display-examples.md` 已补同案三栏对照，当前主锚点包括 `HK.02357 1m range ongoing`、`HK.01339 1m completed_then_new_type`、`SH.601328 1m pre-warning proxy`、`SZ.000651 1m confirmed 3S`、`SH.601318 5m down_bias`、`SZ.000651 30m -> day`、`SZ.002594 30m pre_breakout`。

## 5. review 用任务拆分

### 5.1 已适合开始 review 的部分

- 包含关系与标准化 K 线定义
- 严格分型定义
- 成笔约束与确认原则
- 中枢主辅术语与命名边界
- 原文复核矩阵整体框架

### 5.2 需要重点 review 的部分

- 严格线段理论与当前线段工程实现的边界
- 标准中枢与类中枢的字段和消费分离
- 趋势背驰 vs 盘整背驰的自动判定口径
- 一二三类买卖点与“最近中枢”绑定的严格程度
- 多级别联立下的确认/降级规则

## 6. 完成度口径说明

本文百分比按以下标准估算：

- `0%-20%`: 仅有零散想法或个别实现片段。
- `21%-40%`: 已有文档或已有代码，但链路不闭环。
- `41%-60%`: 文档、样例、实现已具备两项，但仍有主链路缺口。
- `61%-80%`: 主链路基本明确，可做稳定 review，但仍未彻底统一。
- `81%-100%`: 文档、样例、实现、消费口径都已收敛。

若后续实现或复核推进，优先更新本文件，再回写对应专题文档，避免进度信息散落在多个说明页。