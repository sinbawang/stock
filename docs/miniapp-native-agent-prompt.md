# 微信小程序原生端开发 Prompt

下面这段 prompt 可以直接发给负责微信小程序开发的 agent 或开发同学。

```text
你现在要为一个“持仓分析结果展示”微信小程序实现原生页面，不要用 WebView，不要把 JSON 当富文本直接展示，也不要引入云数据库或云函数。

目标：
1. 从 CloudBase 云存储读取已经上传好的发布包。
2. 在小程序里生成原生页面、菜单和导航结构。
3. 展示当前持仓股票的分析结果，包括组合视图、A 股视图、港股视图、个股详情页。
4. UI 适合手机阅读，信息密度高但不拥挤，重点突出 priority、action、bucket、三轴卡片和结构图。

已知后端/数据约束：
1. 只使用 CloudBase 云存储，不使用云数据库，不使用云函数。
2. 发布包已经上传到云存储前缀 `miniapp-publish/latest/`。
3. 顶层入口文件是 `index.json`。
4. 已有一个部署后拿到的 `index_file_id`，小程序会把它作为启动配置常量写在本地，例如：
   `const INDEX_FILE_ID = 'cloud://<env>.<bucket>/miniapp-publish/latest/index.json'`
5. 其余文件不额外硬编码 fileID，而是从 `INDEX_FILE_ID` 推导同目录前缀：
   - 先得到 `FILE_ID_PREFIX = INDEX_FILE_ID.replace(/\/index\.json$/, '')`
   - 然后把 `index.json` 中的相对路径拼成完整 fileID：
     - `groups/portfolio.json` -> `${FILE_ID_PREFIX}/groups/portfolio.json`
     - `stocks/00175/detail.json` -> `${FILE_ID_PREFIX}/stocks/00175/detail.json`
     - `stocks/00175/charts/60m.jpg` -> `${FILE_ID_PREFIX}/stocks/00175/charts/60m.jpg`
6. 读取 JSON 时优先走 CloudBase 文件下载或临时 URL，不要假设有 HTTP 静态站点。

当前发布包结构如下：
1. `index.json`
   - 顶层索引
   - 包含 `counts`、`groups`、`stocks`
   - `stocks` 内每项有 `symbol`、`name`、`market`、`updated_at`、`summary`、`detail`、`cover_chart`、`tags`
2. `groups/portfolio.json`
   - 全部持仓分组
   - 包含一个 section，title 是“全部持仓”
3. `groups/a_share.json`
   - 包含 `today_action`、`watch_pool`、`risk_pool` 三个 section
4. `groups/h_share.json`
   - 结构与 A 股组相同
5. `stocks/<symbol>/summary.json`
   - 列表卡片所需轻量信息
   - 包含 `priority`、`action`、`bucket`、`comment`、`cards`、`cover_chart`、`tags`
6. `stocks/<symbol>/detail.json`
   - 个股详情页所需结构化信息
   - 包含 `headline`、`overview`、`sections`、`charts`、`disclaimer`

真实样例字段：
1. `index.json` 中的单个 stock 记录示例：
   - `symbol`: `00175`
   - `name`: `吉利汽车`
   - `market`: `HK`
   - `summary`: `stocks/00175/summary.json`
   - `detail`: `stocks/00175/detail.json`
   - `cover_chart`: `stocks/00175/charts/60m.jpg`
   - `tags`: [`mixed`, `P3`, `等待冲突缓解`]
2. `summary.json` 示例字段：
   - `priority`: `P3`
   - `action`: `等待冲突缓解`
   - `bucket`: `mixed`
   - `comment`: `分化：基本面质量较好；60M 技术节奏偏积极；资金面已有覆盖，但尚未形成强确认`
   - `cards.fundamental.score`: `65.5`
   - `cards.fundamental.rating`: `B`
   - `cards.technical.conclusion`: `偏多，允许轻仓试错。`
   - `cards.capital_flow.rating`: `C`
3. `detail.json` 示例字段：
   - `headline.title`: `吉利汽车 00175`
   - `headline.priority`: `P3`
   - `overview.summary`: `分化：基本面质量较好；60M 技术节奏偏积极；资金面已有覆盖，但尚未形成强确认`
   - `sections` 是数组，包含 `fundamental`、`technical`、`capital_flow`
   - `charts` 是数组，包含 `60m`、`15m`、`day` 图

请按下面的信息架构实现：

一、页面与菜单
1. 首页
   - 顶部显示更新时间、持仓总数、A 股数量、港股数量
   - 下方显示“优先关注”区域，优先展示 P1 和 P2
   - 再显示“全部持仓列表”
2. 组合页
   - 使用 `groups/portfolio.json`
   - 按 section 渲染
   - 重点展示 priority、action、comment
3. A 股页
   - 使用 `groups/a_share.json`
   - 分成“今日动作”“观察池”“风险池”三个折叠或卡片分区
4. 港股页
   - 使用 `groups/h_share.json`
   - 同 A 股页结构
5. 个股详情页
   - 顶部 headline 区
   - 中间 overview bullets
   - 三个 section 分卡片渲染：基本面、技术面、资金面
   - 底部 charts 横向滑动展示 60m、15m、day 图

二、展示规则
1. `priority` 用颜色标签展示：
   - P1 红色强调
   - P2 橙色
   - P3 蓝灰
   - P5 深灰
2. `bucket` 用中文映射：
   - confirming -> 确认
   - watch -> 观察
   - mixed -> 分化
   - cautious -> 谨慎
3. 列表卡片至少展示：
   - 股票名 + 代码
   - market
   - priority
   - action
   - comment
   - 三轴卡片摘要：fundamental / technical / capital_flow
4. 详情页中：
   - `fundamental.highlights`、`risks`、`follow_ups`、`warnings` 用 bullet list
   - `technical.overview`、`structure`、`signals`、`focus` 用 bullet list
   - `capital_flow.strengths`、`risks`、`warnings` 用 bullet list
   - `capital_flow.metrics` 用两列指标表
5. 图表优先展示 `60m`，其他图可放在 swiper 或 tabs

三、技术实现要求
1. 使用小程序原生页面，不用 WebView。
2. 使用 TypeScript，如果项目已启用 TS。
3. 封装一个 CloudBase storage repository：
   - `loadIndex()`
   - `loadGroup(relativePath)`
   - `loadSummary(relativePath)`
   - `loadDetail(relativePath)`
   - `resolveFileId(relativePath)`
   - `getTempImageUrl(relativePath)`
4. JSON 文件读取流程：
   - 通过 `resolveFileId(relativePath)` 生成完整 fileID
   - 下载文件到本地临时目录或先获取 temp URL 再读取
   - 解析为 JSON
5. 图片读取流程：
   - 通过 `resolveFileId(relativePath)` 生成完整 fileID
   - 调用 CloudBase 获取 temp URL
   - 直接绑定到 image 组件
6. 加缓存：
   - index、group、summary、detail 做内存缓存
   - 二次进入页面时优先展示缓存，再后台刷新
7. 做错误态：
   - index 读取失败
   - group 读取失败
   - detail 读取失败
   - 图表加载失败
8. 做 loading 态和 empty 态

四、代码产出要求
请直接产出可运行的小程序代码，不要只给设计说明。至少包括：
1. `app.json` 或页面路由配置
2. 底部 tabBar 或首页菜单入口配置
3. CloudBase 初始化代码
4. 存储读取与缓存封装
5. 首页、组合页、A 股页、港股页、详情页五个页面
6. 通用股票卡片组件
7. 通用 section 渲染组件
8. 必要的样式文件

五、交付标准
1. 打开小程序后能从 `INDEX_FILE_ID` 启动并读取 `index.json`
2. 能从首页进入组合页、A 股页、港股页、个股详情页
3. 每只股票能正确展示 summary 和 detail
4. 图表能加载
5. 所有页面都适配手机窄屏
6. 不依赖任何服务端接口，全部只读 CloudBase 云存储

六、实现时的注意点
1. 不要假设字段永远完整，像 `technical` 或 `fundamental` 某些数组可能为空
2. 不要把 `notes`、`source_file`、工程口径说明直接暴露在主 UI 的首屏
3. 不要把原始 JSON 全量 stringify 到页面
4. UI 风格偏专业投研看板，不要做成营销风或社区风
5. 页面命名、组件拆分、数据层设计要清晰，方便后续继续加“历史快照”页

如果当前项目里还没有对应的小程序基础目录，请一并补齐最小可运行结构。
```

## 使用建议

- 如果小程序仓库还没开始搭，先把这份 prompt 直接发给负责搭建小程序的 agent。
- 如果小程序仓库已经存在，把 prompt 开头补一句“遵循现有项目结构和编码风格，不要重建工程”。
- 真正接入时，至少要把上传脚本输出的 `index_file_id` 写进小程序配置常量里，否则无法完成冷启动。