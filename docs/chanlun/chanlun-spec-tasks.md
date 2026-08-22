# 缠论规格与落地任务清单

本文件跟踪“严格缠论理论规格”在仓库中的文档化、复核和实现收敛进度。

约定：

- 完成百分比是面向“严格理论落地”的估算，不等于功能能不能跑。
- `已完成` 表示仓库中已有稳定文档、契约或实现支撑。
- `待完成` 表示仍存在理论缺口、实现缺口或 review 资料缺口。
- 本页只保留跨模块看板、优先级和 epic 摘要；具体执行任务拆到各模块 `*-tasks.md`。

## 1. 总体进度

| 维度 | 说明 | 完成度 |
| --- | --- | --- |
| 严格理论规格整理 | 术语、结构、review 路径是否成体系可读 | 82% |
| 原文逐课复核 | 是否已有逐课对照与差异记录 | 88% |
| 当前工程口径沉淀 | 现状实现、契约、样例是否可追踪 | 82% |
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
- [x] 已为中枢沉淀 `1m / 5m / 30m / day映射` 优先的 review 与消费示例链，其中 `HK.02357 1m` 已作为 watch/pending 场景锚点接入，`HK.01339 1m` 已作为 completed_then_new_type 场景锚点接入，真实 `SZ.000651 1m` 已作为正式 `pre_breakdown` 场景锚点接入，`SH.601328 1m` 已作为预警前态代理锚点接入，`1m confirmed 3S` 当前由 regression reference gate 保留；后续优先缺口收敛为真实 `1m pre_breakout` 样本与真实 confirmed 页内卡片。
- [x] `zhongshu-tasks.md` 已补 `ZS5.3.e + ZS6.3` 首版文档-测试映射：`30m pre_breakdown` / `pre_breakout`、`5m down_bias` 已回链到具名 pytest；`1m-confirmed-3s-reference-gate` 与 `1m-proxy-negative-transition-gate` 已落地具名 pytest；`1m pre_breakdown` 已同时补到真实 `tech.json` gate 与真实样本 publish regression，`1m pre_breakout` 仍待真实样本驱动。

## 3. 待完成任务

### 3.0 模块任务入口

- [segment-tasks.md](segment-tasks.md)：线段主链、确认态、重写吸收与回归闸门。
- [zhongshu-tasks.md](zhongshu-tasks.md)：标准线段级中枢主实现、类中枢拆分、输出与消费收口。
- [trend-divergence-tasks.md](trend-divergence-tasks.md)：同级别走势类型自动分解、趋势背驰、盘整背驰。
- [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)：一二三类买卖点、多级别联立、消费降级规则。

维护方式：

- 总表更新百分比、状态和跨模块依赖。
- 模块任务页更新可执行 task、验收口径、当前 blocker。
- 具体实现或 review 完成后，先回写模块任务页，再同步回本页百分比。

### 3.0A 按任务类型看板

阅读方式：

- 文档任务：规格、review、样例库、差异表这类“让 reviewer 看懂”的工作。
- 测试任务：regression gate、fixture、publish 核验、回放工具校验这类“锁结果不漂”的工作。
- 代码任务：严格判定链、字段生成、状态机、消费输出这类“真正改变产物行为”的工作。
- 优先级：`高` 表示当前主线直接依赖；`中` 表示紧跟主线的并行项；`低` 表示需要保留，但不是眼下第一落点。

当前重点：

