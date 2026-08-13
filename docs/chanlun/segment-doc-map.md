# 线段文档地图

本页用于统一 `docs` 下线段相关文档的分层、阅读顺序和维护边界。

## 文档分层

1. 现行实现口径（主文档）
- [segment-implementation-guide.md](segment-implementation-guide.md)
- 用途：说明当前工程实现如何识别线段，供人工核图、调试、回归使用。

2. 原文对照与差异分析（背景文档）
- [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)
- 用途：沉淀原文提炼、偏差来源、演进记录与理论层跟踪项。

3. 稳定接口契约（消费方入口）
- [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 用途：统一 `stop_reason` / `stop_category` 语义，减少下游解释漂移。

4. 变更快照（时点记录）
- [segment-implementation-changelog.md](segment-implementation-changelog.md)
- 用途：沉淀阶段性测试结果、完成度估算和演进快照，避免污染主规范正文。

5. 改动安全清单（执行闸门）
- [segment-safety-checklist.md](segment-safety-checklist.md)
- 用途：统一提交前/发布前必跑检查，降低“肉眼正确但回归退化”的风险。

6. 双模式接入示例（消费方入口）
- [segment-mode-consumer-examples.md](segment-mode-consumer-examples.md)
- 用途：给下游最小可运行的 theory/practical 对照接入范式。

7. 线段到中枢协议草案
- [segment-to-zhongshu-mode-protocol-draft.md](segment-to-zhongshu-mode-protocol-draft.md)
- 用途：约束中枢层如何继承 theory/practical 语义并处理 pending。

## 推荐阅读顺序

1. 先读 [segment-implementation-guide.md](segment-implementation-guide.md)
2. 再读 [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
3. 最后参考 [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)

## 维护规则

- 规则变更：先更新 [segment-implementation-guide.md](segment-implementation-guide.md)
- 契约变更：同步更新 [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 背景说明：补充到 [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)
- 时点快照：记录到 [segment-implementation-changelog.md](segment-implementation-changelog.md)
- 改动前后核验：执行 [segment-safety-checklist.md](segment-safety-checklist.md)
- 避免把“现行规则”和“历史分析”混写在同一段正文。

## 当前 TODO

- [x] 把 71 课再分辨剩余分支（R1-R6）拆到可跟踪 issue/测试映射
- [x] 在发布与报告消费端补一页最小接入示例（theory/practical 双模式）
- [x] 补充线段安全闸门单入口任务（`python scripts/run_segment_safety_gates.py`）
- [x] 增补线段到中枢模式传递协议草案
- [x] 增设 `segment-implementation-changelog.md` 承接时点快照，减少正文历史堆积
