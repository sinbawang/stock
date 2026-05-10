# 科技行业子模型 v0.1

这份文档是 [fundamental-industry-layering.md](fundamental-industry-layering.md) 中“科技行业规则”的进一步细化版本。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

当前这些科技子模型已经落成 Python 配置对象；对象结构说明见 [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md)。

目的不是把所有科技细分行业一次讲完，而是先把你当前更可能用到的几类拆开，确保实现层：

- 同样叫“科技”，但不会把平台互联网、半导体、工业自动化、游戏内容混成一锅
- 同一套字段可以复用，但权重和红线按子行业调整
- 你当前关注的标的能先有一套稳定归类

## 1. 科技行业为什么必须继续细分

科技行业内部差异很大：

- 平台互联网看的是流量变现、经营杠杆、现金流兑现和估值分位
- 半导体看的是库存周期、资本开支、毛利率拐点和国产替代空间
- 工业自动化看的是订单、制造业资本开支、现金流质量和全球竞争力
- 游戏和数字内容看的是产品生命周期、买量效率、递延收入和利润兑现

如果不做子模型，最后会出现两个问题：

- 该关注的风险被平均掉
- 不该拿来横比的指标被硬拉到一起

## 2. 第一阶段建议支持的科技子模型

建议第一阶段先支持四类：

- 平台互联网
- 半导体与电子硬科技
- 工业自动化与智能装备
- 游戏与数字内容

这四类已经能覆盖你当前提到的大部分标的。

## 3. 子模型一：平台互联网

### 3.1 适用对象

- 美团
- 腾讯
- 快手
- 阿里

### 3.2 核心矛盾

平台互联网的核心不是“收入长得快不快”，而是：

- 收入增长能否转化为经营利润
- 经营利润能否转化为真实现金流
- 估值是否已经提前反映多年增长

### 3.3 建议维度权重

- 盈利质量与兑现：`35`
- 成长能力：`25`
- 现金流与运营效率：`20`
- 估值匹配：`20`

### 3.4 建议优先指标

- `revenue_growth`
- `net_profit_growth`
- `operating_cashflow_to_profit`
- `pe_percentile_5y`
- `peg`
- `roe_3y_cv`

建议新增字段：

- `take_rate_trend`
- `deferred_revenue_growth`
- `user_growth`
- `arpu_growth`
- `marketing_expense_ratio`

### 3.5 建议降权或停用指标

建议降权：

- `inventory_growth`
- `current_ratio`
- `debt_to_asset`

原因：

- 平台互联网通常不是库存驱动业务
- 轻资产结构下流动比率解释力有限
- 负债率不像重资产行业那样关键

### 3.6 建议红线

- `operating_cashflow_to_profit` 连续 2 期 `< 0.8`
- 收入仍增长，但营销投入显著上升而利润率恶化
- 用户增长放缓，估值分位仍高
- 核心业务现金牛转弱，但新业务亏损扩大

### 3.7 第一版评分参数表

这一节的目标不是补充概念说明，而是对照当前配置层给出一份可直接落地的参数表。

#### 3.7.1 模型标识

| 项目 | 参数 |
| --- | --- |
| `industry_bucket` | `technology` |
| `submodel_id` | `platform_internet_v1` |
| 适用标的 | 美团、腾讯、快手、阿里 |
| 第一版定位 | 科技主模型 |
| 默认输出风格 | 增长兑现 + 现金流质量优先 |

#### 3.7.2 字段分层

| 分层 | 字段 |
| --- | --- |
| `required_core` | `symbol`、`name`、`market`、`report_period`、`currency`、`source`、`updated_at`、`roe`、`roe_3y_cv`、`operating_cashflow_to_profit`、`operating_cashflow_to_profit_history`、`revenue_growth`、`net_profit_growth`、`pe_percentile_5y`、`peg` |
| `optional_manual` | `dupont_driver`、`guidance_attainment`、`deferred_revenue_growth`、`user_growth`、`arpu_growth`、`marketing_expense_ratio` |
| `disabled_or_deweighted` | `inventory_growth`、`current_ratio`、`debt_to_asset` |

第一版对平台互联网的关键要求是：

- 必须能评估增长、利润兑现、现金流兑现、估值匹配
- 不要求把库存和负债率当成主决策因子
- 允许通过手工字段补强“用户质量”和“营销效率”判断

#### 3.7.3 维度参数

