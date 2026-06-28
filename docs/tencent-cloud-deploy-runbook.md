# 腾讯云容器一键发布 Runbook

这份 runbook 对应当前仓库里的发布入口：

- `scripts/deploy_tencent_container_service.py`
- `bin/deploy_service.bat`

目标是把本地这版 FastAPI 服务用一条命令发布到 CloudBase Run 服务；如果目标服务还不存在，脚本会先失败并给出首次建服所需的精确参数。

当前仓库的发布脚本会自动识别本机 CloudBase CLI 是旧版 `tcb run ...` 口径还是新版 `tcb cloudrun ...` 口径，并选择对应命令。

## 5 分钟速查版

如果你只想先把第一次发布跑通，可以按这条最短路径走：

1. 安装并登录 CloudBase CLI：

```powershell
npm i -g @cloudbase/cli
tcb login
```

2. 在 CloudBase Run 控制台创建一次服务：

- 服务名：`chanlun-stock-service`
- Dockerfile：仓库根目录里的 `Dockerfile`
- 容器端口：`8000`
- CPU / 内存：`0.5 / 1 GB`
- 副本数：`0 ~ 2`
- 环境变量：`CLOUDBASE_ENV_ID`、`CLOUDBASE_REGION`、`CLOUDBASE_APIKEY`

3. 本地准备环境变量：

```powershell
$env:CLOUDBASE_ENV_ID = "your-env-id"
$env:CLOUDBASE_REGION = "ap-guangzhou"
$env:CLOUDBASE_APIKEY = "your-cloudbase-admin-api-key"
```

4. 先做 dry-run：

```powershell
bin\deploy_service.bat --service-name chanlun-stock-service --dry-run
```

5. 再做真实发布：

```powershell
bin\deploy_service.bat --service-name chanlun-stock-service
```

6. 发布后访问服务域名的 `/healthz`，预期返回 `200`。

## 当前环境最短命令清单

下面这组命令已经替你带上当前环境 ID `cloudbase-d9gplq92zc1d88ee6`，适合在首次建服完成后直接执行。

1. 先设置本地环境变量：

```powershell
$env:CLOUDBASE_ENV_ID = "cloudbase-d9gplq92zc1d88ee6"
$env:CLOUDBASE_REGION = "ap-shanghai"
$env:CLOUDBASE_APIKEY = "你的 CloudBase Admin API Key"
```

2. 查询服务是否已经建好：

```powershell
tcb --env-id cloudbase-d9gplq92zc1d88ee6 cloudrun list --serviceName chanlun-stock-service --json
```

如果你在 PowerShell 里看到“禁止运行脚本”或 `PSSecurityException`，不要继续改 CloudBase 命令本身，直接改用下面任一写法：

```powershell
C:\Windows\System32\cmd.exe /c "tcb --env-id cloudbase-d9gplq92zc1d88ee6 cloudrun list --serviceName chanlun-stock-service --json"
```

```powershell
& "C:\Users\58231\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.16.0-win-x64\tcb.cmd" --env-id cloudbase-d9gplq92zc1d88ee6 cloudrun list --serviceName chanlun-stock-service --json
```

3. 如果你只想先验证命令链路，不跑本地 Docker 构建：

```powershell
bin\deploy_service.bat --env-id cloudbase-d9gplq92zc1d88ee6 --service-name chanlun-stock-service --skip-local-build --dry-run
```

4. 如果服务已经存在，且你本机 Docker 可用，执行真实发布：

```powershell
bin\deploy_service.bat --env-id cloudbase-d9gplq92zc1d88ee6 --service-name chanlun-stock-service
```

5. 如果服务已经存在，但你当前机器还没装 Docker，只想先验证云端发布命令拼装：

```powershell
bin\deploy_service.bat --env-id cloudbase-d9gplq92zc1d88ee6 --service-name chanlun-stock-service --skip-local-build
```

说明：

1. 第 2 步如果返回的 `ServerList` 为空，说明控制台里还没创建 `chanlun-stock-service`。
2. 当前这台机器上脚本会自动走新版 `cloudrun` 命令，不需要手工改 CLI 语法。
3. 新版 `cloudrun deploy` 不会在命令行里直接更新运行时环境变量，所以 `CLOUDBASE_ENV_ID`、`CLOUDBASE_REGION`、`CLOUDBASE_APIKEY` 最好也同步配到控制台服务环境变量里。

## 首次建服 Checklist

如果这是第一次在 CloudBase Run 上落这个服务，先在控制台按下面最小集合创建一次：

| 控制台字段 | 推荐值 |
| --- | --- |
| 环境 | `CLOUDBASE_ENV_ID` 对应环境 |
| 服务名 | `chanlun-stock-service`，或与你本地 `--service-name` 一致 |
| 部署方式 | Dockerfile / 源码构建 |
| 代码目录 | 当前仓库根目录 |
| Dockerfile | 仓库里的 `Dockerfile` |
| 容器端口 | `8000` |
| CPU | `0.5` |
| 内存 | `1 GB` |
| 最小副本数 | `0` |
| 最大副本数 | `2` |
| 必填环境变量 | `CLOUDBASE_ENV_ID`、`CLOUDBASE_REGION`、`CLOUDBASE_APIKEY` |

