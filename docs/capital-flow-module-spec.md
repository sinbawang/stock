# 资金面模块设计规格 v0.1

这份文档用于定义“资金面分析模块要做什么、输入输出是什么、边界在哪里”，作为后续实现代码的依据。

项目现有两条分析主线：

- 技术面：回答走势结构、位置、级别和风险点
- 基本面：回答公司质量、成长、估值和经营风险

资金面模块作为第三条并列主线，主要回答：

- 当前是否有资金参与
- 资金参与是连续性的，还是单日脉冲
- 资金方向是否确认技术面信号
- 是否存在短期拥挤、放量滞涨、通道资金反向等风险

## 1. 模块目标

第一阶段目标不是建立完整微观交易系统，而是建立一套可解释、可测试、可与技术面和基本面联动的资金面骨架。

V1 聚焦以下能力：

- 把来自不同数据源的资金指标统一成标准快照
- 对资金方向、持续性、量能确认、通道线索、过热风险做规则化打分
- 输出可读的资金面优势、风险、缺失项和综合判断
- 为后续“技术面 + 基本面 + 资金面”联合分析提供标准接口

第一阶段不追求：

- 逐笔成交还原
- 高频盘口建模
- 机构席位穿透识别
- 资金流指标的绝对真值判断
- 自动交易或投资建议生成

## 2. 模块边界

资金面模块只负责三件事：

- 接收已经整理好的资金指标
- 生成标准化资金面快照
- 产出评分结果和解释文本

以下内容暂不纳入模块核心：

- Cookie、验证码、登录态对抗
- 多源资金流口径校准的复杂 ETL
- 逐笔、Level-2、席位明细的商业数据适配
- 自动下单、仓位执行和风控撮合

## 3. 使用场景

### 3.1 单标的资金面体检

输入某个交易日或最近窗口的资金指标，输出：

- 总分
- 分项分数
- 评级
- 优势
- 风险
- 缺失项提示

### 3.2 技术面信号确认

当缠论结构给出观察结论时，资金面模块用于判断：

- 技术面买点是否有资金持续确认
- 技术面破位是否伴随资金放量流出
- 放量上涨是健康推动，还是短期拥挤
- 缩量回调是否仍有通道资金维持

### 3.3 候选池排序

对一组股票批量输出资金面状态，用于配合技术面结构筛选和基本面过滤。

## 4. 领域模型

### 4.1 `CapitalFlowSnapshot`

单个标的在某个交易日或窗口的资金面标准快照，是评分引擎的直接输入。

通用字段：

- `symbol`: 标的代码，例如 `03690`、`00700`、`300124`
- `name`: 标的名称
- `market`: 市场标识，例如 `CN`、`HK`
- `trade_date`: 交易日期
- `source`: 数据来源，例如 `eastmoney`、`akshare`、`manual`
- `updated_at`: 快照更新时间

成交与量能字段：

- `turnover`: 成交额
- `turnover_rate`: 换手率，百分比数值
- `volume_ratio`: 量比
- `amount_ratio_5d`: 成交额相对 5 日均值倍数

A 股资金流字段：

- `main_net_inflow`: 当日主力净流入
- `main_net_inflow_3d`: 3 日主力净流入
- `main_net_inflow_5d`: 5 日主力净流入
- `main_net_inflow_10d`: 10 日主力净流入
- `super_large_net_inflow`: 超大单净流入
- `large_order_net_inflow`: 大单净流入
- `medium_order_net_inflow`: 中单净流入
- `small_order_net_inflow`: 小单净流入
- `margin_balance_change`: 融资余额变化
- `northbound_holding_change`: 北向持股变化

港股资金流字段：

- `southbound_net_buy`: 南向净买入
- `southbound_holding_change`: 南向持股变化
- `short_sell_ratio`: 沽空比例
- `short_sell_turnover`: 沽空成交额