1. 测试：补真实 `1m pre_breakout` 样本，并落地 [样本 gate](zhongshu-tasks.md#zs53c-pre-breakout-sample) + [publish gate](zhongshu-tasks.md#zs53d-pre-breakout-publish)。
2. 代码：继续收口 [标准中枢主状态机](zhongshu-tasks.md#zs2-state-machine) 的复杂 `reclaim / rewrite / gap` 真值，以及 [同级别走势类型主链](trend-divergence-tasks.md#td1-route-chain)。
3. 文档：把 `1m pre_breakout` 与 confirmed live 卡片补进 [review / 图示主入口](zhongshu-tasks.md#zs53e-review-gate-map)，当前消费契约页已可视为阶段性收口。

#### 文档任务

| 任务 | 优先级 | 当前重点 | 当前状态 | 完成度 | 执行入口 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 理论/实现/消费三层总差异表 | 高 | 继续压缩 `1m pre_breakout` 与 confirmed live 卡片缺口 | 进行中 | 92% | [中枢映射](zhongshu-tasks.md#zs53e-review-gate-map) / [背驰字段](trend-divergence-tasks.md#td4-output-fields) / [买卖点差异](buy-sell-multi-level-tasks.md#bs1-diff-map) | `1m pre_breakdown` 的真实样本、`tech.json` gate、文案、发布链和 review 主锚点已收口。 |
| 中枢严格定义图示库 | 高 | 补真实 `1m pre_breakout` 卡片与 confirmed live 卡片 | 进行中 | 82% | [样例卡片](zhongshu-tasks.md#zs62-review-cases) | 当前真实 `SZ.000651 1m pre_breakdown` 已接管 `1m` 向下预警主位。 |
| `chanlun-rule-spec` 与严格版差异标注 | 中 | 把“现状 vs 目标”继续拆干净 | 进行中 | 55% | [线段主链](segment-tasks.md#s1-segment-bootstrap) / [走势主链](trend-divergence-tasks.md#td1-route-chain) / [买卖点差异](buy-sell-multi-level-tasks.md#bs1-diff-map) | 当前仍有部分段落把现状与目标写在一起；这是总规格文档继续收口的主入口。 |
| 线段 / 背驰 / 买卖点案例库 | 中 | 继续补原文正反例与映射 | 进行中 | 45%-58% | [线段回归](segment-tasks.md#s4-regression-gates) / [背驰案例](trend-divergence-tasks.md#td5-case-gates) / [买卖点案例](buy-sell-multi-level-tasks.md#bs6-case-gates) | 这三块 review 资料已起骨架，但距离“拿来即审”还有明显缺口。 |

#### 测试任务

| 任务 | 优先级 | 当前重点 | 当前状态 | 完成度 | 执行入口 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| `1m pre_breakout` 对称 gate 链 | 高 | 找到真实样本并补齐 `tech.json` + publish gate | 待完成 | 35% | [样本任务](zhongshu-tasks.md#zs53c-pre-breakout-sample) / [发布核验](zhongshu-tasks.md#zs53d-pre-breakout-publish) | 当前只有 synthetic gate，缺真实落盘样本。 |
| `1m pre_break*` 历史回放工具 | 高 | 用自动扫描缩短真实样本发现路径 | 进行中 | 65% | [探测链路](zhongshu-tasks.md#zs53c-pre-breakout-sample) | `build/probe_intraday_prebreak_sample.py` 已支持手工 cutoff 与 `--auto-find` 扫描。 |
| `1m pre_breakdown` 真实 gate 链 | 中 | 保持 `tech.json` / 文案 / publish 三层真实样本回归 | 进行中 | 86% | [中枢样本](zhongshu-tasks.md#zs53c-pre-breakout-sample) / [发布链](zhongshu-tasks.md#zs53d-pre-breakout-publish) | 真实 `000651 1m` 已补齐独立 `tech.json` gate、文案回归与 publish regression。 |
| 主辅冲突与重写回归集 | 中 | 补复杂 reclaim / gap / rewrite focused regressions | 进行中 | 58% | [线段回归](segment-tasks.md#s4-regression-gates) / [中枢回归](zhongshu-tasks.md#zs3-rewrite-gap) | 现有多组 focused regression 已落地，但复杂交界仍未完全锁死。 |

#### 代码任务

| 任务 | 优先级 | 当前重点 | 当前状态 | 完成度 | 执行入口 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 标准线段级中枢主实现 | 高 | 收口真实 `1m pre_breakout` 之外的主状态机缺口 | 进行中 | 89% | [状态机](zhongshu-tasks.md#zs2-state-machine) / [重写交界](zhongshu-tasks.md#zs3-rewrite-gap) | `ZS2.3a` 已完成首版转场字段与消费契约；`ZS3` 已补 synthetic + real fixture 两层 regression，当前新增锁住了 `00700 30m` 单活跃中枢与 `000591 60m long` 空集真值，并补了 `build/find_segment_reabsorbed_zhongshu_cases.py` 作为真实重吸收窗口探针。`nested deferred -> invalidated` 路径现已由参数化 regression 统一收口，覆盖 `1m/5m/30m/day` 首选级别与 `600900/01024` 跨标的锚点，并新增锚点健康检查确保数据窗口漂移不会先于业务断言失效；常用真实样本首轮扫描 `SCANNED 142 / MATCHED 0`，说明当前主缺口已更明确地落在“真实重吸收 cutoff 样本不足”以及 `ZS2.3b` 统一消费等级字段。 |
| 严格同级别走势类型自动分解 | 高 | 形成稳定自动判定闭环 | 进行中 | 45% | [TD1 主链](trend-divergence-tasks.md#td1-route-chain) | TD1 已落地 `type_chain` 首版并锁回归，背驰严格化进入 TD2/TD3。 |
| `tech.json` / 报告 / 小程序口径统一 | 高 | 继续把 pending / confirmed / auxiliary 三态落到消费层 | 进行中 | 82%-90% | [中枢消费](zhongshu-tasks.md#zs43-consumer-output) / [中枢三态](zhongshu-tasks.md#zs52-tristate-output) / [多级别降级](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | `1m pre_breakdown` 已打通，本轮又把 `transition_state` 接进同级别分解、报告 summary/advice、主分析文案、小程序 focus lines、detail overview bullets 与 index/group 聚合 item 消费链；下一重点是 `1m pre_breakout` 与 confirmed live 卡片。 |
| 趋势背驰 / 盘整背驰严格自动判定 | 中 | 把工程化 divergence 收口成严格判定链 | 进行中 | 65% | [趋势背驰](trend-divergence-tasks.md#td2-trend-divergence) / [盘整背驰](trend-divergence-tasks.md#td3-range-divergence) | 严格判定字段（TD2/TD3）与消费措辞（TD4）均已收口，案例回归归 TD5。 |
| 一二三类买卖点严格确认 | 中 | 与最近中枢、首次回抽、级别绑定收口 | 待完成 | 20%-28% | [一类点](buy-sell-multi-level-tasks.md#bs2-buy1) / [二类点](buy-sell-multi-level-tasks.md#bs3-buy2) / [三类点](buy-sell-multi-level-tasks.md#bs4-buy3) | 当前 buy/sell 规则还不等于严格原文确认链。 |

### 3.1 P0 严格理论主链路

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 标准线段级中枢主实现 | 进行中 | 84% | 当前已完成 `segment` 主口径锁定、仅已确认线段参与标准中枢、reclaim/吸收字段下沉、bootstrap / gap / reclaim / reverse_break 多条边界修正，以及多组真实 fixture regression 锁定；同时 `1m pre_breakdown` 已补到真实 `tech.json / advice_text / publish` 回归，review 主锚点也已切到真实样本，并新增 `build/probe_intraday_prebreak_sample.py` 作为 `1m pre_break*` 历史 cutoff 回放工具；本轮又补了 `relationship.transition_state` 首版 machine-readable 转场字段，并已接进同级别分解 summary/detail 消费层。`nested deferred -> invalidated` 交界已由参数化 regression 统一收口到 `1m/5m/30m/day` 首选级别并扩到 `600900/01024` 跨标的，同时增加了锚点健康检查。剩余主缺口集中在“真实 `1m pre_breakout` 样本”“真实 confirmed 页内卡片”“复杂 reclaim/重写 与 gap 再分辨交界统一”“中枢完成/扩张/新中枢切换”“标准中枢与后续买卖点绑定稳定化”。 |
| 严格同级别走势类型自动分解 | 进行中 | 45% | TD1 已落地 machine-readable `type_chain` 与过渡段转场字段；TD2/TD3 背驰严格判定仍待收口，执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 趋势背驰严格自动判定 | 进行中 | 55% | TD2 已落地 `divergence.trend` 的 `strict / reference_zs_id / departure_confirmed / strength_comparison`；消费端按 `strict` 措辞归 TD4，执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 盘整背驰严格自动判定 | 进行中 | 50% | TD3 已落地 `divergence.range` 的 `strict / reference_zs_id / touches_boundary / strength_comparison`；消费端措辞归 TD4，执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 一类买卖点严格确认 | 待完成 | 22% | 当前 buy_1/sell_1 更接近工程规则，不等于严格原文确认链；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 二类买卖点严格确认 | 待完成 | 20% | 需绑定 1 类点后的首次确认性回抽语义；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 三类买卖点严格确认 | 待完成 | 28% | 文档较清楚，但代码还需与最近中枢、首次回抽严格绑定；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |

### 3.2 P1 理论与工程对齐

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `chanlun-rule-spec` 与严格版差异标注 | 进行中 | 55% | 当前仍有部分段落把“现状”和“目标”写在一起；后续需按模块任务页逐项回写。 |
| 理论/实现/消费三层总差异表 | 进行中 | 92% | 字段级矩阵已大体成型；`1m pre_breakdown` 的真实样本、`tech.json` gate、文案、发布链和 review 主锚点已收口，剩余主要是真实 `1m pre_breakout`、真实 confirmed 页内卡片、工程近似阈值和少量未落主产物字段，详见 [zhongshu-tasks.md](zhongshu-tasks.md) 与 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| `src/chanlun/analysis.py` 买卖点逻辑差异表 | 待完成 | 15% | 需要逐条标记当前 buy/sell 条件与严格理论的偏差；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 类中枢与标准中枢字段完全拆分 | 进行中 | 45% | 文档已拆，输出字段与消费端仍需继续收敛；执行拆解见 [zhongshu-tasks.md](zhongshu-tasks.md)。 |
| 主辅冲突样例库 | 进行中 | 50% | 已有框架，还缺足量正反例；优先围绕中枢主辅冲突和买卖点降级补样例。 |

### 3.3 P1 review 资料层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 中枢严格定义图示库 | 进行中 | 82% | 已有 review 入口、页内真实卡片与消费对照；真实 `SZ.000651 1m pre_breakdown` 已接管 `1m` 向下预警主位，且 `1m pre_break*` 历史 cutoff 回放工具已补齐。剩余案例任务见 [zhongshu-tasks.md](zhongshu-tasks.md)。 |
| 线段严格定义案例库 | 进行中 | 58% | 已补复核矩阵与图示库骨架，仍需补 67/71 课正反例和 R1-R6 映射；执行拆解见 [segment-tasks.md](segment-tasks.md)。 |
| 背驰与盘整背驰标准案例包 | 进行中 | 45% | 已有复核矩阵与图示库骨架，仍需补统一正例、反例、易混淆例；执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 一二三类买卖点标准案例包 | 进行中 | 48% | 已有复核矩阵与图示库骨架，仍需按最近中枢和级别填充案例；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 多级别联立 review 模板 | 进行中 | 40% | 已有区间套/小转大图示骨架，仍需补高一级方向、操作级别、执行级别样例；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |

### 3.4 P2 输出与消费层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `tech.json` 严格结构状态字段补齐 | 阶段性完成 | 89% | `ZS2.3a` 的 `transition_state` 与 `ZS2.3b` 的 `same_level_consumption_level` 已共同收口到 `signals`、`tech.json root`、`summary.same_level_consumption_level*`、standalone 60m / wechat / mixed-report 技术产物根层，并已有 focused regression 锁住独立产物链。当前剩余重点主要转为真实 `1m pre_breakout`、节奏阈值精化与更高层结构真值样本。 |
| confirmed/pending/auxiliary 三态统一 | 阶段性完成 | 82% | 已有统一字段级文档口径，且核心/外围 consumer spec、报告文案、小程序卡片、publish bundle、独立 60m 与 mixed-report 产物链都已切到 `same_level_consumption_level` 主消费、`same_level_decomposition_mode` 兼容回退的正式口径。剩余主要是真实 `1m pre_breakout` 与 confirmed live 卡片落地。 |
| 小程序/报告端主辅口径显式展示 | 阶段性完成 | 88% | 已完成真实发布包样本首轮审计，并补上 `1m pre_breakdown` 的真实文案 / 发布 / review 主锚点闭环；本轮进一步收口了核心/外围 consumer 契约页与 standalone 60m export regression。剩余主要是真实 `1m pre_breakout`、confirmed live 卡片和少量 UI 回归校验。 |

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

### 4.1 模块任务文档使用方式

为避免“总表越做越长、做到哪算哪”，后续统一按以下方式维护：

1. [chanlun-spec-tasks.md](chanlun-spec-tasks.md) 只保留百分比、状态、优先级、跨模块依赖。
2. `segment / zhongshu / trend-divergence / buy-sell-multi-level` 各自维护独立 `*-tasks.md`，把 epic 拆成 task、验收、blocker。
3. 每完成一个 task，先回写模块任务页，再同步总表百分比和状态。
4. 若一个 task 会影响多个模块，统一在总表里记录依赖方向，避免 reviewer 只看到局部结论。

### 4.2 `segment` 下一步拆分

详细拆解见 [segment-tasks.md](segment-tasks.md)。当前优先顺序不变：

1. 线段成立与终结条件。
2. `pending_confirmation` 与 `confirmed` 的统一判定。
3. 线段重写、吸收、复用时的输出口径。

完成这 3 项后，再进入 `zhongshu` 会更稳，因为中枢的进入笔、离开笔、扩张边界与完成状态都直接依赖线段边界是否稳定。

本轮 `segment` review 入口：

- [segment-review-entry.md](segment-review-entry.md)
- 用途：统一原文定义、当前实现、`pending_confirmation` / 再分辨 / 重写吸收样例，以及下游字段红线。
- 当前进展：`segment-visual-example-library.md` 已从纯模板推进到“模板 + 规范回归案例 + 真实回归窗口案例”，现成入口包括 `SZ.000651 30m`、`SZ.000591 15m`、`HK.00700 15m`。

本轮 `zhongshu` review 入口：

- [zhongshu-review-entry.md](zhongshu-review-entry.md)
- 用途：统一原文定义、页内真实卡片、`tech.json` / 报告 / 小程序消费红线，以及 `1m / 5m / 30m / day映射` 的示例优先级。
- 当前进展：`zhongshu-visual-example-library.md` 第 1 至第 4 节均已进入页内可审状态；`zhongshu-consumer-display-examples.md` 已补同案三栏对照，当前主锚点包括 `HK.02357 1m range ongoing`、`HK.01339 1m completed_then_new_type`、真实 `SZ.000651 1m pre_breakdown`、`SH.601328 1m pre-warning proxy`、`1m confirmed 3S` regression reference、`SH.601318 5m down_bias`、`SZ.000651 30m -> day`、`SZ.002594 30m pre_breakout`。其中 `SH.601328 1m` 目前仅作 `1m` 预警前态代理锚点；真实 `SZ.000651 1m` 已接管向下预警主入口，当前主要缺口收敛为真实 `1m pre_breakout` 与真实 confirmed 页内卡片。
- 当前进展补充：已新增 `build/probe_intraday_prebreak_sample.py` 作为 `1m pre_break*` 历史 cutoff 回放工具，并已用它首轮回放否定 `00981 / 00728 / 06088` 三组高优先 `1m pre_breakout` 窗口；下一步应扩历史窗口或换新标的，不再重复把这三组首轮窗口当主候选。
- 当前进展补充：`zhongshu-tasks.md` 的 `ZS6.3` 已把 `30m pre_breakout`、`30m pre_breakdown/route`、`5m down_bias` 收口到具名 pytest；`1m-confirmed-3s-reference-gate` 与 `1m-proxy-negative-transition-gate` 也已落到 `tests/test_build_miniapp_publish_bundle.py`；正式 `1m pre_breakdown` 现已同时具备真实样本 `tech.json` gate 与 publish regression，`1m pre_breakout` 仍停留在 synthetic gate 与样本缺口阶段。

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