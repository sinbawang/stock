# 基本面 Python 数据模型说明

这份文档用于把 [fundamental-module-spec.md](fundamental-module-spec.md) 里的领域模型定义，进一步收敛成“当前 Python 代码里使用什么数据结构，以及这些对象为什么这样拆”。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

这份文档更适合在“总规格、字段边界和数据源口径已经确定”之后再读。建议前置阅读：

- [fundamental-module-spec.md](fundamental-module-spec.md)
- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
- [fundamental-data-source.md](fundamental-data-source.md)

读完这份文档后，通常下一步是：

- [fundamental-submodel-config.md](fundamental-submodel-config.md)
- [fundamental-code-layout.md](fundamental-code-layout.md)

对应的 `src/fundamental/` 目录说明见 [fundamental-code-layout.md](fundamental-code-layout.md)。

它和 [fundamental-submodel-config.md](fundamental-submodel-config.md) 的关系是：

- 本文定义“数据对象长什么样”
- 配置草案定义“子模型参数长什么样”

补充说明：虽然配置草案文件名仍保留“tech”，但当前实际注册表已经扩展到金融和非金融行业桶，因此本文里的模型设计也应按跨行业宽口径来理解。

两者组合后，后续实现路径应是：

1. 先把原始输入解析成 `FundamentalSnapshot`
2. 再由 `SubmodelConfig.field_policy` 判断当前子模型要求哪些字段必填
3. 最后输出 `FundamentalScoreCard`

## 1. 设计结论

如果先说结论，当前 Python 实现采用：

- `Pydantic` 负责基础解析与类型校验
- `FundamentalSnapshot` 保持“宽口径”模型，大多数字段允许为 `None`
- 第一版必填字段不要直接写死在 `FundamentalSnapshot` 类上，而是由子模型配置做第二层校验
- 单期评分输出统一收敛到 `FundamentalScoreCard`
- 跨期 blended 结果单独收敛到 `models/blended.py`

这样做的原因是：

- 同一份快照会被不同子模型复用
- 平台互联网与半导体的必填字段并不完全相同
- 如果把全部必填约束写死在快照模型里，后面每扩一个子模型都会变得很僵硬

## 2. 当前代码分层

按当前仓库实现，数据模型层已经基本采用如下分层：

- `models/snapshot.py`: 输入快照模型
- `models/scorecard.py`: 评分输出模型
- `models/blended.py`: 跨报告期 blended 对象
- `models/common.py`: 公共枚举或基础类型

也就是说，当前实现已经没有沿用早期草案里的 `fundamental_snapshot.py` / `fundamental_scorecard.py`
命名，而是收敛成了更短的 `snapshot.py` / `scorecard.py` / `common.py`。

## 3. `FundamentalSnapshot` 设计

### 3.1 核心原则

`FundamentalSnapshot` 应代表：

- “这家公司在某一报告期的一份标准化财务快照”

它不负责：

- 判定当前子模型是否字段齐全
- 判定当前字段是否足以进入某套评分规则

这些事情应由：

- `FieldPolicy`
- 或单独的 `SnapshotValidator`

来负责。

### 3.2 当前结构

