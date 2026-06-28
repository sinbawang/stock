# 微信小程序服务联调开发 Prompt

下面这段 prompt 可以直接发给负责微信小程序开发的 agent 或开发同学。它对应当前这套后端形态：

1. 小程序展示数据来自 CloudBase 云存储发布包 `miniapp-publish/latest/`
2. 小程序触发“刷新持仓分析”来自容器服务 API
3. 小程序需要读取并展示后台 job 状态 `queued` / `running` / `succeeded` / `failed`
4. 只要当前状态不是 `succeeded` 或 `failed`，刷新按钮就必须禁用，不能重复点击

```text
你现在要在当前微信小程序项目中实现“持仓分析展示 + 刷新持仓分析”能力。不要使用 WebView，不要接云数据库，不要新增云函数。优先遵循现有小程序项目结构和编码风格；如果项目还没搭起来，再补最小可运行骨架。

目标：
1. 从 CloudBase 云存储读取最新发布包，展示持仓分析页面。
2. 适配后端发布包字段变化，不要把前端写死成脆弱结构。
3. 在小程序中增加一个“刷新持仓分析”按钮，用来触发服务端重新生成并上传全持仓分析结果。
4. 小程序要实时读取后台 job 状态并展示：`queued`、`running`、`succeeded`、`failed`。
5. 只要当前 job 状态不是 `succeeded` 或 `failed`，刷新按钮必须禁用，不允许重复触发。

一、当前后端架构

当前系统有两类后端入口：

1. CloudBase 云存储发布包
   - 路径前缀：`miniapp-publish/latest/`
   - 顶层入口：`index.json`
   - 详情入口：`stocks/<symbol>/summary.json` 和 `stocks/<symbol>/detail.json`
   - 图表路径：`stocks/<symbol>/charts/day.svg`、`30m.svg`、`5m.svg`

2. 容器服务 API
   - `GET /healthz`
   - `GET /jobs`
   - `GET /jobs/{job_id}`
   - `POST /jobs/publish-refresh`
   - `POST /jobs/technical-refresh`

本次小程序只需要使用 `POST /jobs/publish-refresh` 触发“全持仓刷新并上传”，并用 `GET /jobs/{job_id}` / `GET /jobs` 读取状态。

二、当前数据入口约定

请在小程序里使用两个配置常量：

1. `INDEX_FILE_ID`
   - 例：`cloud://<env>.<bucket>/miniapp-publish/latest/index.json`
2. `SERVICE_BASE_URL`
   - 例：`https://<your-service-domain>`

其他发布包对象不要硬编码 fileID，而是从 `INDEX_FILE_ID` 推导前缀：

1. `FILE_ID_PREFIX = INDEX_FILE_ID.replace(/\/index\.json$/, '')`
2. 相对路径 `stocks/03690/summary.json` -> `${FILE_ID_PREFIX}/stocks/03690/summary.json`
3. 相对路径 `stocks/03690/detail.json` -> `${FILE_ID_PREFIX}/stocks/03690/detail.json`
4. 相对路径 `stocks/03690/charts/30m.svg` -> `${FILE_ID_PREFIX}/stocks/03690/charts/30m.svg`

三、当前真实发布包字段

1. `index.json`
   - `generated_at`
   - `counts`
   - `groups`
   - `stocks`
2. `stocks[]` 中每项至少有：
   - `symbol`
   - `name`
   - `market`
   - `updated_at`
   - `summary`
   - `detail`
   - `cover_chart`
   - `technical_score`
   - `technical_rating`
   - `technical_bias`
3. `summary.json` 当前重点字段：
   - `comment`
   - `cards.fundamental.summary`
   - `cards.technical.conclusion`
   - `cards.technical.suggestion`
   - `cards.technical.latest_signal_summary.lines`
   - `cards.technical.technical_focus_lines`
4. `detail.json` 当前重点字段：
   - `headline`
   - `overview`
   - `sections`

注意：

1. 当前图表真实产物是 `svg`，不是旧口径的 `jpg/png`
2. 前端要对字段缺失保持容错，不要假设 `cards`、`sections`、数组字段永远完整
3. 前端对 `sections` 要按 `section.key` 分发渲染，并对未知 `key` 做通用兜底

四、刷新按钮的业务定义

需要在小程序首页或持仓页头部增加一个主按钮：

