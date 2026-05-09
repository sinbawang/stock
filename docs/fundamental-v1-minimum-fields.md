# 基本面第一版最小字段集 v0.1

这份文档用于回答一个非常具体的问题：

- 如果下一步开始实现基本面代码，第一版到底必须先支持哪些字段？
- 哪些字段第一版可以先允许手工填写？
- 哪些字段明确推迟到第二阶段，不要一开始就把实现范围做大？

这份文档不是替代 [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md)，而是把其中“建议字段”进一步压缩成“第一版可开工字段边界”。

## 1. 使用原则

第一版字段集遵循三个原则：

- 先保证通用评分骨架能跑通
- 先覆盖科技主模型的共性需求，尤其是平台互联网和半导体硬科技
- 先允许少量人工/半人工字段，不为了全自动而阻塞评分引擎落地

换句话说，第一版追求的是：

- 能输入一份 JSON
- 能输出总分、评级、优势、风险、缺失项
- 能支撑通用模型和科技主模型的第一轮实现

而不是：

- 一开始就把所有行业字段都做齐
- 一开始就自动化连续两期、三期的全部趋势分析
- 一开始就依赖完整财报抓取链路

## 2. 第一版字段分层

建议把字段分成三层：

- `required_core`: 第一版代码必须支持
- `optional_manual`: 第一版可支持，但允许手工填写或缺失
- `deferred_v2`: 明确推迟到第二阶段

## 3. `required_core`：第一版必须支持

### 3.1 标识与口径字段

以下字段建议作为第一版必需字段：

- `symbol`
- `name`
- `market`
- `report_period`
- `currency`
- `source`
- `updated_at`

这些字段的作用不是评分，而是保证：

- 快照可追踪
- 输出结果可定位
- 后续接数据源时不会丢失口径信息

### 3.2 第一版主评分字段

以下字段建议作为第一版主评分必需字段：

- `roe`
- `roe_3y_cv`
- `operating_cashflow_to_profit`
- `revenue_growth`
- `net_profit_growth`
- `debt_to_asset`
- `accounts_receivable_growth`
- `inventory_growth`
- `pe_percentile_5y`
- `peg`

这 10 个字段已经能覆盖当前通用四维评分的主体：

- 盈利质量：`roe`、`roe_3y_cv`、`operating_cashflow_to_profit`
- 成长兑现：`revenue_growth`、`net_profit_growth`
- 资产负债与营运健康：`debt_to_asset`、`accounts_receivable_growth`、`inventory_growth`
- 估值与匹配度：`pe_percentile_5y`、`peg`

### 3.3 第一版自动化红线最小支持

如果第一版希望至少自动支持一条“连续两期红线”，建议先保留：

- `operating_cashflow_to_profit_history`

原因：

- 它已经出现在现有文档里
- 对平台互联网、游戏内容、一般成长股都通用
- 自动化价值高，新增复杂度最低

第一版若只自动化这一条红线，也是可接受的。

## 4. `optional_manual`：第一版允许手工或缺失

以下字段建议第一版先作为可选字段，不要求自动抓取齐全。

### 4.1 评分增强字段

- `dupont_driver`
- `guidance_attainment`

原因：

- 这两个字段很有价值
- 但第一版完全自动化获取成本偏高
- 更适合作为手工补充、研究备注或半自动录入字段

第一版处理原则建议为：

- 有值则参与打分
- 缺失则记入 `missing_metrics`
- 缺失时不报错、不伪造默认值

### 4.2 科技子模型增强字段

以下字段第一版建议允许存在，但不作为基础评分引擎的硬依赖：

- `gross_margin`
- `rd_expense_ratio`
- `deferred_revenue_growth`
- `order_backlog_growth`
- `marketing_expense_ratio`

原因：

- 它们对科技子模型很重要
- 但不适合作为第一版通用引擎的开工门槛
- 更适合在科技主模型或扩展子模型实现时逐步接入

## 5. `deferred_v2`：明确推迟到第二阶段

以下字段建议明确推迟，不要在第一版实现时一起背上。

### 5.1 通用但非第一版刚需字段

- `market_cap`
- `pe_ttm`
- `pb`
- `ps_ttm`
- `dividend_yield`
- `current_ratio`
- `roe_3y_mean`
- `net_margin`

不是说这些字段不重要，而是：

- 第一版主评分并不依赖它们全部到位
- 有些字段行业解释力差异较大
- 太早纳入只会扩大口径讨论范围

### 5.2 自动化多期趋势字段

以下内容建议第二阶段再正式建模：

- `revenue_growth_history`
- `accounts_receivable_growth_history`
- `inventory_growth_history`
- `interest_bearing_debt_growth_history`
- `operating_cashflow_growth_history`

这组字段的主要用途是把以下红线真正自动化：

- 应收连续两期高于营收增速
- 存货连续两期高于营收增速
- 有息负债连续两期快于经营现金流增长

当前文档已经明确这些规则有价值，但第一版不必为了它们阻塞编码。

## 6. 第一版推荐最小 JSON

如果只看“能开工”的最小集合，推荐 JSON 至少包含以下字段：

```json
{
  "symbol": "03690",
  "name": "美团",
  "market": "HK",
  "report_period": "2025-12-31",
  "currency": "CNY",
  "source": "manual",
  "updated_at": "2026-05-09T20:30:00",
  "roe": 18.6,
  "roe_3y_cv": 0.18,
  "operating_cashflow_to_profit": 1.12,
  "operating_cashflow_to_profit_history": [1.12, 1.04],
  "revenue_growth": 21.3,
  "net_profit_growth": 33.8,
  "debt_to_asset": 42.5,
  "accounts_receivable_growth": 8.4,
  "inventory_growth": 10.1,
  "pe_percentile_5y": 41.0,
  "peg": 0.92,
  "dupont_driver": null,
  "guidance_attainment": null
}
```

这份最小 JSON 已经足够支撑：

- 第一版通用四维评分
- 一条自动化红线
- 两个手工增强字段占位

## 7. 第一版缺失字段处理约定

为避免实现时分歧，建议先把缺失策略写死：

- `required_core` 缺失：可以报校验错误，拒绝进入评分
- `optional_manual` 缺失：允许进入评分，但必须记录到 `missing_metrics`
- `deferred_v2` 缺失：第一版不校验、不影响评分

这样后续程序实现会很清晰：

- 模型校验和评分逻辑解耦
- 不会因为拿不到高级字段而整条链路卡死
- 也不会因为字段暂时缺失而偷偷补 `0`

## 8. 对应的第一版实现顺序

若按这份字段文档推进，建议实现顺序固定为：

1. 先实现 `required_core` 的数据模型校验
2. 再实现四维基础评分
3. 再实现 `operating_cashflow_to_profit_history` 的自动红线
4. 最后把 `dupont_driver`、`guidance_attainment` 接成可选增强项

这样能最快得到一套：

- 可跑
- 可测
- 可解释
- 不被字段完备性拖死

## 9. 当前建议结论

如果只说结论：

- 第一版先做 `10 + 1 + 2` 结构最稳
- 也就是 `10` 个主评分字段 + `1` 个历史数组字段 + `2` 个手工增强字段
- 其他多期趋势字段和行业专属字段明确放到第二阶段
- 先让评分引擎成立，再逐步补行业增强层