"""Technology-sector submodel configurations."""

from .models import ExplanationConfig, DimensionConfig, FieldPolicy, RiskRuleConfig, SubmodelConfig

V1_BASE_REQUIRED_FIELDS = (
    "symbol",
    "name",
    "market",
    "report_period",
    "currency",
    "source",
    "updated_at",
)


PLATFORM_INTERNET_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="platform_internet_v1",
    display_name="平台互联网",
    version="v1",
    applicable_symbols=("03690", "00700", "01024", "09988"),
    output_style="growth_and_cashflow_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
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
        disabled_or_deweighted=("inventory_growth", "current_ratio", "debt_to_asset"),
    ),
    dimensions=(
        DimensionConfig(
            name="profit_quality",
            weight=35,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("dupont_driver",),
            notes="Use common quality rules.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=25,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            optional_metrics=("guidance_attainment",),
            notes="Use common growth rules with higher weight.",
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
            notes="First version relies mainly on cashflow conversion.",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y", "peg"),
            notes="Use common valuation rules.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="ocf_profit_history_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("operating_cashflow_to_profit_history",),
            description="Operating cashflow / profit is below 0.8 for two periods.",
        ),
        RiskRuleConfig(
            rule_id="marketing_up_margin_down",
            severity="warning",
            enabled=True,
            automated=False,
            required_metrics=("marketing_expense_ratio",),
            description="Marketing rises while margin quality worsens.",
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


SEMICONDUCTOR_HARDTECH_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="semiconductor_hardtech_v1",
    display_name="半导体与电子硬科技",
    version="v1",
    applicable_symbols=("00981", "603986", "06088"),
    output_style="cycle_inventory_cashflow_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
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
            notes="Growth should be interpreted with order and cycle signals.",
        ),
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("gross_margin", "dupont_driver"),
            notes="Use common quality rules with margin explanation.",
        ),
        DimensionConfig(
            name="operating_and_inventory_cycle",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth"),
            inherited_from_common=False,
            notes="First version uses relative operating-pressure scoring.",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y",),
            optional_metrics=("peg",),
            notes="PEG is optional in the first version.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="inventory_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("inventory_growth", "revenue_growth"),
            description="Inventory growth materially exceeds revenue growth.",
        ),
        RiskRuleConfig(
            rule_id="receivable_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("accounts_receivable_growth", "revenue_growth"),
            description="Receivable growth materially exceeds revenue growth.",
        ),
        RiskRuleConfig(
            rule_id="gross_margin_down_capex_high",
            severity="warning",
            enabled=True,
            automated=False,
            required_metrics=("gross_margin", "capex_growth"),
            description="Margin falls while capex remains high.",
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


INDUSTRIAL_AUTOMATION_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="industrial_automation_v1",
    display_name="工业自动化与智能装备",
    version="v1",
    applicable_symbols=("300124",),
    output_style="cycle_inventory_cashflow_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
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
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("dupont_driver",),
            notes="Use common quality rules with emphasis on cashflow verification.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=25,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            notes="Growth should still be checked against downstream capex demand.",
        ),
        DimensionConfig(
            name="operating_and_inventory_cycle",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth"),
            inherited_from_common=False,
            notes="Order and operating health are approximated by receivable and inventory pressure in v1.",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y",),
            optional_metrics=("peg",),
            notes="Valuation is secondary to order and operating health in v1.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="inventory_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("inventory_growth", "revenue_growth"),
            description="Inventory growth materially exceeds revenue growth.",
        ),
        RiskRuleConfig(
            rule_id="receivable_pressure_single_period",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("accounts_receivable_growth", "revenue_growth"),
            description="Receivable growth materially exceeds revenue growth.",
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
            "订单与下游资本开支能否继续支撑当前增长",
            "应收、存货和现金流是否跟得上收入扩张",
            "当前估值是否已经透支制造升级预期",
        ),
        strength_messages={
            "profit_quality": "工业自动化盈利质量较好，利润改善已得到一定现金流验证。",
            "growth_delivery": "工业自动化增长兑现较好，收入扩张仍有盈利支撑。",
            "operating_and_inventory_cycle": "应收与存货压力可控，订单和营运健康暂未明显失真。",
            "valuation_fit": "当前估值匹配度尚可，市场对制造升级预期透支有限。",
        },
        risk_messages={
            "profit_quality": "工业自动化盈利质量偏弱，利润改善尚未充分得到现金流验证。",
            "growth_delivery": "工业自动化增长兑现偏弱，下游需求支撑仍需继续确认。",
            "operating_and_inventory_cycle": "应收与存货压力偏大，订单与营运健康需要警惕。",
            "valuation_fit": "估值匹配偏弱，当前价格对制造升级兑现要求偏高。",
        },
        bundled_risk_messages={
            (
                "inventory_pressure_single_period",
                "receivable_pressure_single_period",
            ): "应收与存货同步承压，订单与营运健康存在失真风险。",
        },
        summary_when_stable="当前综合评级为 {rating}，工业自动化基本面仍需围绕订单与营运质量持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，工业自动化的订单与营运红线需要优先处理。",
        fallback_highlight="订单兑现与经营质量暂时维持在可跟踪区间。",
        fallback_risk="后续订单、应收和存货节奏能否继续匹配当前评分。",
    ),
)


