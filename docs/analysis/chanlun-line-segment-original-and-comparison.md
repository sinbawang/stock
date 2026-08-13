# 缠论原文关于线段划分的提炼与项目实现对照

## 文档角色与入口

这份文档定位为“原文对照 + 差异分析 + 演进记录”，不是当前工程规则的唯一规范入口。

当前建议按以下入口使用：

- 现行实现口径： [../chanlun/segment-implementation-guide.md](../chanlun/segment-implementation-guide.md)
- 稳定接口契约： [../chanlun/segment-stop-reason-contract.md](../chanlun/segment-stop-reason-contract.md)
- 线段文档地图： [../chanlun/segment-doc-map.md](../chanlun/segment-doc-map.md)

## 1. 原文中“线段划分”的核心定义

下面内容是从《教你炒股票》相关课文中提炼出的关键段落，重点对应 62、67、71 课。

### 1.1 线段的基本构成

> “两个相邻的顶和底之间构成一笔……而所谓的线段，就是至少由三笔组成。”

> “线段有一个最基本的前提，就是线段的前三笔，必须有重叠的部分……线段至少有三笔，但并不是连续的三笔就一定构成线段，这三笔必须有重叠的部分。”

### 1.2 线段的方向与特征序列

> “用 S 代表向上的笔，X 代表向下的笔。那么所有的线段，无非两种：一、从向上笔开始；二、从向下笔开始。”

> “以向上笔开始的线段，可以用笔的序列表示：S1X1S2X2S3X3…SnXn。容易证明，任何 Si 与 Si+1 之间，一定有重合区间。而考察序列 X1X2…Xn，该序列中，Xi 与 Xi+1 之间并不一定有重合区间，因此，这序列更能代表线段的性质。”

> “定义：序列 X1X2…Xn 成为以向上笔开始线段的特征序列；序列 S1S2…Sn 成为以向下笔开始线段的特征序列。特征序列两相邻元素间没有重合区间，称为该序列的一个缺口。”

### 1.3 线段终结的严格判定条件

> “特征序列的顶分型中，第一和第二元素间不存在特征序列的缺口，那么该线段在该顶分型的高点处结束，该高点是该线段的终点。”

> “特征序列的顶分型中，第一和第二元素间存在特征序列的缺口，如果从该分型最高点开始的向下一笔开始的序列的特征序列出现底分型，那么该线段在该顶分型的高点处结束，该高点是该线段的终点。”

> “上面两种情况，就给出所有线段划分的标准。显然，出现特征序列的分型，是线段结束的前提条件。”

### 1.4 线段被破坏的充要条件

> “缠中说禅线段分解定理：线段被破坏，当且仅当至少被有重叠部分的连续三笔的其中一笔破坏。而只要构成有重叠部分的前三笔，那么必然会形成一线段，换言之，线段破坏的充要条件，就是被另一个线段破坏。”

### 1.5 过渡点的边界情况

> “从转折点开始，如果第一笔就破坏了前线段，进而该笔延伸出三笔来，其中第三笔破点第一笔的结束位置，那么，新的线段一定形成，前线段一定结束。”

> “这种情况还有更复杂一点的情况，就是第三笔完全在第一笔的范围内……这种情况下，无非两种最后的结果：一是最终还是先破了第一笔的结束位置，这时候，新的线段显然成立，旧线段还是被破坏了；二是最终，先破第一笔的开始位置，这样，旧线段只被一笔破坏，接着就延续原来的方向，那么，显然旧线段依然延续，新线段没有出现。”

---

## 2. 当前项目实现的主要位置

项目中与线段识别相关的实现主要在：

- [src/chanlun/models.py](src/chanlun/models.py)：定义 Segment 数据结构。
- [src/chanlun/segment.py](src/chanlun/segment.py)：核心线段识别逻辑。
- [src/chanlun/cli.py](src/chanlun/cli.py) 和 [src/chanlun/chart_export.py](src/chanlun/chart_export.py)：调用识别函数并输出结果。

### 2.1 当前实现的基本思路

当前实现大致是：

