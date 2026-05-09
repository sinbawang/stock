# 科技子模型代码配置草案 v0.1

这份文档用于把 [docs/fundamental-tech-submodels.md](docs/fundamental-tech-submodels.md) 里的自然语言参数表，进一步反推成“后续 Python 代码里建议长什么样”。

与输入输出对象对应的 Python 数据模型草案见 [docs/fundamental-python-model-draft.md](docs/fundamental-python-model-draft.md)。

目标不是现在就开始写实现，而是先冻结三件事：

- 配置对象需要表达哪些概念
- 配置和评分逻辑的边界如何切分
- 平台互联网与半导体第一版应如何注册成两个独立模型

## 1. 设计目标

后续代码配置层建议满足以下要求：

- 同一个评分引擎可以加载不同子模型配置
- 维度权重、字段分层、规则开关、红线参数都来自配置，而不是散落在 if/else 里
- 第一版允许部分字段缺失，但缺失策略必须由配置显式表达
- 输出结果里能知道当前是按哪套子模型算出来的

## 2. 建议的模块边界

如果后面开始实现，建议把配置和逻辑分开：

- `config/models.py`: 配置结构定义
- `config/registry.py`: 子模型注册表
- `scoring/base_engine.py`: 通用评分引擎
- `scoring/rules.py`: 通用规则函数
- `scoring/submodels.py`: 子模型特化拼装层，或直接通过注册表装配

第一版更推荐“通用引擎 + 配置注册表”方案，而不是每个子模型单独写一套类。

## 3. 建议的核心配置结构

### 3.1 维度配置

第一层建议定义维度配置对象。

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class DimensionConfig:
    name: str
    weight: int
    primary_metrics: tuple[str, ...]
    optional_metrics: tuple[str, ...] = ()
    inherited_from_common: bool = True
    notes: str = ""
```

作用：

- 表达每个维度的权重
- 表达该维度依赖哪些主字段
- 表达哪些字段只是增强项，不是硬依赖

### 3.2 字段分层配置

第二层建议定义字段分层对象。

```python
@dataclass(frozen=True)
class FieldPolicy:
    required_core: tuple[str, ...]
    optional_manual: tuple[str, ...] = ()
    deferred_v2: tuple[str, ...] = ()
    disabled_or_deweighted: tuple[str, ...] = ()
```

作用：

- 把字段校验逻辑集中起来
- 让“缺失时报错”与“缺失时记录 missing_metrics”可配置

### 3.3 风险规则配置

第三层建议定义红线和风险提示配置。

```python
@dataclass(frozen=True)
class RiskRuleConfig:
    rule_id: str
    severity: Literal["red_flag", "risk", "warning"]
    enabled: bool
    automated: bool
    required_metrics: tuple[str, ...]
    description: str
    notes: str = ""
```

作用：

- 明确哪些规则第一版必须自动化
- 明确哪些规则只是手工/半自动提示
- 避免红线逻辑散落在不同子模型代码里

### 3.4 子模型总配置

最终建议用一个总对象把子模型配置收起来。

```python
@dataclass(frozen=True)
class SubmodelConfig:
    industry_bucket: str
    submodel_id: str
    display_name: str
    version: str
    applicable_symbols: tuple[str, ...]
    output_style: str
    field_policy: FieldPolicy
    dimensions: tuple[DimensionConfig, ...]
    risk_rules: tuple[RiskRuleConfig, ...]
    score_overrides: dict[str, str] = field(default_factory=dict)
    explanation_prompts: tuple[str, ...] = ()