1. 进入 `https://console.cloud.tencent.com/tcbr`，切到目标环境 `CLOUDBASE_ENV_ID`。
2. 新建服务，服务名填写 `chanlun-stock-service`，或者与你本地 `--service-name` 保持一致。
3. 部署方式选 Dockerfile / 源码构建，代码目录指向当前仓库根目录，Dockerfile 选仓库里的 `Dockerfile`。
4. 容器端口填 `8000`。
5. 计算规格先用 `CPU 0.5`、`内存 1 GB`。
6. 副本数先用 `最小 0`、`最大 2`。
7. 环境变量至少补：`CLOUDBASE_ENV_ID`、`CLOUDBASE_REGION`、`CLOUDBASE_APIKEY`。
8. 首次创建完成后，本地先执行一次服务查询，确认服务已存在。新版 CLI 可用：`tcb --env-id ENV_ID cloudrun list --serviceName SERVICE_NAME --json`。
9. 然后再执行：`bin\deploy_service.bat --service-name chanlun-stock-service`。

如果你不想在控制台手填运行时环境变量，也可以只把服务先创建出来，然后继续使用本地脚本在每次发布时通过 `--envParams` 注入。

## 适用边界

当前这条链路基于官方 CloudBase CLI。旧版本主要使用 `tcb run deploy`，新版本主要使用 `tcb cloudrun deploy`。

因此它的边界很明确：

1. 适用于“服务已经在腾讯云控制台创建过一次”的后续版本发布。
2. 适用于从本地代码目录重新构建并发布容器版本。
3. 首次建服仍建议在控制台完成，但当前脚本会先自动检查服务是否存在，并给出明确 bootstrap 提示，而不是直接在 `run deploy` 阶段模糊失败。

这是当前最稳妥的选择，因为公开 Python SDK 侧更容易稳定拿到的是查询能力，而 CloudBase CLI 已明确提供容器服务部署命令。

## 先决条件

### 1. 安装 CloudBase CLI

```powershell
npm i -g @cloudbase/cli
```

如果网络较慢，可使用腾讯云 npm 镜像：

```powershell
npm i -g @cloudbase/cli --registry=http://mirrors.cloud.tencent.com/npm/
```

### 2. 登录 CloudBase CLI

```powershell
tcb login
```

无头环境也可以使用设备码登录；如果要走密钥登录：

```powershell
tcb login --key
```

### 2.1 Windows PowerShell 执行策略说明

如果你在 PowerShell 里直接输入 `tcb ...`，系统可能优先命中 `tcb.ps1`，然后被本机执行策略拦住，报错类似：

- `PSSecurityException`
- `因为在此系统上禁止运行脚本`

这种情况不是 CLI 损坏，也不是登录失效，优先用下面两种方式之一：

```powershell
C:\Windows\System32\cmd.exe /c "tcb login"
```

```powershell
& "C:\Users\58231\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.16.0-win-x64\tcb.cmd" login
```

同理，后续的 `cloudrun list`、`cloudrun deploy` 也都可以套这两种写法。

### 3. 在控制台先创建一次服务

当前脚本调用的是 CloudBase CLI 的更新链路，目标服务首次仍需要先创建一次，例如：

- `chanlun-stock-service`

首次服务创建建议直接在 CloudBase 控制台完成，后续版本全部走本地脚本更新。

如果你直接运行发布脚本而服务不存在，脚本现在会打印：

1. 缺失的服务名和环境 ID
2. 控制台入口 URL
3. 建议的容器端口、CPU、内存、副本数
4. 用于复核的服务查询命令

### 4. 本地 Docker 可用

脚本默认会先执行一次本地 `docker build`，作为发布前校验。

如果当前机器只想直接触发云端发布，可以加：

```powershell
--skip-local-build
```

## 推荐环境变量

建议在本地终端先准备这些变量：

```powershell
$env:CLOUDBASE_ENV_ID = "your-env-id"
$env:CLOUDBASE_REGION = "ap-guangzhou"
$env:CLOUDBASE_APIKEY = "your-cloudbase-admin-api-key"
```

说明：

1. `CLOUDBASE_ENV_ID` 用于部署目标环境，也会注入容器运行时。
2. `CLOUDBASE_REGION` 会注入容器运行时。
3. `CLOUDBASE_APIKEY` 会注入容器运行时，供 API 内部复用现有 CloudBase 发布链路。

## 一键发布命令

### 直接用 bat 入口

```powershell
bin\deploy_service.bat --service-name chanlun-stock-service
```

如果服务还没创建，这条命令会先停在“服务不存在”检查，并打印首次建服需要填的参数。

如果环境变量还没设置全，也可以显式传：

```powershell
bin\deploy_service.bat --env-id your-env-id --service-name chanlun-stock-service --api-key your-cloudbase-admin-api-key
```

### 直接调用 Python 脚本

```powershell
& .\.venv\Scripts\python.exe scripts\deploy_tencent_container_service.py --env-id your-env-id --service-name chanlun-stock-service --api-key your-cloudbase-admin-api-key
```

## 首次建服后的冒烟检查

建议第一次把服务建出来之后，按下面顺序做一次最小验收：

1. 先确认服务已经能被 CLI 查到：

```powershell
tcb --env-id your-env-id cloudrun list --serviceName chanlun-stock-service --json
```

预期结果：

- 返回 JSON，而不是报“服务不存在”或鉴权失败。
- `data` 字段里能看到 `chanlun-stock-service`。

2. 再执行一次本地 dry-run，确认发布命令参数拼装正确：