1. 按钮文案默认：`刷新持仓分析`
2. 点击后触发服务端 `POST /jobs/publish-refresh`
3. 这次刷新是“全持仓刷新并上传”，不是单只股票刷新
4. 小程序要展示当前刷新 job 的状态与时间

按钮状态规则必须严格遵守：

1. 没有 job 时：按钮可点击
2. 当前 job 为 `succeeded`：按钮可点击
3. 当前 job 为 `failed`：按钮可点击
4. 当前 job 为 `queued`：按钮禁用
5. 当前 job 为 `running`：按钮禁用

换句话说：只要状态不是 `succeeded` 或 `failed`，按钮就不能再点。

五、刷新请求的接口约定

点击“刷新持仓分析”按钮时，调用：

1. `POST ${SERVICE_BASE_URL}/jobs/publish-refresh`

请求体使用下面这组默认值：

```json
{
  "market": "ALL",
  "latest_only": true,
  "skip_regenerate": false,
  "skip_build": false,
  "skip_upload": false,
  "skip_gen_base": false,
  "skip_gen_fund": false,
  "tech_timeframes": ["day", "30m", "5m"],
  "publish_timeframes": ["day", "30m", "5m"]
}
```

说明：

1. 不传 `symbols`，表示全持仓刷新
2. 不传 `limit`，表示不截断
3. `skip_upload` 必须是 `false`，因为小程序要消费上传后的最新发布包
4. `skip_gen_base` 和 `skip_gen_fund` 这里固定用 `false`，避免发布包构建依赖缺失

六、job 接口的真实返回模型

1. `POST /jobs/publish-refresh` 成功后返回：

```json
{
  "job_id": "<job-id>",
  "kind": "publish_refresh",
  "status": "queued",
  "created_at": "2026-06-28T20:30:00+08:00"
}
```

2. `GET /jobs/{job_id}` 返回：

```json
{
  "job_id": "<job-id>",
  "kind": "publish_refresh",
  "status": "running",
  "created_at": "2026-06-28T20:30:00+08:00",
  "started_at": "2026-06-28T20:30:03+08:00",
  "finished_at": null,
  "request": {},
  "result": null,
  "error": null
}
```

3. 终态只有两种：
   - `succeeded`
   - `failed`

4. 非终态只有两种：
   - `queued`
   - `running`

七、小程序端的状态机要求

请实现一个清晰的刷新状态机，不要只用一个 `loading` 布尔值糊过去。

至少维护这些状态：

1. `refreshJobId: string | null`
2. `refreshStatus: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed'`
3. `refreshCreatedAt: string | null`
4. `refreshStartedAt: string | null`
5. `refreshFinishedAt: string | null`
6. `refreshError: string | null`
7. `isRefreshButtonDisabled: boolean`

禁用逻辑必须统一收口成一个函数，例如：

```ts
function isTerminalRefreshStatus(status: string | null | undefined): boolean {
  return status === 'succeeded' || status === 'failed'
}

function canTriggerRefresh(status: string | null | undefined): boolean {
  if (!status || status === 'idle') {
    return true
  }
  return isTerminalRefreshStatus(status)
}
```

按钮禁用条件：

1. `queued` -> 禁用
2. `running` -> 禁用
3. 请求提交中 -> 禁用
4. 轮询中不影响，关键取决于当前状态是否终态

八、页面加载时如何恢复 job 状态

页面进入时需要恢复当前刷新状态，避免用户杀掉页面后重新打开，按钮又错误变成可点。

请这样处理：

1. 本地持久化最近一次 `publish_refresh` 的 `job_id`
2. 页面启动时先读本地缓存的 `job_id`
3. 如果有缓存 `job_id`，先调用 `GET /jobs/{job_id}`
4. 如果接口返回 `queued` 或 `running`，页面应恢复到禁用按钮状态并继续轮询
5. 如果接口返回 `succeeded` 或 `failed`，页面显示终态并允许重新点击
6. 如果接口返回 404，说明服务重启或 job 丢失，此时再调用 `GET /jobs` 看看有没有更近的 `publish_refresh`
7. 如果 `GET /jobs` 里也找不到对应活跃 job，就把状态回退为 `idle`，并允许重新点击

九、轮询规则

提交刷新请求成功后，请：

