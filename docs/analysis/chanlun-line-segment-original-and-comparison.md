# 缠论原文关于线段划分的提炼与项目实现对照

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

## 4.5 当前实现状态快照（截至 2026-08-11）

基于当前仓库状态，线段识别的核心实现已经推进到一个可验证阶段：

- 已把“理论主路径”接入 [src/chanlun/segment.py](src/chanlun/segment.py) 的 `_evaluate_theory_stop()`，让特征序列分型优先于早期的兜底反向突破；
- 已把缺口再分辨的“延迟确认”分支纳入扩展流程，并在部分边界场景下避免过早下结论；
- 已把 `termination_mode` 对同向兜底分支的行为显式区分：`theory` 模式不再优先落入 `unexpected_same_direction` / `same_direction_slot_not_filled` / `same_direction_not_extending` 这类工程兜底终结；
- 已把 `termination_mode=theory` 下的 bootstrap/strict 行为收敛到更纯理论路径：
  - 对 `auto` / `prefer_earlier_start` 启发式锚点选择，自动降级到 `first_valid_seed`；
  - 关闭 strict 实盘增强（前三笔推进强化与同向段合并）对理论划分的干扰；
- 已补“第一笔破坏后第三笔分叉”的边界回放用例：
  - 第三笔破第一笔终点 => 保持新段路径；
  - 第三笔破第一笔起点 => 回收至前段语义；
- 已补跨周期（15m/30m/60m）一致性断言：
  - 在 [tests/test_segment_regression_suite.py](tests/test_segment_regression_suite.py) 中按标的分组校验 stop category 覆盖；
  - 锁定跨周期样本至少同时覆盖 `theory_confirmed` 与 `fallback_confirmed`，且不出现 `unknown` 类别；
- 已把 stop 契约字段对齐到下游发布/导出侧：
  - [scripts/build_miniapp_publish_bundle.py](scripts/build_miniapp_publish_bundle.py) 的 segment records 与 annotations 现已输出 `stop_category`、`is_theory_confirmed_stop`、`is_fallback_confirmed_stop`、`is_pending_stop`；
  - [scripts/export_structures_with_boxes.py](scripts/export_structures_with_boxes.py) 的 segments CSV 现已输出同口径字段，避免调用端自行重建分组逻辑；
- 已补上一组回归测试，覆盖理论分型优先、缺口延迟确认、过渡待定态和 theory/practical 分流边界。

最新验证结果：

- 分段相关回归：54 passed；
- 全量测试：491 passed。

按当前进度估算，整体完成度大约为 98%：

- 98%：核心 theory/practical 分流、缺口候选状态化、过渡待定态、特征序列上下文字段、theory 模式下 bootstrap/strict 去实盘化、“第一笔破坏后第三笔分叉”边界回放、跨周期一致性断言，以及下游发布/导出/CLI 消费口径统一都已落地并通过回归；
- 2%：剩余工作主要是把该契约在更多外围脚本/文档入口做统一声明，并沉淀一页简明“调用方接入范式”文档以减少后续扩展时的口径漂移风险。

下一优先级建议：

1. 把状态机语义从“内部状态”进一步提升为“对外稳定接口文档”，统一 `stop_reason`、`stop_category`、`pending` 语义边界；
2. 在文档中补“原文边界样本 -> 当前状态机判决”的示例映射，明确调用方如何消费 `theory` 与 `practical` 两种模式结果。

---

## 4.6 stop_reason 稳定接口约定（当前版）

为减少“同一 stop_reason 在不同调用方被不同解释”的风险，当前实现已提供稳定的分组接口：

- 代码入口：[src/chanlun/segment.py](src/chanlun/segment.py) 的 `get_stop_reason_contract()`
- 语义来源：`STOP_REASON_CATEGORIES` + `STOP_REASONS_BY_CATEGORY`

当前 contract（按 `StopOutcomeCategory`）为：