```python
from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, Field


MarketCode = Literal["CN", "HK", "US"]
GuidanceAttainment = Literal["beat", "meet", "miss"]
DupontDriver = Literal["margin_turnover", "mixed", "leverage"]


class FundamentalSnapshot(BaseModel):
    symbol: str
    name: str
    market: MarketCode
    report_period: date
    currency: str
    source: str
    updated_at: datetime

    market_cap: float | None = None
    pe_ttm: float | None = None
    pe_percentile_5y: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    peg: float | None = None
    dividend_yield: float | None = None

    roe: float | None = None
    roe_3y_mean: float | None = None
    roe_3y_cv: float | None = None
    dupont_driver: DupontDriver | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None

    gross_margin: float | None = None
    gross_margin_trend: str | None = None
    net_margin: float | None = None
    revenue_growth: float | None = None
    net_profit_growth: float | None = None
    overseas_revenue_share: float | None = None

    debt_to_asset: float | None = None
    current_ratio: float | None = None
    operating_cashflow_to_profit: float | None = None
    operating_cashflow_to_profit_history: list[float | None] | None = None

    accounts_receivable_growth: float | None = None
    inventory_growth: float | None = None
    price_war_pressure: str | None = None
    interest_bearing_debt_growth: float | None = None
    operating_cashflow_growth: float | None = None
    free_cashflow_yield: float | None = None
    capex_to_operating_cashflow: float | None = None
    unit_cost_position: float | None = None
    reserve_life_index: float | None = None
    commodity_price_sensitivity: float | None = None

    capital_adequacy_ratio: float | None = None
    core_tier1_ratio: float | None = None
    npl_ratio: float | None = None
    provision_coverage_ratio: float | None = None
    loan_deposit_growth_gap: float | None = None
    net_interest_margin: float | None = None
    solvency_adequacy_ratio: float | None = None
    combined_ratio: float | None = None
    investment_return: float | None = None
    embedded_value_growth: float | None = None
    new_business_value_growth: float | None = None
    net_capital_ratio: float | None = None

    guidance_attainment: GuidanceAttainment | None = None

    period_type: Literal["annual", "ttm", "quarterly_annualized"] | None = None
    industry: str | None = None
    notes: str | None = None
    raw_payload_ref: str | None = None
```

当前实现还额外设置了：

- `model_config = ConfigDict(extra="ignore")`

这样做的作用是：

- 允许数据源层在 schema 有轻微变化时先安全忽略无关字段
- 不把快照模型变成和某个外部源一一绑定的脆弱接口

### 3.3 为什么大多数字段都允许 `None`

这里的关键不是“字段不重要”，而是：

- 快照模型解决的是“标准化承载”
- 子模型配置解决的是“当前规则需要哪些字段”

例如：

- 对平台互联网，`inventory_growth` 可以缺失
- 对半导体，`inventory_growth` 应该是必需项
- 对银行，`core_tier1_ratio`、`npl_ratio`、`provision_coverage_ratio` 应该是必需项
- 对数字基础设施或公用事业，`dividend_yield`、`pb` 或 `pe_percentile_5y` 会重新变得重要

所以更合理的做法是：

- `FundamentalSnapshot` 保持宽口径
- `FieldPolicy.required_core` 做第二层校验

## 4. 第一版最小快照视图

虽然 `FundamentalSnapshot` 可以是宽口径模型，但第一版实现时建议在文档中明确一个最小可运行视图。

```python
V1_BASE_REQUIRED_FIELDS = (
    "symbol",
    "name",
    "market",
    "report_period",
    "currency",
    "source",
    "updated_at",
)
```

然后再由各子模型叠加自己的必需字段。例如：

```python
PLATFORM_INTERNET_REQUIRED_FIELDS = (
    *V1_BASE_REQUIRED_FIELDS,
    "roe",
    "roe_3y_cv",
    "operating_cashflow_to_profit",
    "operating_cashflow_to_profit_history",
    "revenue_growth",
    "net_profit_growth",
    "pe_percentile_5y",
    "peg",
)
```

这比单独再定义一个 `FundamentalSnapshotV1` 子类更稳，因为：

- 子模型差异体现在配置层，不体现在类层继承
- 以后新增模型时，不需要继续膨胀出 `SnapshotV2A`、`SnapshotV2B`

截至当前实现，这种“宽口径快照 + 配置层二次校验”的设计已经验证过可以同时承载：

- 科技子模型
- 金融子模型
- 公用事业、数字基础设施、家电消费制造等扩展行业桶

## 5. 输出模型设计

评分输出建议拆成三个对象：

- `TriggeredRule`
- `FundamentalDimensionScore`
- `FundamentalScoreCard`

### 5.1 `TriggeredRule`

```python
class TriggeredRule(BaseModel):
    rule_id: str
    severity: Literal["pass", "warning", "risk", "red_flag"]
    message: str
    automated: bool = True
```

