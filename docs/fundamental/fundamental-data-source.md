# 基本面数据源策略

这份文档回答两件事：

- 基本面快照应该怎么从数据源进入仓库里的标准模型
- 哪些抓取逻辑应该沉到公共代码，而不是散落在临时脚本或聊天片段里

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

建议在阅读这份文档前，先确认两件事：

- 模块总边界: [fundamental-module-spec.md](fundamental-module-spec.md)
- 第一版字段边界: [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)

看完这份文档后，下一步通常是：

- Python 模型说明: [fundamental-python-model.md](fundamental-python-model.md)
- 代码目录说明: [fundamental-code-layout.md](fundamental-code-layout.md)

## 当前结论

- 基本面分析的统一输入仍然是 `FundamentalSnapshot`
- 从数据源抓快照应走 `src/fundamental/data/`
- “抓取 + 分析”应走 `src/fundamental/services/`
- 第一版已落地的是：港股 + A 股公开数据源快照抓取

当前整体落地状态和已覆盖行业桶，统一以 [fundamental-doc-map.md](fundamental-doc-map.md) 的“当前实现快照”章节为准；本文件重点只保留数据源入口、字段口径和 fallback 策略。

如果当前关注的是港股保险 / 券商为什么还没有 live 闭环，以及第二数据源下一步该怎么接，直接看 [hk-financial-second-source-plan.md](hk-financial-second-source-plan.md)。

## 当前公共代码

公共抓取入口：

- [src/fundamental/data/hk_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/hk_snapshot_fetcher.py)
- [src/fundamental/data/cn_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/cn_snapshot_fetcher.py)

推荐服务入口：

- [src/fundamental/services/fetch_and_analyze_hk_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_snapshot.py)
- [src/fundamental/services/fetch_and_analyze_cn_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_snapshot.py)

当前能力：

- 通过 Eastmoney / AkShare 抓取港股核心指标，默认优先年报；无年报时显式回退到最新可用报告期
- 通过 Eastmoney 原始现金流表计算 `operating_cashflow_to_profit_history`
- 通过 Eastmoney 原始资产负债表回算 `accounts_receivable_growth`、`inventory_growth`
- 通过 Eastmoney 估值对比接口补齐 `pe_ttm`、`pe_percentile_5y` 代理、`pb`、`ps_ttm`
- 可选通过雪球 `quote` 做 secondary overlay，补 `market_cap`、`dividend_yield` 等缺失字段
- 港股金融 live 链路已支持官方披露 fallback：
  - `06886` 可从华泰官方年报 PDF 解析 `风险覆盖率`，并透明映射为 `net_capital_ratio` 代理值
  - `01339` 可从人保官网偿付能力披露列表自动发现最新偿付能力报告摘要 PDF，并补 `solvency_adequacy_ratio`
- 通过 THS 财务摘要 / 资产负债表 / 现金流量表 / 利润表 + Baidu 估值序列构建 A 股快照
- A 股快照当前会优先最近一个 `12-31` 年报期，避免把季度 `ROE`、增速、现金流转化与年报同行直接混比
- 返回 `field_sources`，显式标注字段来自主源还是 overlay
- 直接产出标准 `FundamentalSnapshot`
- 可以继续直接喂给现有基本面评分引擎
- 文本报告当前会额外输出两类可解释信息：
  - 字段来源口径警告，例如 `official.solvency_report`、`official.annual_report_proxy`、`manual.supplement`
  - 报告期口径警告，例如当前结果来自一季报 / 中报 / 三季报，不能直接与年报口径横比
  - 维度得分的简版计算说明，例如“字段值 -> 规则分 -> 平均后乘维度权重”

## 为什么要提取成公共层

如果不抽公共层，后面很容易出现这些问题：

- 每次抓美团、腾讯、中芯都重新拼一段临时代码
- 同一个字段在不同脚本里用不同口径计算
- 代理清理、限流、负 PE 导致的 `PEG` 缺失逻辑被重复实现
- 聊天里临时验证过的抓取方法无法沉淀到仓库