```powershell
bin\deploy_service.bat --env-id your-env-id --service-name chanlun-stock-service --dry-run
```

预期结果：

- 能打印 `docker build ...` 命令。
- 能打印服务查询命令。
- 能打印部署命令。
- 不应真的开始上传或发布。

3. 然后执行一次真实发布：

```powershell
bin\deploy_service.bat --env-id your-env-id --service-name chanlun-stock-service
```

预期结果：

- 本地 Docker 构建成功。
- 服务存在性检查通过。
- 部署命令成功结束，没有停在缺服务提示。

4. 发布完成后，在服务域名后追加 `/healthz` 做最小健康检查，预期应返回健康状态。

预期结果：

- 返回 `200`。
- 响应体应体现服务可用，而不是网关 404、容器启动失败或超时。

5. 如果只是验证服务启动，不想立即跑全持仓任务，先只检查 API 入口是否可访问，再进入下一步小程序联调。

预期结果：

- API 根域名可访问。
- 至少 `/healthz` 正常。
- 后续再做小程序触发或定时任务联调。

如果第 1 步能查到服务，但第 3 步失败，优先检查：

1. CloudBase CLI 是否已登录且登录态仍有效。
2. 控制台中的服务名是否和本地 `--service-name` 完全一致。
3. `CLOUDBASE_APIKEY` 是否已配置且可用于容器内后续 CloudBase 发布链路。
4. Dockerfile 是否仍位于仓库根目录，且服务端口仍为 `8000`。

## 部署成功后的最小 API 验收

容器部署成功只说明镜像能启动；最小可用验收应至少覆盖：

1. 进程存活
2. API 路由可访问
3. 后台 job 能创建
4. job 状态可查询

当前服务对外接口最少有这几个：

1. `GET /healthz`
2. `POST /jobs/publish-refresh`
3. `POST /jobs/technical-refresh`
4. `GET /jobs/{job_id}`
5. `GET /jobs`

下面这组步骤建议作为第一次部署后的最小验收。

### 1. 健康检查

浏览器或命令行访问：

```powershell
Invoke-WebRequest -UseBasicParsing https://<your-service-domain>/healthz
```

如果当前服务只有 HTTP，则改为：

```powershell
Invoke-WebRequest -UseBasicParsing http://<your-service-domain>/healthz
```

预期结果：

1. HTTP 状态码是 `200`
2. 返回 JSON
3. JSON 里至少应包含：
	 - `status: ok`
	 - `holdings_file`

一个正常响应大致会像这样：

```json
{
	"status": "ok",
	"time": "2026-06-28T19:30:00+08:00",
	"root": "/app",
	"holdings_file": "/app/config/stock_holdings.json"
}
```

### 2. 查询当前 job 列表

```powershell
Invoke-WebRequest -UseBasicParsing https://<your-service-domain>/jobs
```

预期结果：

1. 返回 `200`
2. 响应体是 JSON 数组
3. 第一次部署后数组为空也正常

### 3. 提交一个最轻量 technical-refresh job

第一次不要直接跑全持仓，也不要一上来开上传。先提交一个最小 payload，只跑 1 只股票、2 个级别，并关闭上传：

```powershell
$body = @{
	market = "HK"
	symbols = @("03690")
	limit = 1
	tech_timeframes = @("30m", "5m")
	skip_build = $true
	skip_upload = $true
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing \
	-Uri https://<your-service-domain>/jobs/technical-refresh \
	-Method POST \
	-ContentType "application/json" \
	-Body $body
```

预期结果：

1. 返回 `200`
2. 响应 JSON 里有：
	 - `job_id`
	 - `kind: technical_refresh`
	 - `status: queued`

### 4. 轮询 job 状态

把上一步返回的 `job_id` 代入：

```powershell
Invoke-WebRequest -UseBasicParsing https://<your-service-domain>/jobs/<job_id>
```

预期状态流转：

1. `queued`
2. `running`
3. `succeeded` 或 `failed`

如果成功，响应里的 `result` 应至少包含：

1. `security_count`
2. `symbols`
3. `generated_timeframes`
4. `manifest_path`

如果失败，重点看：

1. `error` 字段里的 Python traceback
2. 控制台运行日志
3. 是否是数据源访问、CloudBase key、文件路径、依赖包问题

### 5. 再做一次最小 publish-refresh 验证

当 technical-refresh 成功后，再验一次发布链路，但仍建议先不上传。

注意：第一次 `publish-refresh` 不能使用 `skip_regenerate=true`。原因是 `technical-refresh` 只生成技术分析结果，不会生成 `base.json` / `fund.json`；而 publish bundle 在构建 `summary.json` / `detail.json` 时需要这两个文件。

第一次建议显式打开 regeneration，并强制补齐基础与资金面文件：

```powershell
$body = @{
	market = "HK"
	symbols = @("03690")
	limit = 1
	skip_regenerate = $false
	skip_gen_base = $false
	skip_gen_fund = $false
	skip_upload = $true
	publish_timeframes = @("30m", "5m")
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing \
	-Uri https://<your-service-domain>/jobs/publish-refresh \
	-Method POST \
	-ContentType "application/json" \
	-Body $body
```

这一步的目标不是刷新数据，而是确认：

1. 后台 publish job 能创建
2. `base.json` / `fund.json` / 技术结果能一起补齐
3. 构建 publish bundle 的代码路径正常
3. 不上传时也能顺利收敛到 `succeeded`