| 维度 | 权重 | 第一版主字段 | 第一版实现口径 |
| --- | --- | --- | --- |
| 盈利质量与兑现 | `35` | `roe`、`roe_3y_cv`、`operating_cashflow_to_profit`、`dupont_driver` | 沿用通用打分，`dupont_driver` 缺失时只跳过该子项 |
| 成长能力 | `25` | `revenue_growth`、`net_profit_growth`、`guidance_attainment` | 沿用通用打分，但总权重由 `20` 提升到 `25` |
| 现金流与运营效率 | `20` | `operating_cashflow_to_profit`、`deferred_revenue_growth`、`user_growth`、`arpu_growth`、`marketing_expense_ratio` | 第一版默认仅强制使用 `operating_cashflow_to_profit`，其余字段存在则加注释或增强判断 |
| 估值匹配 | `20` | `pe_percentile_5y`、`peg` | 沿用通用估值打分 |

#### 3.7.4 第一版规则覆盖

| 规则项 | 平台互联网第一版处理 |
| --- | --- |
| `debt_to_asset` | 默认不进入主评分 |
| `inventory_growth` | 默认不进入主评分 |
| `accounts_receivable_growth` | 默认不作为主模型硬依赖；若存在，可只进入风险提示，不进入主评分 |
| `operating_cashflow_to_profit_history` | 作为第一版唯一自动化连续两期红线 |
| `guidance_attainment` | 可选增强项，缺失不阻塞 |
| `marketing_expense_ratio` | 第一版只用于人工解释，不建议先写硬阈值 |

#### 3.7.5 第一版红线参数

| 红线 | 类型 | 第一版实现建议 |
| --- | --- | --- |
| `operating_cashflow_to_profit_history` 连续 2 期 `< 0.8` | 自动化 | 第一版必须实现 |
| 收入增长但营销投入显著上升且利润率恶化 | 手工/半自动 | 先作为 `warnings` 或 `risks` 文本，不先做硬拦截 |
| 用户增长放缓且估值分位仍高 | 手工/半自动 | 先作为研究备注，不先做硬拦截 |
| 核心业务现金牛转弱但新业务亏损扩大 | 手工/半自动 | 第一版不自动化 |

#### 3.7.6 输出解释模板

平台互联网第一版输出时，建议优先解释：

- 增长有没有兑现成利润
- 利润有没有兑现成现金流
- 当前估值是否仍要求高增长持续

如果手工字段不足，宁可明确写“缺少用户/营销效率字段”，也不要伪造结论。

## 4. 子模型二：半导体与电子硬科技

### 4.1 适用对象

- 中芯国际港股
- 兆易创新
- 鸿腾精密

### 4.2 核心矛盾

半导体与电子硬科技的关键是：

- 周期下行时库存和资本开支会先出问题
- 周期上行时利润很好看，但不能只看单年利润弹性
- 订单和库存才是最早的拐点信号之一

### 4.3 建议维度权重

- 成长与景气度：`25`
- 盈利质量：`25`
- 营运与库存周期：`30`
- 估值匹配：`20`

### 4.4 建议优先指标

- `revenue_growth`
- `net_profit_growth`
- `gross_margin`
- `inventory_growth`
- `accounts_receivable_growth`
- `operating_cashflow_to_profit`
- `pe_percentile_5y`

建议新增字段：

- `inventory_turnover_days_trend`
- `capex_growth`
- `capacity_utilization`
- `order_backlog_growth`
- `wafer_price_trend` 或产品 ASP 趋势

### 4.5 建议红线

- `inventory_growth > revenue_growth + 15%` 连续 2 期
- `accounts_receivable_growth > revenue_growth + 15%` 连续 2 期
- 毛利率下滑且资本开支仍在高位
- 经营现金流明显弱于利润增长

### 4.6 估值说明

半导体估值可以高，但必须和景气拐点、库存周期一起看。

因此：

- `peg` 可用，但不应单独决定结论
- `pe_percentile_5y` 要结合行业景气位置判断

### 4.7 第一版评分参数表

半导体与电子硬科技第一版的重点是把“库存周期”和“利润兑现质量”从通用模型里单独抬出来。

#### 4.7.1 模型标识

| 项目 | 参数 |
| --- | --- |
| `industry_bucket` | `technology` |
| `submodel_id` | `semiconductor_hardtech_v1` |
| 适用标的 | 中芯国际港股、兆易创新、鸿腾精密 |
| 第一版定位 | 科技主模型 |
| 默认输出风格 | 周期位置 + 库存质量 + 现金流兑现 |

#### 4.7.2 字段分层

