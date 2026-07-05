# 持仓分析 API / 腾讯云容器方案

这份文档描述当前仓库新增的第一版服务化落地方式：

- 保留本地脚本链路作为稳定基线
- 把技术分析批处理和发布总控暴露为容器内 API
- 让微信小程序、定时任务、以及后续腾讯侧触发入口，共用同一套服务端作业接口

## 当前新增能力

### 1. 容器内 API 入口

新增 FastAPI 应用：

- `src/chanlun_api/app.py`

当前提供四个核心接口：

- `GET /healthz`
- `POST /jobs/publish-refresh`
- `POST /jobs/technical-refresh`
- `GET /jobs/{job_id}`

其中：

- `publish-refresh` 复用现有 `refresh_holdings_publish_to_cloudbase.py` 总链路，适合“全持仓一键生成 + 构建 + 发布”
- `technical-refresh` 只跑技术分析批处理，再重建并上传发布包，适合交易时段内的 `30m/5m` 定时刷新

### 2. 技术分析脚本已可直接被服务层调用

新增公共函数：

- `scripts/batch_prepare_chanlun_reports.py::run_batch_prepare(...)`

这一步很关键，因为后续定时任务不必再通过命令行子进程调用主脚本，也不必重新拼装第二套逻辑。

### 3. 发布总控已支持时间级别参数透传

`scripts/refresh_holdings_publish_to_cloudbase.py` 当前已经支持并透传：

- `--m30-bars`
- `--m5-bars`
- `--tech-timeframes`
- `--publish-timeframes`

这让本地模式和容器模式都能明确控制要生成哪些级别，以及发布包应包含哪些图表。

## 推荐运行方式

### 本地启动服务

```powershell
.venv\Scripts\python.exe -m uvicorn chanlun_api.app:app --host 0.0.0.0 --port 8000
```

### 容器构建

```powershell
docker build -t chanlun-stock-service .
docker run --rm -p 8000:8000 \
  -e CLOUDBASE_ENV_ID=your-env \
  -e CLOUDBASE_REGION=ap-guangzhou \
  -e CLOUDBASE_APIKEY=your-key \
  chanlun-stock-service
```

## 推荐 API 用法

### 1. 小程序按钮触发全持仓刷新

请求：

```json
{
  "latest_only": true,
  "tech_timeframes": ["day", "60m", "30m", "15m", "5m"],
  "pending_reverse_mode": "effective_only",
  "zhongshu_level": "segment"
}
```

接口：

- `POST /jobs/publish-refresh`

行为：

- 重新生成持仓分析
- 重建 `build/miniapp-publish/latest`
- 上传到 CloudBase

### 2. 交易时段定时刷新 30m/5m

请求：

```json
{
  "latest_only": true,
  "tech_timeframes": ["30m", "5m"],
  "pending_reverse_mode": "effective_only",
  "zhongshu_level": "segment",
  "skip_upload": false
}
```

接口：

- `POST /jobs/technical-refresh`

行为：

- 只刷新技术级别图和 `tech.json`
- 然后重建发布包并上传

## 腾讯侧推荐架构

当前最推荐的部署方式不是“纯云函数直跑全量分析”，而是：

1. 小程序调用云函数或 CloudBase HTTP 入口。
2. 云函数只做鉴权、参数整理、提交作业。
3. 真正的 Python 重任务跑在腾讯云容器或 CloudBase 容器托管。
4. 作业完成后继续上传到 CloudBase 存储。
5. 小程序轮询作业状态，并刷新 `miniapp-publish/latest/index.json`。

原因：

- 当前依赖较重，含 `pandas`、`matplotlib`、`akshare`
- 技术分析图导出和批量抓取耗时较长
- 全持仓批任务天然更适合容器，不适合把 SCF 当主执行层

## 目前这版的边界

当前这版服务化骨架已经能支撑：

- 本地直接运行
- 容器中运行
- 小程序或定时任务通过 HTTP 触发

但它仍有三个已知边界：

1. 作业状态目前是进程内内存存储，容器重启会丢失。
2. 还没有分布式锁，多个并发全量刷新需要后续加互斥保护。
3. 业务主链路仍有部分脚本层耦合，后续建议继续向 `src/` 服务层收口。

## 下一步建议

1. 把作业状态从内存迁移到 CloudBase 集合或 Redis。
2. 给全量刷新增加互斥锁和幂等键，避免小程序重复点击触发重叠作业。
3. 腾讯云侧一键发布入口已经补上：
  - `scripts/deploy_tencent_container_service.py`
  - `bin/deploy_service.bat`
  - 使用说明见 [tencent-cloud-deploy-runbook.md](tencent-cloud-deploy-runbook.md)
4. 把当前 `scripts/` 中的编排逻辑逐步下沉到 `src/` 服务模块，减少容器内脚本导入耦合。