1. 先从三笔构成一个初始种子，要求方向交替且首尾笔同向，并且前三笔有公共重叠区间；
2. 再往后扩展线段，并跟踪“反向特征序列”的顶/底分型；
3. 如果特征序列形成了分型，或者出现了缺口分型候选，则试图确认旧线段终结；
4. 如果上述理论条件没有成立，则退回为“反向笔直接突破最近关键点”等工程化兜底规则。

---

## 3. 对照后发现的主要不准确/不严格之处

### 3.1 现有实现把“理论判定”和“工程兜底”混在同一个扩展循环里

原文的目标非常明确：线段的终结应基于“特征序列的分型 / 缺口分型”这一严格几何条件。当前实现虽然在 [src/chanlun/segment.py](src/chanlun/segment.py) 中实现了 `_feature_sequence_break()` 和 `_gap_feature_sequence_candidate()`，但实际判定流程中又加入了大量别的中间状态：

- `reverse_break`
- `reverse_break_after_gap`
- `unexpected_same_direction`
- `same_direction_not_extending`
- `same_direction_slot_not_filled`

这说明当前实现已经不是单纯“按原文定义唯一划分”的严格几何器，而是“理论判定 + 实盘兜底”的混合算法。它的优点是实用，但严格性没有完全对齐原文。

建议：把“理论主路径”和“工程兜底路径”分成两个层级：

- 第一层：只用特征序列分型 / 缺口分型来判定线段终结；
- 第二层：只有在第一层没有形成明确分型时，才启用 `reverse_break` 等兜底规则。

### 3.2 缺口分型的再分辨逻辑是工程化近似，不是原文的纯理论判定

原文里关于“缺口”的表述是：当特征序列的第一和第二元素之间有缺口时，只有当后续相反方向序列的分型出现，才能确认旧线段结束。这个逻辑在当前代码中被拆成了一套更复杂的状态机：

- `_gap_feature_sequence_candidate()` 先找出缺口候选；
- `_evaluate_pending_gap_candidate()` 再做再分辨；
- `_rediscriminate_gap_break_detail()` 还引入了“弱同向未突破 / 强同向推进”这种延迟确认概念。

这类判断对实盘很有帮助，但它并不等价于原文的“缺口必须由后续相反方向序列的分型封闭”这一条。换言之，当前实现更像“实盘可用的近似版”，而不是“严格版理论定义”。

建议：把这部分抽象为一个清晰的状态机：

- `gap_candidate_pending`
- `gap_confirmed`
- `gap_invalidated`
- `gap_deferred`

并且明确记录这一次是“严格理论确认”还是“工程兜底确认”。

### 3.3 当前实现没有把“转折点起始第一笔破坏前线段”的边界情况正式建模

原文特别强调了一个很关键的边界条件：

> 如果第一笔就破坏了前线段，且后续延伸出三笔，第三笔再破点第一笔的结束位置，那么新的线段一定形成，前线段一定结束。

而如果第三笔完全落在第一笔的范围内，则需要继续看是先破结束位置还是先破起始位置，才能决定是新线段成立还是旧线段继续延续。

当前代码中虽然有 `_reclaims_transition_back_to_prior_segment()`，但它主要是通过“反向笔是否重新回到原段方向/破坏起点”来做回收判断，属于经验式处理，并没有把原文那个“中间地带”的待定状态完整表达出来。

建议：增加一个明确的“待定过渡态”（例如 `transition_pending`），在这类边界案例中不急着给出最终结论，而是等后续再看是否出现三笔成立的新线段。

### 3.4 当前实现对“线段前三笔必须有重叠”的约束是做了，但后续扩展/过渡阶段没有保留原文那种“同一特征序列内的包含关系”语义

原文中非常强调：

- 线段的“特征序列元素”必须是在“同一特征序列”内部讨论包含关系；
- 这不是简单地拿某个高点/低点和前后所有笔做比较，而是要在一个明确的特征序列上下文中判断。

当前代码里的 `_build_standard_feature_sequence()` 和 `_contains()` 做了一个很接近的抽象，但它们是面向“工程化窗口”的实现。对于“同一特征序列”的概念，它没有在数据结构层面做出显式的状态分隔，也没有把“元素属于前一段/后一段/中间过渡区”的边界状态清晰表示出来。