| 分层 | 字段 |
| --- | --- |
| `required_core` | `symbol`、`name`、`market`、`report_period`、`currency`、`source`、`updated_at`、`roe`、`roe_3y_cv`、`operating_cashflow_to_profit`、`revenue_growth`、`net_profit_growth`、`accounts_receivable_growth`、`inventory_growth`、`pe_percentile_5y` |
| `optional_manual` | `gross_margin`、`dupont_driver`、`order_backlog_growth`、`capacity_utilization`、`capex_growth`、`wafer_price_trend` |
| `deferred_v2` | `inventory_growth_history`、`accounts_receivable_growth_history`、`gross_margin_trend`、`order_backlog_history` |

第一版半导体模型和平台互联网最大的不同是：

- `inventory_growth` 必须保留
- `accounts_receivable_growth` 必须保留
- `peg` 可以先降为可选，而不是硬依赖

#### 4.7.3 维度参数

| 维度 | 权重 | 第一版主字段 | 第一版实现口径 |
| --- | --- | --- | --- |
| 成长与景气度 | `25` | `revenue_growth`、`net_profit_growth`、`order_backlog_growth` | 第一版至少使用营收和利润；订单字段缺失时不阻塞 |
| 盈利质量 | `25` | `roe`、`roe_3y_cv`、`operating_cashflow_to_profit`、`gross_margin` | 第一版默认使用前三项，`gross_margin` 有则增强解释 |
| 营运与库存周期 | `30` | `inventory_growth`、`accounts_receivable_growth`、`revenue_growth` | 第一版必须实现这一维；相对压力计算优先于绝对值 |
| 估值匹配 | `20` | `pe_percentile_5y`、`peg` | 第一版至少使用 `pe_percentile_5y`，`peg` 缺失时允许降级 |

#### 4.7.4 第一版规则覆盖

| 规则项 | 半导体第一版处理 |
| --- | --- |
| `inventory_growth` | 必须进入主评分和风险提示 |
| `accounts_receivable_growth` | 必须进入主评分和风险提示 |
| `debt_to_asset` | 第一版不作为硬依赖 |
| `gross_margin` | 第一版可选增强项；有值则优先写入解释 |
| `peg` | 第一版允许缺失，但若存在则参与估值匹配 |
| `operating_cashflow_to_profit_history` | 可复用通用自动化红线，但不是半导体模型唯一重点 |

#### 4.7.5 第一版红线参数

| 红线 | 类型 | 第一版实现建议 |
| --- | --- | --- |
| `inventory_growth > revenue_growth + 15%` | 自动化单期风险提示 | 第一版先做单期风险提示，不强依赖历史数组 |
| `accounts_receivable_growth > revenue_growth + 15%` | 自动化单期风险提示 | 第一版先做单期风险提示，不强依赖历史数组 |
| 毛利率下滑且资本开支仍高位 | 手工/半自动 | 第一版写成 `warnings`，第二阶段再自动化 |
| 经营现金流明显弱于利润增长 | 自动化 | 可直接基于 `operating_cashflow_to_profit` 与利润增速输出风险 |

#### 4.7.6 输出解释模板

半导体第一版输出时，建议优先解释：

- 收入增长是否伴随库存和应收同步失真
- 周期位置是否支持当前估值分位
- 利润改善是否已经被现金流验证

如果没有订单、产能利用率、ASP 等高级字段，结论要明确标注为“周期信息不完整”。

## 5. 子模型三：工业自动化与智能装备

### 5.1 适用对象

- 汇川技术
- 吉利，若后续定义为“智能电动化装备链核心标的”时可归入此扩展组
- 中航科工，若按高端装备与军工制造链观察，可放在此扩展组而非纯科技

### 5.2 核心矛盾

这类公司介于制造和科技之间，不能只按互联网或半导体的逻辑看。

真正要看的是：

- 订单能不能持续
- 下游资本开支是否支撑增长
- 应收、存货和现金流是否跟得上
- 是否具备技术壁垒和进口替代能力

### 5.3 建议维度权重

- 盈利质量：`25`
- 成长能力：`25`
- 订单与营运健康：`30`
- 估值匹配：`20`

### 5.4 建议优先指标

- `revenue_growth`
- `net_profit_growth`
- `roe`
- `operating_cashflow_to_profit`
- `accounts_receivable_growth`
- `inventory_growth`

建议新增字段：

- `order_backlog_growth`
- `book_to_bill_ratio`
- `capex_of_downstream_trend`
- `export_growth`
- `rd_expense_ratio`

### 5.5 建议红线

- `accounts_receivable_growth > revenue_growth + 15%` 连续 2 期
- `inventory_growth > revenue_growth + 15%` 连续 2 期
- 订单增速下滑但产能和费用仍在扩张
- 利润增长明显快于经营现金流增长