```

这里的关键点是：

- `field_policy` 负责校验边界
- `dimensions` 负责分数结构
- `risk_rules` 负责风险拦截和警告
- `score_overrides` 负责告诉引擎哪些通用规则在子模型里要换口径

## 4. 通用引擎与配置的职责切分

建议职责分配如下：

通用引擎负责：

- 读取快照
- 校验 `required_core`
- 按维度遍历规则
- 聚合总分
- 汇总 `missing_metrics`、`warnings`、`risks`

子模型配置负责：

- 指定权重
- 指定字段依赖
- 指定哪些指标停用或降权
- 指定第一版自动化红线和半自动红线
- 指定输出解释的优先话术

这样后续新增第三个、第四个科技子模型时，优先新增配置，而不是复制引擎代码。

## 5. 平台互联网第一版配置草案

```python
PLATFORM_INTERNET_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="platform_internet_v1",
    display_name="平台互联网",
    version="v1",
    applicable_symbols=("03690", "00700", "01024", "BABA"),
    output_style="growth_and_cashflow_first",
    field_policy=FieldPolicy(
        required_core=(
            "symbol",
            "name",
            "market",
            "report_period",
            "currency",
            "source",
            "updated_at",
            "roe",
            "roe_3y_cv",
            "operating_cashflow_to_profit",
            "operating_cashflow_to_profit_history",
            "revenue_growth",
            "net_profit_growth",
            "pe_percentile_5y",
            "peg",
        ),
        optional_manual=(
            "dupont_driver",
            "guidance_attainment",
            "deferred_revenue_growth",
            "user_growth",
            "arpu_growth",
            "marketing_expense_ratio",
        ),
        disabled_or_deweighted=(
            "inventory_growth",
            "current_ratio",
            "debt_to_asset",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="profit_quality",
            weight=35,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("dupont_driver",),
            notes="沿用通用盈利质量规则",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=25,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            optional_metrics=("guidance_attainment",),
            notes="沿用通用成长规则，但总权重提升",
        ),
        DimensionConfig(
            name="cashflow_and_operating_efficiency",
            weight=20,
            primary_metrics=("operating_cashflow_to_profit",),
            optional_metrics=(
                "deferred_revenue_growth",
                "user_growth",
                "arpu_growth",
                "marketing_expense_ratio",
            ),
            inherited_from_common=False,
            notes="第一版主要依赖现金流兑现，其余字段只增强解释",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y", "peg"),
            notes="沿用通用估值规则",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="ocf_profit_history_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("operating_cashflow_to_profit_history",),
            description="经营现金流/净利润连续两期低于 0.8",
        ),
        RiskRuleConfig(
            rule_id="marketing_up_margin_down",
            severity="warning",
            enabled=True,
            automated=False,
            required_metrics=("marketing_expense_ratio",),
            description="收入增长但营销投入上升且利润率恶化",
        ),
    ),
    score_overrides={
        "growth_delivery.weight": "25",
        "debt_to_asset.enabled": "false",
        "inventory_growth.enabled": "false",
    },
    explanation_prompts=(
        "增长有没有兑现成利润",
        "利润有没有兑现成现金流",
        "当前估值是否仍要求高增长持续",
    ),
)
```

这套草案表达的核心是：

- 平台互联网复用通用评分骨架最多
- 只新增一个“现金流与运营效率”特化维度解释层
- 第一版只强制自动化一条红线

## 6. 半导体与电子硬科技第一版配置草案

```python
SEMICONDUCTOR_HARDTECH_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="semiconductor_hardtech_v1",
    display_name="半导体与电子硬科技",
    version="v1",
    applicable_symbols=("00981", "603986", "06088"),
    output_style="cycle_inventory_cashflow_first",
    field_policy=FieldPolicy(
        required_core=(
            "symbol",
            "name",
            "market",
            "report_period",
            "currency",
            "source",
            "updated_at",
            "roe",
            "roe_3y_cv",
            "operating_cashflow_to_profit",
            "revenue_growth",
            "net_profit_growth",
            "accounts_receivable_growth",
            "inventory_growth",
            "pe_percentile_5y",
        ),
        optional_manual=(
            "gross_margin",
            "dupont_driver",
            "order_backlog_growth",
            "capacity_utilization",
            "capex_growth",
            "wafer_price_trend",
            "peg",
            "operating_cashflow_to_profit_history",
        ),
        deferred_v2=(
            "inventory_growth_history",
            "accounts_receivable_growth_history",
            "gross_margin_trend",
            "order_backlog_history",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="growth_and_cycle",
            weight=25,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            optional_metrics=("order_backlog_growth",),
            inherited_from_common=False,
            notes="增长要结合景气和订单判断",
        ),
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("gross_margin", "dupont_driver"),
            notes="沿用通用盈利质量骨架，加入毛利率解释",
        ),
        DimensionConfig(
            name="operating_and_inventory_cycle",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth"),
            inherited_from_common=False,
            notes="第一版必须实现相对压力计算",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y",),
            optional_metrics=("peg",),
            notes="至少基于估值分位，peg 允许缺失",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="inventory_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("inventory_growth", "revenue_growth"),
            description="存货增速显著高于营收增速",
        ),
        RiskRuleConfig(
            rule_id="receivable_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("accounts_receivable_growth", "revenue_growth"),
            description="应收增速显著高于营收增速",
        ),
        RiskRuleConfig(
            rule_id="gross_margin_down_capex_high",
            severity="warning",
            enabled=True,
            automated=False,
            required_metrics=("gross_margin", "capex_growth"),
            description="毛利率下滑且资本开支仍在高位",
        ),
    ),
    score_overrides={
        "inventory_growth.enabled": "true",
        "accounts_receivable_growth.enabled": "true",
        "debt_to_asset.enabled": "false",
        "peg.required": "false",
    },
    explanation_prompts=(
        "收入增长是否伴随库存和应收同步失真",
        "周期位置是否支持当前估值分位",
        "利润改善是否已经被现金流验证",
    ),
)
```

这套草案表达的核心是：

- 半导体模型比平台互联网更依赖营运质量字段
- 第一版优先做单期风险提示，再逐步升级到多期红线
- `peg` 和毛利率先作为增强项，不把开工门槛抬太高

## 7. 注册表草案

后续代码里建议不要手工 if symbol in ...，而是先有注册表。

```python
SUBMODEL_REGISTRY: dict[str, SubmodelConfig] = {
    "platform_internet_v1": PLATFORM_INTERNET_V1,
    "semiconductor_hardtech_v1": SEMICONDUCTOR_HARDTECH_V1,
}
```

如果后面要按证券代码直接映射，可以单独再加一个符号到模型的索引层：

```python
SYMBOL_TO_SUBMODEL: dict[str, str] = {
    "03690": "platform_internet_v1",
    "00700": "platform_internet_v1",
    "01024": "platform_internet_v1",
    "00981": "semiconductor_hardtech_v1",
    "603986": "semiconductor_hardtech_v1",
}
```

这样做的好处是：

- 模型定义和标的映射解耦
- 未来同一模型可复用到更多股票
- 行业归类调整时，不会动到评分结构本身

## 8. 第一版落地建议

如果下一步开始写代码，建议按这个顺序：

1. 先实现 `DimensionConfig`、`FieldPolicy`、`RiskRuleConfig`、`SubmodelConfig`
2. 再实现 `SUBMODEL_REGISTRY`
3. 再让通用评分引擎读取 `field_policy` 和 `dimensions`
4. 先接入 `platform_internet_v1`
5. 再接入 `semiconductor_hardtech_v1`

这样最稳，因为：

- 平台互联网复用通用骨架最多
- 半导体能验证“子模型确实覆盖了营运质量差异”
- 两个模型足以证明配置化方案成立

## 9. 当前建议结论

如果只说结论：

- 后续实现应该优先走“通用引擎 + 子模型配置注册表”
- 不建议一开始为每个科技子模型单独写一个评分类
- 平台互联网和半导体第一版都已经可以被表达成独立配置对象
- 这份文档可以直接作为后续 Python 结构设计草案