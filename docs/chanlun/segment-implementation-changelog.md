# 线段实现变更快照（Changelog）

本页用于记录线段实现的时间点快照、回归结果和完成度估计。

稳定规则口径请看：

- [segment-implementation-guide.md](segment-implementation-guide.md)
- [segment-stop-reason-contract.md](segment-stop-reason-contract.md)

## 2026-08-11 快照

基于当时仓库状态，线段识别核心实现已推进到可验证阶段：

- theory/practical 分流已接入主路径；
- 缺口再分辨延迟确认已纳入扩展流程；
- `termination_mode=theory` 下 bootstrap/strict 行为已收敛；
- 过渡边界（第一笔破坏后第三笔分叉）已补回放用例；
- 跨周期 stop category 覆盖断言已补齐；
- 下游发布/导出侧已对齐 `stop_category` 与布尔字段。

当时验证结果：

- 分段相关回归：54 passed
- 全量测试：491 passed

当时完成度估算：

- 约 98%（核心分流、状态化、边界回放和下游契约统一已落地）
- 约 2%（外围入口统一声明与调用方接入范式沉淀）

注：该页允许保留历史数值快照；如与当前仓库实时状态不一致，以最新测试结果为准。

## 2026-08-14 快照

本次快照用于固化“任务完成 -> 回归结果 -> 文档更新”的闭环记录。

### 闭环记录模板（后续沿用）

每个任务至少记录三项：

1. 任务范围：改了什么（代码/测试）。
2. 回归结果：跑了哪些闸门、结果如何。
3. 文档更新：更新了哪些规范/导航/看板。

### 本轮闭环记录

| 任务 | 任务范围（代码/测试） | 回归结果 | 文档更新 |
| --- | --- | --- | --- |
| N1 过渡边界待定态收口 | 修正 `transition_pending` 判定边界；新增 `test_transition_pending_uses_fallback_seed_boundary_instead_of_anchor_start` | 核心与矩阵通过（51+） | 更新任务看板完成说明 |
| N2 核心边界回归补齐 | 增补 dual-mode/unknown 守卫、关键地标防超长单段、bootstrap 分类守卫 | 线段回归闸门通过（47+） | 更新任务看板完成说明 |
| N3 strict 规则剥离 | strict 显式绑定 practical；新增 theory 对 strict 不敏感回归 | 核心与跨周期回归通过（37+） | 更新任务看板完成说明 |
| N4 bootstrap 主流程解耦 | 拆分基础起点层与评分优化层；新增 first_valid 不受评分影响回归 | 核心与回归闸门通过（48+） | 更新实现指南与任务看板 |
| N5 特征序列上下文强化 | 增加跨序列包含守卫与 triplet 上下文校验；新增 2 条上下文回归 | 核心与回归闸门通过（48+） | 更新实现指南与任务看板 |
| Later-1 课文边界 fixture 化 | 新增 `segment_lesson_boundary_fixtures` 与消费测试 | 新增 fixture 测试通过（9）并纳入闸门（57+） | 更新任务看板完成说明 |
| Later-2 双模式接入示例 | 新增消费方最小接入文档 | 文档命令抽样可执行（39+） | 更新文档地图、README、任务看板 |
| B1 再分辨 R1-R6 映射 | 在 `test_segment_rediscrimination_matrix` 增加 R1-R6 参数化映射、唯一 ID 与双模式断言 | 目标测试通过（39+） | 更新任务看板与文档地图 |
| B2 消费端双模式冒烟 | 新增 `test_segment_consumer_mode_smoke`；验证 pending/terminal 按模式消费 | 目标测试通过（39+） | 更新示例文档与任务看板 |
| B3 安全闸门单入口 | 新增 `scripts/run_segment_safety_gates.py`、任务入口与脚本单测 | `--dry-run` 与 `--only core consumer` 通过 | 更新任务看板与文档地图 |
| B4 双模式可视化对照 | 在消费者示例新增 stop_reason 双模式对照表 | 文档对照与 contract 口径一致 | 更新示例文档与任务看板 |
| B5 线段到中枢协议草案 | 新增模式传递协议草案并接入文档导航 | 文档检查无诊断错误 | 更新 README、文档地图、任务看板 |

说明：

- 表中计数为本轮执行时的通过数快照，后续以实时 CI/本地闸门为准。
- 任务源看板见 [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)。