所以当前约定是：

- `data/` 只负责从外部源拿原始口径并映射到标准快照
- `services/` 负责把快照送进配置化分析流程
- `scoring/` 不直接碰外部数据源

## 当前港股快照口径

第一版港股公共抓取采用以下口径：

- `roe`、`revenue_growth`、`net_profit_growth`、`current_ratio`、`debt_to_asset`
  来自 Eastmoney 港股核心指标
- `operating_cashflow_to_profit_history`
  来自 Eastmoney 港股现金流量表里经营现金流净额 / 股东应占利润
- `accounts_receivable_growth`、`inventory_growth`
  来自 Eastmoney 港股资产负债表，分别用 `STD_ITEM_CODE == "004002003"` 与
  `STD_ITEM_CODE == "004002001"` 的最近两期金额回算同比增速
- `pe_percentile_5y`
  当前用 Eastmoney 估值对比接口里的 TTM PE 分位做代理

报告期选择补充约定：

- `hk_snapshot_fetcher` 当前优先选择 `DATE_TYPE_CODE == "001"` 的年报行
- 若公共源暂时没有年报行，则回退到最新可用报告期，并把 `period_type` 写为 `report`
- 这类回退不会静默发生：
  - fetch 结果里会留下 assumption
  - 服务层与最终简报会输出“非年报口径”警告

金融补充字段对齐补充约定：

- `financial_indicator_df` 当前会优先匹配主快照对应的 `report_period`
- 如果同报告期指标行不存在，才回退到最新可用指标期
- 这类 indicator fallback 当前也会在 assumptions 中显式记录，不再默认拿“最新一行”静默补字段

这意味着第一版不是“完美多源校验后的财务数据库”，而是：

- 先把一个稳定、可复用、可解释的抓取闭环落下来
- 对代理字段和运行时放宽规则明确记录假设

这次补上港股资产负债表口径之后，像 `00981` 这类半导体子模型所要求的
`accounts_receivable_growth`、`inventory_growth` 已经能直接从公共层返回，不需要再在脚本侧做特判。

## 当前 A 股快照口径

当前 A 股公共抓取采用以下组合：

- THS `stock_financial_abstract_ths(..., indicator="按报告期")`
  提供 `roe`、`revenue_growth`、`net_profit_growth`、`gross_margin`、`current_ratio`、`debt_to_asset`
- THS `stock_financial_debt_new_ths`
  提供 `accounts_receivable`、`inventory` 等资产负债表科目，并回算
  `accounts_receivable_growth`、`inventory_growth`
- THS `stock_financial_cash_new_ths` 与 `stock_financial_benefit_new_ths`
  回算 `operating_cashflow_to_profit`、`operating_cashflow_to_profit_history`
- Baidu `stock_zh_valuation_baidu`
  提供 `pe_ttm`、`pb`、`market_cap` 以及 `pe_percentile_5y` 所需的时间序列

报告期选择补充约定：

- `cn_snapshot_fetcher` 当前优先抽取最近一个 `12-31` 年报期对应的摘要、资产负债表、现金流量表和利润表行
- 若主源暂时没有年报期，才回退到最新报告期
- 当前简报会对这类回退输出“非年报口径”警告，提醒不要直接和年报口径横比

当前 A 股抓取目标不是一步覆盖所有行业增强字段，而是先提供一套能直接进入当前已落地 A 股相关子模型的最小公共快照，例如：

- `industrial_automation_v1`
- `game_content_v1`
- `utility_operator_v1`
- `home_appliance_v1`
- `energy_resource_v1`

也就是说，当前公共 A 股快照已经不再只服务于“科技扩展模型”，也开始支撑公用事业与成熟消费制造行业桶。

补充说明：