### 5.6 关于吉利和中航科工

这两只不是“纯科技”，但也不能粗暴归到传统周期或纯消费：

- 吉利更像“智能电动化制造 + 汽车科技链”
- 中航科工更像“高端装备制造 + 军工科技链”

第一阶段若只做纯科技核心模型，建议把它们先标为：

- `tech_adjacent_industrial`

也就是“科技相邻行业”，先不纳入最先落地的科技评分内核。

## 6. 子模型四：游戏与数字内容

### 6.1 适用对象

- 三七互娱

### 6.2 核心矛盾

游戏和数字内容公司不是典型平台互联网，也不是传统制造科技。核心看的是：

- 新产品周期是否接续
- 买量投放是否高效
- 收入和利润是否可持续
- 现金流是否扎实

### 6.3 建议维度权重

- 现金流与利润兑现：`30`
- 成长能力：`25`
- 产品周期与运营质量：`25`
- 估值匹配：`20`

### 6.4 建议优先指标

- `revenue_growth`
- `net_profit_growth`
- `operating_cashflow_to_profit`
- `roe`
- `dividend_yield`

建议新增字段：

- `new_game_pipeline_strength`
- `marketing_expense_ratio`
- `deferred_revenue_growth`
- `overseas_revenue_growth`

### 6.5 建议红线

- 利润增长但经营现金流走弱
- 新品流水不及预期而买量上升
- 海外增长放缓且老产品流水下行
- 高分红维持但产品储备不足

## 7. 你提到标的的归类建议

以下是按第一阶段文档口径给出的建议归类，不是永久结论，而是为了后续实现先稳定一版行业桶。

| 标的 | 建议归类 | 第一阶段处理建议 |
| --- | --- | --- |
| 美团 | 平台互联网 | 直接纳入科技主模型 |
| 腾讯 | 平台互联网 | 直接纳入科技主模型 |
| 快手 | 平台互联网 | 直接纳入科技主模型 |
| 阿里 | 平台互联网 | 直接纳入科技主模型 |
| 中芯国际港股 | 半导体与电子硬科技 | 直接纳入科技主模型 |
| 兆易创新 | 半导体与电子硬科技 | 直接纳入科技主模型 |
| 鸿腾精密 | 半导体/电子硬科技偏硬件链 | 纳入科技主模型，偏硬件口径 |
| 汇川技术 | 工业自动化与智能装备 | 纳入科技扩展子模型 |
| 三七互娱 | 游戏与数字内容 | 纳入科技扩展子模型 |
| 吉利 | 科技相邻行业：智能电动化制造 | 第一阶段暂不放入科技主模型 |
| 中国电信港股 | 数字基础设施/通信运营 | 不建议先归入科技主模型 |
| 太阳能 | 新能源运营或设备链，视具体公司业务 | 更接近新能源，不先归科技 |
| 中航科工 | 高端装备制造/军工科技链 | 先放科技相邻行业 |

## 8. 关于几只边界模糊标的的判断

### 8.1 中国电信港股

它有数字基础设施和云业务属性，但本质上更接近：

- 通信运营商
- 高股息央企
- 数字基础设施资产

所以第一阶段不建议直接放进“科技主模型”，更适合后续单独建一个：

- `digital_infra`

### 8.2 太阳能

这类公司需要先分清：

- 是光伏设备制造
- 还是电站运营
- 还是新能源投资平台

如果是电站运营，核心更像公用事业与新能源资产，而不是科技。

所以第一阶段建议：

- 默认不归科技

### 8.3 中航科工

它具备科技与高端装备属性，但盈利与订单逻辑更接近：

- 高端制造
- 军工装备链

因此第一阶段建议放入：

- `tech_adjacent_industrial`

而不是纯科技。

## 9. 第一阶段实现优先级

基于你当前持仓和历史持仓，我建议科技子模型实现顺序按这个来：

1. 平台互联网
2. 半导体与电子硬科技
3. 工业自动化与智能装备
4. 游戏与数字内容

这样一来，先能覆盖：

- 美团
- 腾讯
- 快手
- 中芯国际
- 兆易创新
- 鸿腾精密
- 汇川技术
- 三七互娱

## 10. 当前建议结论

如果只说结论：

- 科技行业必须再细分
- 第一阶段科技主模型先做“平台互联网 + 半导体硬科技”最划算
- 汇川技术和三七互娱可以作为第二层科技扩展子模型
- 吉利、中国电信、太阳能、中航科工先不要硬塞进纯科技桶