建议：把“特征序列元素”抽成一个更显式的结构，显式保存：

- 所属特征序列 ID；
- 是否属于前一段；
- 是否属于后续新段；
- 是否处于中间过渡区。

### 3.5 `strict_segment_rules=True` 不是原文定义，而是项目自定义的实盘规则

当前默认值为 `DEFAULT_STRICT_SEGMENT_RULES = True`，并且在 [src/chanlun/segment.py](src/chanlun/segment.py) 的 `identify_segments()` 中，若 `strict_segment_rules` 为真，会额外要求：

- “前三笔同向推进”；
- “合并同向相邻线段”。

这两个规则对工程上减少噪声很有帮助，但它们并不是原文中的严格定义。原文里线段的核心判定是“特征序列分型 / 缺口分型 + 被另一线段破坏”，而不是“前三笔必须更强推进”或“相邻同向线段自动合并”。

建议：把这种行为拆成一个单独的“严格实盘模式”而不是默认替代理论定义：

- `theory_mode`：按原文几何定义；
- `practical_mode`：启用严格推进和相邻合并规则。

### 3.6 启动锚点选择（bootstrap）不是理论定义的一部分

当前实现还引入了 `bootstrap_mode`、`bootstrap_skip_confirmed_bis` 以及一套启发式打分逻辑，目的是选择一个更好的线段起点。它对工程上稳定输出很有帮助，但它不是缠论原文中的线段划分定义。也就是说，当前算法的结果会受到“起点锚定方式”的影响，这使得结果更像“某个工程约束下的最优输出”，而不是“纯理论唯一分割”。

建议：在严格模式下，默认关闭 bootstrap 选择，或者把 bootstrap 单独作为“可选的后处理优化”。

---

## 4. 最值得优先改进的 6 类点

从“原文定义”角度看，当前实现里最明显的偏差可以概括为这 6 类：

1. 把“严格理论判定”和“实盘兜底判定”混在同一条扩展路径里；这最不符合原文的纯几何定义。
2. 缺口再分辨和延迟确认是工程近似，不是原文的纯理论判定；它们应该单独成状态，而不是隐含在多条分支里。
3. “第一笔就破坏旧段，第三笔又回收”的过渡案例没有被显式建模；当前更像经验式回补，而非原文中的严格边界处理。
4. `strict_segment_rules` 里的“三笔同向推进 / 相邻同向线段合并”属于项目增强规则，不是原文核心定义。
5. bootstrap 起点选择属于“工程优化”，不是线段定义的一部分，应该降级为可选流程。
6. 当前 `stop_reason` 与内部状态混用，导致“哪个是理论确认、哪个是兜底确认、哪个是待定”不够清晰。

---

## 4.5 当前实现状态（稳定摘要）

本节只保留长期有效的稳定摘要；带时间戳的回归数值与完成度估算统一收敛到：

- [../chanlun/segment-implementation-changelog.md](../chanlun/segment-implementation-changelog.md)

当前稳定结论：

1. 核心识别路径已形成 theory/practical 分流，且对下游消费字段已有统一口径。
2. 缺口再分辨、过渡边界和跨周期一致性已具备回归基线。
3. 后续工作重点从“主流程落地”转向“外围入口一致性与调用方接入范式沉淀”。

---

## 4.6 stop_reason 稳定接口约定（当前版）

本节保留为背景说明；对外接口以 [../chanlun/segment-stop-reason-contract.md](../chanlun/segment-stop-reason-contract.md) 为准。

这里仅保留“为什么需要 contract”的背景结论：

1. 同一 `stop_reason` 必须有唯一 category（互斥）。
2. 调用方不应自行硬编码分组，避免版本漂移。
3. 分类迁移属于行为变更，必须配回归与变更记录。

具体分组清单、helper API、消费规则、稳定性约束统一收敛到：

- [../chanlun/segment-stop-reason-contract.md](../chanlun/segment-stop-reason-contract.md)

---

## 4.7 原文边界样本到状态机判决的映射

为便于调用方把“原文叙述”落到可编程判决，这里给出最常用的映射口径：

