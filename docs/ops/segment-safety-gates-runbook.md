# Segment Safety Gates Runbook

本手册用于发布前执行线段改动闸门，目标是把分散的测试入口收敛为一条命令并提供失败定位。

## 1. 适用场景

- 修改 `src/chanlun/segment.py` 及其依赖分支判断。
- 修改线段相关测试基线或回归样本。
- 准备发布包含 `segments` 字段变更的图表/报告产物。

## 2. 快速执行

在仓库根目录执行：

```powershell
python scripts/run_segment_safety_gates.py
```

脚本将顺序执行：

- `core`
- `regression`
- `consumer`

若任一闸门失败，脚本会立即返回非 0 退出码并打印失败 gate 名称。

## 3. 选择性执行

仅跑核心与消费闸门：

```powershell
python scripts/run_segment_safety_gates.py --only core consumer
```

仅查看将执行的命令（不实际运行）：

```powershell
python scripts/run_segment_safety_gates.py --dry-run
```

## 4. 推荐发布前步骤

1. 执行 `python scripts/run_segment_safety_gates.py`。
2. 若通过，再按 [kline-cache-cloud-backup-runbook.md](kline-cache-cloud-backup-runbook.md) 或相应发布流程上传产物。
3. 对关键标的做本地/云端 `segments` 一致性抽检。

## 5. 常见失败定位

- `core` 失败：优先检查 `tests/test_segment.py` 与 `tests/test_segment_rediscrimination_matrix.py` 的分支语义变化。
- `regression` 失败：优先检查跨样本基线、bootstrap 行为和 lesson fixture 兼容性。
- `consumer` 失败：优先检查 `stop_reason` 分类契约与 theory/practical 消费逻辑是否漂移。

## 6. 关联文档

- [../chanlun/segment-safety-checklist.md](../chanlun/segment-safety-checklist.md)
- [../chanlun/segment-stop-reason-contract.md](../chanlun/segment-stop-reason-contract.md)
- [../chanlun/segment-mode-consumer-examples.md](../chanlun/segment-mode-consumer-examples.md)