作用：

- 统一承载命中的规则结果
- 方便后面同时输出 `passed_rules`、`warnings`、`risks`

### 5.2 `FundamentalDimensionScore`

```python
class FundamentalDimensionScore(BaseModel):
    dimension: str
    score: float
    weight: int
    max_score: float
    score_basis: str | None = None
    used_metrics: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    passed_rules: list[TriggeredRule] = Field(default_factory=list)
    failed_rules: list[TriggeredRule] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

当前实现除了 `used_metrics` 和 `missing_metrics`，还保留了 `score_basis`，原因是：

- 第一版会有很多可选增强字段
- 用户以后需要知道“这个维度到底按哪些字段算出来的”
- 报告层当前已经会输出维度分数的简版计算依据

### 5.3 `FundamentalScoreCard`

```python
class FundamentalScoreCard(BaseModel):
    symbol: str
    name: str
    market: MarketCode
    report_period: date

    industry_bucket: str
    submodel_id: str
    submodel_version: str

    total_score: float
    rating: Literal["A", "B", "C", "D"]
    red_flag: bool = False

    dimension_scores: list[FundamentalDimensionScore]

    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    focus_questions: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)

    triggered_rules: list[TriggeredRule] = Field(default_factory=list)
    combined_comment: str | None = None
```

这里建议把以下字段提前纳入：

- `industry_bucket`
- `submodel_id`
- `submodel_version`

原因是当前文档体系已经明确了：

- 行业分层存在
- 科技行业内还有子模型
- 后续联合分析时必须知道当前结论按哪套规则得出

## 6. 跨期 blended 对象

当前模型层已经不只包含单期评分对象，也已经新增：

- `AnnualAnchorScore`
- `OverlayComponent`
- `InterimOverlayScore`
- `InterimWeightingProfile`
- `BlendedFundamentalScoreCard`

这组对象的作用是：

- 保留年报锚定结果
- 用组件化结构表达季报刷新层
- 把 blended 最终结果和单期 `FundamentalScoreCard` 分开，避免对象职责混乱

## 7. 可选的校验结果对象

如果后续想把“字段校验”和“评分执行”完全解耦，可以再补一个轻量对象。

```python
class SnapshotValidationResult(BaseModel):
    is_valid: bool
    required_missing: list[str] = Field(default_factory=list)
    optional_missing: list[str] = Field(default_factory=list)
    deferred_missing: list[str] = Field(default_factory=list)
```

它不是第一版必须实现，但很有价值，因为：

- 可以先做字段校验，再决定是否进入评分
- 也可以把“缺什么字段”单独输出给用户

## 8. 推荐扩展策略

当前输入输出对象已经落地，因此后续更合理的扩展顺序是：

1. 在不破坏 `FundamentalSnapshot` 宽口径边界的前提下继续补行业字段
2. 在 `FundamentalScoreCard` 与 blended 对象上继续补可解释信息
3. 继续保持“对象层稳定，字段准入放在配置层”的分工

原因是：当前对象层已经稳定，后续更重要的是扩字段和扩解释，而不是重做类层次。

## 9. 与现有文档的关系

这份文档和现有文档的分工建议固定为：

- [fundamental-module-spec.md](fundamental-module-spec.md): 领域模型和规则边界
- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md): 第一版字段最小集
- [fundamental-submodel-config.md](fundamental-submodel-config.md): 子模型配置结构
- 本文：Python 输入输出对象草案

## 10. 当前结论

如果只说结论：

- `FundamentalSnapshot` 应该宽口径，不要把第一版必填硬编码进类定义
- 第一版必填字段应由 `FieldPolicy` 按子模型二次校验
- `FundamentalScoreCard` 应提前带上 `submodel_id`、`industry_bucket`、`red_flag`
- 当前实现验证下来，较稳的顺序仍然是“快照模型 -> 输出模型 -> 配置模型 -> 校验函数 -> 评分引擎"