| 原文边界语义 | 当前状态机入口 | 典型 stop_reason / category | 调用方建议 |
| --- | --- | --- | --- |
| 无缺口特征序列分型成立，旧段终结 | `_evaluate_theory_stop()` -> `_feature_sequence_break()` | `feature_sequence_fractal` / `theory_confirmed` | 可直接作为理论终结信号使用 |
| 缺口分型后经再分辨确认终结 | `_evaluate_gap_candidate_state()` | `feature_sequence_gap_fractal` 或 `feature_sequence_gap_fractal_delayed_true` / `theory_confirmed` | 若为 delayed_true，建议在 UI 或报告中标注“延迟确认” |
| 转折第一笔破坏旧段后，第三笔先破第一笔终点 | `_evaluate_transition_state()` | `TransitionState.NONE`（新段路径继续） | 后续按新段方向继续观察，不回收旧段 |
| 转折第一笔破坏旧段后，第三笔先破第一笔起点 | `_evaluate_transition_state()` | `TransitionState.RECLAIMED`（回收旧段） | 视为旧段延续，前一次“新段尝试”失效 |
| 证据不足但已出现初始破坏，等待后续确认 | `_extend_segment()` 过渡态分支 | `transition_pending` / `pending` | 作为“待确认结构”，不应当作已确认终结 |
| 工程兜底终结（非理论主路径） | `_extend_segment()` fallback 分支 | `reverse_break` / `fallback_confirmed` | 建议与 theory_confirmed 分开展示，避免混淆 |

调用约定建议：

1. 若策略强调“严格几何定义”，优先使用 `termination_mode=theory` 并仅消费 `theory_confirmed`。
2. 若策略强调“实盘响应速度”，可使用 `termination_mode=practical`，但在信号层区分 `theory_confirmed` 与 `fallback_confirmed`。
3. 对 `pending` 类别保持非终结语义，直到后续样本把状态推进到 confirmed 类别。

---

## 4.8 调用方契约与维护清单（统一入口）

本节不再重复接口细节与维护步骤，统一引用：

- [../chanlun/segment-stop-reason-contract.md](../chanlun/segment-stop-reason-contract.md)

调用方如果要接入/改造，请按文档地图中的顺序阅读：

- [../chanlun/segment-doc-map.md](../chanlun/segment-doc-map.md)

---

## 5. Board（Archive + New Backlog）

任务源仍基于 [src/chanlun/segment.py](src/chanlun/segment.py) 与 [src/chanlun/models.py](src/chanlun/models.py)。

### 5.1 Archive（2026-08-14 已完成批次）

- [x] N1~N5：过渡边界、核心回归、strict 解耦、bootstrap 解耦、特征序列上下文强化。
- [x] Later-1：62/67/71/78 课边界样本 fixture 化与回归接入。
- [x] Later-2：theory/practical 双模式最小接入示例与导航接入。
- [x] Later-3：看板与 changelog 闭环联动模板落地。

详细记录见：

- [../chanlun/segment-implementation-changelog.md](../chanlun/segment-implementation-changelog.md)

### 5.2 New Backlog（下一轮）

#### Now

- [x] B1：补齐 71 课再分辨 R1-R6 的 issue/test 映射
  - 目标：把剩余边界分支从“描述”变成“可执行样本 + 明确断言”。
  - 代码锚点：
    - [src/chanlun/segment.py](src/chanlun/segment.py)
    - [tests/test_segment_rediscrimination_matrix.py](tests/test_segment_rediscrimination_matrix.py)
    - [tests/test_segment_lesson_boundary_fixtures.py](tests/test_segment_lesson_boundary_fixtures.py)
  - 验收标准：
    - 每个 R 分支有唯一测试 ID；
    - 每个分支都有 theory/practical 对照断言；
    - 不出现 `unknown` 分类漂移。
  - 完成说明（2026-08-14）：
    - 在 [tests/test_segment_rediscrimination_matrix.py](tests/test_segment_rediscrimination_matrix.py) 新增 `R1~R6` 参数化样本映射与唯一 ID 守卫；
    - 同时补充 dual-mode 断言，校验首段 stop_reason/confirmed 与 `unknown` 分类漂移。

