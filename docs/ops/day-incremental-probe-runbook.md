# Day 增量探针运行手册

用于单标的 day 级别本地历史仓库效果核验，一条命令输出：

1. 本次远端抓取行数
2. 本地合并后分析行数
3. 节省行数占比
4. 最近 N 次探针趋势（热缓存命中率、平均节省占比、平均耗时）

## 命令

```powershell
py -3 scripts/run_day_incremental_probe.py 000651 --name 格力电器 --market CN --day-bars 1200 --history-window 10
```

## 仅读取当前产物（不触发新一轮 day 刷新）

```powershell
py -3 scripts/run_day_incremental_probe.py 000651 --name 格力电器 --market CN --day-bars 1200 --no-execute-run
```

## 输出文件

默认输出到 `data/reports/_meta/`：

1. `day_incremental_probe_<symbol>_YYYYmmdd_HHMMSS.json`
2. `day_incremental_probe_<symbol>_latest.json`
3. `day_incremental_probe_<symbol>_YYYYmmdd_HHMMSS.txt`
4. `day_incremental_probe_history.jsonl`（历史样本）

## 关键字段

- `metrics.local_rows_before`: 本次执行前本地仓库已有行数
- `metrics.remote_rows`: 本次远端实际拉取行数
- `metrics.analysis_rows`: 本次用于分析的行数
- `metrics.saved_rows_ratio`: 估算节省占比 `(analysis_rows - remote_rows) / analysis_rows`
- `metrics.requested_start`: 目标历史起点
- `metrics.effective_start`: 实际增量抓取起点
- `history_trend.warm_cache_ratio`: 最近窗口热缓存命中率
- `history_trend.avg_saved_rows_ratio`: 最近窗口平均节省占比
- `history_trend.avg_elapsed_seconds`: 最近窗口平均执行耗时