### 6. 再决定是否打开真实上传

只有在下面 3 项都通过后，再打开真实上传更稳：

1. `/healthz` 正常
2. `technical-refresh` 成功
3. `publish-refresh` 在 `skip_upload=true` 下成功

这样做能把“服务启动问题”和“CloudBase 上传问题”分开，不会把第一次验收混成一团。

## 小程序联调检查清单

当真实 `publish-refresh` 已经成功后，下一步不要立刻怀疑小程序页面代码，先按下面顺序确认“云端发布物”本身已经可被前端消费。

这部分路径和字段约定以 [docs/miniapp-cloud-publish-schema.md](c:/sandbox/sinba/stock/docs/miniapp-cloud-publish-schema.md) 为准。

### 1. 先确认 latest 索引已经更新

先到 CloudBase 云存储里确认下面这个对象已经存在，且更新时间就是刚刚那次成功上传：

- `miniapp-publish/latest/index.json`

最少核对这几个字段：

1. `schema_version`
2. `generated_at`
3. `counts`
4. `groups`
5. `stocks`

预期结果：

1. `generated_at` 明显晚于上一次发布
2. `stocks` 数组非空
3. 刚刚验证过的股票，例如 `03690`，能在 `stocks` 数组里找到

如果这一步就不对，优先排查上传链路，而不是小程序页面。

### 2. 再确认单只股票入口文件齐全

以 `03690` 为例，至少应能在云存储里看到：

- `miniapp-publish/latest/stocks/03690/summary.json`
- `miniapp-publish/latest/stocks/03690/detail.json`

如果你的小程序首页依赖封面图，再继续确认 `index.json` 或 `summary.json` 里引用的图表路径所对应的对象也已存在，例如：

- `miniapp-publish/latest/stocks/03690/charts/...`

预期结果：

1. `summary.json` 存在且可读取
2. `detail.json` 存在且可读取
3. JSON 里引用的图表文件真实存在，而不是只有字段没有文件

### 3. 校对 index.json 里的相对路径语义

当前发布层 JSON 里通常保存的是相对 `miniapp-publish/latest/` 的相对路径，而不是完整 CDN URL。

例如 `index.json` 里的单只股票记录通常应包含：

1. `summary: stocks/03690/summary.json`
2. `detail: stocks/03690/detail.json`
3. `cover_chart: stocks/03690/charts/...`

小程序侧联调时要特别确认两件事：

1. 不要把 `latest/` 或 `miniapp-publish/latest/` 重复拼两次
2. 不要把相对 JSON 路径当成 HTTP 页面路由去请求

如果页面报 404，但云存储里文件明明存在，十有八九是这里的前缀拼接错了。

### 4. 首页列表页最小验收

首页列表页最少只依赖 `index.json` 加若干 `summary.json` 就应该能起页面。

建议按下面顺序核对：

1. 小程序先成功读取 `miniapp-publish/latest/index.json`
2. 页面能渲染 `stocks[].symbol`、`stocks[].name`、`stocks[].market`
3. 点击一只股票时，能根据 `summary` 或 `detail` 路径继续请求下一级 JSON

如果首页只想做最小联通验证，先别要求所有图都显示出来，先确认：

1. 列表能出来
2. 股票能点进去
3. 详情接口数据能读到

### 5. 详情页最小验收

详情页建议至少验证这 4 类内容：

1. 基本标识：`symbol`、`name`、`market`
2. 更新时间：`updated_at`
3. 摘要卡片：例如基本面、技术面、操作建议摘要
4. 图表资源：封面图或分级别结构图

如果 `summary.json` 正常、`detail.json` 正常，但图片不显示，优先检查：

1. 图表路径是否和 JSON 中一致
2. 小程序是否把云存储路径正确转换成可访问资源地址
3. 是否命中了旧缓存

### 6. 分组页最小验收

如果小程序有 A 股 / H 股 / 组合分组页，再补一轮分组文件检查：

1. `miniapp-publish/latest/groups/a_share.json`
2. `miniapp-publish/latest/groups/h_share.json`
3. `miniapp-publish/latest/groups/portfolio.json`

预期结果：

1. 分组文件存在
2. 分组内股票数量与 `index.json.counts` 大体一致
3. 分组页点击后仍能回到同一套 `summary/detail` 路径

### 7. 最常见的 4 个联调错位

1. 后端已经成功上传，但小程序还在读旧前缀，不是 `miniapp-publish/latest/`。
2. 小程序把 JSON 里的相对路径再错误拼上一级目录，导致出现重复 `latest/latest/...`。
3. 图表文件已上传，但页面端只接受固定后缀，而实际当前股票落的是另一种图表后缀。
4. 云存储对象已更新，但小程序本地缓存或 CDN 缓存还没刷新，看到的是旧数据。

### 8. 建议的联调顺序

第一次联调不要同时查页面、接口、上传日志。按这个顺序最快：

1. 先确认 `publish-refresh` job 是 `succeeded`
2. 再确认 `miniapp-publish/latest/index.json` 已更新
3. 再确认目标股票的 `summary.json`、`detail.json`、图表对象存在
4. 再让小程序只读 `index.json` 做列表页联通
5. 最后再接详情页和图表展示

这样可以把问题收敛到“上传层”还是“页面消费层”，不会混在一起。

## 小程序最小读取顺序

