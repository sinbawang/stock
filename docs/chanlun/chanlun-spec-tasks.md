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
| 原文逐课复核 | 是否已有逐课对照与差异记录 | 92% |
| 当前工程口径沉淀 | 现状实现、契约、样例是否可追踪 | 86% |
| 严格理论自动化实现 | §3.1–§3.4 跟踪项完成度的算术平均（可复算） | 82% |
| 综合进度 | 上表四个维度的算术平均 | 86% |

说明：

- 文档层完成度高于实现层。
- 当前项目“能跑”不等于“已严格按原文完成”。
- 低于 50% 的模块，通常不是缺样例，而是缺严格自动判定链路。
- **口径（2026-09-12 起）**：`严格理论自动化实现` = §3.1–§3.4 全部跟踪项完成度的算术平均（20 项，
  合计 1638，均值 81.90 → 82%）；`综合进度` = 上表四个维度的算术平均（(82+92+86+82)/4 = 85.5 → 86%）。
  此前该两行为人工估算（58% / 68%），与分项明显脱节，且无法复算；改为可复算口径后为 82% / 86%。
  复算：`python scripts/check_spec_progress.py`（返回码非 0 表示口径不自洽）；
  自检：`python scripts/check_spec_progress.py --selftest`。
- **2026-09-12 核对订正**：对照 `zhongshu-tasks.md` / `trend-divergence-tasks.md` 的 epic 看板与
  代码实际输出，确认 3 项此前记为「进行中」的分项其实已落地（见 §3.1 / §3.2 对应行的证据），
  同时修正 1 处同页状态自相矛盾。分项行是权威源，本页百分比只是聚合。
- **2026-09-12 新增下游闸门**：以一次性探针对全部冻结真实窗口核查了「线段 → 标准中枢 →
  笔级类中枢 → 买卖点」各层的推进程度，**未发现静默停滞**（最差 `segment → 标准中枢`
  lag 比例 8/22 = 0.36）；随后把该不变量固化为 `tests/test_downstream_chain_integrity.py`
  并注册进 `scripts/run_segment_safety_gates.py` 的 `regression` 闸门，见
  [segment-safety-checklist.md](segment-safety-checklist.md)。
- **2026-09-12 多级别降级 fail-open 修复**：共享兜底 `_build_same_level_consumption_level`
  在缺证据时默认 `confirmed`，会击穿「高一级未确认时下游不得越级显示强确认」红线；
  已按 ZS5.2 契约改为降级，并以全参数空间不变量闸门
  `tests/test_multilevel_downgrade_invariant.py` 锁定。详见
  [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md) T2 / C3 行。

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
- [x] 建立同级别分解理论规格 [same-level-decomposition-spec.md](same-level-decomposition-spec.md)，把中枢形成 / 盘整候选 / 趋势形成 / 切点确认的判定顺序写成应然口径，并与工程主链 [trend-type-decomposition.md](trend-type-decomposition.md) 拆开。

### 2.2 原文对照层

- [x] 完成第 17/18/20/21/25/29/36/38/39/53/83/92 课首轮复核框架。
- [x] 明确“基本一致”与“工程近似/待补”的区分，不再把两者混写成同一口径。
- [x] 明确中枢主口径为线段级，类中枢为笔级辅助口径。
- [x] 新增课程可追溯矩阵 [lesson-traceability-matrix.md](lesson-traceability-matrix.md)，把第 24/25/27/33/35/37/40/43/44/61/86/102 课映射到 spec/design/tasks/tests/code 五层，并区分“显式映射 / 部分覆盖 / 缺口”。

口径说明：本页“严格理论自动化实现 82% / 综合 86%”面向代码落地（2026-09-12 起改为 §3.1–§3.4 分项算术平均，可复算）；“首轮 12 课复核闭环”面向文档层，二者不矛盾，详细澄清见 [lesson-traceability-matrix.md](lesson-traceability-matrix.md) 的“口径澄清”。

### 2.3 工程现状沉淀层

