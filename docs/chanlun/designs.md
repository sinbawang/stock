# 设计层总入口（Designs Index）

本页是 `docs/chanlun` 设计层的总入口，只做索引，不重复写定义。

设计层回答「当前工程如何把规格落地为可复现的判定流程 / 状态机 / 协议」，
介于「规格层（应然）」与「任务层（排期）」之间。

## 按模块

### 线段

- [segment-implementation-guide.md](segment-implementation-guide.md)：线段现行实现口径（识别 / 确认 / 双模式）。
- [segment-doc-map.md](segment-doc-map.md)：线段文档分层导航。
- [segment-zhongshu-boundary.md](segment-zhongshu-boundary.md)：线段 → 中枢 进入段 / 本体 / 离开段边界口径。
- [segment-to-zhongshu-mode-protocol-draft.md](segment-to-zhongshu-mode-protocol-draft.md)：线段 theory/practical 语义向中枢传递的协议草案。

### 中枢

- [zhongshu-state-machine.md](zhongshu-state-machine.md)：中枢完成 / 扩张 / 新中枢状态机（ZS2 交付说明）。
- [zhongshu-input-qualification.md](zhongshu-input-qualification.md)：标准中枢输入 segment 资格表（ZS1.1 交付说明）。
- [zhongshu-recompute-order.md](zhongshu-recompute-order.md)：中枢重算顺序与旧中心清理规则（ZS3.1 交付说明）。

### 走势类型 / 背驰

- [trend-type-decomposition.md](trend-type-decomposition.md)：同级别走势类型自动分解主链（TD1）。
- [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md)：走势多义性与结合律（允许/禁止重组、中枢选择）。

## 关联

- 规格层总入口：[chanlun-rule-spec.md](chanlun-rule-spec.md)、[chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- 任务层总入口：[chanlun-spec-tasks.md](chanlun-spec-tasks.md)
- 总入口：[README.md](README.md)