当前 HK V1 已接入六类公开数据：港股通成份行情用 `turnover` / `turnover_rate` 提供成交额和换手率量能线索，东方财富港股 1 分钟历史用于计算 `volume_ratio`，东方财富港股日线历史用于计算 `amount_ratio_5d`，东方财富港股通个股成交榜历史用 `southbound_net_buy` 提供个股南向净买额，沪深港通持股统计用 `southbound_holding_change` 提供 1 日南向持股市值变化，HKEX 日终沽空统计用 `short_sell_turnover` 提供沽空成交额；当成交额可用时，用 `short_sell_turnover / turnover * 100` 派生 `short_sell_ratio`。其中 `volume_ratio` 的当前口径是“最近 5 个交易日同一时刻的分钟成交量对比”，`amount_ratio_5d` 的当前口径是“当日成交额 / 最近 5 日平均成交额”。缓存文件分别为 `data/_meta/capital_flow_cache/hk_eastmoney_hk_connect_components.csv`、`data/_meta/capital_flow_cache/hk_eastmoney_hk_minute_hist_<symbol>.csv`、`data/_meta/capital_flow_cache/hk_eastmoney_hk_daily_hist_<symbol>.csv`、`data/_meta/capital_flow_cache/hk_eastmoney_southbound_net_buy_<symbol>.csv`、`data/_meta/capital_flow_cache/hk_eastmoney_southbound_holding.csv` 和 `data/_meta/capital_flow_cache/hk_hkex_short_selling_turnover.csv`。其中个股南向净买额只在标的进入港股通成交榜的交易日可用，因此缺失时应回退到南向持股变化与量能/沽空线索，而不是把缺失误判为净流出。

事件字段：

- `dragon_tiger_flag`: 是否出现龙虎榜等异常交易事件
- `block_trade_flag`: 是否出现大宗交易事件
- `notes`: 口径说明或手工补充

### 4.2 `CapitalFlowScoreCard`

评分引擎输出的结构化结果，用于 CLI、报告、后续联合分析。

建议字段：

- `symbol`
- `name`
- `market`
- `trade_date`
- `total_score`: 总分，范围 `0-100`
- `rating`: 评级，例如 `A/B/C/D`
- `red_flag`: 是否命中红线
- `dimension_scores`: 各维度分数
- `strengths`: 优势列表
- `risks`: 风险列表
- `warnings`: 口径或缺失提示
- `missing_metrics`: 缺失指标列表
- `triggered_rules`: 命中规则明细
- `combined_comment`: 面向报告层的综合说明

### 4.3 `CapitalFlowDimensionScore`

用于描述单个维度打分结果。

建议字段：

- `dimension`: 维度名
- `score`: 当前维度得分
- `weight`: 维度权重
- `max_score`: 维度最高分
- `score_basis`: 简短解释
- `used_metrics`: 参与评分的指标
- `missing_metrics`: 缺失指标
- `passed_rules`: 正向规则
- `failed_rules`: 负向规则

## 5. V1 评分维度

V1 建议先使用五个维度，总分 100。

### 5.1 `flow_direction` 资金方向，权重 25

关注主力、南向、北向等关键资金是否净流入。

典型正向信号：

- 当日主力净流入为正
- 多日净流入为正
- 南向或北向持仓增加

典型风险信号：

- 当日与多日净流入均为负
- 大单流出，小单流入

### 5.2 `flow_persistence` 资金持续性，权重 20

关注资金流入是否持续，而不是单日脉冲。

典型正向信号：

- 3 日、5 日、10 日窗口持续净流入
- 当日流入与中短期流入方向一致

典型风险信号：

- 当日大幅流入但 5 日、10 日仍为净流出
- 单日放量后缺少持续性

### 5.3 `volume_confirmation` 量能确认，权重 20

关注成交额、换手率、量比是否支持资金判断。

典型正向信号：

- 成交额温和放大
- 量比改善但不过热

典型风险信号：

- 放量滞涨
- 突然极端放量但资金净流出

当前实现口径：