- `theory_confirmed`
  - `feature_sequence_fractal`
  - `feature_sequence_gap_fractal`
  - `feature_sequence_gap_fractal_delayed_true`
- `fallback_confirmed`
  - `reverse_break`
  - `reverse_break_after_gap`
- `pending`
  - `unexpected_same_direction`
  - `no_followup_same_direction`
  - `same_direction_slot_not_filled`
  - `same_direction_not_extending`
  - `transition_pending`
  - `exhausted_confirmed_bis`
- `unknown`
  - 空集合（仅用于未知码/空值兜底）

配套回归：

- [tests/test_segment_rediscrimination_matrix.py](tests/test_segment_rediscrimination_matrix.py)
  - `test_stop_reason_contract_groups_are_stable_and_complete`
  - `test_stop_reason_category_buckets_match_expected_semantics`

这两个测试用于锁定：

1. contract 分类集合完整且互斥；
2. 每个状态码归属不漂移；
3. 公开 contract 与内部分类常量保持一致。

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

## 4.8 调用方接口契约（建议直接采用）

为保证后续演进时调用方不被内部重构影响，建议统一使用以下稳定接口，而不是自行硬编码状态码分组：

- 分组 contract：
  - `get_stop_reason_contract()`
- 分类函数：
  - `classify_stop_reason(stop_reason)`
- 便捷判定：
  - `is_theory_confirmed_stop_reason(stop_reason)`
  - `is_fallback_confirmed_stop_reason(stop_reason)`
  - `is_pending_stop_reason(stop_reason)`
- 调用方摘要：
  - `summarize_stop_reason_outcome(stop_reason, mode="practical")`

推荐消费策略：

1. 若策略强调“理论严格性”，使用 `termination_mode=theory`，并仅把 `is_theory_confirmed_stop_reason(...) == True` 作为正式终结信号。
2. 若策略强调“实盘响应”，使用 `termination_mode=practical`，并分开展示 theory/fallback 两类 confirmed 信号。
3. 对 `is_pending_stop_reason(...) == True` 的样本，不做最终终结结论，只作为“待确认结构”。
4. 对未知 stop reason（`classify_stop_reason(...) == unknown`）按降级策略处理：记录告警、降级为只读展示，不进入自动交易/自动评分主流程。

兼容性约定：

- 新增 stop reason 时，必须同步更新：
  - `STOP_REASON_LABELS`
  - `STOP_REASON_CATEGORIES`
  - `get_stop_reason_contract()` 对应回归
- 任何 stop reason 的分类迁移都视为“行为变更”，需补回归并在文档快照中记录。

配套回归锚点：

- [tests/test_segment_rediscrimination_matrix.py](tests/test_segment_rediscrimination_matrix.py)
  - `test_stop_reason_contract_groups_are_stable_and_complete`
  - `test_stop_reason_category_buckets_match_expected_semantics`
  - `test_stop_reason_helpers_follow_contract_categories`

---

## 4.9 新增 stop_reason 维护清单

当新增或调整 stop reason 时，按以下顺序执行，避免调用口径漂移：

1. 核心语义：更新 [src/chanlun/segment.py](src/chanlun/segment.py) 中 `STOP_REASON_LABELS` 与 `STOP_REASON_CATEGORIES`。
2. contract 导出：确认 `get_stop_reason_contract()` 与 helper（`is_theory_confirmed_stop_reason` 等）结果符合预期。
3. 下游消费：检查 [scripts/build_miniapp_publish_bundle.py](scripts/build_miniapp_publish_bundle.py) 与 [scripts/export_structures_with_boxes.py](scripts/export_structures_with_boxes.py) 的 `stop_category`/布尔字段是否自动对齐。
4. 回归测试：至少通过以下测试集合：
   - [tests/test_segment_rediscrimination_matrix.py](tests/test_segment_rediscrimination_matrix.py)
   - [tests/test_build_miniapp_publish_bundle.py](tests/test_build_miniapp_publish_bundle.py)
   - [tests/test_export_structures_with_boxes.py](tests/test_export_structures_with_boxes.py)
   - [tests/test_chanlun_cli.py](tests/test_chanlun_cli.py)
