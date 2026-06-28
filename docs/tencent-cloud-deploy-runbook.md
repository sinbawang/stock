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