- 当前 A 股公共抓取仍不稳定提供点位型 `dividend_yield`
- 因此对 `bank_v1`、`utility_operator_v1`、`home_appliance_v1`、`energy_resource_v1` 这类把 `dividend_yield` 作为准入字段的 CN 子模型，live 分析链路当前统一按运行时放宽处理
- 当前 A 股与港股快照都已经内建一批派生字段计算，至少包括 `peg`、`net_margin`、`asset_turnover`、`equity_multiplier`、`dupont_driver`

## 雪球 overlay 策略

最新探测结果表明：

- 雪球 `quote` 接口能稳定返回港股估值/市值类字段
- 但本轮探测到的港股 F10/财务表接口路径并不稳定，不能替代当前主源

所以当前策略不是“切主源”，而是：

- 财务表主源仍然用 Eastmoney / AkShare
- 雪球只作为可选 secondary overlay
- overlay 默认不覆盖主源已有值，只补缺失字段
- 字段级来源通过 `field_sources` 显式输出，而不是只在报告里口头说明

当前 overlay 主要补这些字段：

- `market_cap`
- `dividend_yield`
- 当主源缺失时，补 `pe_ttm`、`pb`、`ps_ttm`

## 港股金融第二数据源当前状态

截至 2026-05-11，港股金融 second source 已经从“方案设计”推进到“部分 live 落地”：

- `06886`:
  - 当前公共源仍不直接提供 `net_capital_ratio`
  - 现已接入华泰官方年报 PDF fallback
  - 当前实现口径是把年报中的 `风险覆盖率` 透明映射为 `net_capital_ratio` 代理值
  - 报告文本会明确提示这不是公司直接披露的 `净资本比率` 字段
- `01339`:
  - 当前公共源仍不稳定提供 `solvency_adequacy_ratio`
  - 现已接入人保官网偿付能力披露列表 fallback
  - 当前实现会抓最新公开偿付能力报告摘要 PDF 并解析 `综合偿付能力充足率`
  - 报告文本会明确提示这条官方披露可能滞后于 `report_period` 对应年报口径
- `insurance_v1` 的 `combined_ratio`、`investment_return`、`embedded_value_growth`、`new_business_value_growth` 目前仍主要依赖 `manual supplement`

这意味着当前 live 能力不是“港股金融字段已全部自动化”，而是：

- 先把最关键、最影响模型准入的监管字段接入官方披露 fallback
- 对仍无法稳定自动化的字段保留 `manual supplement`
- 通过 `field_sources` 与报告 `警告` 段显式区分字段口径

## 双源估值对照

如果要判断估值字段应该优先信哪个源，不要只靠一次聊天里的探测，直接跑对照脚本：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/compare_hk_valuation_sources.py 03690 --name 美团 --output data/reports/_meta/hk_valuation_compare_03690_20260510.md
```

当前脚本：

- 对照 `pe_ttm`、`pb`、`ps_ttm`
- 额外列出雪球可补的 `market_cap`、`dividend_yield`
- 输出 markdown 小报告，便于后续沉淀样本
- 支持批量模式，方便验证差异是否只出现在个别标的

当前实测样本：

- [data/reports/_meta/hk_valuation_compare_03690_20260510.md](../data/reports/_meta/hk_valuation_compare_03690_20260510.md)
- [data/reports/_meta/hk_valuation_compare_batch_20260510.md](../data/reports/_meta/hk_valuation_compare_batch_20260510.md)

批量示例：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/compare_hk_valuation_sources.py --symbols 03690 00700 00981 --output data/reports/_meta/hk_valuation_compare_batch_20260510.md
```

在这份样本里，`pe_ttm`、`pb`、`ps_ttm` 的双源差异都不大，因此当前更合理的策略仍然是：

- Eastmoney / AkShare 做主源
- 雪球做估值校验和缺失字段 overlay

不过批量样本也提示了一个细节：

- `pe_ttm`、`pb` 在多只样本上都比较接近
- `ps_ttm` 与雪球 `psr` 在个别标的上可能出现更明显差异，因此应持续保留 source trace，而不是简单当成完全等价字段

## 运行时放宽规则

