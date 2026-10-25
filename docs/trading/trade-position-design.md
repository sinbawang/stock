# 交易记录与仓位管理模块 Design

本页承接 [trade-position-spec.md](./trade-position-spec.md) 的需求，定义技术实现：架构分层、
数据模型、算法推导、云函数接口、小程序页面与测试策略。任务拆解见
[trade-position-tasks.md](./trade-position-tasks.md)。

## 1. 架构分层

```
微信小程序 (westock)
  ├─ pages/positionManager/index         交易录入 + 配对列表 + 仓位表 + 上限编辑
  ├─ services/tradeStoreService.js       封装 wx.cloud.callFunction('tradeStore')
  └─ utils/
       ├─ tradeTime.js                    成交时间默认补时 / 解析
       ├─ tradePairing.js                 价差最优配对（纯函数）
       ├─ positionAggregation.js          移动加权均成本 + FIFO 持有天数 + 仓位% + 报警
       └─ tradeValidation.js              录入校验 + 超限预检
          │
          ▼ wx.cloud.callFunction
CloudBase 云函数 tradeStore (wx-server-sdk)
  └─ 动作: listTrades/addTrade/updateTrade/deleteTrade/getLimits/setLimits
          │
          ▼
CloudBase 文档数据库
  ├─ 集合 trades            (按 _openid 隔离)
  └─ 集合 position_limits   (按 _openid 隔离)

当前价来源（只读，复用已发布数据）
  └─ services/cloudbaseStorageRepository.js → 最近 K 线收盘价
```

### 1.1 设计原则
- **真源单一**：交易与上限配置以 CloudBase 文档库为唯一真源，按 `_openid` 隔离。
- **计算在端**：配对与仓位聚合是纯函数，放小程序端，便于离线与 node 单测；不依赖 `wx`。
- **容器不介入**：stock Python 容器保持只读发布分析数据，不存储 / 不计算交易数据。
- **读写分离**：读分析数据走现有 `cloudbaseStorageRepository`（云存储）；读写交易数据走
  新云函数 `tradeStore`（云数据库）。两条通道互不耦合。

## 2. 数据模型（CloudBase 集合）

### 2.1 `trades`
字段见 spec §4.1。约束与索引：
- `quantity` 存正整数；方向由 `direction` 表达。
- `market ∈ {CN, HK}`，`level ∈ {m1,m5,m30,md}`，`direction ∈ {buy,sell}`。
- 复合索引：`(_openid, symbol, level, tradeTime)`，支持按股票 + 级别 + 时间排序拉取。
- 所有写入由云函数用 `getWXContext().OPENID` 强制盖 `_openid`，前端不可伪造。

### 2.2 `position_limits`
字段见 spec §4.2。约束与索引：
- 唯一键逻辑：`(_openid, symbol)`；`setLimits` 用 upsert（存在则更新，否则插入）。
- 复合索引：`(_openid, symbol)`。

## 3. 云函数 `tradeStore` 接口

统一入参 `{ action, payload }`，统一出参 `{ success, data?, errMsg? }`。全部动作内部
`const { OPENID } = cloud.getWXContext()`，查询 / 写入都带 `_openid: OPENID`。

| action | payload | 说明 |
| --- | --- | --- |
| `listTrades` | `{ symbol }` | 返回该用户该股票全部交易（按 tradeTime 升序） |
| `addTrade` | `{ symbol, market, level, direction, tradeTime, price, quantity, note? }` | 服务端盖 `_openid/createdAt/updatedAt` 后 insert |
| `updateTrade` | `{ _id, ...fields }` | 仅更新归属本人的记录，刷新 `updatedAt` |
| `deleteTrade` | `{ _id }` | 仅删除归属本人的记录 |
| `getLimits` | `{ symbol }` | 返回上限配置；无则返回 `null`（前端回退默认） |
| `setLimits` | `{ symbol, market, maxTotal, perLevel, holdingDaysThreshold }` | upsert |

- 权限：`where({ _id, _openid })` 双条件，杜绝越权改他人数据。
- 入参校验：云函数侧对 `level/direction/market` 做白名单校验，`price>0`、`quantity>0`、
  `tradeTime` 可解析，否则返回 `success:false`。
