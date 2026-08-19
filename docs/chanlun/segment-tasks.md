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

## 任务拆分

### S1 线段成立与终结条件统一

- 明确严格线段从哪些已确认笔开始计入。
- 明确首段 bootstrap 允许的候选范围，以及 later confirmed 候选何时必须让位于更早未解决窗口。
- 明确哪些尾部延伸只能保留为候选，不能提前确认为 completed。
- 把 `reverse_break`、`feature_sequence_fractal`、`same_direction_not_extending` 的边界写进 review 示例。

验收：

- 同一真实窗口下，`first_valid_seed` / `auto` / `prefer_earlier_start` 不再分叉出不同首段。
- 首段起点、方向、`is_confirmed`、`stop_reason` 可由单页 review 解释清楚。

### S2 `pending_confirmation` 与 `confirmed` 统一

- 统一 `segment_tail_interpretations`、同级别走势摘要、消费者文案中的确认态命名。
- 明确 practical 主循环遇到首个未确认段时，何时继续扫描、何时停止。
- 把“预处理尾段”“未确认尾段”“可独立启动的新 confirmed 段”拆成稳定状态机。

验收：

- 不再出现一处已确认、另一处仍显示待确认的冲突。
- `000591-day`、`300124 15m` 这类 live / mixed 窗口的尾段解释保持稳定。

### S3 重写 / 吸收 / 复用输出口径稳定

- 统一 reclaim、重写、absorb、overlap、restart 的事件顺序和优先级。
- 约束 local gap false `DEFERRED -> INVALIDATED` 与 latent reclaim 的相对优先级。
- 把“旧线段被吸收”“边界右移重算”“后续段复用 break 笔”写成 machine-readable 字段和案例。

验收：

- `break_bi_id -> next start_bi_id` restart anchor 在真实窗口中不漂移。
- `segments.csv`、miniapp `summary/detail`、review 示例对同一重写事件给出同一解释。

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