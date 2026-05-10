# 港股保险 / 券商第二数据源方案

这份文档只回答一件事：

- 在当前公共港股源无法稳定覆盖保险 / 券商监管字段时，第二数据源应如何落地

如果需要回到数据源总说明，见 [fundamental-data-source.md](fundamental-data-source.md)。

## 1. 当前状态

当前仓库里，港股基本面公共抓取主入口仍是：

- [src/fundamental/data/hk_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/hk_snapshot_fetcher.py)

它已经能稳定给出：

- `roe`
- `revenue_growth`
- `net_profit_growth`
- `pe_ttm`
- `pe_percentile_5y`
- `pb`
- `ps_ttm`
- `operating_cashflow_to_profit_history`
- `accounts_receivable_growth`
- `inventory_growth`
- `dividend_yield`，当通用指标表或雪球 quote 能补到时

但对金融子模型来说，目前还不够。

## 2. 已验证结论

2026-05-10 的 live probe 已确认：

- `stock_financial_hk_analysis_indicator_em`
  和 `stock_hk_financial_indicator_em`
  对 `01339`、`06886` 只稳定提供通用盈利、估值、股息率字段
- 当前 public raw tables 里，没有稳定出现保险 / 券商一阶段模型需要的监管字段：
  - `solvency_adequacy_ratio`
  - `combined_ratio`
  - `embedded_value_growth`
  - `new_business_value_growth`
  - `net_capital_ratio`
- 这意味着当前问题不是“字段名没对上”，而是“主源本身就没把这些字段公开给当前接口”

同时还确认了两个重要细节：

- AkShare 提供的 `stock_financial_hk_report_em`、`stock_hk_dividend_payout_em` 在当前环境里会被代理影响，但它们对应的 Eastmoney 原始接口在 `requests.Session(trust_env=False)` 下是可访问的
- Eastmoney 的港股分红接口 `RPT_HKF10_MAIN_DIVBASIC` 可稳定返回 `01339`、`06886` 的分红方案文本，因此“二源”里至少可以把分红口径做得更扎实

## 3. 第二数据源目标

第二数据源不是为了替换现有主源，而是为了补两类能力：

### 3.1 先补可直接落地的字段

- 更稳定的 `dividend_yield` / 分红口径
- 对金融股年报 / 中报分红方案的结构化追踪

### 3.2 再补当前主源缺失的监管字段

保险优先补：

- `solvency_adequacy_ratio`
- `combined_ratio`
- `investment_return`
- `embedded_value_growth`
- `new_business_value_growth`

券商优先补：

- `net_capital_ratio`

## 4. 当前推荐方案

### 4.1 第一层：继续保留 Eastmoney / AkShare 主源

原因：

- 通用财务字段已经稳定
- 现有测试和评分链路都基于这层主源
- 不值得为了少量缺字段整体换源

### 4.2 第二层：新增“无代理 Eastmoney 原始接口”补充层

这层不应再走 AkShare 包装函数，而应在仓库里直接封装无代理请求，至少包括：

- 港股分红接口：`RPT_HKF10_MAIN_DIVBASIC`
- 港股原始财报表元数据接口：`RPT_CUSTOM_HKSK_APPFN_CASHFLOW_SUMMARY`
- 港股原始资产负债表：`RPT_HKF10_FN_BALANCE_PC`
- 港股原始利润表：`RPT_HKF10_FN_INCOME_PC`
- 港股原始现金流量表：`RPT_HKF10_FN_CASHFLOW_PC`

这层的用途不是盲目增加字段，而是：

- 先把二源请求能力和代理隔离做稳定
- 对保险 / 券商逐项验证“字段是否存在”
- 若字段存在，再把映射沉入 `hk_snapshot_fetcher.py`

### 4.3 第三层：公司披露 / 手工快照补充层

如果 public API 仍不给监管字段，就不要硬猜。

这时更现实的第二方案是：

- 允许对 `insurance_v1` / `broker_v1` 额外注入公司披露字段
- 来源可以是公告、年报、业绩发布会材料、公司 IR 摘要
- 先作为 `manual supplement` 进入 `FundamentalSnapshot`

这层适合承接：

- 保险公司的 `综合偿付能力充足率`
- `内含价值增长`
- `新业务价值增长`
- 券商的 `净资本相关监管指标`

## 5. 为什么不建议当前直接切到别的网站做主源

当前不建议直接把第二数据源主押在新的网页站点上，原因很简单：

- 还没有验证这些站点能稳定给到结构化监管字段
- 很多站点只给图表，不给可复用 API
- 增加反爬 / 登录 / 编码问题，会让主链路变脆

所以更合理的顺序是：

1. 先把 Eastmoney 原始接口在仓库内做无代理封装
2. 明确哪些字段真的存在，哪些字段根本不存在
3. 对仍不存在的字段，转向公告 / 手工快照补充方案

## 6. 对当前子模型的影响

### 6.1 `insurance_v1`

当前状态：

- mock / 单测链路已闭环
- live 公共源仍缺核心监管字段

短期建议：

- 保持严格必填，不要偷偷放宽 `solvency_adequacy_ratio`、`embedded_value_growth`、`new_business_value_growth`
- 真正缺字段时直接报缺失，这比伪造分析更安全

### 6.2 `broker_v1`

当前状态：

- mock / 单测链路已闭环
- live 公共源仍缺 `net_capital_ratio`

短期建议：

- 保持 `net_capital_ratio` 必填
- 在第二源接进来前，不要把 live 券商分析伪装成已闭环能力

## 7. 推荐实现顺序

建议按下面顺序继续：

1. 在 `hk_snapshot_fetcher.py` 旁边补无代理 Eastmoney 二源 helper
2. 先接港股分红接口，稳定补充金融股分红 / 股息口径
3. 对 `01339`、`06886` 的原始财报表做字段词典扫描，确认监管字段是否真的缺失
4. 若仍缺失，给 `insurance_v1` / `broker_v1` 设计 `manual supplement` 输入方案
5. 再决定是否需要第三方站点或公告解析

## 8. 当前最务实的下一步

如果继续编码，最值得先做的是：

- 在公共层新增港股分红二源 helper，并把代理隔离逻辑收口到仓库内
- 同时为保险 / 券商保留 `manual supplement` 方案，而不是继续假设 public API 很快会给出监管字段

这条路线的好处是：

- 有真实可交付增量
- 不会误判当前 public source 的能力边界
- 后续若接公告 / IR 摘要，也有明确落点