下面这套顺序不是抽象 schema，而是按当前真实发布包字段整理的最小调用链。以当前 `latest/index.json` 和 `stocks/03690/*.json` 为例，小程序侧可以直接照这个顺序接。

### 1. 首屏只读 index.json

首页第一次进入时，只请求一个文件：

- `miniapp-publish/latest/index.json`

当前 `index.json` 里每只股票最少已经给出这些字段：

1. `symbol`
2. `name`
3. `market`
4. `updated_at`
5. `summary`
6. `detail`
7. `cover_chart`
8. `technical_score`
9. `technical_rating`
10. `technical_bias`

列表页建议直接使用：

1. `name` + `symbol` 作为标题
2. `market` 作为市场标签
3. `technical_rating` / `technical_score` / `technical_bias` 作为首页技术卡片摘要
4. `updated_at` 作为更新时间

这样首页不需要先逐只再拉 `summary.json`，只靠 `index.json` 就能把持仓列表先渲染出来。

### 2. 点击列表项后，再读 summary.json

用户点击某只股票后，第二个请求建议先读 `index.json` 里给出的 `summary` 路径，例如：

- `stocks/03690/summary.json`

当前 `summary.json` 适合承接“详情页顶部摘要区”，常用字段是：

1. `comment`
2. `cards.fundamental.score`
3. `cards.fundamental.rating`
4. `cards.fundamental.summary`
5. `cards.technical.timeframe`
6. `cards.technical.operation_level`
7. `cards.technical.score`
8. `cards.technical.rating`
9. `cards.technical.bias`
10. `cards.technical.conclusion`
11. `cards.technical.suggestion`
12. `cards.technical.signal_descriptions`
13. `cards.technical.technical_focus_lines`

详情页顶部建议先只渲染这几块：

1. 一句话结论：`cards.technical.conclusion`
2. 操作建议：`cards.technical.suggestion`
3. 风险提示：`comment`
4. 基本面摘要：`cards.fundamental.summary`
5. 最近信号：`cards.technical.latest_signal_summary.lines`

这样第二屏的主要文字信息就够了，不需要一开始把完整 `detail.json` 全部铺出来。

### 3. 需要完整分段内容时，再读 detail.json

如果用户进入完整详情页，或者点击“展开更多”，再读取 `index.json` 里给出的 `detail` 路径，例如：

- `stocks/03690/detail.json`

当前 `detail.json` 适合做“完整详情页”，建议按下面映射：

1. 页面标题：`headline.title`
2. 页面副标题：`headline.subtitle`
3. 顶部摘要：`overview.summary`
4. 顶部 bullet：`overview.bullets`
5. 主体内容：`sections`

`sections` 当前已经按主题拆段，小程序侧建议不要硬编码位置，而是按 `key` 分发：

1. `key = fundamental` 时渲染基本面 section
2. `key = technical` 时渲染技术面 section
3. 其他 section 如果后续新增，页面可以先按通用卡片兜底

这样后端后续加新 section 时，前端不用立刻改接口协议。

### 4. 图表资源直接取 cover_chart 和 charts

当前 `index.json` 里的 `cover_chart` 已经能给首页或详情页顶部直接用，例如：

- `stocks/03690/charts/30m.svg`

并且实际图表目录下当前已经是：

1. `day.svg`
2. `30m.svg`
3. `5m.svg`

这和旧文档里早期写过的 `jpg/png` 不同。当前联调时应按真实发布包处理为 `svg`。

如果小程序图像组件不能直接满足当前 `svg` 展示要求，就不要先改后端路径，先确认前端展示层是否需要：

1. 增加 `svg` 渲染方案
2. 或在发布层补一条面向小程序的位图转换链路

### 5. 推荐的最小前端请求链

第一次联通时，前端只需要 3 步：

1. 启动页读取 `miniapp-publish/latest/index.json`
2. 点击股票后读取 `stocks/<symbol>/summary.json`
3. 进入完整详情后读取 `stocks/<symbol>/detail.json`

不要一开始就：

1. 首页逐只并发请求全部 `summary.json`
2. 首页直接加载所有图表
3. 首次进入就把 `detail.json` 全量拉完

先把首屏链路做轻，联调会稳定很多。

### 6. 当前最稳的字段使用建议

如果你想先做最小页面，优先使用这些相对稳定的字段：

1. 列表页：`symbol`、`name`、`market`、`updated_at`、`technical_score`、`technical_rating`、`technical_bias`
2. 摘要页：`comment`、`cards.fundamental.summary`、`cards.technical.conclusion`、`cards.technical.suggestion`
3. 详情页：`headline`、`overview`、`sections`

像 `signal_catalog`、`same_level_decomposition`、`precision_entry` 这类结构更深的字段，建议放到第二阶段，再做更细的专业化展示。

## 小程序页面数据映射表

这一节的目标不是重新解释协议，而是把“页面上一个元素应该读哪个字段”直接列出来，方便前端按表接线。

### 1. 列表页映射

数据源：`miniapp-publish/latest/index.json`