当前最典型的例子是平台互联网子模型的 `PEG`。

如果最新 `TTM PE <= 0`，那么：

- `PEG` 在财务意义上就不可用
- 运行时服务会把 `PEG` 从必填放宽为可选
- 这条放宽规则会作为 assumption 返回，而不是悄悄吞掉

这样做的目的不是“美化结果”，而是避免因为估值指标本身失效而让整个快照无法进入分析流程。

## 当前推荐调用方式

只抓快照：

```python
from fundamental.data import fetch_hk_fundamental_snapshot

result = fetch_hk_fundamental_snapshot("03690", name="美团")
snapshot = result.snapshot
assumptions = result.assumptions
field_sources = result.field_sources
```

带雪球 overlay 抓快照：

```python
from fundamental.data import fetch_hk_fundamental_snapshot

result = fetch_hk_fundamental_snapshot(
  "03690",
  name="美团",
  quote_overlay_source="xueqiu",
)
snapshot = result.snapshot
assumptions = result.assumptions
field_sources = result.field_sources
```

`field_sources` 当前会返回类似这样的结构：

```python
{
    "accounts_receivable_growth": "eastmoney.analysis",
    "inventory_growth": "eastmoney.analysis",
    "pe_ttm": "eastmoney+akshare.valuation",
    "pb": "eastmoney+akshare.valuation",
    "ps_ttm": "eastmoney+akshare.valuation",
    "operating_cashflow_to_profit": "eastmoney.cashflow",
    "market_cap": "xueqiu.quote",
}
```

在港股金融 live 链路里，当前还可能出现这些来源：

```python
{
  "solvency_adequacy_ratio": "official.solvency_report",
  "net_capital_ratio": "official.annual_report_proxy",
  "combined_ratio": "manual.supplement",
  "investment_return": "manual.supplement",
}
```

这层 source trace 的用途是：

- 让 `ps_ttm` / `psr` 这类近似字段保留来源痕迹
- 在批量对照里发现异常差值时，能回溯是主源字段还是 overlay 字段
- 为后续字段级 fallback 和审计输出打基础

抓取并直接分析：

```python
from fundamental.services import fetch_and_analyze_hk_snapshot

result = fetch_and_analyze_hk_snapshot("03690", name="美团")
snapshot = result.fetched.snapshot
scorecard = result.scorecard
assumptions = result.assumptions
```

如果要消费用户可见报告，而不是只消费总分，当前还应注意：

- `scorecard.warnings` 已经会反映字段来源口径
- `reporting.render_scorecard_text(...)` 已经会把维度得分的简版计算依据一起渲染出来
- 如果把 `snapshot` 一起传给 `render_scorecard_text(...)`，文本报告还会附带关键指标与现金流/杠杆指标摘要
- 因此脚本侧不应再重复手写“这个分数怎么来的”或“这个字段来自哪里”这类说明，除非需要额外业务总结

如果希望直接把文本评分卡落盘，而不是只生成 brief，当前可以直接复用 reporting helper：

```python
from fundamental.reporting import save_scorecard_text

scorecard_path = save_scorecard_text(
  scorecard=result.scorecard,
  snapshot=result.fetched.snapshot,
  output_dir="data/_meta",
)
```

脚本层也已经开放了对应参数：

```powershell
.\venv\Scripts\python.exe scripts/generate_fundamental_brief.py 601088 --name 中国神华 --save-scorecard-text
```

```powershell
.\venv\Scripts\python.exe scripts/batch_regenerate_fundamental_briefs.py --save-scorecard-text
```

带雪球 overlay 抓取并直接分析：

```python
from fundamental.services import fetch_and_analyze_hk_snapshot

result = fetch_and_analyze_hk_snapshot(
  "03690",
  name="美团",
  quote_overlay_source="xueqiu",
)
snapshot = result.fetched.snapshot
scorecard = result.scorecard
assumptions = result.assumptions
```

A 股只抓快照：

