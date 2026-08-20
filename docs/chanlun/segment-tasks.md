# 线段模块任务拆解

本页把 [chanlun-spec-tasks.md](chanlun-spec-tasks.md) 中与 `segment` 直接相关的工作拆成可执行任务，避免总表里只剩长段状态描述。

## 关联总表条目

- 严格线段主链路
- 线段严格定义案例库
- confirmed / pending / auxiliary 三态统一（上游部分）

## 当前 epic 看板

| ID | 任务 | 状态 | 依赖 | 完成定义 |
| --- | --- | --- | --- | --- |
| S1 | 线段成立与终结条件统一 | 进行中 | 分型 / 笔已稳定 | theory / practical 对同一窗口能解释“为什么已成立、为什么已终结、为什么尾段仍未确认” |
| S2 | `pending_confirmation` 与 `confirmed` 统一 | 进行中 | S1 | `segment_tail_interpretations`、摘要字段、消费文案三处状态一致 |
| S3 | 重写 / 吸收 / 复用输出口径稳定 | 进行中 | S1, S2 | `is_reclaimed`、`absorbed_segment_ids`、边界复用语义能稳定落到输出字段与示例 |
| S4 | 真实窗口回归闸门收口 | 进行中 | S1-S3 | synthetic tests、focused regressions、发布前闸门覆盖关键 restart / overlap / preprocess-tail 分支 |

## 按任务类型看板

阅读方式：

- 文档任务：规则说明、review 入口、案例库、实现指南这类帮助 reviewer 快速定位语义边界的工作。
- 测试任务：synthetic coverage、focused regression、真实窗口闸门这类锁边界不漂的工作。
- 代码任务：线段成立、确认态、重写/吸收/复用输出这类直接改变产物行为的实现工作。
- 优先级：`高` 表示当前线段主线直接卡住；`中` 表示并行收口项；`低` 表示保留但不抢当前主线。

当前重点：

1. 代码：继续收口 `S1-S3`，先稳住首段 bootstrap、尾段确认和重写 / absorb 事件顺序。
2. 测试：保持真实窗口 regression 和发布前安全闸门，防止边界漂移传到中枢层。
3. 文档：继续补 67/71 课正反例与 restart / overlap review 解释。

### 文档任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| D1 | 线段规则说明与实现指南 | 中 | 把 bootstrap / stop_reason / 重写吸收口径继续写清 | 进行中 | [segment-implementation-guide.md](segment-implementation-guide.md) 已有主框架，后续仍需跟规则变更同步回写。 |
| D2 | review 入口与图示库 | 中 | 补 67/71 课正反例与 restart / overlap 解释 | 进行中 | review 入口和图示库已起骨架，现成真实窗口入口已有 `000651 30m`、`000591 15m`、`00700 15m`。 |

### 测试任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| T2 | 真实窗口 regressions | 高 | 维护 `000591`、`300124`、`00700`、`03690` 的 focused regressions | 进行中 | 这是当前线段层最直接的稳定性护栏。 |
| T3 | 发布前安全闸门 | 高 | 保证线段改动不会把未解释漂移传到中枢层 | 进行中 | 仍需持续对照 [segment-safety-checklist.md](segment-safety-checklist.md)。 |
| T1 | synthetic coverage | 中 | 继续锁 gap / reclaim / reverse_break / preprocess-tail 交界 | 进行中 | 已有多组基础 synthetic 闸门，复杂组合交界仍待继续扩充。 |

### 代码任务

| 类型 ID | 任务 | 优先级 | 当前重点 | 当前状态 | 进展 |
| --- | --- | --- | --- | --- | --- |
| C1 | S1 线段成立与终结条件统一 | 高 | 锁首段 bootstrap、尾段确认与 stop_reason 解释 | 进行中 | 属于当前线段主实现的第一优先级。 |
| C2 | S2 `pending_confirmation` 与 `confirmed` 统一 | 高 | 收口尾段状态机与 practical 主循环停扫规则 | 进行中 | 当前多个消费位点仍需要保持同一命名和同一结论。 |
| C3 | S3 重写 / 吸收 / 复用输出口径稳定 | 高 | 统一 reclaim / overlap / restart / absorb 的事件顺序 | 进行中 | 是当前上游边界继续漂移的核心 blocker。 |

## 任务拆分

<a id="s1-segment-bootstrap"></a>
### S1 线段成立与终结条件统一

- 明确严格线段从哪些已确认笔开始计入。
- 明确首段 bootstrap 允许的候选范围，以及 later confirmed 候选何时必须让位于更早未解决窗口。
- 明确哪些尾部延伸只能保留为候选，不能提前确认为 completed。
- 把 `reverse_break`、`feature_sequence_fractal`、`same_direction_not_extending` 的边界写进 review 示例。

验收：

- 同一真实窗口下，`first_valid_seed` / `auto` / `prefer_earlier_start` 不再分叉出不同首段。
- 首段起点、方向、`is_confirmed`、`stop_reason` 可由单页 review 解释清楚。

<a id="s2-confirmation-state"></a>
### S2 `pending_confirmation` 与 `confirmed` 统一

- 统一 `segment_tail_interpretations`、同级别走势摘要、消费者文案中的确认态命名。
- 明确 practical 主循环遇到首个未确认段时，何时继续扫描、何时停止。
- 把“预处理尾段”“未确认尾段”“可独立启动的新 confirmed 段”拆成稳定状态机。

验收：

- 不再出现一处已确认、另一处仍显示待确认的冲突。
- `000591-day`、`300124 15m` 这类 live / mixed 窗口的尾段解释保持稳定。

<a id="s3-rewrite-absorb"></a>
### S3 重写 / 吸收 / 复用输出口径稳定

- 统一 reclaim、重写、absorb、overlap、restart 的事件顺序和优先级。
- 约束 local gap false `DEFERRED -> INVALIDATED` 与 latent reclaim 的相对优先级。
- 把“旧线段被吸收”“边界右移重算”“后续段复用 break 笔”写成 machine-readable 字段和案例。

验收：

- `break_bi_id -> next start_bi_id` restart anchor 在真实窗口中不漂移。
- `segments.csv`、miniapp `summary/detail`、review 示例对同一重写事件给出同一解释。

<a id="s4-regression-gates"></a>
### S4 真实窗口回归闸门收口

- 维护 synthetic coverage，专门锁定 gap / reclaim / reverse_break / preprocess-tail 交界。
- 维护真实 fixture regression：`000591`、`300124`、`00700`、`03690`。
- 任何新增线段分支都必须补 focused regression，再进入发布链。

验收：

- 提交前能通过 [segment-safety-checklist.md](segment-safety-checklist.md) 定义的闸门。
- 线段变更不会在下游中枢识别中引入未解释的边界漂移。

## 当前 blocker

- reclaim / 重写 与 gap 再分辨交界仍未完全统一。
- 上游线段边界只要继续漂移，下游标准中枢完成态也会跟着漂移。

## 回写规则

- 线段规则变更：同步更新 [segment-implementation-guide.md](segment-implementation-guide.md)。
- review 解释补充：同步更新 [segment-review-entry.md](segment-review-entry.md) 与 [segment-visual-example-library.md](segment-visual-example-library.md)。
- 总进度变化：回写 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。