- 复用策略：可在现有 `quickstartFunctions` 旁**新增独立函数** `tradeStore`，避免污染示例函数。

## 4. 配置默认值

### 4.1 级别展示顺序
固定 `['m1','m5','m30','md']`（从细到粗），列表与仓位表统一按此顺序。

### 4.2 全局默认（未配置时回退）
```
DEFAULT_LIMITS = {
  maxTotal: null,                                  // 未设则仓位% 不可计算，显示 '--'
  perLevel: { m1: null, m5: null, m30: null, md: null },
  holdingDaysThreshold: { m1: 2, m5: 10, m30: 30, md: 250 }
}
```
- `maxTotal` 无默认（因人而异）：未设置时仓位% 显示 `--`，不做超限红标。
- `holdingDaysThreshold` 给经验默认，用户可覆盖。

## 5. 核心算法

> 关键认知：**配对盈亏**与**持仓成本**是两套独立口径，服务不同面板，不要相互套用。
> 配对面板回答「历史买卖实现了多少盈亏」，用价差最优；仓位面板回答「当前持仓成本多少、
> 拿了多久」，用移动加权均成本 + FIFO。

### 5.1 成交时间补时 `tradeTime.js`
```
normalizeTradeTime(input, { direction, market }):
  解析 input：
    - 'YYYY-MM-DD HH:mm' / ISO → 原样
    - 'YYYY-MM-DD' 或 'MM-DD'（补当前年）→ 仅日期
  若仅日期：
    buy  → 补 '09:30'
    sell → market==='HK' ? '16:00' : '15:00'
  返回 ISO 本地时间字符串
```

### 5.2 配对展示 `tradePairing.js`（价差最优 / max_profit）
按 symbol 已给定，入参为该股票 trades。流程：
```
pairAll(trades):
  for level in LEVELS:
    buys  = trades[level].filter(buy)  →  lots {price, qty, time}
    sells = trades[level].filter(sell) →  lots {price, qty, time}
    rows += pairLevel(level, buys, sells)

pairLevel(level, buys, sells):
  B = buys 按 price 升序（最低买价优先）
  S = sells 按 price 降序（最高卖价优先）
  i=j=0; rows=[]
  while i<B.len and j<S.len:
    q = min(B[i].remain, S[j].remain)
    rows.push({level, quantity:q,
               buyTime:B[i].time, buyPrice:B[i].price,
               sellTime:S[j].time, sellPrice:S[j].price,
               status:'done', pnl:(S[j].price-B[i].price)*q})
    B[i].remain-=q; S[j].remain-=q
    if B[i].remain==0: i++
    if S[j].remain==0: j++
  // 剩余净持仓
  剩余 B（较高价买单）→ {status:'wait_sell'(待卖), buyTime/buyPrice, quantity}
  剩余 S（较低价卖单）→ {status:'wait_buy'(待买), sellTime/sellPrice, quantity}
```
- 匹配股数 = `min(ΣbuyQty, ΣsellQty)`；排序保证实现盈亏最大化。
- `done` 行可因部分成交拆成多行，buyTime/sellTime 取各自被匹配 lot 的时间。

### 5.3 仓位聚合 `positionAggregation.js`
对每个级别，按 `tradeTime` 升序处理：

#### 5.3.1 移动加权均成本 + 净数量
```
qty=0; avg=0
for t in sortedByTime(levelTrades):
  if t.buy:
    avg = (qty*avg + t.qty*t.price) / (qty + t.qty)
    qty += t.qty
  else: // sell
    qty -= t.qty          // 卖出按当前 avg 扣减，avg 不变
    if qty <= 0: qty=max(qty,0); avg=0   // 清仓则重置
netQty = qty; avgCost = avg
```

#### 5.3.2 FIFO 最长持有天数
```
// 用 FIFO 队列确定“最早仍未平仓”的买入
queue=[]  // {time, remain}
for t in sortedByTime(levelTrades):
  if t.buy: queue.push({time:t.time, remain:t.qty})
  else:
    r=t.qty
    while r>0 and queue: take=min(queue[0].remain,r)
      queue[0].remain-=take; r-=take
      if queue[0].remain==0: queue.shift()
earliestOpen = queue.length ? queue[0].time : null
longestHoldingDays = earliestOpen ? floor((now - earliestOpen)/天) : 0  // 自然日
```