- [x] B2：发布/报告消费端双模式冒烟对齐
  - 目标：确保下游消费层按 contract 区分 `theory_confirmed` 与 `fallback_confirmed`。
  - 代码锚点：
    - [scripts/batch_prepare_chanlun_reports.py](scripts/batch_prepare_chanlun_reports.py)
    - [scripts/build_miniapp_publish_bundle.py](scripts/build_miniapp_publish_bundle.py)
    - [src/report_json.py](src/report_json.py)
  - 验收标准：
    - 至少 2 个标的在双模式下输出可对照；
    - `pending` 不被下游当作终结信号消费；
    - 文档示例与实际字段一致。
  - 完成说明（2026-08-14）：
    - 新增 [tests/test_segment_consumer_mode_smoke.py](tests/test_segment_consumer_mode_smoke.py)，使用 `000591-day` 与 `00700-30m` 进行双模式冒烟；
    - 校验 `pending` 在两模式下均非 terminal，且 theory 下 fallback 不直接终结。

#### Next

- [x] B3：把线段安全闸门固化为单入口任务
  - 目标：将当前分散命令收敛为一个可复用 task 或脚本入口。
  - 锚点：
    - [docs/chanlun/segment-safety-checklist.md](../chanlun/segment-safety-checklist.md)
    - [tests/test_segment_regression_suite.py](tests/test_segment_regression_suite.py)
  - 验收标准：
    - 一条命令可跑完核心闸门；
    - 输出包含失败定位摘要。
  - 完成说明（2026-08-14）：
    - 新增单入口脚本 [scripts/run_segment_safety_gates.py](scripts/run_segment_safety_gates.py)；
    - 新增 VS Code task `segment-safety-gates`；
    - 新增脚本单测 [tests/test_run_segment_safety_gates.py](tests/test_run_segment_safety_gates.py)。

- [x] B4：补齐双模式对照的可视化示例（文档）
  - 目标：给消费方提供一眼可懂的 theory/practical 差异样例。
  - 文档锚点：
    - [../chanlun/segment-mode-consumer-examples.md](../chanlun/segment-mode-consumer-examples.md)
  - 验收标准：
    - 至少 1 个样本给出双模式 stop_reason 对照表；
    - 与 contract 口径一致。
  - 完成说明（2026-08-14）：
    - 在 [../chanlun/segment-mode-consumer-examples.md](../chanlun/segment-mode-consumer-examples.md) 新增 stop_reason 双模式对照表；
    - 对照项覆盖 theory_confirmed/fallback_confirmed/pending 三类语义。

#### Later

- [x] B5：线段到中枢的模式传递协议草案
  - 目标：明确中枢计算是否继承 theory/practical 口径以及边界语义。
  - 影响范围：
    - [src/chanlun](src/chanlun)
    - [docs/chanlun](../chanlun)
  - 完成说明（2026-08-14）：
    - 新增协议草案 [../chanlun/segment-to-zhongshu-mode-protocol-draft.md](../chanlun/segment-to-zhongshu-mode-protocol-draft.md)；
    - 已接入 [../chanlun/README.md](../chanlun/README.md) 与 [../chanlun/segment-doc-map.md](../chanlun/segment-doc-map.md)。

### 5.3 基线（长期保持）

- [x] 线段终结已实现 theory 主路径与 fallback 兜底分流。
- [x] `stop_reason` 已统一为 `theory_confirmed / fallback_confirmed / pending` 三类语义。
- [x] 缺口再分辨已状态化（`gap_candidate_pending / gap_confirmed / gap_invalidated / gap_deferred`）。
- [x] 过渡边界已引入 `transition_pending`。
- [x] `_FeatureSequenceElement` 已扩展上下文字段（`feature_sequence_id` 等）。
- [x] `theory_mode` 纯几何路径已保留，避免 strict 默认值污染理论结果。

---

## 6. 一句话结论

当前项目已经把缠论原文里“线段由三笔构成、需要重叠、由特征序列分型来终结”的主线抓住了，但仍然偏向“实盘可用的工程近似”，而不是“严格按原文几何定义”的实现。若要进一步逼近原文，最先要做的是把“特征序列分型 / 缺口分型”放回主路径，把所有反向笔突破、同向推进不足、相邻合并、bootstrap 起点选择降级为辅助兜底。