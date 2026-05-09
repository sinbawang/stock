# 基本面 Python 数据模型草案 v0.1

这份文档用于把 [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md) 里的领域模型定义，进一步收敛成“后续 Python 代码里建议使用什么数据结构”。

它和 [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md) 的关系是：

- 本文定义“数据对象长什么样”
- 配置草案定义“子模型参数长什么样”

两者组合后，后续实现路径应是：

1. 先把原始输入解析成 `FundamentalSnapshot`
2. 再由 `SubmodelConfig.field_policy` 判断当前子模型要求哪些字段必填
3. 最后输出 `FundamentalScoreCard`

## 1. 设计结论

如果先说结论，后续 Python 实现建议采用：

- `Pydantic` 负责基础解析与类型校验
- `FundamentalSnapshot` 保持“宽口径”模型，大多数字段允许为 `None`
- 第一版必填字段不要直接写死在 `FundamentalSnapshot` 类上，而是由子模型配置做第二层校验
- 评分输出统一收敛到 `FundamentalScoreCard`

这样做的原因是：

- 同一份快照会被不同子模型复用
- 平台互联网与半导体的必填字段并不完全相同
- 如果把全部必填约束写死在快照模型里，后面每扩一个子模型都会变得很僵硬

## 2. 建议的代码分层

后续实现时，数据模型层建议如下：

- `models/fundamental_snapshot.py`: 输入快照模型
- `models/fundamental_scorecard.py`: 评分输出模型
- `models/fundamental_common.py`: 公共枚举或基础类型

如果后面不想拆太细，第一版也可以先放在一个文件里，但对象边界最好先固定。

## 3. `FundamentalSnapshot` 设计草案

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

### 3.2 推荐结构

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

    gross_margin: float | None = None
    net_margin: float | None = None
    revenue_growth: float | None = None
    net_profit_growth: float | None = None

    debt_to_asset: float | None = None
    current_ratio: float | None = None
    operating_cashflow_to_profit: float | None = None
    operating_cashflow_to_profit_history: list[float | None] | None = None

    accounts_receivable_growth: float | None = None
    inventory_growth: float | None = None
    interest_bearing_debt_growth: float | None = None
    operating_cashflow_growth: float | None = None

    guidance_attainment: GuidanceAttainment | None = None

    period_type: Literal["annual", "ttm", "quarterly_annualized"] | None = None
    industry: str | None = None
    notes: str | None = None
    raw_payload_ref: str | None = None
```

### 3.3 为什么大多数字段都允许 `None`

这里的关键不是“字段不重要”，而是：

- 快照模型解决的是“标准化承载”
- 子模型配置解决的是“当前规则需要哪些字段”

例如：

- 对平台互联网，`inventory_growth` 可以缺失
- 对半导体，`inventory_growth` 应该是必需项

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

## 5. 输出模型设计草案

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
    max_score: float = 100.0
    used_metrics: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    passed_rules: list[TriggeredRule] = Field(default_factory=list)
    failed_rules: list[TriggeredRule] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

这里建议补 `used_metrics` 和 `missing_metrics`，原因是：

- 第一版会有很多可选增强字段
- 用户以后需要知道“这个维度到底按哪些字段算出来的”

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

## 6. 可选的校验结果对象

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

## 7. 推荐实现策略

后续真正开始写 Python 时，建议按这个顺序：

1. 先实现 `FundamentalSnapshot`
2. 再实现 `TriggeredRule`、`FundamentalDimensionScore`、`FundamentalScoreCard`
3. 再实现配置层里的 `FieldPolicy` 和 `SubmodelConfig`
4. 最后写 `validate_snapshot_against_policy(snapshot, policy)`

原因是：

- 没有快照模型，配置层无处落地
- 没有输出模型，评分引擎很快会变成字典拼接脚本
- 先把输入输出对象固定，再接评分逻辑最稳

## 8. 与现有文档的关系

这份文档和现有文档的分工建议固定为：

- [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md): 领域模型和规则边界
- [docs/fundamental-v1-minimum-fields.md](docs/fundamental-v1-minimum-fields.md): 第一版字段最小集
- [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md): 子模型配置结构
- 本文：Python 输入输出对象草案

## 9. 当前建议结论

如果只说结论：

- `FundamentalSnapshot` 应该宽口径，不要把第一版必填硬编码进类定义
- 第一版必填字段应由 `FieldPolicy` 按子模型二次校验
- `FundamentalScoreCard` 应提前带上 `submodel_id`、`industry_bucket`、`red_flag`
- 后续实现最稳的顺序是“快照模型 -> 输出模型 -> 配置模型 -> 校验函数 -> 评分引擎"