- [x] 分型、笔、线段、类中枢已有工程主链路。
- [x] 线段终结、`stop_reason`、theory/practical 双模式已有契约和说明。
- [x] 发布/分析消费端已有主辅冲突与降级语义的基本约束。
- [x] 已沉淀样例包、图文化示例库、节奏回放模板。
- [x] 已为中枢沉淀 `1m / 5m / 30m / day映射` 优先的 review 与消费示例链，其中 `HK.02357 1m` 已作为 watch/pending 场景锚点接入，`HK.01339 1m` 已作为 completed_then_new_type 场景锚点接入，真实 `SZ.000651 1m` 已作为正式 `pre_breakdown` 场景锚点接入，`SH.601328 1m` 已作为预警前态代理锚点接入，真实 `600900 1m confirmed 3S` 与真实 `00700 5m confirmed buy2like` 已分别补齐卖侧/买侧 confirmed live 锚点；后续优先缺口收敛为稳定的 `1m confirmed` 买点样本与更多 confirmed 多案例对照。
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
| 理论/实现/消费三层总差异表 | 高 | 继续压缩 `1m pre_breakout` 与 confirmed live 卡片缺口 | 进行中 | 95% | [中枢映射](zhongshu-tasks.md#zs53e-review-gate-map) / [背驰字段](trend-divergence-tasks.md#td4-output-fields) / [买卖点差异](buy-sell-multi-level-tasks.md#bs1-diff-map) | `1m pre_breakdown` 的真实样本、`tech.json` gate、文案、发布链和 review 主锚点已收口；`1m pre_breakout` 已补 `002555` + `03690` + `600900` 三真实 analysis/publish gate。 |
| 中枢严格定义图示库 | 高 | 补真实 `1m pre_breakout` 卡片与 confirmed live 卡片 | 进行中 | 87% | [样例卡片](zhongshu-tasks.md#zs62-review-cases) | 真实 `SZ.000651 1m pre_breakdown` 已接管 `1m` 向下预警主位；`1m pre_breakout` 已有 `002555` + `03690` + `600900` 三真实 replay 样本可作卡片主锚点。 |
| `chanlun-rule-spec` 与严格版差异标注 | 中 | 把“现状 vs 目标”继续拆干净 | 进行中 | 55% | [线段主链](segment-tasks.md#s1-segment-bootstrap) / [走势主链](trend-divergence-tasks.md#td1-route-chain) / [买卖点差异](buy-sell-multi-level-tasks.md#bs1-diff-map) | 当前仍有部分段落把现状与目标写在一起；这是总规格文档继续收口的主入口。 |
| 线段 / 背驰 / 买卖点案例库 | 中 | 继续补原文正反例与映射 | 进行中 | 45%-58% | [线段回归](segment-tasks.md#s4-regression-gates) / [背驰案例](trend-divergence-tasks.md#td5-case-gates) / [买卖点案例](buy-sell-multi-level-tasks.md#bs6-case-gates) | 这三块 review 资料已起骨架，但距离“拿来即审”还有明显缺口。 |

#### 测试任务

| 任务 | 优先级 | 当前重点 | 当前状态 | 完成度 | 执行入口 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| `1m pre_breakout` 对称 gate 链 | 高 | 找到真实样本并补齐 `tech.json` + publish gate | 完成 | 100% | [样本任务](zhongshu-tasks.md#zs53c-pre-breakout-sample) / [发布核验](zhongshu-tasks.md#zs53d-pre-breakout-publish) | 真实 replay 三锚点已落地：`002555 2026-08-04 13:35` + `03690 2026-08-05 09:56` + `600900 2026-08-04 13:18`，analysis 与 publish 双真实 gate 均已固化，并移除 `_replay` 内 synthetic fallback。 |
| `1m pre_breakout` 扩样本广度（P0.1） | 高 | 三锚点基础上的扩样本已收口，后续转维护回归稳定性 | 完成 | 100% | [样本任务](zhongshu-tasks.md#zs53c-pre-breakout-sample) / [发布核验](zhongshu-tasks.md#zs53d-pre-breakout-publish) | `build/scan_real_1m_prebreakout_samples.json` 已确认 16/16 标的存在历史 cutoff。`01024 2026-08-10 09:56`、`09988 2026-08-05 10:01`、`00700 2026-08-05 10:01` 均已新增 analysis + publish 双 gate；`2026-09-06` 关门验收回归（6 条：analysis 3 + publish 3）已通过（6/6）。 |
| `1m pre_break*` 历史回放工具 | 高 | 用自动扫描缩短真实样本发现路径 | 完成 | 100% | [探测链路](zhongshu-tasks.md#zs53c-pre-breakout-sample) | `build/probe_intraday_prebreak_sample.py` 已支持手工 cutoff 与 `--auto-find` 扫描；`build/scan_real_1m_prebreakout_samples.py` 与对称的 `build/scan_real_1m_prebreakdown_samples.py` 已分别确认 16/16 个 `1m` 标的均存在真实 `pre_breakout` / `pre_breakdown` 历史 cutoff，上/下双向探测工具已闭环。 |
| `1m pre_breakdown` 真实 gate 链 | 中 | 保持 `tech.json` / 文案 / publish 三层真实样本回归 | 完成 | 100% | [中枢样本](zhongshu-tasks.md#zs53c-pre-breakout-sample) / [发布链](zhongshu-tasks.md#zs53d-pre-breakout-publish) | 真实 `000651 1m` 已补齐独立 `tech.json` gate、文案回归与 publish regression；`2026-08-23` 又补第二个真实锚点 `03690 2026-08-05 09:46`（analysis + publish 双 gate），与 `03690 09:56 pre_breakout` 构成同日同标对照。 |
| 主辅冲突与重写回归集 | 中 | 补复杂 reclaim / gap / rewrite focused regressions | 进行中 | 70% | [线段回归](segment-tasks.md#s4-regression-gates) / [中枢回归](zhongshu-tasks.md#zs3-rewrite-gap) | 现有多组 focused regression 已落地；`2026-08-23` 补了首选级别（1m/5m）多中枢真实窗口 gate（`600900 1m`、`09988 1m`、`03690 5m`、`00700 1m`），并确认真实 `reabsorbed lineage` 为确定性数据缺口（全量 558 窗口 + 09988 1334 瞬态 MATCHED 0）。 |

#### 代码任务

| 任务 | 优先级 | 当前重点 | 当前状态 | 完成度 | 执行入口 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 标准线段级中枢主实现 | 高 | 转向 `candidate_new_type` 真实窗口回放与 confirmed 对照扩样本 | 完成 | 94% | [状态机](zhongshu-tasks.md#zs2-state-machine) / [重写交界](zhongshu-tasks.md#zs3-rewrite-gap) | `ZS2.3a` 已完成首版转场字段与消费契约；`ZS3` 已补 synthetic + real fixture 两层 regression，当前新增锁住了 `00700 30m` 单活跃中枢与 `000591 60m long` 空集真值，并补了 `build/find_segment_reabsorbed_zhongshu_cases.py` 作为真实重吸收窗口探针。`2026-09-06` 补齐了弱同向笔紧邻创新极值时的线段延伸规则（含 bootstrap 保护网），线段延伸逻辑现已涵盖"即使当前同向笔未创新高/低，只要紧邻下一根同向笔立即创出段内新极值，就继续延伸"（仅非首段放开），进一步提高线段判定完整性；`1m pre_breakout` 扩样本（01024/09988/00700）已关门回归 `6/6`。`candidate_new_type` 根因已确认：不是结构逻辑失真，而是 coarse scan 以大步长前缀遍历跳过短 strict 窗口；已修复为 coarse + fine-grained fallback，并新增针对 `scan_real_candidate_new_type_samples.py` 的 regression，当前严格 probe 结果已在 `002555 5m`、`00981 1m`、`03690 5m`、`06088 1m`、`01024 5m` 上稳定命中 `matches=5`。 |
| 严格同级别走势类型自动分解 | 高 | 维持主链稳定并继续补真实样本 / 展示回归 | 阶段性完成 | 88% | [TD1 主链](trend-divergence-tasks.md#td1-route-chain) | TD1 主链、publish/miniapp 消费、`type_chain` 透传与核心回归已闭环，并已补 `09988 1m` / `03690 5m` 真实窗口 gate；`candidate_new_type` 当前转由扫描工具持续搜当前 live cutoff，剩余主要是更多真实窗口覆盖、图示/案例绑定与前端展示细化。 |
| `tech.json` / 报告 / 小程序口径统一 | 高 | 维持主消费口径稳定并继续补真实样本 / 卡片广度 | 阶段性完成 | 88%-92% | [中枢消费](zhongshu-tasks.md#zs43-consumer-output) / [中枢三态](zhongshu-tasks.md#zs52-tristate-output) / [多级别降级](buy-sell-multi-level-tasks.md#bs5-multi-level-consumer) | `same_level_consumption_level` / `transition_state` / `lifecycle_state`、forming / invalidated、区间套 `dynamic_grade` / `small_to_large_status` 与买卖点降级文案已贯通 `signals`、`tech.json`、报告、小程序与 publish bundle；剩余重点转为真实 `1m pre_breakout`、confirmed live 卡片与样本广度。 |
| 趋势背驰 / 盘整背驰严格自动判定 | 中 | 把工程化 divergence 收口成严格判定链 | 完成 | 98% | [趋势背驰](trend-divergence-tasks.md#td2-trend-divergence) / [盘整背驰](trend-divergence-tasks.md#td3-range-divergence) | 2026-09-12 核对：严格判定字段（TD2/TD3）、消费措辞（TD4）、案例回归（TD5）均已收口，与 §3.1 两行改为一致口径。剩余只有真实样本与易混淆反例广度。 |
| 一二三类买卖点严格确认 | 中 | 转向样例广度、review 资料与跨级别对照 | 完成 | 98% | [一类点](buy-sell-multi-level-tasks.md#bs2-buy1) / [二类点](buy-sell-multi-level-tasks.md#bs3-buy2) / [三类点](buy-sell-multi-level-tasks.md#bs4-buy3) | 一二三类点已在段级中枢链路上按最近中枢 + 离开段 / 回抽 + 转折确认收口；一 / 二类的 bi-level 中枢回退已收敛为「仅观察 / 执行级别用途」，不再冒充操作级别确认点；剩余主要是案例广度与跨级别 review 资料。 |

### 3.1 P0 严格理论主链路

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 标准线段级中枢主实现 | 完成 | 94% | 当前已完成 `segment` 主口径锁定、仅已确认线段参与标准中枢、reclaim/吸收字段下沉、bootstrap / gap / reclaim / reverse_break 多条边界修正，以及多组真实 fixture regression 锁定；`2026-09-06` 新增弱同向笔延伸规则（含 bootstrap 保护），进一步完善线段延伸判定链；`1m pre_breakdown` / `1m pre_breakout`（002555/03690/600900）与 confirmed 3S/3B live 样本均已补真实回归；`transition_state` / `consumption_level` 转场字段已贯通消费层；复杂 reclaim/重写与 gap 交界、中枢完成/扩张/新中枢切换、标准中枢与后续买卖点绑定（买卖点段级化）均已收口。`candidate_new_type` 的实质问题已被确认并修正：粗扫描步长错误导致短 strict 窗口被跳过；现细粒度 fallback 已落地并通过 `tests/test_scan_real_candidate_new_type_samples.py` 回归。当前仅剩真实样本广度与文档同步，不再阻塞主实现。 |
| 严格同级别走势类型自动分解 | 阶段性完成 | 88% | 同级别分解 spec、TD1 主链、`type_chain` / `transition_state` / `same_level_consumption_level` 字段与 publish/miniapp 消费链已收口，并已补 `09988 1m` / `03690 5m` 真实窗口 gate；`candidate_new_type` 当前转由扫描工具持续搜当前 live cutoff，剩余主要是样例库、真实窗口广度与前端展示细化，执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 趋势背驰严格自动判定 | 完成 | 98% | 2026-09-12 核对：`src/chanlun/analysis.py` 的 `divergence.trend` 实际输出 `strict / reference_zs_id / departure_confirmed / strength_comparison`（L1008-1011），TD2 严格判定链已落地；消费端按 `strict` 措辞已在 TD4 收口，TD5 案例回归完成，`trend-divergence-tasks.md` epic 看板 TD2 亦为「完成」。剩余只剩真实样本广度（另见 §3.3 案例库行）。 |
| 盘整背驰严格自动判定 | 完成 | 98% | 2026-09-12 核对：`src/chanlun/analysis.py` 的 `divergence.range` 实际输出 `strict / reference_zs_id / touches_boundary / strength_comparison`（L1022-1025），TD3 已与趋势背驰分轨独立判定；消费端措辞归 TD4、案例归 TD5，两者均完成。剩余只剩真实样本与易混淆反例广度（另见 §3.3）。 |
| 一类买卖点严格确认 | 完成 | 98% | buy_1/sell_1 已落地“确认离开 + 反向转折 + 段级「离开段 vs 进入段」力度、边界、转折均以离开段末笔为基准”（信号锚点 `_bi_by_id(exit_segment.end_bi_id)`）；RS3 后 bi-level 中枢不再发操作级别一类点，仅保留观察 / 执行级别用途；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 二类买卖点严格确认 | 完成 | 98% | 已落地「绑定一买/一卖 + 不破前低/前高 + 首次回抽锁定 + 再度走强/走弱（创新高/新低）」，段级链路上前置/不破前低以离开段末笔为锚点；`_is_first_reverse_hold` 已补首次窗口占用 / 破位失败口径，且 RS3 后 bi-level 中枢不再发操作级别二类点；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 三类买卖点严格确认 | 完成 | 97% | 已落地「离开 + 不回归 + 首次回试锁定 + 回试后重新向上/向下」，段级链路上离开以向上/向下离开段为锚点、信号价格锚定在首次回试/反抽极值（不强制创新高/新低，贴合第20课）；RS0 已补跨帧回中枢 invalidated 护栏；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |

### 3.2 P1 理论与工程对齐

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `chanlun-rule-spec` 与严格版差异标注 | 进行中 | 55% | 当前仍有部分段落把“现状”和“目标”写在一起；后续需按模块任务页逐项回写。 |
| 理论/实现/消费三层总差异表 | 进行中 | 95% | 字段级矩阵已大体成型；`1m pre_breakdown` 与 `1m pre_breakout` 的真实样本、`tech.json` gate、文案、发布链和 review 主锚点均已收口（`pre_breakout` 已补 `002555` + `03690` + `600900` 三真实锚点），剩余主要是 confirmed 页内卡片广度、工程近似阈值和少量未落主产物字段，详见 [zhongshu-tasks.md](zhongshu-tasks.md) 与 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| `src/chanlun/analysis.py` 买卖点逻辑差异表 | 完成 | 95% | BS1 差异表已逐条标记 buy_1/2/3、sell_1/2/3 的严格一致 / 工程近似 / 待实现，并回写了 RS2 多级别联立、RS3 级别收敛与首次回抽窗口收口结果；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 类中枢与标准中枢字段完全拆分 | 完成 | 98% | 2026-09-12 核对：`src/chanlun/zhongshu_contract.py` 落实 `SPEC.ZHONGSHU.DUAL_TRACK`；`Zhongshu.structure_level` 区分 `segment`（标准）与类中枢；主产物分列 `latest_zhongshu` / `latest_lei_zhongshu`，analyze 侧产出独立 `*_normalized_zhongshu_lei.csv`；消费端（summary / 报告 / 小程序）与图表 `lei_zhongshus` 分轨均已贯通。`zhongshu-tasks.md` 的 ZS4（含 ZS4.1-ZS4.3）均为「完成」。剩余为样例广度。 |
| 主辅冲突样例库 | 进行中 | 50% | 已有框架，还缺足量正反例；优先围绕中枢主辅冲突和买卖点降级补样例。 |

### 3.3 P1 review 资料层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 中枢严格定义图示库 | 进行中 | 87% | 2026-09-12 核对：与 §3.0A 同名行百分比不一致（此处 82% 来自 2026-08-20 的 `72598775`，§3.0A 的 87% 来自 2026-08-23 的 `f0e0654b`，以后者为准）。已有 review 入口、页内真实卡片与消费对照；真实 `SZ.000651 1m pre_breakdown` 已接管 `1m` 向下预警主位，`1m pre_breakout` 已有 `002555` + `03690` + `600900` 三真实 replay 样本可作卡片主锚点，`1m pre_break*` 历史 cutoff 回放工具已补齐。剩余案例任务见 [zhongshu-tasks.md](zhongshu-tasks.md)。 |
| 线段严格定义案例库 | 进行中 | 58% | 已补复核矩阵与图示库骨架，仍需补 67/71 课正反例和 R1-R6 映射；执行拆解见 [segment-tasks.md](segment-tasks.md)。 |
| 背驰与盘整背驰标准案例包 | 进行中 | 45% | 已有复核矩阵与图示库骨架，仍需补统一正例、反例、易混淆例；执行拆解见 [trend-divergence-tasks.md](trend-divergence-tasks.md)。 |
| 一二三类买卖点标准案例包 | 进行中 | 48% | 已有复核矩阵与图示库骨架，仍需按最近中枢和级别填充案例；执行拆解见 [buy-sell-multi-level-tasks.md](buy-sell-multi-level-tasks.md)。 |
| 多级别联立 review 模板 | 进行中 | 68% | 已补区间套/小转大图示骨架，并新增前端可见级别的页内卡片：真实 `600900 1m confirmed 3S`、真实 `002555 1m -> 5m` 候选观察链，以及 `5m buy3 -> third_class_confirmed` 契约对照卡；RS2 已落地 `higher_level_confirmed` 自动升级与区间套反向确认，后续主要补更多 `1m/5m/day` 样本广度与页内对照。 |

### 3.4 P2 输出与消费层

| 任务 | 当前状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| `tech.json` 严格结构状态字段补齐 | 阶段性完成 | 89% | `ZS2.3a` 的 `transition_state` 与 `ZS2.3b` 的 `same_level_consumption_level` 已共同收口到 `signals`、`tech.json root`、`summary.same_level_consumption_level*`、standalone 60m / wechat / mixed-report 技术产物根层，并已有 focused regression 锁住独立产物链。当前剩余重点主要转为真实 `1m pre_breakout`、节奏阈值精化与更高层结构真值样本。 |
| confirmed/pending/auxiliary 三态统一 | 阶段性完成 | 88% | 已有统一字段级文档口径，且核心/外围 consumer spec、报告文案、小程序卡片、publish bundle、独立 60m 与 mixed-report 产物链都已切到 `same_level_consumption_level` 主消费、`same_level_decomposition_mode` 兼容回退的正式口径；买卖点侧 RS1-RS5 的 `forming / confirmed / invalidated` 生命周期与多级别降级也已贯通。剩余主要是真实 `1m pre_breakout` 与 confirmed live 卡片广度。 |
| 小程序/报告端主辅口径显式展示 | 阶段性完成 | 91% | 已完成真实发布包样本首轮审计，并补上 `1m pre_breakdown` 的真实文案 / 发布 / review 主锚点闭环；买卖点页现已透出 `lifecycle_state`、forming / invalidated、`dynamic_grade`、`small_to_large_status` 与失效文本行。剩余主要是真实 `1m pre_breakout`、confirmed live 卡片和少量 UI 回归校验。 |

## 4. 下一阶段建议顺序

按「先正确识别当下结构，再精确买卖点，最后迭代收口」的优先级推进（优先保证：**当下走势类型 → 最近中枢 → 一二三类买卖点**识别正确，再不断迭代完善）：

1. 巩固上游基础（基础结构 / 线段）：已较完整，维持现状与回归闸门，不再新增主线工作。
2. 维持「当下走势类型 + 最近中枢」主链稳定：TD1 同级别分解与 ZS 标准中枢主链已能稳定给出 `current_ongoing.type`、`current_zs`、`type_chain`，下一步重点转为真实窗口广度与样例绑定，而非重写主逻辑。
3. 继续补「一二三类买卖点严格确认」的样例广度与 review 资料：主判定链已落地，剩余重点是更多正反例与跨级别样本。
4. 继续补「趋势背驰 / 盘整背驰」真实样本与案例库（TD2/TD3 已落地、TD5 持续扩样）：作为一类点支撑，优先补图示库和易混淆反例。
5. 迭代完善：输出差异表、前端/小程序展示细化、真实样本案例包，逐项压缩工程近似与文档残留旧措辞。

依赖说明：走势类型依赖中枢、中枢依赖线段，因此 1 是 2/3 的前置；但线段已较稳定，不再作为主线阻塞项，重点是 2 → 3 这条「结构 → 买卖点」正确性链。

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
- 当前进展：`zhongshu-visual-example-library.md` 第 1 至第 4 节均已进入页内可审状态；`zhongshu-consumer-display-examples.md` 已补同案三栏对照，当前主锚点包括 `HK.02357 1m range ongoing`、`HK.01339 1m completed_then_new_type`、真实 `SZ.000651 1m pre_breakdown`、`SH.601328 1m pre-warning proxy`、真实 `600900 1m confirmed 3S`、真实 `00700 5m confirmed buy2like`、`1m confirmed 3S` regression reference、`SH.601318 5m down_bias`、`SZ.000651 30m -> day`、`SZ.002594 30m pre_breakout`。其中 `SH.601328 1m` 目前仅作 `1m` 预警前态代理锚点；真实 `SZ.000651 1m` 已接管向下预警主入口，当前主要缺口收敛为稳定的 `1m confirmed` 买点样本与更多 confirmed 多案例对照。
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
- 例外：§1 的 `严格理论自动化实现` 与 `综合进度` 是 §3.1–§3.4 分项完成度的**算术平均**，按可复算口径计算，不使用上述档位；分项行始终是权威源。改动分项后请同步跑 `scripts/check_spec_progress.py`。

若后续实现或复核推进，优先更新本文件，再回写对应专题文档，避免进度信息散落在多个说明页。