# Ops Docs

部署、运维和执行流程相关文档索引。

## 文件清单

- [tencent-container-service-plan.md](tencent-container-service-plan.md): 腾讯云容器服务化方案
- [tencent-cloud-deploy-runbook.md](tencent-cloud-deploy-runbook.md): 腾讯云部署操作手册
- [add-hk-holding-runbook.md](add-hk-holding-runbook.md): 新增港股持仓运行手册
- [incremental-observability-runbook.md](incremental-observability-runbook.md): 本地历史仓库增量命中率与耗时趋势观测
- [day-incremental-probe-runbook.md](day-incremental-probe-runbook.md): day 级别单标增量抓取/分析探针
- [day-incremental-probe-batch-runbook.md](day-incremental-probe-batch-runbook.md): day 级别持仓批量增量探针榜单
- [kline-cache-cloud-backup-runbook.md](kline-cache-cloud-backup-runbook.md): 本地 K 线缓存备份到 CloudBase/COS 与新实例恢复手册（含 CloudBase 托管容器模式）
- [segment-safety-gates-runbook.md](segment-safety-gates-runbook.md): 线段改动发布前单入口闸门执行手册

相关模板：

- `bin/linux/cloud-init/install-kline-cache-backup.yaml`: 可选的自管 CVM / 传统机器 cloud-init 模板，不用于 CloudBase Run 容器实例