5. 快照更新：同步本文件 4.5 的“最新验证结果”和进度评估。

---

## 5. TODO List（按优先级重排）

下面这份清单是基于当前实现 [src/chanlun/segment.py](src/chanlun/segment.py) 和 [src/chanlun/models.py](src/chanlun/models.py) 逐项拆出来的，优先级从高到低。

### P0：先把“理论主路径”和“工程兜底路径”彻底分开

- [x] 在 [src/chanlun/segment.py](src/chanlun/segment.py) 的 `_extend_segment()` 中，把线段终结拆成两条路径：
  - 理论主路径：只依赖 `_feature_sequence_break()` 和 `_gap_feature_sequence_candidate()`；
  - 工程兜底路径：只在主路径未给出明确结论时才启用 `reverse_break`、`same_direction_not_extending` 等规则。
- [x] 把 `stop_reason` 的语义统一成三类：`theory_confirmed`、`fallback_confirmed`、`pending`。

### P0：把缺口再分辨和过渡点边界改成显式状态

- [x] 把 `_evaluate_pending_gap_candidate()` 和 `_rediscriminate_gap_break_detail()` 的返回值从“布尔/空值混用”改成明确状态：`gap_candidate_pending`、`gap_confirmed`、`gap_invalidated`、`gap_deferred`。
- [x] 在 [src/chanlun/segment.py](src/chanlun/segment.py) 中为 `_reclaims_transition_back_to_prior_segment()` 的边界案例增加一个明确状态，例如 `transition_pending`。
- [ ] 当第一笔就破坏旧段、但后续第三笔又出现回收或反向回拉时，不要立刻下结论，而是进入等待态，等后续特征序列结果再确认。

### P1：把特征序列从“窗口式”提升为“显式上下文结构”

- [x] 把 `_FeatureSequenceElement` 扩展为显式字段：`feature_sequence_id`、`belongs_to_prior_segment`、`belongs_to_new_segment`、`in_transition`。
- [x] 让 `_build_standard_feature_sequence()` 生成带上下文的元素，而不是只依赖当前窗口的高低点推断。
- [ ] 这样可以更严格地体现原文中“特征序列元素必须在同一特征序列内部讨论包含关系”的语义。

### P1：把实盘增强规则从理论定义中剥离

- [ ] 把 `strict_segment_rules` 的“三笔同向推进”和“相邻同向线段合并”改成独立的 `practical_mode`，而不是默认替代理论逻辑。
- [x] 保留 `theory_mode` 的纯几何判定路径，避免当前默认 `DEFAULT_STRICT_SEGMENT_RULES = True` 让理论结果被实盘增强规则污染。
- [ ] 把 bootstrap 相关逻辑（`bootstrap_mode`、`bootstrap_skip_confirmed_bis`、打分函数）从主识别流程中分离为可选后处理/可选起点优化。

### P2：补回归测试，先锁住原文中的边界案例

- [ ] 针对 62/67/71/78 课里提到的边界例子，补测试覆盖：
  - 无缺口的特征序列分型；
  - 有缺口但后续被反向特征序列确认；
  - 第一笔破坏旧线段、第三笔回收的过渡案例；
  - 同向推进不足的兜底情况。
- [ ] 重点测试 [src/chanlun/segment.py](src/chanlun/segment.py) 的 `_extend_segment()` 和 `identify_segments()`。

---

## 6. 一句话结论

当前项目已经把缠论原文里“线段由三笔构成、需要重叠、由特征序列分型来终结”的主线抓住了，但仍然偏向“实盘可用的工程近似”，而不是“严格按原文几何定义”的实现。若要进一步逼近原文，最先要做的是把“特征序列分型 / 缺口分型”放回主路径，把所有反向笔突破、同向推进不足、相邻合并、bootstrap 起点选择降级为辅助兜底。