| 页面元素 | 推荐字段 | 说明 |
| --- | --- | --- |
| 股票主标题 | `stocks[].name` | 例如“美团” |
| 股票副标题 | `stocks[].symbol` | 例如 `03690` |
| 市场标签 | `stocks[].market` | 当前值如 `CN`、`HK` |
| 技术评分 | `stocks[].technical_score` | 例如 `74` |
| 技术评级 | `stocks[].technical_rating` | 例如 `A`、`B`、`C` |
| 技术倾向 | `stocks[].technical_bias` | 例如“偏多”“偏空”“偏弱” |
| 更新时间 | `stocks[].updated_at` | 建议前端格式化显示 |
| 点击跳转参数 | `stocks[].summary`、`stocks[].detail` | 作为后续 JSON 请求路径 |
| 列表封面图 | `stocks[].cover_chart` | 当前真实产物是 `svg` 路径 |

最小列表页建议只展示：

1. `name`
2. `symbol`
3. `market`
4. `technical_rating`
5. `technical_score`
6. `technical_bias`

### 2. 详情页顶部摘要映射

数据源：`stocks/<symbol>/summary.json`

| 页面元素 | 推荐字段 | 说明 |
| --- | --- | --- |
| 股票名称 | `name` | 可与 `symbol` 拼成标题 |
| 股票代码 | `symbol` | 例如 `03690` |
| 市场标签 | `market` | 例如 `HK` |
| 更新时间 | `updated_at` | 详情页顶部时间 |
| 风险提示 | `comment` | 没值时前端可隐藏整块 |
| 基本面分数 | `cards.fundamental.score` | 例如 `23.18` |
| 基本面评级 | `cards.fundamental.rating` | 例如 `D` |
| 基本面摘要 | `cards.fundamental.summary` | 一段简述 |
| 技术级别 | `cards.technical.timeframe_label` | 例如 `30M` |
| 操作级别 | `cards.technical.operation_level` | 例如 `30M` |
| 技术分数 | `cards.technical.score` | 例如 `74` |
| 技术评级 | `cards.technical.rating` | 例如 `B` |
| 技术倾向 | `cards.technical.bias` | 例如“偏空” |
| 一句话结论 | `cards.technical.conclusion` | 顶部最重要文案 |
| 操作建议 | `cards.technical.suggestion` | 顶部第二重要文案 |
| 最近信号摘要 | `cards.technical.latest_signal_summary.lines` | 建议按列表渲染 |
| 走势重点 | `cards.technical.technical_focus_lines` | 建议按 bullet 渲染 |

最小摘要页建议只展示：

1. `cards.technical.conclusion`
2. `cards.technical.suggestion`
3. `comment`
4. `cards.fundamental.summary`

### 3. 详情页完整内容映射

数据源：`stocks/<symbol>/detail.json`

| 页面元素 | 推荐字段 | 说明 |
| --- | --- | --- |
| 页面大标题 | `headline.title` | 例如“美团 03690” |
| 页面副标题 | `headline.subtitle` | 当前如“三轴综合观察” |
| 顶部摘要文案 | `overview.summary` | 一句话总览 |
| 顶部 bullet 列表 | `overview.bullets` | 建议按列表渲染 |
| 主体 section 列表 | `sections` | 按 `key` 分发渲染 |

`sections` 建议按下面方式处理：

| section.key | 页面块 | 优先字段 |
| --- | --- | --- |
| `fundamental` | 基本面卡片 | `title`、`rating`、`score`、`summary`、`risks`、`follow_ups` |
| `technical` | 技术面卡片 | `title`、`timeframe`、`rating`、`score`、`bias`、`conclusion`、`suggestion` |

如果后续出现新的 `section.key`，前端先按通用文本块兜底：

1. 显示 `title`
2. 如果有 `summary` 就显示 `summary`
3. 如果有数组字段就按列表渲染

### 4. 图表展示映射

当前图表路径有两种直接来源：

1. 列表或详情顶部封面：`index.json` 中的 `cover_chart`
2. 股票图表目录：`stocks/<symbol>/charts/`

以 `03690` 为例，当前实际文件是：

1. `stocks/03690/charts/day.svg`
2. `stocks/03690/charts/30m.svg`
3. `stocks/03690/charts/5m.svg`

建议页面映射为：

| 页面元素 | 推荐来源 |
| --- | --- |
| 列表卡片封面 | `stocks[].cover_chart` |
| 详情页默认主图 | `stocks[].cover_chart` |
| 日线图 Tab | `stocks/<symbol>/charts/day.svg` |
| 30 分钟图 Tab | `stocks/<symbol>/charts/30m.svg` |
| 5 分钟图 Tab | `stocks/<symbol>/charts/5m.svg` |

### 5. 分组页映射

数据源：

1. `miniapp-publish/latest/groups/a_share.json`
2. `miniapp-publish/latest/groups/h_share.json`
3. `miniapp-publish/latest/groups/portfolio.json`

分组页建议复用列表页组件，不单独发明新字段。最稳的做法是：

1. 分组文件负责给出分组后的股票集合
2. 列表项渲染仍复用 `index.json` 那套字段语义

### 6. 前端字段使用优先级

如果小程序页面要分阶段交付，建议优先级如下：

1. 第一阶段只接 `index.json`，先把列表跑通
2. 第二阶段接 `summary.json`，把详情顶部跑通
3. 第三阶段接 `detail.json` 的 `sections`，把完整详情跑通
4. 第四阶段再消费深层专业字段，例如 `signal_catalog`、`precision_entry`、`same_level_decomposition`

## 小程序前端伪代码与请求流程

这一节的目标是把上面的字段映射变成一套可直接照搬的前端请求顺序。这里不绑定具体状态管理库，重点只放在路径拼接和页面加载顺序。

