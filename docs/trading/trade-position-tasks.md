# 交易记录与仓位管理模块 任务拆解

本页承接 [trade-position-spec.md](./trade-position-spec.md) 与
[trade-position-design.md](./trade-position-design.md)，给出可执行的任务看板。文档任务先行，
其后为云函数、小程序工具/页面与测试。

## 1. Epic 看板

| ID | 任务 | 类型 | 状态 | 依赖 | 完成定义 |
| --- | --- | --- | --- | --- | --- |
| T0-SPEC | 编写 spec.md | 文档 | 完成 | — | 需求/行为/数据契约/验收齐备 |
| T0-DESIGN | 编写 design.md | 文档 | 完成 | T0-SPEC | 架构/数据模型/算法/接口/页面/测试策略齐备 |
| T0-TASKS | 编写 tasks.md | 文档 | 完成 | T0-DESIGN | 任务分解与依赖齐备 |
| T1-CF | 云函数 `tradeStore` + 集合 | 代码 | 待办 | T0-DESIGN | CRUD + limits 读写，按 `_openid` 隔离，含白名单校验 |
| T2-UTIL | 小程序纯 JS 工具 | 代码 | 待办 | T0-DESIGN | 补时/配对/仓位聚合/校验 纯函数可用、可 node 单测 |
| T3-SVC | `tradeStoreService` 封装 | 代码 | 待办 | T1-CF | 封装 callFunction + 当前价获取 + 错误处理 |
| T4-PAGE | `positionManager` 页面 + 入口 | 代码 | 待办 | T2-UTIL, T3-SVC | 交易/仓位两 Tab 可用，stockDetail 入口接入 |
| T5-TEST | 纯函数单元测试 | 测试 | 待办 | T2-UTIL | 覆盖 spec 示例与边界，node 可跑通 |
| T6-OVERVIEW | 顶部「仓位」总览标签页 | 代码 | 待办 | T2-UTIL, T1-CF | 各股持仓总览卡片，点击进个股页；现价来自保存值 |

## 2. 任务明细

### T1-CF 云函数 `tradeStore`
- 新增 `cloudfunctions/tradeStore/`（独立于 quickstartFunctions）：`index.js` + `package.json`
  （依赖 `wx-server-sdk`）。
- 实现动作：`listTrades / addTrade / updateTrade / deleteTrade / getLimits / setLimits`
  （见 design §3）。
- 每个动作内 `getWXContext().OPENID`，查询/写入均带 `_openid`；改删用 `{_id,_openid}` 双条件。
- 白名单校验 `level/direction/market`，`price>0`、`quantity>0`、`tradeTime` 可解析。
- 集合 `trades`、`position_limits` 首次调用自动建（或文档说明手动建），建议建复合索引
  `(_openid,symbol,level,tradeTime)` 与 `(_openid,symbol)`。
- 完成定义：本地/云端可完成一条交易的增改删查与 limits upsert，越权访问被拒。

### T2-UTIL 小程序纯 JS 工具（CommonJS，不引用 wx）
- `utils/tradeTime.js`：`normalizeTradeTime(input,{direction,market})`（design §5.1）。
- `utils/tradePairing.js`：`pairAll(trades)` / `pairLevel(...)`（design §5.2）。
- `utils/positionAggregation.js`：`aggregatePositions(trades, limits, priceByLevelOrSymbol)`
  （design §5.3，含均成本、FIFO 持有天数、仓位%、浮盈浮亏、报警标志）。
- `utils/tradeValidation.js`：录入校验 + 超限预检（design §5.4）。
- 完成定义：四个模块导出纯函数，可被 node require 直接调用。

### T3-SVC `services/tradeStoreService.js`
- 封装 `wx.cloud.callFunction({name:'tradeStore', data:{action,payload}})`，统一解包
  `{success,data,errMsg}`。
- `getLatestPrice(symbol)`：复用 `cloudbaseStorageRepository` 取最近 K 线收盘价
  （1m 优先、回退 day，design §6）。
- 基本缓存与错误提示。

### T4-PAGE `pages/positionManager/index`
- `index.js/.wxml/.wxss/.json`，入参 `symbol/market`，两 Tab（design §7.1）。
- 交易 Tab：录入表单（默认补时+校验+超限预检提示）、配对列表、单条编辑/删除。
- 仓位 Tab：各级别仓位表 + 颜色报警 + 总仓位% + 上限编辑。
- `app.json` 注册路由；`pages/stockDetail/index` 增加「仓位/交易」入口按钮。
- 完成定义：真机/工具上可录入→看到配对与仓位→编辑上限→颜色报警正确。

### T5-TEST 单元测试
- 为 T2-UTIL 四个模块写 node 单测（可放 `westock` 下的 `test/` 或 `__tests__/`）。
- 必覆盖用例：
  - 配对：m1 买 53.52/卖 54.32×500 → done 盈亏 400；部分成交拆行；净多→待卖；净空→待买。
  - 仓位：示例四级别合计总仓位 90%；移动加权均成本多买一卖；清仓重置；FIFO 最长持有天数。
  - 报警：超级别上限、超总上限、超合理持仓天数、浮盈红/浮亏绿。
  - 补时：仅日期 buy→09:30、sell CN→15:00/HK→16:00；`MM-DD` 补当前年。
  - 总览：`aggregateSymbol` 全仓成本/市值/盈亏/盈亏率。

### T6-OVERVIEW 顶部「仓位」总览标签页
- `utils/positionAggregation.js` 增 `aggregateSymbol`（全仓移动加权 + 市值/盈亏/盈亏率/比例）。
- 云函数 `tradeStore` 增 `listAllTrades`/`listAllLimits`；`addTrade`/`updateTrade` 透传 `name`；
  `setLimits` 支持 `name`/`currentPrice`。
- `utils/pageNav.js` `PRIMARY_PAGES` 增「仓位」；`app.json` 注册 `pages/positionsOverview/index`。
- 新页面 `pages/positionsOverview/index`：聚合各股持仓→卡片列表→点击进个股页。
- `positionManager` 仓位 Tab：当前价预填 `limits.currentPrice` 并支持保存；录入/设限携带 `name`。
- 完成定义：录完几只股票并在个股页存现价后，「仓位」页能正确展示各股总览并跳转。

## 3. 阶段与并行建议
- 阶段 A（文档）：T0-SPEC → T0-DESIGN → T0-TASKS（已完成）。
- 阶段 B（并行）：T1-CF 与 T2-UTIL 可并行（均只依赖 design）；T5-TEST 紧随 T2-UTIL。
- 阶段 C（集成）：T3-SVC 依赖 T1-CF；T4-PAGE 依赖 T2-UTIL + T3-SVC。

## 4. 验收对齐
全部实现任务完成后，对照 spec §5 验收标准逐条核验，并运行 T5-TEST 单测作为回归闸门。

## 5. 后续演进（非本期）
- 交易纪律 Phase 2（spec §6）：买入依据关联买点类型、止损价、首页/组合页聚合超限超期提醒。
- 金额口径仓位、资金曲线 / 已实现盈亏统计。
- 级别集合扩展（m15/m60/mw）。
