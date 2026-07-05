# 子模型代码配置说明

这份文档用于把 [fundamental-tech-submodels.md](fundamental-tech-submodels.md) 里的自然语言参数表，进一步映射成当前 Python 配置层采用的对象结构。

虽然文件名仍保留 `tech`，但按当前仓库实现，这份文档已经不应只按“科技子模型草案”理解，而应按“跨行业子模型配置接口说明”理解。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

这份文档适合放在“模型对象已经明确，准备理解规则如何配置化”这一层来读。建议前置阅读：

- [fundamental-module-spec.md](fundamental-module-spec.md)
- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
- [fundamental-python-model.md](fundamental-python-model.md)
- [fundamental-tech-submodels.md](fundamental-tech-submodels.md)

读完这份文档后，通常下一步是：

- [fundamental-code-layout.md](fundamental-code-layout.md)
- [fundamental-roadmap.md](fundamental-roadmap.md)

与输入输出对象对应的 Python 数据模型说明见 [fundamental-python-model.md](fundamental-python-model.md)。

对应的代码目录说明见 [fundamental-code-layout.md](fundamental-code-layout.md)。

目标不是重复展开实现细节，而是明确三件事：

- 配置对象需要表达哪些概念
- 配置和评分逻辑的边界如何切分
- 科技子模型应如何注册成独立模型

## 1. 设计目标

当前代码配置层已经围绕以下要求组织：

- 同一个评分引擎可以加载不同子模型配置
- 维度权重、字段分层、规则开关、红线参数都来自配置，而不是散落在 if/else 里
- 第一版允许部分字段缺失，但缺失策略必须由配置显式表达
- 输出结果里能知道当前是按哪套子模型算出来的

## 2. 当前模块边界

当前实现里，配置和逻辑已经基本分开：

- `config/models.py`: 配置结构定义
- `config/registry.py`: 子模型注册表
- `scoring/base_engine.py`: 通用评分引擎
- `scoring/common_rules.py`: 通用评分规则函数
- `scoring/risk_rules.py`: 风险规则函数

当前实现采用的是“通用引擎 + 配置注册表”方案，而不是每个子模型单独写一套类。

## 3. 当前核心配置结构

### 3.1 维度配置

当前实现：

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

当前实现：

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

当前实现：

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

当前实现：

```python
@dataclass(frozen=True)
class ExplanationConfig:
    focus_questions: tuple[str, ...] = ()
    strength_messages: dict[str, str] = field(default_factory=dict)
    risk_messages: dict[str, str] = field(default_factory=dict)
    bundled_risk_messages: dict[tuple[str, ...], str] = field(default_factory=dict)
    summary_when_stable: str = "当前综合评级为 {rating}，基本面整体处于可跟踪区间。"
    summary_when_red_flag: str = "当前综合评级为 {rating}，需要优先处理红线风险。"
    fallback_highlight: str = "整体评分仍处于可跟踪区间。"
    fallback_risk: str = "后续基本面兑现能否延续当前评分。"


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
    explanation: ExplanationConfig = field(default_factory=ExplanationConfig)
```

这里的关键点是：

- `field_policy` 负责校验边界
- `dimensions` 负责分数结构
- `risk_rules` 负责风险拦截和警告
- `score_overrides` 负责告诉引擎哪些通用规则在子模型里要换口径
- `explanation` 负责输出时的业务关注问题、强项话术和风险话术
- `explanation` 也负责综合说明里的摘要模板和缺省亮点/风险兜底句

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

当前这套分工已经不只服务于科技子模型，也已经承载：

- 金融子模型：`bank_v1`、`insurance_v1`、`broker_v1`
- 非金融扩展行业桶：`utility_operator_v1`、`digital_infra_v1`、`home_appliance_v1`、`auto_manufacturing_v1`、`energy_resource_v1`

也就是说，后续新增模型时，优先新增配置，而不是复制引擎代码，这条原则已经被跨行业实现验证过。

## 5. 当前注册表快照

当前注册表入口是 [src/fundamental/config/registry.py](c:/sinba/stock/src/fundamental/config/registry.py)。按当前实现，`SUBMODEL_REGISTRY` 已经统一挂接三类来源：

- `tech_submodels.py`
- `finance_submodels.py`
- `nonfinancial_submodels.py`

这意味着这层配置文件已经不再只是“科技配置草案”，而是：

- 科技子模型的主要示例来源
- 跨行业注册表结构的统一接口

## 6. 平台互联网配置示例