1. 立即保存 `job_id`
2. 立即把按钮置为禁用
3. 每 5 秒轮询一次 `GET /jobs/{job_id}`
4. 当状态变为 `succeeded` 或 `failed` 时停止轮询
5. 如果状态是 `succeeded`，要自动重新加载 `index.json`
6. 如果状态是 `failed`，显示错误提示，并允许再次点击刷新

轮询过程中的 UI 要显示：

1. 当前状态文案
2. 创建时间
3. 开始时间
4. 完成时间
5. 如果失败，显示错误摘要

状态文案建议：

1. `queued` -> `已排队，等待执行`
2. `running` -> `正在刷新持仓分析`
3. `succeeded` -> `刷新完成`
4. `failed` -> `刷新失败`

十、成功后的行为

当 `publish_refresh` 状态变成 `succeeded` 后，小程序必须：

1. 停止轮询
2. 重新请求 `index.json`
3. 用新的 `generated_at` 和 `stocks` 刷新首页列表
4. 如果当前在详情页，可以提示“数据已更新，可返回列表查看最新结果”
5. 重新允许点击“刷新持仓分析”按钮

十一、失败后的行为

当 `publish_refresh` 状态变成 `failed` 后，小程序必须：

1. 停止轮询
2. 显示失败态
3. 从 `error` 字段中提取简短错误摘要展示给用户
4. 不要把整段 Python traceback 原样灌到首屏，可默认折叠到“查看详情”
5. 重新允许点击“刷新持仓分析”按钮

十二、页面与组件要求

请至少实现这些页面或模块：

1. 首页 / 持仓页
   - 顶部统计：总持仓、A 股数、港股数、更新时间
   - 刷新按钮
   - 刷新状态卡片
   - 优先关注列表
   - 全部持仓列表
2. 个股详情页
   - 标题区
   - 摘要区
   - sections 区
   - 图表区

请至少封装这些能力：

1. `loadIndex()`
2. `loadSummary(relativePath)`
3. `loadDetail(relativePath)`
4. `resolveFileId(relativePath)`
5. `getTempImageUrl(relativePath)`
6. `triggerPublishRefresh()`
7. `getJob(jobId)`
8. `listJobs()`
9. `resumeRefreshJob()`
10. `pollRefreshJob()`

十三、适配服务端变化的要求

请把前端写成“尽量适配后端字段变化”的形式，而不是强耦合死结构：

1. 列表页优先使用 `index.json` 已经给出的字段，不要重复推导
2. 详情页顶部先用 `summary.json` 的稳定字段：
   - `comment`
   - `cards.fundamental.summary`
   - `cards.technical.conclusion`
   - `cards.technical.suggestion`
3. 详情正文优先用 `detail.json` 的：
   - `headline`
   - `overview`
   - `sections`
4. `sections` 按 `key` 分发，并对未知 `key` 做通用渲染兜底
5. 图表不要写死扩展名为 `jpg/png`，当前真实格式是 `svg`
6. 对所有可选字段做空值保护

十四、代码产出要求

请直接输出可运行代码，不要只给设计说明。至少包含：

1. 页面路由配置
2. CloudBase 初始化代码
3. 发布包读取 repository
4. 服务端 API client
5. 首页/持仓页代码
6. 详情页代码
7. 刷新按钮组件或状态卡片组件
8. 轮询与本地持久化逻辑
9. 必要样式

十五、实现注意点

1. 不要在 `queued` 或 `running` 状态下再次提交刷新
2. 不要让按钮在页面重进后丢失禁用状态
3. 不要首页并发拉全量 `summary.json` 和 `detail.json`
4. 不要把原始 JSON 全量 stringify 到页面
5. 不要假设服务端一定永远保留历史 job，404 要做恢复处理
6. 不要把 traceback 全量直接暴露给普通用户
7. UI 风格偏专业投研面板，不要做成营销风或社区风

十六、交付标准

1. 小程序能从 `INDEX_FILE_ID` 冷启动读取 `index.json`
2. 小程序能展示首页持仓列表和个股详情页
3. 小程序能点击“刷新持仓分析”并成功调用 `POST /jobs/publish-refresh`
4. 小程序能轮询并展示 `queued` / `running` / `succeeded` / `failed`
5. 当状态为 `queued` 或 `running` 时，按钮必须禁用
6. 当状态为 `succeeded` 或 `failed` 时，按钮恢复可点击
7. 当状态为 `succeeded` 时，小程序会自动重新读取最新发布包
8. 当状态为 `failed` 时，小程序会显示错误摘要并允许重试
```