- CN：`volume_ratio` 在 `1.0-2.5` 记作“量比温和放大”，`amount_ratio_5d` 在 `1.0-2.5` 记作“成交额温和放大”
- HK：`volume_ratio` 在 `1.0-3.2` 记作“量比温和放大”，`amount_ratio_5d` 在 `1.0-3.0` 记作“成交额温和放大”
- 该差异用于反映港股分钟量能波动通常高于 A 股、但仍不希望把极端脉冲误判为正向确认

### 5.4 `institutional_hint` 通道与机构线索，权重 20

关注北向、南向、融资余额、沽空比例等相对机构化的线索。

典型正向信号：

- 北向或南向持股增加
- 融资余额温和增加且价格趋势配合

典型风险信号：

- 港股沽空比例偏高
- 通道资金与价格方向背离

### 5.5 `overheat_risk` 过热风险，权重 15

关注资金拥挤、短线亢奋、异常事件扰动。

典型风险信号：

- 量比极高
- 换手率异常高
- 龙虎榜或大宗交易事件带来短期扰动

当前实现口径：

- CN：`volume_ratio >= 5.0` 视为“量比极端放大”
- HK：`volume_ratio >= 6.0` 视为“量比极端放大”
- `turnover_rate >= 15` 仍统一视为偏高换手风险，后续如发现 HK 样本分布显著不同，再单独拆市场阈值

## 6. 数据口径约定

- 比率类指标统一使用百分比数值，不带 `%` 符号，例如 `12.5` 表示 `12.5%`
- 净流入、成交额等金额类指标保留原始数值，评分阶段只比较正负和相对方向
- 缺失不等于 0，缺失字段不能强行参与打分
- 不同数据源的“主力资金”口径可能不同，必须在 `source` 或 `warnings` 中保留来源说明
- 资金流指标只作为确认信号，不直接生成买卖建议
- `*.fallback` 低置信度来源只作为观察线索，评分阶段按保守系数折减，避免用替代口径给出过强确认

## 7. 与联合分析的关系

后续联合分析建议升级为：

1. 技术面观察
2. 基本面体检
3. 资金面确认
4. 综合结论

资金面在联合结论中的定位：

- 技术面有买点 + 基本面不差 + 资金持续流入：确认度提高
- 技术面有买点 + 资金持续流出：降低信号质量
- 技术面破位 + 资金放量流出：风险确认
- 基本面较好 + 资金未明显参与：适合观察，不急于确认

## 8. 第一阶段落地顺序

建议按以下顺序推进：

1. 落 `CapitalFlowSnapshot`、`CapitalFlowScoreCard`、`CapitalFlowDimensionScore`，已完成
2. 落一个可对手工快照评分的 `analyze_capital_flow_snapshot(...)`，已完成
3. 落资金面文本报告渲染，已完成
4. 对 A 股优先接入公开资金流数据源，已完成初版，主资金流来自东方财富个股资金流接口，成交额和换手率来自 AkShare 日线历史
5. 为 A 股资金流增加本地缓存回退，已完成初版，默认缓存目录为 `data/_meta/capital_flow_cache`
6. 增加 A 股低置信度 fallback，已完成初版，主源和缓存不可用时用同花顺资金净额替代主力净流入口径；同花顺 fallback 周期表会落地到 `data/_meta/capital_flow_cache`，后续远端失败时可继续回退到最近一次成功缓存
7. 增加 A 股第二 fallback 来源，已完成初版，同花顺不可用时用腾讯分笔成交的买盘成交金额减卖盘成交金额近似资金净额，并标记为低置信度口径
8. 为低置信度 fallback 增加评分降权，已完成初版，`*.fallback` 来源总分按 85% 保守折减，并在 warning 中标明
9. 对港股接入 HK V1 数据源，已完成初版，当前已覆盖港股通成份行情的成交额/换手率、港股 1 分钟历史量比、港股日线成交额均值、个股南向净买入、沪深港通持股统计的 1 日南向持股市值变化，以及 HKEX 日终沽空成交额，并支持本地缓存回退
10. 对港股继续提升量比/换手等阈值口径，按更多真实样本迭代市场特异性评分参数
11. 最后再接入联合分析服务