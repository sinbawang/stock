# 基本面数据源策略

这份文档回答两件事：

- 基本面快照应该怎么从数据源进入仓库里的标准模型
- 哪些抓取逻辑应该沉到公共代码，而不是散落在临时脚本或聊天片段里

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

建议在阅读这份文档前，先确认两件事：

- 模块总边界: [fundamental-module-spec.md](fundamental-module-spec.md)
- 第一版字段边界: [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)

看完这份文档后，下一步通常是：

- Python 模型草案: [fundamental-python-model-draft.md](fundamental-python-model-draft.md)
- 代码目录草案: [fundamental-code-layout-draft.md](fundamental-code-layout-draft.md)

## 当前结论

- 基本面分析的统一输入仍然是 `FundamentalSnapshot`
- 从数据源抓快照应走 `src/fundamental/data/`
- “抓取 + 分析”应走 `src/fundamental/services/`
- 第一版已落地的是：港股 + A 股公开数据源快照抓取

如果当前关注的是港股保险 / 券商为什么还没有 live 闭环，以及第二数据源下一步该怎么接，直接看 [hk-financial-second-source-plan.md](hk-financial-second-source-plan.md)。

## 当前公共代码

公共抓取入口：

- [src/fundamental/data/hk_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/hk_snapshot_fetcher.py)
- [src/fundamental/data/cn_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/cn_snapshot_fetcher.py)

推荐服务入口：

- [src/fundamental/services/fetch_and_analyze_hk_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_snapshot.py)
- [src/fundamental/services/fetch_and_analyze_cn_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_snapshot.py)

当前能力：

- 通过 Eastmoney / AkShare 抓取港股年报核心指标
- 通过 Eastmoney 原始现金流表计算 `operating_cashflow_to_profit_history`
- 通过 Eastmoney 原始资产负债表回算 `accounts_receivable_growth`、`inventory_growth`
- 通过 Eastmoney 估值对比接口补齐 `pe_ttm`、`pe_percentile_5y` 代理、`pb`、`ps_ttm`
- 可选通过雪球 `quote` 做 secondary overlay，补 `market_cap`、`dividend_yield` 等缺失字段
- 通过 THS 财务摘要 / 资产负债表 / 现金流量表 / 利润表 + Baidu 估值序列构建 A 股快照
- 返回 `field_sources`，显式标注字段来自主源还是 overlay
- 直接产出标准 `FundamentalSnapshot`
- 可以继续直接喂给现有基本面评分引擎

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

当前 A 股抓取目标不是覆盖所有行业增强字段，而是先提供一套能直接进入
`industrial_automation_v1`、`game_content_v1` 等子模型的最小公共快照。

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

## 双源估值对照

如果要判断估值字段应该优先信哪个源，不要只靠一次聊天里的探测，直接跑对照脚本：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/compare_hk_valuation_sources.py 03690 --name 美团 --output data/_meta/hk_valuation_compare_03690_20260510.md
```

当前脚本：

- 对照 `pe_ttm`、`pb`、`ps_ttm`
- 额外列出雪球可补的 `market_cap`、`dividend_yield`
- 输出 markdown 小报告，便于后续沉淀样本
- 支持批量模式，方便验证差异是否只出现在个别标的

当前实测样本：

- [data/_meta/hk_valuation_compare_03690_20260510.md](../data/_meta/hk_valuation_compare_03690_20260510.md)
- [data/_meta/hk_valuation_compare_batch_20260510.md](../data/_meta/hk_valuation_compare_batch_20260510.md)

批量示例：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/compare_hk_valuation_sources.py --symbols 03690 00700 00981 --output data/_meta/hk_valuation_compare_batch_20260510.md
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

## 下一步扩展方向

当前这层公共代码已经覆盖港股与 A 股的公开财务快照。后续自然扩展顺序建议是：

1. 更严格的估值分位回算，而不是只用分位代理
2. 平台互联网之外的业务增强字段抓取，例如 `marketing_expense_ratio`、订单类指标、新品储备等
3. 多数据源交叉验证和字段级 source trace
4. A/H 两条抓取链路共享更多公共计算逻辑，减少同比和现金流口径重复实现