### 1. 先约定一个发布根路径

前端不要把完整对象路径写死在每个页面里，先收成一个发布根路径，例如：

```ts
const PUBLISH_ROOT = 'miniapp-publish/latest/'
```

然后统一通过一个函数拼接对象路径：

```ts
function resolvePublishPath(relativePath: string): string {
	return `${PUBLISH_ROOT}${relativePath}`
}
```

这样可以避免后面出现：

1. 少拼 `latest/`
2. 多拼一层 `latest/latest/`
3. 页面各自维护不同前缀

### 2. 首页加载伪代码

首页进入时只读一次 `index.json`：

```ts
type StockIndexItem = {
	symbol: string
	name: string
	market: 'CN' | 'HK'
	updated_at: string
	summary: string
	detail: string
	cover_chart?: string
	technical_score?: number
	technical_rating?: string
	technical_bias?: string
}

type PublishIndex = {
	generated_at: string
	stocks: StockIndexItem[]
}

async function loadIndex(): Promise<PublishIndex> {
	return await fetchJson(resolvePublishPath('index.json'))
}

async function onPortfolioPageLoad() {
	setPageState({ loading: true, error: null })
	try {
		const index = await loadIndex()
		setPageState({
			loading: false,
			generatedAt: index.generated_at,
			stocks: index.stocks,
		})
	} catch (error) {
		setPageState({ loading: false, error: 'index.json 加载失败' })
	}
}
```

首页渲染时直接使用：

1. `stock.name`
2. `stock.symbol`
3. `stock.market`
4. `stock.technical_rating`
5. `stock.technical_score`
6. `stock.technical_bias`

### 3. 列表点击跳转伪代码

点击列表项时，不要重新推导路径，直接把 `index.json` 里的 `summary`、`detail`、`cover_chart` 透传给详情页：

```ts
function onTapStock(stock: StockIndexItem) {
	navigateToDetailPage({
		symbol: stock.symbol,
		name: stock.name,
		market: stock.market,
		summaryPath: stock.summary,
		detailPath: stock.detail,
		coverChartPath: stock.cover_chart ?? null,
	})
}
```

这样做的好处是：

1. 详情页不需要自己再拼 `stocks/<symbol>/summary.json`
2. 后端以后如果改了目录组织，前端只需要重新读 `index.json`

### 4. 详情页顶部摘要加载伪代码

详情页先读 `summary.json`，优先把最关键的结论展示出来：

```ts
type SummaryPayload = {
	symbol: string
	name: string
	market: 'CN' | 'HK'
	updated_at: string
	comment?: string | null
	cards?: {
		fundamental?: {
			score?: number
			rating?: string
			summary?: string
		}
		technical?: {
			timeframe_label?: string
			operation_level?: string
			score?: number
			rating?: string
			bias?: string
			conclusion?: string
			suggestion?: string
			latest_signal_summary?: {
				lines?: string[]
			}
			technical_focus_lines?: string[]
		}
	}
}

async function loadSummary(summaryPath: string): Promise<SummaryPayload> {
	return await fetchJson(resolvePublishPath(summaryPath))
}

async function onDetailPageLoad(routeParams: { summaryPath: string; detailPath: string; coverChartPath?: string | null }) {
	setDetailState({ loadingSummary: true, loadingDetail: false, error: null })
	try {
		const summary = await loadSummary(routeParams.summaryPath)
		setDetailState({
			loadingSummary: false,
			summary,
			coverChartPath: routeParams.coverChartPath ?? null,
		})
	} catch (error) {
		setDetailState({ loadingSummary: false, error: 'summary.json 加载失败' })
	}
}
```

详情页首屏建议先只渲染：

1. `summary.cards?.technical?.conclusion`
2. `summary.cards?.technical?.suggestion`
3. `summary.comment`
4. `summary.cards?.fundamental?.summary`

### 5. 用户展开更多时，再读 detail.json

完整详情不要和首屏抢首包时间，建议在用户进入详情页后延迟加载，或者点击“展开更多”时再读：

```ts
type DetailSection = {
	key: string
	title?: string
	summary?: string
	[key: string]: unknown
}

type DetailPayload = {
	headline?: {
		title?: string
		subtitle?: string
	}
	overview?: {
		summary?: string
		bullets?: string[]
	}
	sections?: DetailSection[]
}

async function loadDetail(detailPath: string): Promise<DetailPayload> {
	return await fetchJson(resolvePublishPath(detailPath))
}

async function onExpandDetail(detailPath: string) {
	setDetailState({ loadingDetail: true })
	try {
		const detail = await loadDetail(detailPath)
		setDetailState({ loadingDetail: false, detail })
	} catch (error) {
		setDetailState({ loadingDetail: false, error: 'detail.json 加载失败' })
	}
}
```

渲染 `sections` 时建议按 `section.key` 分发：

```ts
function renderSection(section: DetailSection) {
	switch (section.key) {
		case 'fundamental':
			return renderFundamentalSection(section)
		case 'technical':
			return renderTechnicalSection(section)
		default:
			return renderGenericSection(section)
	}
}
```

### 6. 图表路径使用伪代码

封面图直接使用 `index.json` 里的 `cover_chart`，不要自己猜文件名：

```ts
function getCoverChartUrl(coverChartPath?: string | null): string | null {
	if (!coverChartPath) {
		return null
	}
	return resolvePublishPath(coverChartPath)
}
```

