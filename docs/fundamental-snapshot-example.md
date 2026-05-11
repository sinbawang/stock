# 基本面快照输入样例 v0.1

这份文档定义当前项目统一采用的标准输入样例口径，目标是冻结字段名、单位和缺失值写法。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

如果要看“第一版代码最少要支持哪些字段”，请优先看 [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)。本文件展示的是标准快照样例，不等于第一版必须一次支持全部字段。

## 1. 标准 JSON 示例

```json
{
  "symbol": "03690",
  "name": "美团",
  "market": "HK",
  "report_period": "2025-12-31",
  "currency": "CNY",
  "source": "manual",
  "updated_at": "2026-05-09T20:30:00",
  "market_cap": 812500000000,
  "pe_ttm": 22.4,
  "pe_percentile_5y": 41.0,
  "pb": 4.1,
  "ps_ttm": 2.7,
  "peg": 0.92,
  "dividend_yield": 0.0,
  "roe": 18.6,
  "roe_3y_mean": 17.2,
  "roe_3y_cv": 0.18,
  "dupont_driver": "margin_turnover",
  "gross_margin": 37.1,
  "net_margin": 11.2,
  "revenue_growth": 21.3,
  "net_profit_growth": 33.8,
  "debt_to_asset": 42.5,
  "current_ratio": 1.68,
  "operating_cashflow_to_profit": 1.12,
  "operating_cashflow_to_profit_history": [1.12, 1.04, 0.96],
  "accounts_receivable_growth": 8.4,
  "inventory_growth": 10.1,
  "interest_bearing_debt_growth": 5.3,
  "operating_cashflow_growth": 18.7,
  "guidance_attainment": "meet"
}
```

这份样例仍以平台互联网为主，因为它最适合展示宽口径字段全集。当前代码里，金融、公用事业、数字基础设施等子模型会在这份宽口径快照之上，只使用各自需要的字段子集。

## 2. 字段说明

- `symbol`: 证券代码，不带市场前缀时也允许，但同一批处理中应统一
- `name`: 证券名称
- `market`: 市场，例如 `CN`、`HK`
- `report_period`: 财报期末日期
- `currency`: 财务指标对应币种
- `source`: 数据来源
- `updated_at`: 快照生成时间

财务指标：

- `market_cap`: 总市值
- `pe_ttm`: 市盈率 TTM
- `pe_percentile_5y`: PE 历史分位
- `pb`: 市净率
- `ps_ttm`: 市销率 TTM
- `peg`: PEG
- `dividend_yield`: 股息率，百分比口径
- `roe`: 净资产收益率，百分比口径
- `roe_3y_mean`: 近 3 年平均 ROE
- `roe_3y_cv`: 近 3 年 ROE 变异系数
- `dupont_driver`: DuPont 驱动类型
- `gross_margin`: 毛利率，百分比口径
- `net_margin`: 净利率，百分比口径
- `revenue_growth`: 营收同比增速，百分比口径
- `net_profit_growth`: 净利润同比增速，百分比口径
- `debt_to_asset`: 资产负债率，百分比口径
- `current_ratio`: 流动比率，倍数口径
- `operating_cashflow_to_profit`: 经营现金流 / 净利润，倍数口径
- `operating_cashflow_to_profit_history`: 最近多期经营现金流 / 净利润
- `accounts_receivable_growth`: 应收同比增速，百分比口径
- `inventory_growth`: 存货同比增速，百分比口径
- `interest_bearing_debt_growth`: 有息负债同比增速，百分比口径
- `operating_cashflow_growth`: 经营现金流同比增速，百分比口径
- `guidance_attainment`: 指引兑现度，例如 `beat`、`meet`、`miss`

## 3. 缺失值写法

缺失值统一使用 `null`，不要用：

- 空字符串
- `-`
- `N/A`
- `0` 来冒充缺失

示例：

```json
{
  "symbol": "00700",
  "name": "腾讯",
  "market": "HK",
  "report_period": "2025-12-31",
  "currency": "CNY",
  "source": "manual",
  "updated_at": "2026-05-09T20:30:00",
  "market_cap": 4150000000000,
  "pe_ttm": 18.2,
  "pe_percentile_5y": null,
  "pb": 3.6,
  "ps_ttm": null,
  "peg": null,
  "dividend_yield": 1.1,
  "roe": 21.4,
  "roe_3y_mean": 20.1,
  "roe_3y_cv": null,
  "dupont_driver": null,
  "gross_margin": null,
  "net_margin": 31.7,
  "revenue_growth": 10.4,
  "net_profit_growth": 18.9,
  "debt_to_asset": 46.2,
  "current_ratio": 1.32,
  "operating_cashflow_to_profit": 1.05,
  "operating_cashflow_to_profit_history": [1.05, 0.98, null],
  "accounts_receivable_growth": null,
  "inventory_growth": null,
  "interest_bearing_debt_growth": null,
  "operating_cashflow_growth": 12.8,
  "guidance_attainment": null
}
```

## 4. 口径提醒

- 百分比字段直接写数值，不带 `%`
- 不同来源如果币种不同，必须显式写 `currency`
- 若 `report_period` 与 `updated_at` 不一致，不视为错误，前者是财报期，后者是快照生成时间
- 若字段来自 TTM 而不是年报，使用已有 `period_type` 扩展字段标注口径
- 多期字段若长度不足 2，不应参与“连续两期红线”判断
- `dupont_driver` 和 `guidance_attainment` 第一阶段可允许人工填写

## 5. 扩展字段预留

以下字段不要求在第一阶段实现，但建议保留扩展空间：

- `period_type`: `annual`、`ttm`、`quarterly_annualized`
- `industry`: 行业分类
- `notes`: 人工备注
- `raw_payload_ref`: 原始数据引用或缓存路径

其中 `period_type`、`industry`、`notes`、`raw_payload_ref` 在当前 `FundamentalSnapshot` 模型里已经预留。

另外，当前模型也已经预留或实际使用了更多行业专属字段，例如：

- 银行：`core_tier1_ratio`、`npl_ratio`、`provision_coverage_ratio`、`loan_deposit_growth_gap`、`net_interest_margin`
- 保险：`solvency_adequacy_ratio`、`combined_ratio`、`investment_return`、`embedded_value_growth`、`new_business_value_growth`
- 券商：`net_capital_ratio`

这些字段不必出现在所有样例里，但它们已经属于统一快照模型的一部分。

## 6. 第一阶段输入约束

第一阶段只要求：

- 能读取单个 JSON 快照
- 字段名与本文件一致
- 缺失值使用 `null`
- 百分比和倍数单位符合本文件定义

达到这个约束后，就可以开始写评分引擎，而无需等所有数据源接好。

## 7. 第一版最小输入提醒

如果只是启动第一版评分引擎实现，不必等待本文件中的全部字段齐备。

第一版建议至少具备：

- 标识字段：`symbol`、`name`、`market`、`report_period`、`currency`、`source`、`updated_at`
- 主评分字段：`roe`、`roe_3y_cv`、`operating_cashflow_to_profit`、`revenue_growth`、`net_profit_growth`、`debt_to_asset`、`accounts_receivable_growth`、`inventory_growth`、`pe_percentile_5y`、`peg`
- 一个自动化历史字段：`operating_cashflow_to_profit_history`
- 两个可选增强字段：`dupont_driver`、`guidance_attainment`

完整字段分层定义见 [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)。