#### 5.3.3 仓位% 与浮盈浮亏
```
positionPct = maxTotal ? netQty / maxTotal : null
currentPrice = 最近 K 线收盘价（见 §6）
floatPnl = currentPrice!=null ? (currentPrice - avgCost) * netQty : null
floatPnlSign = floatPnl>0 ? 'profit'(红) : floatPnl<0 ? 'loss'(绿) : 'flat'
```

#### 5.3.4 报警标志
```
overLevelLimit  = perLevel[level]!=null && netQty > perLevel[level]
overHoldingDays = longestHoldingDays > holdingDaysThreshold[level]
totalPct        = maxTotal ? Σ netQty / maxTotal : null
overTotalLimit  = maxTotal!=null && Σ netQty > maxTotal
```

### 5.4 录入校验 `tradeValidation.js`
- 必填：level/direction/tradeTime/price/quantity；`price>0`、`quantity>0` 且为整数。
- 超限预检：以「现有净持仓 + 本次买入」预估该级别与总仓位是否越限，越限返回 warning
  （不阻断，供 UI 高亮确认）。

## 6. 当前价获取
- 复用 `cloudbaseStorageRepository` 读该股票已发布技术数据（detail/base），取最近一根
  K 线收盘价：优先 1m 最新 close，缺失回退 day 最新 close。
- 封装到 `tradeStoreService.getLatestPrice(symbol)` 或 positionManager 页加载时一并取。
- 无法取到时 `currentPrice=null`，浮盈浮亏显示 `--`，不做红绿。

## 7. 小程序页面

### 7.1 `pages/positionManager/index`
入参 `?symbol=&market=`。两个 Tab：
- **交易 Tab**：
  - 录入表单：级别选择、方向切换、日期/时间、价格、数量、备注，含默认补时与校验。
  - 配对列表：按级别分组展示 done/待卖/待买 行（spec §3.2.3），done 行显示盈亏红/绿。
  - 每条原始流水可编辑 / 删除。
- **仓位 Tab**：
  - 各级别仓位表（spec §3.3.1）+ 颜色报警。
  - 顶部总仓位%（超总上限红标）。
  - 上限配置编辑入口（maxTotal / perLevel / holdingDaysThreshold）。

### 7.2 入口
- 在 `pages/stockDetail/index` 增加「仓位/交易」按钮，`navigateTo` 带 `symbol/market`。
- `app.json` 注册新页面路由。

## 8. 测试策略
- **纯函数单测（node，无 wx 依赖）**：`tradePairing` / `positionAggregation` / `tradeTime` /
  `tradeValidation`。用例覆盖：
  - spec §3.2.3 / §3.3.1 示例数值（m1 毛利 400、总仓位 90%）。
  - 部分成交拆行、净多（待卖）、净空（待买）。
  - 移动加权均成本多笔买入、卖出后 avg 不变、清仓重置。
  - FIFO 最长持有天数（卖出抵消最早买入）。
  - 超级别/总上限、超合理持仓天数、浮盈浮亏红绿。
  - 补时：仅日期时 buy→09:30、sell CN→15:00 / HK→16:00；MM-DD 补年。
- **云函数**：手动 / 轻量集成验证 CRUD 与 `_openid` 隔离、白名单校验。
- 运行方式：JS 单测用 `node` 直接跑（utils 导出为 CommonJS，不引用 `wx`）。

## 9. 风险与权衡
- 价差最优配对与移动加权均成本口径不同，`待卖` 行里显示的「剩余买单」是较高价的那部分，
  而均成本是移动加权值——两者数值不必相等，UI 文案需说明「配对盈亏 ≠ 持仓成本」。
- 当前价依赖已发布数据的时效；盘中与发布时刻可能有延迟，浮盈浮亏为参考值。
- `maxTotal` 以「股数」为口径（与示例一致），非金额；若未来要金额口径需另行扩展。