GAME_CONTENT_V1 = SubmodelConfig(
    industry_bucket="technology",
    submodel_id="game_content_v1",
    display_name="游戏与数字内容",
    version="v1",
    applicable_symbols=("002555",),
    output_style="growth_and_cashflow_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "operating_cashflow_to_profit",
            "operating_cashflow_to_profit_history",
            "revenue_growth",
            "net_profit_growth",
            "pe_percentile_5y",
        ),
        optional_manual=(
            "dividend_yield",
            "roe_3y_cv",
            "peg",
            "notes",
        ),
        deferred_v2=(
            "new_game_pipeline_strength",
            "marketing_expense_ratio",
            "deferred_revenue_growth",
            "overseas_revenue_growth",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="cashflow_and_operating_efficiency",
            weight=30,
            primary_metrics=("operating_cashflow_to_profit",),
            optional_metrics=("operating_cashflow_to_profit_history",),
            inherited_from_common=False,
            notes="Cash conversion is the first-order signal in v1.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=25,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            notes="Growth quality proxies product-cycle sustainability in v1.",
        ),
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "operating_cashflow_to_profit"),
            optional_metrics=("roe_3y_cv",),
            notes="Profit quality is anchored on ROE and cashflow verification.",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=20,
            primary_metrics=("pe_percentile_5y",),
            optional_metrics=("peg", "dividend_yield"),
            notes="Valuation is secondary to product-cycle and cashflow continuity.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="ocf_profit_history_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("operating_cashflow_to_profit_history",),
            description="Operating cashflow / profit is below 0.8 for two periods.",
        ),
    ),
    score_overrides={
        "cashflow_and_operating_efficiency.weight": "30",
        "peg.required": "false",
        "dividend_yield.required": "false",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "产品周期能否接续当前收入与利润增长",
            "利润兑现是否已经稳定转化为经营现金流",
            "当前估值是否已经提前透支新产品预期",
        ),
        strength_messages={
            "cashflow_and_operating_efficiency": "游戏现金流兑现较好，利润与经营现金回款匹配度较高。",
            "growth_delivery": "游戏增长兑现较好，当前产品周期仍在支撑收入与利润扩张。",
            "profit_quality": "数字内容盈利质量较好，资本回报与现金流验证较为一致。",
            "valuation_fit": "当前估值匹配度尚可，市场对新品周期的透支相对有限。",
        },
        risk_messages={
            "cashflow_and_operating_efficiency": "游戏现金流兑现偏弱，利润增长尚未稳定转化为经营现金流。",
            "growth_delivery": "游戏增长兑现偏弱，当前产品周期持续性仍需确认。",
            "profit_quality": "数字内容盈利质量偏弱，资本回报与现金流验证仍有缺口。",
            "valuation_fit": "估值匹配偏弱，当前价格对新品周期延续要求偏高。",
        },
        summary_when_stable="当前综合评级为 {rating}，游戏与数字内容基本面仍需围绕产品周期与现金流持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，产品周期兑现与现金流红线需要优先处理。",
        fallback_highlight="当前产品周期与现金流兑现暂时维持在可跟踪区间。",
        fallback_risk="后续新品表现与现金流转化能否继续支撑当前评分。",
    ),
)
