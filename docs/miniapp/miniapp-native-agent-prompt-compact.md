# 微信小程序原生端开发 Prompt（精简版）

```text
请在当前微信小程序项目中实现一个“持仓分析展示”原生小程序，只读 CloudBase 云存储，不使用云数据库、不使用云函数、不使用 WebView。

目标：
1. 从 CloudBase 云存储读取已经上传好的发布包。
2. 生成首页、组合页、A 股页、港股页、个股详情页。
3. 用原生组件展示持仓股票分析结果，适合手机窄屏阅读。

已知数据入口：
1. 小程序本地会提供一个常量：
   `const INDEX_FILE_ID = 'cloud://<env>.<bucket>/miniapp-publish/latest/index.json'`
2. 其他文件不要硬编码 fileID，而是从 `INDEX_FILE_ID` 推导前缀：
   - `FILE_ID_PREFIX = INDEX_FILE_ID.replace(/\/index\.json$/, '')`
   - 相对路径 `groups/portfolio.json` -> `${FILE_ID_PREFIX}/groups/portfolio.json`
   - 相对路径 `stocks/00175/detail.json` -> `${FILE_ID_PREFIX}/stocks/00175/detail.json`
   - 相对路径 `stocks/00175/charts/60m.jpg` -> `${FILE_ID_PREFIX}/stocks/00175/charts/60m.jpg`

发布包结构：
1. `index.json`
   - 包含 `counts`、`groups`、`stocks`
   - `stocks` 每项有：`symbol`、`name`、`market`、`updated_at`、`summary`、`detail`、`cover_chart`、`tags`
2. `groups/portfolio.json`
   - 全部持仓组合视图
3. `groups/a_share.json`
   - A 股分组，包含 `today_action`、`watch_pool`、`risk_pool`
4. `groups/h_share.json`
   - 港股分组，结构同上
5. `stocks/<symbol>/summary.json`
   - 列表页卡片摘要
   - 关键字段：`priority`、`action`、`bucket`、`comment`、`cards`、`cover_chart`、`tags`
6. `stocks/<symbol>/detail.json`
   - 个股详情数据
   - 关键字段：`headline`、`overview`、`sections`、`charts`、`disclaimer`

真实字段示例：
1. `summary.json`
   - `priority`: `P3`
   - `action`: `等待冲突缓解`
   - `bucket`: `mixed`
   - `comment`: `分化：基本面质量较好；60M 技术节奏偏积极；资金面已有覆盖，但尚未形成强确认`
   - `cards.fundamental.score`: `65.5`
   - `cards.fundamental.rating`: `B`
   - `cards.technical.conclusion`: `偏多，允许轻仓试错。`
   - `cards.capital_flow.rating`: `C`
2. `detail.json`
   - `headline.title`: `吉利汽车 00175`
   - `headline.priority`: `P3`
   - `overview.summary`: `分化：基本面质量较好；60M 技术节奏偏积极；资金面已有覆盖，但尚未形成强确认`
   - `sections` 包含 `fundamental`、`technical`、`capital_flow`
   - `charts` 包含 `60m`、`15m`、`day`

信息架构要求：
1. 首页
   - 显示更新时间、持仓总数、A 股数、港股数
   - 显示优先关注列表（优先 P1/P2）
   - 显示全部持仓列表
2. 组合页
   - 读取 `groups/portfolio.json`
3. A 股页
   - 读取 `groups/a_share.json`
   - 分区展示今日动作、观察池、风险池
4. 港股页
   - 读取 `groups/h_share.json`
5. 个股详情页
   - 显示 headline
   - 显示 overview bullets
   - 分卡片展示基本面、技术面、资金面
   - 展示 60m / 15m / day 图表

展示规则：
1. `priority` 做醒目标记：P1 红、P2 橙、P3 蓝灰、P5 深灰
2. `bucket` 中文映射：
   - confirming -> 确认
   - watch -> 观察
   - mixed -> 分化
   - cautious -> 谨慎
3. 列表卡片至少展示：股票名、代码、market、priority、action、comment、三轴摘要
4. 详情页数组字段都用 bullet list 渲染，不要原样 dump JSON
5. 图表默认先展示 60m，其余放 tabs 或 swiper

技术实现要求：
1. 使用微信小程序原生页面。
2. 使用 TypeScript（如果项目支持）。
3. 封装一个 CloudBase storage repository，至少包含：
   - `loadIndex()`
   - `loadGroup(relativePath)`
   - `loadSummary(relativePath)`
   - `loadDetail(relativePath)`
   - `resolveFileId(relativePath)`
   - `getTempImageUrl(relativePath)`
4. JSON 读取：
   - 通过 fileID 下载或获取临时 URL 后读取
   - 做内存缓存
   - 有 loading、error、empty 状态
5. 图片读取：
   - 通过 fileID 获取 temp URL
   - 绑定到 image 组件

代码交付要求：
1. 直接输出可运行代码，不要只给设计说明。
2. 至少包含：
   - 页面路由配置
   - CloudBase 初始化代码
   - 数据读取层
   - 首页、组合页、A 股页、港股页、详情页
   - 股票卡片组件
   - section 渲染组件
   - 必要样式
3. 如果当前仓库没有小程序结构，请补齐最小可运行骨架。

注意：
1. 不要使用 WebView。
2. 不要接云数据库。
3. 不要接云函数。
4. 不要把 `notes`、`source_file`、工程说明直接放到首屏。
5. 不要把原始 JSON 字符串直接输出到页面。
6. UI 风格偏专业投研看板，不要做成社区风或营销风。
```

## 使用方式

- 如果你要直接丢给 Claude/Cursor/Copilot，用这份精简版更合适。
- 如果对方需要更多上下文，再补充参考 [miniapp-native-agent-prompt.md](miniapp-native-agent-prompt.md)。