分时图 Tab 如果要直接拼，可以只在当前目录约定稳定后使用：

```ts
function getTimeframeChartPath(symbol: string, timeframe: 'day' | '30m' | '5m'): string {
	return resolvePublishPath(`stocks/${symbol}/charts/${timeframe}.svg`)
}
```

注意：当前真实产物是 `svg`。如果小程序端当前图像展示方案不支持 `svg`，先把文本链路跑通，再单独处理图表渲染，不要把两个问题绑在一起查。

### 7. 建议的页面状态流转

为了联调时更容易定位问题，建议页面状态拆开：

1. `loadingIndex`
2. `loadingSummary`
3. `loadingDetail`
4. `errorIndex`
5. `errorSummary`
6. `errorDetail`

这样你一眼就能看出失败点是在：

1. 顶层索引
2. 摘要 JSON
3. 完整详情 JSON

而不是都显示成一个笼统的“加载失败”。

### 8. 最小 fetchJson 抽象

如果前端同事要一个最小工具函数，建议至少保留路径和错误信息：

```ts
async function fetchJson<T>(objectPath: string): Promise<T> {
	const response = await fetch(objectPath)
	if (!response.ok) {
		throw new Error(`request failed: ${response.status} ${objectPath}`)
	}
	return (await response.json()) as T
}
```

如果你们实际不是用 HTTP `fetch`，而是用 CloudBase 存储下载接口，也建议保持这个函数签名不变，把底层适配隐藏在 `fetchJson` 里。这样页面层不需要知道底下是 HTTP 地址还是云存储文件下载。

## 常用参数

- `--skip-local-build`: 跳过本地 Docker 构建校验
- `--dry-run`: 只打印将执行的命令
- `--container-port 8000`: 服务监听端口
- `--cpu 0.5 --mem 1`: 容器规格
- `--min-num 0 --max-num 2`: 副本上下限
- `--set-env KEY=VALUE`: 额外注入运行时环境变量

示例：

```powershell
bin\deploy_service.bat --service-name chanlun-stock-service --cpu 1 --mem 2 --max-num 4 --set-env JOB_STORE=memory
```

## 当前命令实际做了什么

当前脚本会按顺序执行两步：

1. 本地执行一次 `docker build -f Dockerfile -t chanlun-stock-service:local .`
2. 调用官方 CLI 检查服务是否存在：

```powershell
tcb --env-id ENV_ID cloudrun list --serviceName SERVICE_NAME --json
```

3. 如果服务存在，再调用官方 CLI：

```powershell
tcb --env-id ENV_ID cloudrun deploy -s SERVICE_NAME --port 8000 --source REPO_ROOT --force
```

如果本机装的是旧版 CLI，脚本会自动回退到旧 `run` 口径，不需要手工改命令。

说明：新版 CLI 的 `cloudrun deploy` 不会像旧版 `run deploy` 一样在命令行里直接更新运行时环境变量，因此 `CLOUDBASE_ENV_ID`、`CLOUDBASE_REGION`、`CLOUDBASE_APIKEY` 更适合预先配置在控制台的服务环境变量中。

## 已知限制

1. 当前脚本仍不直接负责“首次创建 CloudBase Run 服务”；它只会在缺失时给出精确 bootstrap 提示。
2. `--set-env` 通过 `--envParams` 透传，值里不应包含 `&`。
3. 如果要把更复杂的密钥体系放进运行时，长期更推荐在控制台侧直接维护服务环境变量，而不是每次从本地命令注入。

## 常见失败场景

| 场景 | 现象 | 优先处理 |
| --- | --- | --- |
| 服务不存在 | 脚本在发布前直接提示缺少服务 | 先去控制台按上面的 Checklist 创建一次服务，再重跑发布命令 |
| CLI 未登录或登录态失效 | 服务查询 / 部署命令返回鉴权失败 | 重新执行 `tcb login`，或使用 `tcb login --key` |
| 服务名不一致 | 控制台明明有服务，但本地脚本仍提示查不到 | 核对控制台服务名和本地 `--service-name` 是否完全一致 |
| Docker 构建失败 | 发布前卡在本地 `docker build` | 先单独执行 `docker build -f Dockerfile -t chanlun-stock-service:local .` 看具体报错 |
| `/healthz` 返回 404 | 服务能发布，但健康检查不是 200 | 先确认服务实际启动的是当前 FastAPI 镜像，且容器端口仍是 `8000` |
| `/healthz` 超时或 5xx | 服务域名可访问，但响应超时或网关报错 | 优先看容器启动日志、依赖安装是否成功、运行时环境变量是否缺失 |
| 容器内后续发布失败 | API 服务起来了，但后续 CloudBase 上传链路报权限或 key 错误 | 核对 `CLOUDBASE_APIKEY` 是否已正确注入容器运行时 |
| `--set-env` 参数异常 | 发布命令在拼接环境变量时失败 | 检查 `KEY=VALUE` 里是否包含非法的 `&` |

如果第一次排查还不够，建议按这个顺序缩小范围：

1. 先跑服务查询命令，确认不是环境或服务名问题。
2. 再跑 `bin\deploy_service.bat --dry-run`，确认不是命令拼装问题。
3. 再单独跑 `docker build`，确认不是镜像构建问题。
4. 最后再看 `/healthz` 和容器日志，确认是不是运行时配置问题。