```python
PLATFORM_INTERNET_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="platform_internet_v1",
    display_name="平台互联网",
    version="v1",
    applicable_symbols=("03690", "00700", "01024", "09988"),
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
    explanation=ExplanationConfig(
        focus_questions=(
            "增长有没有兑现成利润",
            "利润有没有兑现成现金流",
            "当前估值是否仍要求高增长持续",
        ),
        strength_messages={
            "profit_quality": "平台经营利润质量较好，利润与现金流匹配度较高。",
            "growth_delivery": "平台增长兑现较好，营收扩张已经较多转化为利润。",
            "cashflow_and_operating_efficiency": "平台现金流兑现较好，经营效率和变现能力表现稳定。",
            "valuation_fit": "平台估值匹配度较好，当前估值对增长的透支相对有限。",
        },
        risk_messages={
            "profit_quality": "平台盈利质量偏弱，利润稳定性或现金流兑现存在压力。",
            "growth_delivery": "平台增长兑现偏弱，营收扩张尚未充分转化为利润。",
            "cashflow_and_operating_efficiency": "平台现金流兑现偏弱，经营效率仍需进一步验证。",
            "valuation_fit": "平台估值匹配偏弱，当前价格对后续增长要求偏高。",
        },
        summary_when_stable="当前综合评级为 {rating}，平台基本面整体处于可跟踪区间。",
        summary_when_red_flag="当前综合评级为 {rating}，平台现金流或利润兑现红线需要优先处理。",
        fallback_highlight="平台经营质量与增长兑现暂时保持在可跟踪区间。",
        fallback_risk="后续增长兑现和现金流转化能否延续当前评分。",
    ),
)
```

这套草案表达的核心是：

- 平台互联网复用通用评分骨架最多
- 只新增一个“现金流与运营效率”特化维度解释层
- 第一版只强制自动化一条红线