```python
from fundamental.data import fetch_cn_fundamental_snapshot

result = fetch_cn_fundamental_snapshot("300124", name="汇川技术")
snapshot = result.snapshot
assumptions = result.assumptions
field_sources = result.field_sources
```

A 股抓取并直接分析：

```python
from fundamental.services import fetch_and_analyze_cn_snapshot

result = fetch_and_analyze_cn_snapshot("002555", name="三七互娱")
snapshot = result.fetched.snapshot
scorecard = result.scorecard
assumptions = result.assumptions
```

A 股抓取并直接分析，同时补充暂时无法稳定自动化的行业字段：

```python
from fundamental.services import fetch_and_analyze_cn_snapshot

result = fetch_and_analyze_cn_snapshot(
  "601088",
  name="中国神华",
  manual_supplement={
    "dividend_yield": 6.3,
    "capex_to_operating_cashflow": 0.42,
    "unit_cost_position": 0.82,
    "reserve_life_index": 14.5,
    "commodity_price_sensitivity": 0.46,
    "notes": "manual supplement from annual report",
  },
)
snapshot = result.fetched.snapshot
scorecard = result.scorecard
assumptions = result.assumptions
field_sources = result.fetched.field_sources
```

这层 `manual_supplement` 当前适合承接：

- A 股能源资源子模型暂时缺失的 `dividend_yield`
- 年报或公告里可手工摘取的 `capex_to_operating_cashflow`
- 研究口径维护的 `unit_cost_position`、`reserve_life_index`、`commodity_price_sensitivity`

约束仍然和港股一致：

- 只能写入当前子模型 `required_core`、`optional_manual`、`deferred_v2` 和 `notes`
- 写入后会进入 `field_sources`，来源标记为 `manual.supplement`
- 越权字段会直接抛错，而不是静默忽略

如果补录信息已经写在 brief 文本里，也可以直接传文件路径。当前服务层支持：

- `json` 模板文件，例如 `data/_meta/manual_supplements/01339_中国人保_insurance_v1_latest.json`
- `txt` / `md` brief 文件中的 `- field=value` 行

例如：

```python
from fundamental.services import fetch_and_analyze_cn_snapshot

result = fetch_and_analyze_cn_snapshot(
  "601088",
  name="中国神华",
  manual_supplement_path="data/_meta/601088_中国神华_fundamental_brief_latest.txt",
)
```

brief 文本里推荐额外维护一个明确区块，例如：

```text
手工补充字段:
- dividend_yield=6.3
- capex_to_operating_cashflow=0.42
- unit_cost_position=0.82
- reserve_life_index=14.5
- commodity_price_sensitivity=0.46
- notes="2025 年报 p.34, 经营数据公告 2026-03-28"
```

这里的解析规则刻意保持很窄：

- 只读取 bullet 形式的 `field=value`
- 单行多个字段也可以，例如 `- pe_ttm=12.4, pb=1.8`
- `notes` 如果包含逗号，建议整段加引号

如果希望重新生成一份带机器可读补充区块的 brief，当前也可以直接用脚本：

```powershell
.\venv\Scripts\python.exe scripts\generate_fundamental_brief.py 601088 --name 中国神华 --manual-supplement-path data/_meta/manual_supplements/601088_中国神华_energy_resource_v1_latest.txt
```

这个脚本会：

- 调用现有 HK/CN fetch-and-analyze 服务
- 自动把 `manual.supplement` 字段写回 brief 尾部的 `手工补充字段:` 区块
- 输出到 `data/_meta/*_fundamental_brief_时间戳.txt`

## 下一步扩展方向

当前这层公共代码已经覆盖港股与 A 股的公开财务快照。后续自然扩展顺序建议是：

1. 更严格的估值分位回算，而不是只用分位代理
2. 平台互联网之外的业务增强字段抓取，例如 `marketing_expense_ratio`、订单类指标、新品储备等
3. 多数据源交叉验证和字段级 source trace
4. A/H 两条抓取链路共享更多公共计算逻辑，减少同比和现金流口径重复实现