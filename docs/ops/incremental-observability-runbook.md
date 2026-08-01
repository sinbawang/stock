# 增量观测日报运行手册

用于量化本地 K 线仓库增量改造效果，重点观察：

1. 热缓存命中率
2. 远端抓取行数占比
3. 估算节省行数占比
4. 全链路耗时相对基线变化

## 运行命令

```powershell
python scripts/generate_incremental_observability_report.py
```

常用参数：

```powershell
python scripts/generate_incremental_observability_report.py --timeframes 30m 5m 1m --timing-window 10
```

## 输出文件

默认输出到 `data/reports/_meta/`：

1. `incremental_observability_YYYYmmdd_HHMMSS.json`
2. `incremental_observability_latest.json`
3. `incremental_observability_YYYYmmdd_HHMMSS.txt`

## 核心指标解释

- `scan.scanned_tech_json_count`: 本次纳入统计的 `tech.json` 数量
- `scan.local_store_enabled_count`: 带 `data_fetch.local_store` 元数据的报告数量
- `scan.warm_cache_count`: `local_rows_before > 0` 的报告数量，代表热缓存命中
- `aggregate.saved_rows_ratio`: 估算节省行数占比，计算方式：
  - `(analysis_rows - remote_rows) / analysis_rows`
- `aggregate.warm_cache_ratio`: 热缓存命中率，计算方式：
  - `warm_cache_count / local_store_enabled_count`

## 耗时趋势口径

- 数据源：`data/reports/_meta/holdings_refresh_timing_*.json`
- 最新耗时：最新样本的 `stages.total_seconds`
- 基线耗时：历史样本（不含最新）最近 N 条中位数
- 改善幅度：
  - `(baseline_median - latest_total_seconds) / baseline_median`

若没有足够历史样本，`timing_trend` 会返回 `null` 或 `baseline_median_total_seconds=null`。

## 建议阈值

1. `warm_cache_ratio >= 0.7`：表示增量命中稳定
2. `saved_rows_ratio >= 0.4`：说明远端抓取压力明显下降
3. `improvement_pct_vs_baseline > 0`：全链路耗时较基线有改善