## 7. 半导体与电子硬科技配置示例

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
    explanation=ExplanationConfig(
        focus_questions=(
            "收入增长是否伴随库存和应收同步失真",
            "周期位置是否支持当前估值分位",
            "利润改善是否已经被现金流验证",
        ),
        strength_messages={
            "growth_and_cycle": "景气与成长匹配较好，当前增长没有明显脱离周期支撑。",
            "profit_quality": "半导体盈利质量尚可，利润改善已有一定现金流验证。",
            "operating_and_inventory_cycle": "库存与应收压力可控，经营质量暂未出现明显失真。",
            "valuation_fit": "当前估值分位尚可，估值压力处于可接受区间。",
        },
        risk_messages={
            "growth_and_cycle": "景气与成长支撑偏弱，当前增长仍需更多周期信号确认。",
            "profit_quality": "半导体盈利质量偏弱，利润改善尚未充分被现金流验证。",
            "operating_and_inventory_cycle": "库存与应收压力偏大，经营质量存在失真风险。",
            "valuation_fit": "估值匹配偏弱，当前估值分位对景气持续性要求较高。",
        },
        bundled_risk_messages={
            (
                "inventory_pressure_single_period",
                "receivable_pressure_single_period",
            ): "库存与应收压力偏大，经营质量存在失真风险。",
        },
        summary_when_stable="当前综合评级为 {rating}，硬科技基本面仍需结合周期继续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，景气与经营质量红线需要优先处理。",
        fallback_highlight="景气和盈利质量暂未明显脱离可跟踪区间。",
        fallback_risk="后续库存、应收与景气节奏能否继续匹配当前评分。",
    ),
)
```

这套草案表达的核心是：

- 半导体模型比平台互联网更依赖营运质量字段
- 第一版优先做单期风险提示，再逐步升级到多期红线
- `peg` 和毛利率先作为增强项，不把开工门槛抬太高

## 7. 工业自动化与智能装备配置示例

```python
INDUSTRIAL_AUTOMATION_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="industrial_automation_v1",
    display_name="工业自动化与智能装备",
    version="v1",
    applicable_symbols=("300124",),
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
            "operating_cashflow_to_profit_history",
            "peg",
            "notes",
        ),
        deferred_v2=(
            "order_backlog_growth",
            "book_to_bill_ratio",
            "capex_of_downstream_trend",
            "export_growth",
            "rd_expense_ratio",
        ),
    ),
    dimensions=(
        DimensionConfig(name="profit_quality", weight=25, primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit")),
        DimensionConfig(name="growth_delivery", weight=25, primary_metrics=("revenue_growth", "net_profit_growth")),
        DimensionConfig(
            name="operating_and_inventory_cycle",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth"),
            inherited_from_common=False,
        ),
        DimensionConfig(name="valuation_fit", weight=20, primary_metrics=("pe_percentile_5y",), optional_metrics=("peg",)),
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
    ),
    explanation=ExplanationConfig(
        focus_questions=(
            "订单与下游资本开支能否继续支撑当前增长",
            "应收、存货和现金流是否跟得上收入扩张",
            "当前估值是否已经透支制造升级预期",
        ),
        summary_when_stable="当前综合评级为 {rating}，工业自动化基本面仍需围绕订单与营运质量持续跟踪。",
    ),
)
```

这套草案表达的核心是：

- 先用现有字段近似表达“订单与营运健康”，不强行扩快照模型
- 第一版复用单期应收/存货压力规则，后续再升级到多期订单红线
- `order_backlog_growth`、`book_to_bill_ratio`、下游 capex 趋势保留在 v2 增强层

## 8. 游戏与数字内容配置示例

```python
GAME_CONTENT_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="game_content_v1",
    display_name="游戏与数字内容",
    version="v1",
    applicable_symbols=("002555",),
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
            "operating_cashflow_to_profit",
            "operating_cashflow_to_profit_history",
            "revenue_growth",
            "net_profit_growth",
            "pe_percentile_5y",
        ),
        optional_manual=("dividend_yield", "roe_3y_cv", "peg", "notes"),
        deferred_v2=(
            "new_game_pipeline_strength",
            "marketing_expense_ratio",
            "deferred_revenue_growth",
            "overseas_revenue_growth",
        ),
    ),
    dimensions=(
        DimensionConfig(name="cashflow_and_operating_efficiency", weight=30, primary_metrics=("operating_cashflow_to_profit",)),
        DimensionConfig(name="growth_delivery", weight=25, primary_metrics=("revenue_growth", "net_profit_growth")),
        DimensionConfig(name="profit_quality", weight=25, primary_metrics=("roe", "operating_cashflow_to_profit")),
        DimensionConfig(name="valuation_fit", weight=20, primary_metrics=("pe_percentile_5y",), optional_metrics=("peg", "dividend_yield")),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="ocf_profit_history_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("operating_cashflow_to_profit_history",),
            description="经营现金流/净利润连续两期偏弱",
        ),
    ),
    explanation=ExplanationConfig(
        focus_questions=(
            "产品周期能否接续当前收入与利润增长",
            "利润兑现是否已经稳定转化为经营现金流",
            "当前估值是否已经提前透支新产品预期",
        ),
        summary_when_stable="当前综合评级为 {rating}，游戏与数字内容基本面仍需围绕产品周期与现金流持续跟踪。",
    ),
)
```

这套草案表达的核心是：

- 第一版先用现金流兑现、成长和估值三组已有字段近似表达产品周期质量
- `marketing_expense_ratio`、新品储备和海外增长等更贴近业务的问题保留到 v2 增强层
- 自动化红线先抓“利润增长但现金流连续偏弱”这一类最容易失真的情形

## 9. 注册表

当前代码已经不再手工写 `if symbol in ...`，而是先通过注册表查子模型。

```python
SUBMODEL_REGISTRY: dict[str, SubmodelConfig] = {
    "platform_internet_v1": PLATFORM_INTERNET_V1,
    "semiconductor_hardtech_v1": SEMICONDUCTOR_HARDTECH_V1,
    "industrial_automation_v1": INDUSTRIAL_AUTOMATION_V1,
    "game_content_v1": GAME_CONTENT_V1,
    "utility_operator_v1": UTILITY_OPERATOR_V1,
    "digital_infra_v1": DIGITAL_INFRA_V1,
    "home_appliance_v1": HOME_APPLIANCE_V1,
}
```

按证券代码直接映射时，可以再加一个符号到模型的索引层：

```python
SYMBOL_TO_SUBMODEL: dict[str, str] = {
    "03690": "platform_internet_v1",
    "00700": "platform_internet_v1",
    "01024": "platform_internet_v1",
    "09988": "platform_internet_v1",
    "00981": "semiconductor_hardtech_v1",
    "603986": "semiconductor_hardtech_v1",
    "300124": "industrial_automation_v1",
    "02357": "industrial_automation_v1",
    "002555": "game_content_v1",
    "600900": "utility_operator_v1",
    "000591": "utility_operator_v1",
    "00728": "digital_infra_v1",
    "000651": "home_appliance_v1",
}
```

这样做的好处是：

- 模型定义和标的映射解耦
- 同一模型可复用到更多股票
- 行业归类调整时，不会动到评分结构本身

补充说明：

- 注册表机制已经不再只服务于科技子模型，而是开始承载跨行业的统一映射层
- 新增的 `utility_operator_v1`、`digital_infra_v1`、`home_appliance_v1` 说明这套配置结构已经能扩到科技之外

## 10. 第一版落地建议

如果要回看当前实现最关键的落地顺序，可以按这个顺序理解：

1. 先实现 `DimensionConfig`、`FieldPolicy`、`RiskRuleConfig`、`SubmodelConfig`
2. 再实现 `SUBMODEL_REGISTRY` 和 `SYMBOL_TO_SUBMODEL`
3. 再让通用评分引擎读取 `field_policy`、`dimensions` 和 `risk_rules`
4. 先接入 `platform_internet_v1` 与 `semiconductor_hardtech_v1`
5. 再扩到 `industrial_automation_v1` 与 `game_content_v1`
6. 再把同一套配置机制扩展到科技之外的行业桶

这样最稳，因为：

- 平台互联网复用通用骨架最多
- 半导体能验证“子模型确实覆盖了营运质量差异”
- 两个模型足以证明配置化方案成立
- 后续新增的公用事业、数字基础设施、家电消费制造，进一步证明这套配置结构并不局限于科技行业

## 11. 当前建议结论

如果只说结论：

- 当前实现已经走通“通用引擎 + 子模型配置注册表”这条路线
- 不建议一开始为每个科技子模型单独写一个评分类
- 平台互联网、半导体、工业自动化、游戏内容都已经可以被表达成独立配置对象
- 同一套配置结构也已经扩展到公用事业、数字基础设施和家电消费制造
- 这份文档现在更适合作为当前配置层的设计说明草案