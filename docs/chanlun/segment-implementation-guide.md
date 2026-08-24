---
spec_id: SPEC.SEGMENT.IMPLEMENTATION
status: stable
owner: chanlun
applyTo: src/chanlun/segment.py
tests: tests/test_segment.py, tests/test_segment_regression_suite.py
---

# 线段实现专题

文档入口：

- 理论规格（应然）： [segment-spec.md](segment-spec.md)
- 总导航： [segment-doc-map.md](segment-doc-map.md)
- 稳定接口契约： [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 变更快照： [segment-implementation-changelog.md](segment-implementation-changelog.md)

这份文档只说明当前项目里“线段是怎么画出来的”，目标是方便人工核图。

严格缠论原文口径与当前工程实现并不完全等价；如果两者冲突，以这里描述的“当前实现口径”作为现阶段对图结果的解释标准。

## 状态总览（先看这里）

- 工程层：已完成当前版本闭环。67 课第一/第二种情况已落地，71 课相关再分辨矩阵主路径已固化并有测试基线。
- 严格理论层：仍有待跟踪项，但不再是当前工程实现的待办清单。

“8.2 当前仍待落地：无”仅表示该矩阵清单已完成，不代表后续理论收敛空间为零。

当前实现已经吸收两条更严格的约束：

- 起段前三笔必须存在公共重叠区间
- 反向特征序列在做分型前，会先做同序列内的非包含处理，生成标准特征序列
- 段内优先用反向特征序列的直接顶/底分型确认终结
- 对“第一二元素存在缺口”的特征序列分型，会按 71 课的再分辨思路，比较后续序列是先破第一笔终点还是先破第一笔起点，再决定旧线段终结还是延续

但它仍不是 67、71 课的完整实现：

- 67 课第一种情况已实现
- 67 课第二种情况（第一二元素有缺口）已实现最小闭环
- 71 课更细的完整再分辨仍未全部落地

关于 78 课：78 课要求「第二种情况的第二特征序列分型判断必须严格按包含关系处理」。当前再分辨主路径采用 71 课「先破终点/先破起点」捷径（`_rediscriminate_gap_break_detail`），该捷径在判定上**蕴含** 67 课「第二特征序列分型」（分型左元素条件即捷径的「先破终点」条件），因此 78 课的包含处理要求被隐含满足，无需在同一窗口内再单独判一次第二特征序列分型。78 课的「缺口后 C 段未成第二特征序列分型又直接新高/新低 → A+B+C 只算一个线段」规则对应 `is_reclaimed`/`absorbed_segment_ids` 再吸收路径，当前尚未与该原文判据显式对齐。

## 1. 输入口径

- 线段不直接从 K 线生成。
- 线段基于笔序列生成。
- 当前实现只使用 `is_confirmed=True` 的已确认笔。
- 未确认尾笔不会参与线段起段、扩展或终结判断。

对应代码位置：`src/chanlun/segment.py` 的 `identify_segments(...)`。

## 2. 起段条件

一条线段至少需要 3 笔。

这 3 笔必须同时满足：

- 方向交替
- 第 1 笔和第 3 笔同向
- 前三笔存在公共重叠区间
- 第 3 笔相对第 1 笔继续推进

更具体地说：

- 向上线段：第 3 笔高点必须高于第 1 笔高点
- 向下线段：第 3 笔低点必须低于第 1 笔低点

如果不满足这组条件，这 3 笔就不能构成当前实现下的线段起点。

## 3. 段内扩展

线段不是一笔一笔随便往后接，而是按“两笔一组”扩展：

- 先来一笔反向回撤笔
- 再来一笔同向推进笔

只有后面这笔同向笔继续创出新高或新低，线段才允许延长。

当前实现的判定方式：

- 向上线段：新的同向上笔高点必须高于前一个同向上笔高点
- 向下线段：新的同向下笔低点必须低于前一个同向下笔低点

如果没有继续推进，当前线段就在已有位置停住。

## 4. 线段终结

当前实现先看反向特征序列是否已经形成可直接确认的顶/底分型；只有还没形成这类分型时，才退回“破坏笔是否破坏最近关键低点/高点”的简化判定。

### 直接特征序列分型终结

在判顶/底分型前，当前实现会先把反向特征序列按 65 课的非包含思路做一次标准化：

- 只在同一条反向特征序列内部处理包含关系
- 相邻特征元素若出现包含，按当前序列方向做合并
- 合并后的元素继续参与后续分型判断

- 向上线段：抽取段内向下笔作为反向特征序列；若连续三个反向元素形成顶分型，且前两个元素之间没有缺口，则线段在该顶分型高点处终结
- 向下线段：抽取段内向上笔作为反向特征序列；若连续三个反向元素形成底分型，且前两个元素之间没有缺口，则线段在该底分型低点处终结

这里的终点，会落在形成该分型的中间反向笔之前那一笔同向笔上；后一线段从这根中间反向笔之后重新寻找新的三笔起段种子。

### 有缺口的第二种情况

- 若反向特征序列分型的第一、第二元素之间存在缺口，当前实现不会立刻终结旧线段
- 这时会把该分型对应的反向笔记为待确认转折点，并把它视为新序列的第一笔
- 若后续同向第三笔先破这第一笔的终点，则确认新线段成立，旧线段在原分型极值处终结
- 若后续反向笔先破这第一笔的起点，则视为旧线段延续，撤销这次候选分界点

这对应 67 课的第二种情况，目前状态码记为 `feature_sequence_gap_fractal`。

### 第一笔破坏前线段（71课第一种情况）

- 从转折点开始，若第一笔反向笔就破坏了前线段，且该笔延伸出三笔后第三笔破第一笔的结束位置，则新线段一定形成、前线段一定结束
- 当前实现把这条主路径正式建模为理论确认：`_first_bi_breaks_prior_segment_and_third_extends()` 在首个转折轮次检测该条件，满足时以 `first_bi_break_then_third_extends`（`theory_confirmed`）确认前线段结束，下一段从该转折第一笔开始
- 仅在 theory 模式触发；practical 模式下同一形态由 `reverse_break` 兜底覆盖

### 向上线段

- 若反向下笔低点已经跌破当前线段最近一个关键低点，则视为“直接破坏”，向上线段在该下笔结束时立即终结
- 若这根反向下笔低点仍高于最近关键低点，则视为“震荡未破坏”，旧段暂不终结
- 有缺口时，若后续同向上笔重新创出新高，则原向上线段继续延伸
- 震荡未破坏时，若后续同向上笔未创新高，且再下一根反向下笔跌破最近关键低点，则确认原向上线段被破坏；这根最早的反向下笔作为新向下线段的第一笔

### 向下线段

- 若反向上笔高点已经突破当前线段最近一个关键高点，则视为“直接破坏”，向下线段在该上笔结束时立即终结
- 若这根反向上笔高点仍低于最近关键高点，则视为“震荡未破坏”，旧段暂不终结
- 有缺口时，若后续同向下笔重新创出新低，则原向下线段继续延伸
- 震荡未破坏时，若后续同向下笔未创新低，且再下一根反向上笔突破最近关键高点，则确认原向下线段被破坏；这根最早的反向上笔作为新向上线段的第一笔

一旦发生这种“有效破坏”，前一线段会被标记为 `is_confirmed=True`。

## 5. 未确认尾段

如果线段已经满足起段条件，也出现了若干次正常推进，但最后还没有被有效反向破坏，当前实现会保留一个未确认尾段：

- `is_confirmed=False`
- 图上仍然会画出来
- 这表示“当前最后一段还在进行中”

这不是错误，而是当前实现特意保留的尾部状态。

## 6. 导出判定痕迹

当前 `segments.csv` 已经把线段最后一次判定时的几个关键痕迹导出来，方便人工核图：

- `last_same_extreme`：当前线段最后一个同向推进笔所形成的最新极值
- `last_reverse_extreme`：当前线段最近一次反向回撤笔留下的关键低点或关键高点
- `break_bi_id`：让线段停下来的那一笔 ID；可能是确认破坏的反向笔，也可能是推进失败时对应的笔
- `stop_reason`：线段为何停在当前终点的工程状态码

其中 `stop_reason` 当前常见取值包括：

完整分类与消费口径见 [segment-stop-reason-contract.md](segment-stop-reason-contract.md)。

- `feature_sequence_fractal`：反向特征序列已经形成可直接确认的顶/底分型，旧线段在该分型对应极值处终结
- `feature_sequence_gap_fractal`：反向特征序列分型的第一二元素存在缺口，需等待其后的反向序列再长出分型，随后回头确认旧线段终结
- `feature_sequence_gap_fractal_delayed_true`：缺口分型进入再分辨后，先经历至少一轮“弱同向未突破”，随后由更晚一轮同向强推进确认旧线段终结
- `first_bi_break_then_third_extends`：转折点第一笔破坏前线段，且第三笔破第一笔结束位置，前线段确认终结（71课第一种情况）
- `reverse_break`：反向笔直接破坏最近关键低点或关键高点，前一线段立即确认终结
- `reverse_break_after_gap`：首根反向笔尚未破坏最近关键低点/高点，但后续同向恢复失败，并由再次反向扩张完成确认破坏
- `no_followup_same_direction`：出现反向回撤后，没有等到后续同向推进笔
- `same_direction_slot_not_filled`：按“两笔一组”应该出现同向推进笔的位置，没有出现同向笔
- `same_direction_not_extending`：出现了同向笔，但没有继续创新高或新低
- `unexpected_same_direction`：在预期应出现反向回撤笔的位置，直接又来了同向笔
- `exhausted_confirmed_bis`：确认笔序列已经走完，线段尾部暂时停住

## 7. 人工核图清单

看一条线段是否符合当前实现，可以按下面顺序检查：

1. 起段的前三笔是不是方向交替、首尾同向，而且存在公共重叠区间。
2. 第三笔是不是相对第一笔真的推进了。
3. 反向特征序列里是否已经出现无缺口的直接顶/底分型。
4. 如果没有直接分型终结，后续延长是不是按“反向一笔 + 同向一笔”的节奏发生。
5. 每次同向延长时，是不是创出了新高或新低。
6. 如果一条线段结束了，是否存在直接特征序列分型，或一笔反向笔破坏了最近关键低点或高点。
7. 如果最后一条线段没有结束，它是否应当是一个未确认尾段。

## 8. 特征序列上下文约束（N5）

为了避免“跨序列污染”导致的隐式误判，当前实现对特征序列上下文增加了显式约束：

- 包含关系 `_contains(...)` 只在同一 `feature_sequence_id` 内生效；若序列 ID 不一致，直接拒绝包含判定。
- 三元素分型入口（无缺口分型、缺口候选）会先校验上下文一致性，再进入几何比较。

这两条约束的目的不是改变理论定义，而是把“同一特征序列内部比较”从隐含前提提升为显式执行规则。

### 7.1 600 根窗口的起点锚定（可选）

这一节需要区分三层口径：

- 函数默认值：`identify_segments(...)` 自身的默认 `bootstrap_mode`
- 当前生产链路：报表生成和发布打包阶段实际传入的 `bootstrap_mode`
- 实验口径：人工做 A/B 对照时可显式指定的模式

当前实现已把 bootstrap 拆成两层：

- 基础起点层：负责确定“不做评分优化时”的起点（例如 `first_valid_seed`、`skip_left_edge`）
- 评分优化层：仅在 `auto` / `prefer_earlier_start` 下启用，用于候选评分与优选

这意味着：

- 关闭评分优化（例如使用 `first_valid_seed`）时，结果不会受候选评分函数影响
- 理论模式会把 `auto` / `prefer_earlier_start` 收敛到 `first_valid_seed`，避免评分优化影响理论主路径

代码默认口径（当前 `identify_segments(...)` 默认值）：

- `identify_segments(..., bootstrap_mode="prefer_earlier_start")`
- 含义：先枚举候选起点并试跑首段，再按工程评分选择“接近最优且尽量靠左”的起点。

当前报表/发布链路的实际使用口径：

- `1m`：显式使用 `first_valid_seed`
- 其他周期（如 `5m/15m/30m/60m/day`）：当前仍使用 `prefer_earlier_start`

之所以分开，是因为 `1m` 更容易受窗口左边界截断和局部噪声影响；若继续沿用评分选起点，首段锚点更容易右移，进而带动整串端点漂移。当前工程因此优先固定 `1m` 的首个合法种子，换取更强的可复现性。

#### 7.1.1 `first_valid_seed`

- `identify_segments(..., bootstrap_mode="first_valid_seed")`
- 含义：从窗口最左侧开始，只要找到第一个合法三笔种子，就从该位置启动首段识别。
- 特点 1：规则直接
- 特点 2：人工核图时最容易解释
- 特点 3：首段锚点稳定，不会因为后面出现“评分更高”的候选而右移

这里的“合法三笔种子”仍然要满足本文件第 2 节列出的起段条件；`first_valid_seed` 只决定“合法之后怎么选”，并不会放宽种子合法性本身。

#### 7.1.2 `prefer_earlier_start`

- `identify_segments(..., bootstrap_mode="prefer_earlier_start")`
- 含义：不是直接选第一个合法种子，而是先对每个候选起点试跑首段，再做评分和筛选。

它包含“合法种子”这层基础要求，但不等于“第一个合法种子优先”。

当前实现步骤是：

1. 枚举所有可能的起点位置。
2. 从每个起点尝试扩展出一条首段；不能形成合法首段的候选直接丢弃。
3. 对每个可行候选按首段结果打分。
4. 先找最高分 `best_score`。
5. 再取所有 `score >= best_score - 20` 的候选。
6. 最后在这批“接近最优”的候选中选最靠左的起点。

也就是说，`prefer_earlier_start` 的“prefer earlier”并不是无条件向左，而是“在接近最优的前提下尽量向左”。

#### 7.1.3 当前评分逻辑（工程启发式）

当前代码中的评分逻辑是工程启发式，不是缠论原文中的严格理论公式。它的目的，是在一个被 600 根窗口截断后的局部视图中，尽量挑出“更像完整首段”的起点。

当前主要评分项包括：

- 段越长，分越高：`segment_len * 3`
- 若首段已经被确认终结，额外加分：`+80`
- 若终结原因属于较强确认类型，额外加分：`+40`
- 对应状态码：`feature_sequence_fractal`、`feature_sequence_gap_fractal`、`feature_sequence_gap_fractal_delayed_true`、`first_bi_break_then_third_extends`、`reverse_break`、`reverse_break_after_gap`
- 若终结或停驻原因偏弱，扣分：`-20`
- 对应状态码：`unexpected_same_direction`、`same_direction_slot_not_filled`、`same_direction_not_extending`、`no_followup_same_direction`
- 若只是因为确认笔用尽而停住，重扣：`-120`
- 对应状态码：`exhausted_confirmed_bis`

这些分值当前是经验参数，代表的是工程偏好，而不是被理论证明的唯一合理取值。

#### 7.1.4 为什么“段越长，分越高”

这个评分项最有争议，但当前工程里保留它，是出于下面的实用考虑：

- 如果两个起点都合法，工程上通常更偏向那个“能顺利长成更完整首段”的起点。
- 一个起点若刚起段就很快停住，可能只是卡在窗口左边界的一段截断结构里。
- 另一个稍靠后的起点若能形成更连贯、已确认的首段，往往在局部窗口里更稳定。

因此，“更长”在当前实现里被当成一种弱信号：它不代表理论上更正确，只代表在当前窗口中更像一条完整、可延展、可解释的首段。

#### 7.1.5 当前已知争议与局限

这套起点评分不是严格理论结论，而是工程启发式，因此必须明确它的边界：

- 它不是“最正确起点”的证明器，只是“当前窗口下的排序器”。
- “段越长，分越高”会天然偏向后面那些能长成大段的候选，可能导致首段锚点右移。
- 一旦首段锚点右移，后续整串线段端点都会跟着变化。
- 对 `1m` 这类噪声高、笔密集、窗口截断影响更强的级别，这种右移副作用更明显。
- `best_score - 20` 这一阈值当前也是经验参数，不是理论常数；它只是给“尽量靠左”留出一个近似最优区间。

因此，当前工程并不把 `prefer_earlier_start` 解释为“理论更严格”，而是解释为“对多数非 1m 周期更兼容旧结果的工程默认值”。

#### 7.1.6 为什么当前 `1m` 用 `first_valid_seed`

当前 `1m` 改为显式使用 `first_valid_seed`，主要是为了解决以下问题：

- `1m` 窗口内笔更密，评分法更容易被局部延展长度、临时终结质量等因素推向更靠右的起点。
- 起点一旦右移，后面所有端点链条都会变化，人工确认过的首段锚点也会被改写。
- 对发布链路而言，本地 `segments.csv` 与发布 JSON 若使用不同起点口径，还会出现“本地对、发布错”的不一致。

所以当前工程策略是：

- `1m` 优先首段锚点稳定、结果可复现、人工核图可解释。
- 其他周期暂保留 `prefer_earlier_start`，以减少对现有回归基线和历史结果的整体扰动。

可选实验口径（左侧预热）：

- `identify_segments(..., bootstrap_mode="skip_left_edge", bootstrap_skip_confirmed_bis=N)`
- 含义：先跳过左侧 `N` 根已确认笔，再从该位置开始寻找第一个合法三笔种子。
- 适用：当你怀疑 600 根窗口最左侧处于“截断中的旧结构”时，可做 A/B 对照观察起段稳定性。

A/B 最小验证命令：

- `pytest -q tests/test_segment_bootstrap_anchor.py`
- 锁定点 1：`first_valid_seed` 不受 `bootstrap_skip_confirmed_bis` 影响
- 锁定点 2：`skip_left_edge` 模式可把首个起段种子右移

## 8. 当前实现边界

这份实现是工程化简化版本，不代表已经完整落实严格缠论线段定义。当前已知边界包括：

| 层级 | 当前状态 | 说明 |
|---|---|---|
| 工程实现 | 已完成 | 67/71 课的工程主路径、缺口再分辨闭环、候选替代与回归样本已落地。 |
| 严格理论 | 待跟踪 | 仍有更细再分辨、走势类型一体化、尾部临界语义等理论收敛空间。 |
| 文档口径 | 已收敛 | 当前文档采用“工程已完成 / 严格理论未完成”的双层表述，避免混淆。 |

- 不处理更严格的走势分解口径
- 67 课第一种情况已实现
- 67 课第二种情况（第一二元素有缺口）已实现最小闭环
- 71 课更细的完整再分辨尚未完成
- 不让未确认尾笔参与线段计算
- 更偏向“稳定、可重复导出”的图表实现，而不是最严格的理论细分
- `prefer_earlier_start` 的评分公式和阈值属于工程经验参数，当前已用于兼容旧结果，但并不应视为严格理论结论
- `1m` 与其他周期当前采用不同起点锚定口径，这是一种工程折中，而不是理论上必须分级别处理的结论

### 8.1 严格理论层待跟踪项（非工程待办）

说明：本节是“严格理论层”的后续研究项，不代表当前工程实现尚未完成；与 8.2 的工程矩阵完成状态并不冲突。

1. P0：补全 71 课再分辨完整分支

- 目标：把“第一二元素有缺口”后的再分辨从最小闭环扩展到完整分支覆盖。
- 当前：已有候选识别与最小回判链路，可输出 `feature_sequence_gap_fractal`。
- 缺口：仍缺少更细分支与多阶段回判的一致化规则，和 71 课完整口径不等价。
- 验收：
	- 提供覆盖全部目标分支的用例集（正例/反例/边界例）。
	- `stop_reason` 在各分支下稳定可复现，不因起点滑移出现随机漂移。
	- 回归样本（day/60m/15m）中关键地标段不回退为超长单段。
- 代码锚点：`_gap_feature_sequence_candidate(...)`、`_rediscriminate_gap_break(...)`。

#### 1.1 71 课剩余分支拆解表（执行清单）

> 目标：把“仍未全部落地”拆成可逐条交付的最小任务，避免一次性大改导致回归漂移。

| 编号 | 触发条件（缺口候选后） | 当前工程行为 | 目标严格化行为 | 预期状态码 | 建议测试锚点 |
|---|---|---|---|---|---|
| R1 | 多候选连续出现（A 后 B）且 A/B 都可在后续触发 | 固定“后候选覆盖前候选” | 增加可切换策略并固定默认优先级（后候选覆盖或首次有效优先二选一） | `feature_sequence_gap_fractal` 或新增细分码 | `test_multiple_gap_candidates_switch_priority_deterministically` |
| R2 | 先弱同向、再弱反向、再同向强突破（多轮弱信号穿插） | 已覆盖部分路径，仍有分支空白 | 明确多轮序列的判决顺序与终止条件，避免同型样本出现不同结论 | `feature_sequence_gap_fractal_delayed_true` | `test_gap_candidate_weak_reverse_then_late_strong_same_dir_confirms_break` |
| R3 | 先出现可判 False 信号，后续又出现可判 True 信号（冲突） | 已固定为“先破起点优先” | 一旦缺口再分辨先触发 False（先破第一笔起点），当前线段后续不再接受 gap 候选 True 翻案，改由后续常规终结规则确认 | `reverse_break`（优先）或后续常规终结码 | `test_gap_false_outcome_has_priority_over_late_true_candidate` |
| R4 | 候选跨段边界，后续三笔同时可作为旧段再分辨与新段起段种子 | 主路径已防吞并，但边界口径散落 | 统一边界裁剪规则：旧段判决窗口与新段起段窗口互斥 | `feature_sequence_gap_fractal` + 新段正常起段 | `test_next_segment_waits_for_fresh_three_bi_seed_after_break` |
| R5 | 特征序列在包含合并后，候选索引与原始索引错位 | 已有稳定性基线 | 固化“候选索引映射不回退”规则，明确映射优先级 | `feature_sequence_gap_fractal` | `test_gap_candidate_stays_stable_when_feature_sequence_is_merged` |
| R6 | 不同级别窗口（day/60m/15m）对同类形态给出不同终结时点 | 通过样本回归观察，不可解释项仍存在 | 增加级别一致性约束（允许偏差但要求可解释） | 同状态码，边界偏移受限 | `tests/test_segment_regression_suite.py` 场景扩展 |

#### 1.2 为什么不直接“一次性全落地”

- 分支不是线性叠加：R1-R6 相互耦合，一次改完通常会破坏已有稳定地标。
- 回归成本高于编码成本：每条规则都要在多标的、多级别上验证“新增/消失/位移段”是否可接受。
- 产线要求可复现：当前数据导出、打包与展示链路依赖稳定 stop_reason 语义，需避免大面积漂移。

#### 1.3 建议落地顺序（两周节奏）

1. 先落 R1 + R3：统一候选优先级与冲突判决，先解决“同图不同判”问题。
2. 再落 R2 + R5：补全多轮弱信号与索引映射稳定性。
3. 最后落 R4 + R6：做段边界互斥和跨级别一致性收敛。

每完成一条：

1. 先补/改矩阵测试。
2. 再跑回归样本（000591/00700/03690/300124）。
3. 最后更新本节“当前行为/目标行为/状态码”。

2. P1：走势类型分解与线段判定一体化

- 目标：从“工程线段”向“走势类型驱动线段”收敛，减少规则拼接感。
- 当前：线段主要依赖已确认笔、特征序列分型、关键高低点破坏。
- 缺口：尚未把段内中枢、段破坏、走势类型统一到同一层级语义。
- 验收：
	- 形成统一术语与层级定义（走势类型 -> 线段 -> 中枢）。
	- 新老口径可并行输出并可比较差异（实验层与默认层并存）。
	- 至少一组真实标的样本显示人工核图一致性提升。
- 代码锚点：`identify_segments(...)` 主循环与后续线段级结构输出链路。

3. P1：尾部未确认笔解释层（受控引入）

- 目标：不改变正式识别结果前提下，提升尾部临界结构的可解释性。
- 当前：未确认尾笔完全不参与线段计算。
- 缺口：图上常见“人工直觉已转折，但结构仍停在上一段”的解释空白。
- 验收：
	- 保持正式 `segments` 结果不变；新增独立“解释层”字段或导出对象。
	- 解释层必须显式标注置信级与不确定性，不得写回正式段边界。
	- 报表与图上可开关显示，默认关闭。
- 代码锚点：`_confirmed_bis(...)` 与 `segments.csv` 导出字段扩展。

4. P2：`stop_reason` 对外释义标准化（已闭环）

- 目标：让 CSV、图标注、分析文本三处的状态语义完全一致。
- 当前：已建立统一映射，CSV 与发布打包数据均已导出/补齐 `stop_reason_label`，摘要/详情的 `technical_focus_lines` 也会在可用时追加“最近线段停驻原因”人话行。
- 缺口：无（`chart_data` 已新增 `segment_stop_reason_annotations`，与 `stop_reason_label` 共用同一映射）。
- 验收：
	- 固定释义表覆盖当前所有状态码，并由单测锁定。
	- 报表层与图注层复用 `stop_reason_label`，不再单独维护第二套文案。
	- 新增测试约束释义表与状态码同步演进。
- 代码锚点：`stop_reason` 生产位置与报表渲染模板。

5. P2：线段回归样本基线扩充

- 目标：把“规则变化 -> 图形变化”的风险前置到回归测试。
- 当前：已有 000591 多级别回归地标，并新增 00700、03690、300124 的 day/30m/15m 回归基线，覆盖缺口分型、缺口后反向破坏、无后续同向推进与尾段未确认等敏感状态；000591/00700/03690/300124 回归断言已统一复用差异摘要工具，便于定位新增/消失/位移段。另已补充 `tests/test_segment_regression_suite.py` 作为单文件快速入口，并加入 60m 覆盖点、confirmed/preprocessing 分层统计检查，以及集中场景清单与样本路径存在性检查。
- 缺口：样本覆盖仍不足以约束不同市场风格（趋势/震荡/跳空密集）。
- 验收：
	- 新增多标的、多级别地标用例并固定关键段边界。
	- 变更时自动输出差异摘要（新增/消失/位移的段）；当前已落地摘要脚手架 `tests/segment_regression_support.py`，支持首个错位地标的 `start_bi/end_bi` 位移幅度统计、净新增/净减少段计数，并按 `stop_reason` 聚合增减计数。
	- 对 `feature_sequence_gap_fractal`、`reverse_break_after_gap` 等敏感状态做专项回归。
- 代码锚点：`tests/test_segment.py`、`tests/test_segment_regression_000591.py`。

### 8.2 P0 再分辨用例矩阵（实施入口）

为避免“边改边飘”，P0 建议按固定矩阵逐条落地，每条都包含：输入笔序列、触发分支、预期 `stop_reason`、预期旧段终结位置、预期新段起点。

建议先覆盖以下 8 类：

1. 缺口分型后，后续同向第三笔先破第一笔终点，旧段确认终结（正例）。
状态：已落测试基线，见 `test_gap_fractal_then_break_first_bi_end_confirms_new_segment`。
2. 缺口分型后，后续反向笔先破第一笔起点，旧段延续（反例）。
状态：已落测试基线，见 `test_gap_fractal_then_break_first_bi_start_keeps_prior_segment`。
3. 缺口分型后，先出现弱同向恢复但不破终点，再被反向破起点（应判延续）。
状态：已落测试基线，见 `test_gap_candidate_weak_recovery_then_late_reverse_break_keeps_prior_segment`。
4. 缺口分型后，先出现弱反向未破起点，再由同向强推进破终点（应判终结）。
状态：已完成（pass），见 `test_gap_candidate_weak_reverse_then_late_strong_same_dir_confirms_break` 与 `test_delayed_true_path_emits_dedicated_stop_reason`。
5. 同一候选转折点后出现多次来回，最终首次有效触发决定（防抖与首次有效优先）。
状态：已先固化当前工程替代策略“后候选覆盖前候选”，见 `test_multiple_gap_candidates_switch_priority_deterministically`；后续若切到“首次有效优先”，需连同测试一起改口径。
6. 缺口分型候选形成后，后续特征序列被包含合并改写（标准特征序列稳定性）。
状态：已落基线测试，见 `test_gap_candidate_stays_stable_when_feature_sequence_is_merged`。
7. 缺口候选跨越段边界时，是否错误吞并下一段起段三笔（边界例）。
状态：已落基线测试，见 `test_next_segment_waits_for_fresh_three_bi_seed_after_break`。
8. 两个缺口候选连续出现时，旧候选与新候选优先级切换（替代规则）。
状态：并入第 5 条，当前工程口径已固化为“后候选覆盖前候选”。

最小交付顺序建议：

1. 先做 1/2 两条“互斥主路径”样例，锁定主判别。
2. 再做 3/4 两条“弱信号穿插”样例，锁定抗噪。
3. 最后补 5-8 的稳定性与边界样例。

当前仍待落地：无。

### 8.3 矩阵完成状态（截至当前）

| 编号 | 场景 | 当前状态 | 对应测试 |
|---|---|---|---|
| 1 | 先破第一笔终点，旧段终结 | 已完成（pass） | `test_gap_fractal_then_break_first_bi_end_confirms_new_segment` |
| 2 | 先破第一笔起点，旧段延续 | 已完成（pass） | `test_gap_fractal_then_break_first_bi_start_keeps_prior_segment` |
| 3 | 弱同向恢复后再破起点（延续） | 已完成（pass） | `test_gap_candidate_weak_recovery_then_late_reverse_break_keeps_prior_segment` |
| 4 | 弱反向后再强同向破终点（终结） | 已完成（pass） | `test_gap_candidate_weak_reverse_then_late_strong_same_dir_confirms_break`、`test_delayed_true_path_emits_dedicated_stop_reason` |
| 5 | 候选切换优先级 | 已完成（pass） | `test_multiple_gap_candidates_switch_priority_deterministically` |
| 6 | 包含合并后的候选稳定性 | 已完成（pass） | `test_gap_candidate_stays_stable_when_feature_sequence_is_merged` |
| 7 | 不吞并下一段起段三笔 | 已完成（pass，主测试覆盖） | `test_next_segment_waits_for_fresh_three_bi_seed_after_break` |
| 8 | 连续候选优先级替代规则 | 已并入第5条 | 同上 |

### 8.4 第4条实现切入点（代码）

- 主函数：`src/chanlun/segment.py` 的 `_rediscriminate_gap_break(...)`
- 当前行为：一旦满足当前轮的“同向笔突破 first_end_extreme”，即立刻返回 `True`
- 第4条目标：允许“弱反向/弱同向”先走一轮，再在后续轮次出现“同向强推进”时确认 `True`
- 建议改法：
	1. 在 `_rediscriminate_gap_break(...)` 内增加“至少经历一次弱轮次”的状态标记（不改外部接口）。
	2. 仅当已进入弱轮次后再满足突破条件时返回 `True`，并保持先破起点返回 `False` 的优先级不变。
	3. 落地后将第4条 `xfail` 转为正常断言，并复跑 `tests/test_segment.py`。

建议测试文件：`tests/test_segment_rediscrimination_matrix.py`。

### 8.5 gap defer / invalidated 交界优先级清单（工程已锁定）

本清单把 `_extend_segment(...)` 主循环里 `pending_gap_break_idx` 被触发后的判决顺序固定下来，
避免“同图不同判”。`GapCandidateState` 取值与含义：

- `NONE`：无缺口候选。
- `CONFIRMED`：缺口再分辨为 `True`（后续同向先破第一笔终点）。
- `INVALIDATED`：缺口再分辨为 `False`（后续反向先破第一笔起点），且未进入 defer。
- `DEFERRED`：缺口再分辨为 `False`，但满足 `enable_gap_false_defer` 且候选恰为当前 cursor、后续笔数足够，延迟到下一轮再判。
- `PENDING`：再分辨为 `None`（证据不足），暂不下结论。

判决优先级（高 → 低）：

1. **CONFIRMED**：立即按缺口分型终结，`stop_reason` 为 `feature_sequence_gap_fractal` 或
   `feature_sequence_gap_fractal_delayed_true`。唯一例外是“下行弱缺口未破 `last_same_extreme`”
   会继续保持 pending，不提前确认。
2. **INVALIDATED + reclaim**：非 defer 窗口下，先尝试 `_reclaims_transition_back_to_prior_segment(...)`；
   若反向笔已破第一笔起点、转折被收回前段，则回退 cursor、清空 gap 候选、继续扫描。
3. **DEFERRED**：更新 `last_same_extreme / last_reverse_extreme`、置 `defer_next_reverse_break=True`、
   裁掉旧 `reverse_indices`，`cursor += 2` 进入下一轮，本轮不确认。
4. **INVALIDATED（无可 reclaim）**：置 `gap_false_locked=True` 锁死候选，清 `defer_next_reverse_break`，
   转 fallback 路径（`reverse_break` / theory stop / `same_direction_not_extending`）。

pending / confirmed 共存红线：

- 只有 `CONFIRMED` 才允许写 confirmed 终结码；`DEFERRED / INVALIDATED / PENDING` 一律不得提前写 confirmed。
- `DEFERRED` 期间 `defer_next_reverse_break=True` 会抑制下一轮 fallback `reverse_break`，保证结构未落定前不确认。
- `INVALIDATED` 后 `gap_false_locked=True`，后续不再接受 gap 候选 True 翻案（“先破起点优先”），
  已作废的 pending 候选不得与后续 confirmed 在同一角色并存。
- 下游中枢层只消费 confirmed 段（未确认尾段被裁，见 [zhongshu-input-qualification.md](zhongshu-input-qualification.md)），
  因此 defer / invalidated 期间的“候选转折”不会漏进中枢输入。

## 9. 线段与中枢的关系

当前项目里的线段，可以作为后续“线段级中枢实验口径”的输入候选，但这里有两个边界必须先说清楚：

- 当前线段实现是工程化简化线段，不等于严格缠论中的完整走势类型分解结果
- 因此“基于线段构建中枢”在本阶段只能理解为更高一级的实验结构摘要，不能直接替代当前笔级中枢主口径

如果后续要增加线段级中枢，建议遵守以下顺序：

1. 保留现有笔级中枢为主输出
2. 新增单独的线段级中枢输出层
3. 在图上把线段级中枢与笔级中枢分层显示
4. 先做人工核图，再决定是否提升其解释权重

不建议当前就把“线段 = 更标准的中枢输入”直接写成实现前提。更准确的说法是：

- 线段级中枢是更高层级的候选表达
- 是否更接近严格缠论，要取决于线段本身是否已经足够接近严格走势类型
- 在这件事尚未验证前，应把线段级中枢明确标为实验层，而不是默认层

后续若继续完善，优先级建议如下：

- 先扩充线段回归样本基线，覆盖趋势/震荡/跳空密集三类风格，降低规则迭代回退风险
- 再评估是否需要让部分尾部未确认笔以受控方式参与线段尾段解释，而不是直接参与正式起段/终结判定
- 最后才考虑把当前工程化线段升级为更严格的走势类型/特征序列口径

因此，如果后续要继续收严线段定义，应优先修改 `src/chanlun/segment.py`，再同步更新这里和总规格文档。