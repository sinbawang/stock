# 基本面模块设计规格 v0.1

这份文档用于先定义“基本面分析模块要做什么、输入输出是什么、边界在哪里”，作为后续实现代码的依据。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

如果只想抓主线，建议从这份文档开始，再按下面顺序继续：

- 字段边界: [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
- 数据源入口: [fundamental-data-source.md](fundamental-data-source.md)
- Python 模型: [fundamental-python-model-draft.md](fundamental-python-model-draft.md)
- 代码目录: [fundamental-code-layout-draft.md](fundamental-code-layout-draft.md)

如果后续要开始把这些领域对象落成 Python 类，数据模型草案见 [fundamental-python-model-draft.md](fundamental-python-model-draft.md)。

目标不是直接做成全自动财报系统，而是先建立一个可解释、可测试、可扩展的基本面分析骨架，并能和现有缠论技术面分析组合使用。

## 1. 模块目标

配套行业文档见 [fundamental-industry-layering.md](fundamental-industry-layering.md)。通用评分骨架在本文件定义，行业特化规则在行业文档定义。

基本面模块第一阶段聚焦以下问题：

- 把来自不同数据源的财务指标统一成同一份标准快照
- 对盈利、增长、杠杆、现金流、估值做规则化打分
- 输出可读的优势、风险、缺失项摘要
- 为后续“技术面 + 基本面”联动过滤提供标准接口

第一阶段不追求：

- 自动抓取所有财报字段
- 完整行业估值模型
- DCF、分部估值、因子回归等复杂模型
- 自动下单或投资建议生成

## 2. 模块边界

基本面模块只负责三件事：

- 接收已经整理好的指标数据
- 生成标准化基本面快照
- 产出评分结果和解释文本

以下内容暂不纳入模块核心：

- 数据源登录、Cookie 管理、验证码对抗
- 复杂财报清洗 ETL
- 公司公告文本抽取
- 宏观择时和行业轮动

也就是说，第一阶段先做“标准化分析内核”，不把代码绑定死在某一个抓数来源上。

## 3. 使用场景

### 3.1 单标的基本面体检

输入某个标的最近一个报告期的关键指标，输出：

- 总分
- 分项分数
- 评级
- 优势
- 风险
- 指标缺失提示

### 3.2 候选池过滤

对一组股票批量输出基本面评分，用于配合技术面结构筛选。

### 3.3 技术面结果二次确认

当缠论结构给出观察结论时，使用基本面模块判断该标的是否属于：

- 技术面成立且基本面良好
- 技术面成立但基本面一般
- 技术面成立但基本面明显偏弱

## 4. 领域模型

第一阶段建议围绕以下领域对象建模。

### 4.1 `FundamentalSnapshot`

单个标的在某个报告期的基本面标准快照，是评分引擎的直接输入。

第一版最小实现边界见 [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)。本节保留的是“建议字段全集”，不是第一版必须一步到位全部实现。

建议字段：

- `symbol`: 标的代码，例如 `03690`、`00700`、`300124`
- `name`: 标的名称
- `market`: 市场标识，例如 `CN`、`HK`
- `report_period`: 报告期，例如 `2025-12-31`
- `currency`: 财务币种，例如 `CNY`、`HKD`
- `source`: 数据来源，例如 `akshare`、`tushare`、`manual`
- `updated_at`: 快照更新时间

关键财务指标字段：

- `market_cap`: 总市值
- `pe_ttm`: 市盈率 TTM
- `pe_percentile_5y`: PE 历史分位
- `pb`: 市净率
- `ps_ttm`: 市销率 TTM
- `peg`: PEG
- `dividend_yield`: 股息率
- `roe`: 净资产收益率
- `roe_3y_mean`: 近 3 年平均 ROE
- `roe_3y_cv`: 近 3 年 ROE 变异系数
- `dupont_driver`: ROE 驱动类型，例如 `margin_turnover`、`mixed`、`leverage`
- `gross_margin`: 毛利率
- `net_margin`: 净利率
- `revenue_growth`: 营收同比增速
- `net_profit_growth`: 归母净利润同比增速
- `debt_to_asset`: 资产负债率
- `current_ratio`: 流动比率
- `operating_cashflow_to_profit`: 经营现金流 / 净利润
- `operating_cashflow_to_profit_history`: 最近多期经营现金流 / 净利润
- `accounts_receivable_growth`: 应收同比增速
- `inventory_growth`: 存货同比增速
- `interest_bearing_debt_growth`: 有息负债同比增速
- `operating_cashflow_growth`: 经营现金流同比增速
- `guidance_attainment`: 指引兑现度，例如 `beat`、`meet`、`miss`

如果后续要把“连续两期”红线全面自动化，建议第二阶段再补充以下多期字段：

- `revenue_growth_history`
- `accounts_receivable_growth_history`
- `inventory_growth_history`
- `interest_bearing_debt_growth_history`
- `operating_cashflow_growth_history`

### 4.2 `FundamentalScoreCard`

评分引擎输出的结构化结果，用于 CLI、报告、后续策略组合。

建议字段：

- `symbol`
- `report_period`
- `total_score`: 总分，范围建议为 `0-100`
- `rating`: 评级，例如 `A/B/C/D`
- `dimension_scores`: 各维度分数
- `strengths`: 优势列表
- `risks`: 风险列表
- `warnings`: 规则冲突或口径提示
- `missing_metrics`: 缺失指标列表

### 4.3 `FundamentalDimensionScore`

用于描述单个维度打分结果。

建议字段：

- `dimension`: 维度名
- `score`: 当前维度得分
- `weight`: 维度权重
- `passed_rules`: 命中的正向规则
- `failed_rules`: 命中的负向规则

## 5. 数据口径约定

### 5.1 指标单位

默认约定：

- 比率类指标统一使用百分比数值，不带 `%` 符号，例如 `18.6` 表示 `18.6%`
- 估值倍数类指标使用原始倍数，例如 `22.4`
- `operating_cashflow_to_profit` 为倍数，例如 `1.12`
- 市值保留原始数值，不在评分阶段强依赖单位换算

### 5.2 缺失值处理

- 缺失字段允许存在
- 缺失不等于 0
- 缺失字段不能强行参与打分
- 缺失项需要单独记录到 `missing_metrics`

### 5.3 报告期优先级

第一阶段默认使用“最近已披露年报或最近 12 个月口径”为主。

优先顺序建议：

1. 年报口径
2. TTM 口径
3. 单季年化口径

当多个口径混用时，需要在结果中显式记录。

### 5.4 第一版字段边界

为避免后续实现范围持续膨胀，第一版应遵循单独的最小字段集，而不是默认本文件出现过的字段都必须一次实现。

边界文件见 [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)。

执行口径建议固定为：

- 第一版必须实现：通用四维评分所需核心字段
- 第一版允许手工补充：`dupont_driver`、`guidance_attainment` 等增强字段
- 第二阶段再引入多期趋势数组和更多行业专属字段

## 6. 评分框架

第一阶段采用“维度分 + 权重汇总”的可解释评分，而不是黑盒模型。

建议总分为 `100` 分。若没有命中红线规则，再进入常规打分。

### 6.1 红线规则

红线规则用于拦截“总分可能不低，但质量已显著恶化”的标的。

建议口径：

- `operating_cashflow_to_profit` 连续 2 期 `< 0.8`
- `accounts_receivable_growth` 连续 2 期 `> revenue_growth + 15%`
- `inventory_growth` 连续 2 期 `> revenue_growth + 15%`
- `interest_bearing_debt_growth` 连续 2 期 `> operating_cashflow_growth + 20%`

只要命中任意一条：

- 直接附加 `red_flag=true`
- 评级上限降到最低风险档
- 输出结果中必须写明命中的红线条目

注意：

- 红线规则适合放在“风险拦截层”，不建议简单并入普通分数扣分
- “连续 2 期”要求输入必须是多期数据，不应由单期快照硬算

### 6.2 常规打分维度

你提供的四维框架比当前文档版更接近实盘使用，建议采用以下主结构：

- 盈利质量：`35`
- 成长兑现：`20`
- 资产负债与营运健康：`25`
- 估值与匹配度：`20`

这比原先的“五维平均拆法”更有优先级表达，尤其强化了现金流、营运质量和估值匹配。

## 7. 分维度打分规则

### 7.1 盈利质量 `35`

指标：

- `roe`
- `roe_3y_cv`
- `dupont_driver`
- `operating_cashflow_to_profit`

建议规则：

- `roe` 水平 `12` 分：
	- `roe <= 8`，记 `0` 分
	- `8 < roe < 12`，线性得分到 `7` 分
	- `12 <= roe < 20`，线性得分到 `12` 分
	- `roe >= 20`，记 `12` 分

- `roe_3y_cv` 稳定性 `8` 分：
	- `roe_3y_cv >= 0.5`，记 `0` 分
	- `0.2 < roe_3y_cv < 0.5`，线性得分到 `8` 分
	- `roe_3y_cv <= 0.2`，记 `8` 分

- `dupont_driver` 质量 `5` 分：
	- `margin_turnover`，记 `5` 分
	- `mixed`，记 `3` 分
	- `leverage`，记 `0` 分

- `operating_cashflow_to_profit` `10` 分：
	- `<= 0.6`，记 `0` 分
	- `0.6-1.0`，线性得分到 `8` 分
	- `1.0-1.5`，线性得分到 `10` 分
	- `>= 1.5`，记 `10` 分

### 7.2 成长兑现 `20`

指标：

- `revenue_growth`
- `net_profit_growth`
- `guidance_attainment`

建议规则：

- `revenue_growth` `8` 分：
	- `<= 0`，记 `0` 分
	- `0-20`，线性得分到 `8` 分
	- `>= 20`，记 `8` 分

- `net_profit_growth` `8` 分：
	- `<= 0`，记 `0` 分
	- `0-30`，线性得分到 `8` 分
	- `>= 30`，记 `8` 分

- `guidance_attainment` `4` 分：
	- `beat`，记 `4` 分
	- `meet`，记 `2` 分
	- `miss`，记 `0` 分

### 7.3 资产负债与营运健康 `25`

指标：

- `debt_to_asset`
- `accounts_receivable_growth`
- `inventory_growth`
- `revenue_growth`

建议规则：

- `debt_to_asset` `10` 分，非金融行业：
	- `>= 70`，记 `0` 分
	- `40-70`，线性得分到 `10` 分，越低越好
	- `<= 40`，记 `10` 分

- `应收压力` `7.5` 分：
	- 使用 `(accounts_receivable_growth - revenue_growth)` 作为相对压力
	- `>= 15`，记 `0` 分
	- `0-15`，线性得分到 `7.5` 分
	- `<= 0`，记 `7.5` 分

- `存货压力` `7.5` 分：
	- 使用 `(inventory_growth - revenue_growth)` 作为相对压力
	- `>= 15`，记 `0` 分
	- `0-15`，线性得分到 `7.5` 分
	- `<= 0`，记 `7.5` 分

### 7.4 估值与匹配度 `20`

指标：

- `pe_percentile_5y`
- `peg`

建议规则：

- `pe_percentile_5y` `10` 分：
	- `<= 25`，记 `10` 分
	- `25-75`，线性从 `10` 降到 `4`
	- `>= 75`，记 `0-4` 分，默认建议按 `2` 分处理

- `peg` `10` 分：
	- `<= 0.8`，记 `10` 分
	- `0.8-1.5`，线性从 `10` 降到 `6`
	- `1.5-2.0`，线性从 `6` 降到 `2`
	- `>= 2.0`，记 `0` 分

### 7.5 为什么不直接保留原文档中的 `gross_margin`、`net_margin`、`current_ratio`、`pb`、`dividend_yield`

它们不是没价值，而是建议改成：

- 作为补充字段保留在快照模型中
- 在行业特化模型中重新启用
- 不在第一版通用主评分里占主要权重

原因：

- `gross_margin`、`net_margin` 容易受到行业结构影响，跨行业通用阈值偏粗
- `current_ratio` 对轻资产平台型公司解释力有限
- `pb` 对高周转或轻资产企业常常不够稳定
- `dividend_yield` 更适合作为成熟稳健风格的加分项，而不是主驱动因子

## 8. 评级规则

建议按总分映射为四档：

- `A`: `80-100`，基本面优秀
- `B`: `65-79`，基本面良好
- `C`: `45-64`，基本面中性
- `D`: `0-44`，基本面偏弱

评级只表达“基于当前规则的质量判断”，不表达未来收益承诺。

## 9. 风险标记规则

除总分外，建议引入硬性风险标记。

在保留红线规则的前提下，还建议保留软风险标记。只要命中以下任一条件，就在结果中追加高风险提示：

- `revenue_growth < 0` 且 `net_profit_growth < 0`
- `debt_to_asset > 75`
- `operating_cashflow_to_profit < 0.5`
- `pe_ttm <= 0` 或 `peg >= 2.0`

这样可以避免“某些维度得分尚可，但关键财务质量明显恶化”被总分掩盖。

## 10. 对用户这版框架的评估结论

整体评价：方向是对的，而且明显强于单期静态打分模型。

建议保留的部分：

- 红线规则优先于总分
- 把 `经营现金流/净利润` 放进高权重区
- 用 `应收/存货相对营收增速` 识别伪增长
- 用 `PE 历史分位 + PEG` 替代单看绝对 PE
- 把 `ROE 稳定性` 和 `DuPont 质量` 纳入盈利质量维度

建议改进的部分：

- 连续 2 期规则必须显式依赖多期数据，不能靠单期快照伪装实现
- `指引兑现度`、`DuPont 质量` 暂时更适合人工录入或半自动输入，不适合作为第一版硬依赖字段
- `资产负债率` 必须按行业分层，金融、地产、保险不应套用同一阈值
- 仓位动作建议不要放在基础评分模型里硬编码，建议作为上层策略模块处理

不建议直接写死在第一版内核的内容：

- `加仓 +2%`、`减仓 -4%` 这类动作映射
- 所有行业共用同一套负债阈值
- 依赖分析师预期数据库才能跑起来的指标

## 11. 输出形式

第一阶段至少支持两种输出：

- 面向程序的结构化输出
- 面向人工检查的文本摘要

文本摘要建议包括：

- 标的名称和代码
- 报告期
- 总分与评级
- 各维度分数
- 3 条以内优势摘要
- 3 条以内风险摘要
- 缺失指标说明

## 12. 与技术面模块的关系

基本面模块不替代缠论模块，而是作为并列分析层。

后续组合关系建议为：

- 先用技术面给出结构结论
- 再用基本面判断标的质量
- 最终生成“结构成立，但是否值得重点观察”的联合结论

联合分析输出建议包含：

- `technical_view`
- `fundamental_rating`
- `fundamental_risks`
- `combined_comment`

## 13. 第一阶段交付范围

第一阶段只确认以下交付物：

- 基本面标准快照模型
- 可解释评分规则
- 风险标记规则
- 文本报告格式
- 与技术面联合分析的接口预留
- 支持人工输入的高级字段占位，如 `dupont_driver`、`guidance_attainment`

第一阶段不要求：

- 大规模数据抓取
- 行业差异化阈值
- 多报告期趋势分析
- 自动化图形展示
- 自动仓位管理动作

## 14. 后续迭代方向

第二阶段可继续扩展：

- 行业分层阈值
- 多期财务趋势评分
- 质量因子稳定性分析
- 财报日期与技术信号联动
- 基本面结果持久化到 CSV / JSON
- 与微信发送链路结合
- 金融行业专属评分模型
- 动作映射作为策略层单独模块

## 15. 与行业分层文档的关系

本文件负责定义：

- 通用字段
- 通用输出结构
- 通用红线容器
- 通用评分框架

行业文档 [fundamental-industry-layering.md](fundamental-industry-layering.md) 负责定义：

- 金融、科技、能源资源等行业的权重调整
- 指标启用与停用
- 阈值覆盖规则
- 行业专属红线

后续实现时，应优先遵循：

1. 通用结构来自本文件
2. 行业参数来自行业分层文件
3. 上层策略动作来自独立策略模块