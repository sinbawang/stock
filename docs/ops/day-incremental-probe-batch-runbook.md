# Day 批量增量探针运行手册

用于按持仓批量生成 day 级别本地仓库增量效果榜单。

## 快速命令

```powershell
py -3 scripts/run_day_incremental_probe_batch.py --holdings-file data\stock_holdings.json --market ALL --limit 10 --no-execute-run
```

默认 `--no-execute-run`（仅读已有 tech.json）。
如果希望逐只先执行 day 刷新再统计：

```powershell
py -3 scripts/run_day_incremental_probe_batch.py --holdings-file data\stock_holdings.json --market ALL --limit 10 --execute-run
```

## 常用参数

1. `--market {ALL|CN|HK}`: 市场过滤
2. `--symbols 000651 00700`: 指定代码
3. `--limit N`: 限制标的数量
4. `--day-bars 1200`: day 分析目标根数
5. `--incremental-overlap-bars 120`: 增量回看根数
6. `--history-window 10`: 单标趋势窗口

## 输出文件

默认输出到 `data/reports/_meta/`：

1. `day_incremental_probe_batch_YYYYmmdd_HHMMSS.json`
2. `day_incremental_probe_batch_latest.json`
3. `day_incremental_probe_batch_YYYYmmdd_HHMMSS.txt`

## 关注指标

1. `summary.warm_cache_ratio`: 热缓存命中率
2. `summary.avg_saved_rows_ratio`: 平均节省行数占比
3. `summary.avg_elapsed_seconds`: 平均执行耗时（当 `--execute-run` 生效时）
4. `summary.top_saved_rows_ratio`: 节省占比最高标的
5. `summary.bottom_saved_rows_ratio`: 节省占比最低标的
