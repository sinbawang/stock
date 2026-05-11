"""Non-financial sector submodel configurations for additional holdings."""

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


UTILITY_OPERATOR_V1 = SubmodelConfig(
    industry_bucket="utility",
    submodel_id="utility_operator_v1",
    display_name="公用事业与新能源运营",
    version="v1",
    applicable_symbols=("600900", "000591"),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "roe_3y_cv",
            "operating_cashflow_to_profit",
            "dividend_yield",
            "pe_percentile_5y",
            "revenue_growth",
            "net_profit_growth",
        ),
        optional_manual=(
            "operating_cashflow_to_profit_history",
            "debt_to_asset",
            "pb",
            "notes",
        ),
        disabled_or_deweighted=(
            "inventory_growth",
            "current_ratio",
            "peg",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            notes="Utilities should first be read through profitability stability and cashflow conversion.",
        ),
        DimensionConfig(
            name="cashflow_and_operating_efficiency",
            weight=25,
            primary_metrics=("operating_cashflow_to_profit",),
            optional_metrics=("operating_cashflow_to_profit_history",),
            inherited_from_common=False,
            notes="Cashflow conversion and payout sustainability are the main v1 anchors.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=20,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            optional_metrics=("debt_to_asset",),
            notes="Utilities still need modest growth support, but it is secondary to cashflow and payout quality.",
        ),
        DimensionConfig(
            name="yield_and_valuation",
            weight=30,
            primary_metrics=("dividend_yield", "pe_percentile_5y"),
            inherited_from_common=False,
            notes="Dividend yield plus PE percentile is more informative than the financial PB rubric for mature power assets.",
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
        "inventory_growth.enabled": "false",
        "current_ratio.enabled": "false",
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "现金流与分红能力能否继续支撑当前估值",
            "负债表韧性是否足以穿越电价或来水波动",
            "公用事业属性之外是否还有稳定增长支撑",
        ),
        strength_messages={
            "profit_quality": "公用事业盈利质量较稳，利润与现金流匹配度仍处于可跟踪区间。",
            "cashflow_and_operating_efficiency": "公用事业现金流兑现较好，分红与经营效率具备一定支撑。",
            "growth_delivery": "公用事业增长兑现尚可，稳健经营之外仍有一定增量支撑。",
            "yield_and_valuation": "当前股息率与估值分位匹配较好，防御型回报特征较明确。",
        },
        risk_messages={
            "profit_quality": "公用事业盈利质量偏弱，利润稳定性或现金流兑现仍需确认。",
            "cashflow_and_operating_efficiency": "公用事业现金流兑现偏弱，分红可持续性需要继续验证。",
            "growth_delivery": "公用事业增长兑现偏弱，稳健经营之外的增量支撑仍需确认。",
            "yield_and_valuation": "股息率与估值分位保护偏弱，当前防御型安全边际并不充分。",
        },
        summary_when_stable="当前综合评级为 {rating}，公用事业与新能源运营基本面仍应围绕现金流、分红与负债表持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，公用事业现金流或负债表红线需要优先处理。",
        fallback_highlight="现金流、分红与负债表暂时维持在可跟踪区间。",
        fallback_risk="后续现金流转换、分红稳定性与负债水平能否继续匹配当前评分。",
    ),
)


DIGITAL_INFRA_V1 = SubmodelConfig(
    industry_bucket="digital_infrastructure",
    submodel_id="digital_infra_v1",
    display_name="数字基础设施",
    version="v1",
    applicable_symbols=("00728",),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "operating_cashflow_to_profit",
            "operating_cashflow_to_profit_history",
            "revenue_growth",
            "net_profit_growth",
            "pb",
            "dividend_yield",
        ),
        optional_manual=(
            "roe_3y_cv",
            "pe_percentile_5y",
            "peg",
            "notes",
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
            weight=25,
            primary_metrics=("roe", "operating_cashflow_to_profit"),
            optional_metrics=("roe_3y_cv",),
            notes="Digital infrastructure should be judged by service economics and cashflow quality.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=20,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            notes="Growth is secondary to payout and infrastructure monetization quality.",
        ),
        DimensionConfig(
            name="cashflow_and_operating_efficiency",
            weight=25,
            primary_metrics=("operating_cashflow_to_profit", "operating_cashflow_to_profit_history"),
            inherited_from_common=False,
            notes="Cashflow conversion is the main automated red-flag anchor in v1.",
        ),
        DimensionConfig(
            name="shareholder_return_and_valuation",
            weight=30,
            primary_metrics=("pb", "dividend_yield"),
            inherited_from_common=False,
            notes="Telecom operators are better framed through payout and balance-sheet-backed valuation.",
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
        "inventory_growth.enabled": "false",
        "debt_to_asset.enabled": "false",
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "云网与基础通信业务能否继续兑现成稳定现金流",
            "高股息分配是否仍有经营现金流支撑",
            "数字基础设施投入能否带来可持续回报",
        ),
        strength_messages={
            "profit_quality": "数字基础设施盈利质量较稳，通信主业与现金流匹配度较好。",
            "growth_delivery": "数字基础设施增长兑现尚可，新业务扩张仍有利润支撑。",
            "cashflow_and_operating_efficiency": "数字基础设施现金流兑现较好，网络资产经营效率保持稳定。",
            "shareholder_return_and_valuation": "当前 PB 与股息率组合较有吸引力，防御与回报特征兼具。",
        },
        risk_messages={
            "profit_quality": "数字基础设施盈利质量偏弱，主业回报或现金流匹配仍需验证。",
            "growth_delivery": "数字基础设施增长兑现偏弱，新业务对利润拉动仍不充分。",
            "cashflow_and_operating_efficiency": "数字基础设施现金流兑现偏弱，资本开支回收效率需要继续跟踪。",
            "shareholder_return_and_valuation": "PB 与股息率保护偏弱，当前回报型安全边际并不充分。",
        },
        summary_when_stable="当前综合评级为 {rating}，数字基础设施基本面仍应围绕现金流、分红与云网回报持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，数字基础设施现金流红线需要优先处理。",
        fallback_highlight="现金流、分红与基础通信资产回报暂时维持在可跟踪区间。",
        fallback_risk="后续云网投入、现金流转换与股东回报能否继续匹配当前评分。",
    ),
)


HOME_APPLIANCE_V1 = SubmodelConfig(
    industry_bucket="consumer",
    submodel_id="home_appliance_v1",
    display_name="家电消费制造",
    version="v1",
    applicable_symbols=("000651",),
    output_style="risk_first",
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
            "pb",
            "dividend_yield",
        ),
        optional_manual=(
            "gross_margin",
            "pe_percentile_5y",
            "peg",
            "notes",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("gross_margin",),
            notes="Consumer durables still need profitability to be checked against cashflow conversion.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=20,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            notes="Growth quality matters, but mature appliance leaders should not be judged by speed alone.",
        ),
        DimensionConfig(
            name="operating_and_inventory_cycle",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth"),
            inherited_from_common=False,
            notes="Channel inventory and receivable pressure are the first-order operating risks in v1.",
        ),
        DimensionConfig(
            name="shareholder_return_and_valuation",
            weight=25,
            primary_metrics=("pb", "dividend_yield"),
            inherited_from_common=False,
            notes="For mature appliance leaders, payout and PB are more stable anchors than PEG alone.",
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
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "渠道库存与应收变化是否仍与收入节奏匹配",
            "成熟家电龙头的利润能否继续兑现成现金流与分红",
            "当前估值和股东回报是否足以覆盖增长放缓风险",
        ),
        strength_messages={
            "profit_quality": "家电盈利质量较好，利润与现金流匹配度仍处于较稳区间。",
            "growth_delivery": "家电增长兑现尚可，收入扩张仍有利润支撑。",
            "operating_and_inventory_cycle": "渠道库存与应收压力可控，经营质量暂未明显失真。",
            "shareholder_return_and_valuation": "当前 PB 与股息率组合较有吸引力，股东回报保护较好。",
        },
        risk_messages={
            "profit_quality": "家电盈利质量偏弱，利润稳定性或现金流兑现仍需验证。",
            "growth_delivery": "家电增长兑现偏弱，收入扩张对利润拉动仍不充分。",
            "operating_and_inventory_cycle": "渠道库存与应收压力偏大，经营质量需要警惕。",
            "shareholder_return_and_valuation": "PB 与股息率保护偏弱，当前股东回报安全边际并不充分。",
        },
        bundled_risk_messages={
            (
                "inventory_pressure_single_period",
                "receivable_pressure_single_period",
            ): "渠道库存与应收同步承压，经营质量存在失真风险。",
        },
        summary_when_stable="当前综合评级为 {rating}，家电消费制造基本面仍应围绕渠道健康、现金流与股东回报持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，家电渠道与营运红线需要优先处理。",
        fallback_highlight="渠道健康、现金流与股东回报暂时维持在可跟踪区间。",
        fallback_risk="后续渠道库存、应收与分红稳定性能否继续匹配当前评分。",
    ),
)


AUTO_MANUFACTURING_V1 = SubmodelConfig(
    industry_bucket="consumer",
    submodel_id="auto_manufacturing_v1",
    display_name="汽车消费制造",
    version="v1",
    applicable_symbols=("00175",),
    output_style="risk_first",
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
            "asset_turnover",
            "pe_percentile_5y",
        ),
        optional_manual=(
            "gross_margin",
            "gross_margin_trend",
            "peg",
            "pb",
            "dividend_yield",
            "debt_to_asset",
            "current_ratio",
            "price_war_pressure",
            "overseas_revenue_share",
            "dupont_driver",
            "notes",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="profit_quality",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "operating_cashflow_to_profit"),
            optional_metrics=("gross_margin", "gross_margin_trend", "dupont_driver"),
            notes="Auto manufacturers still need profitability to be checked against cashflow conversion and financing dependence.",
        ),
        DimensionConfig(
            name="growth_delivery",
            weight=20,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            optional_metrics=("overseas_revenue_share",),
            notes="Vehicle volume and mix growth matters, but the first version still judges delivery through revenue and profit growth.",
        ),
        DimensionConfig(
            name="inventory_channel_and_turnover",
            weight=30,
            primary_metrics=("inventory_growth", "accounts_receivable_growth", "revenue_growth", "asset_turnover"),
            optional_metrics=("price_war_pressure",),
            inherited_from_common=False,
            notes="Dealer inventory and receivable pressure should be read together with asset turnover, not with a generic leverage penalty.",
        ),
        DimensionConfig(
            name="valuation_fit",
            weight=25,
            primary_metrics=("pe_percentile_5y",),
            optional_metrics=("peg",),
            inherited_from_common=False,
            notes="Auto valuation should first anchor on historical PE percentile, then treat PEG as a secondary cross-check because cycle and model launches can distort single-period growth.",
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
        "peg.required": "false",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "库存、渠道和应收变化是否仍与销量和收入节奏匹配",
            "总资产周转率能否维持在健康区间，证明扩张没有被低效资产吞噬",
            "汽车制造利润能否继续兑现成经营现金流",
            "毛利率趋势、价格战压力与海外收入占比是否支持当前增长质量判断",
            "当前 PE 分位与 PEG 是否已经较充分反映行业竞争与价格战风险",
        ),
        strength_messages={
            "profit_quality": "汽车制造盈利质量较好，利润与现金流匹配度仍处于较稳区间。",
            "growth_delivery": "汽车制造增长兑现尚可，收入扩张仍有利润支撑。",
            "inventory_channel_and_turnover": "库存、渠道与周转效率匹配尚可，经营质量暂未明显失真。",
            "valuation_fit": "当前 PE 分位仍处低位，估值匹配度尚可。",
        },
        risk_messages={
            "profit_quality": "汽车制造盈利质量偏弱，利润稳定性或现金流兑现仍需验证。",
            "growth_delivery": "汽车制造增长兑现偏弱，收入扩张对利润拉动仍不充分。",
            "inventory_channel_and_turnover": "库存、渠道或周转效率偏弱，经营质量需要警惕。",
            "valuation_fit": "PE 分位与 PEG 保护偏弱，当前估值安全边际并不充分。",
        },
        bundled_risk_messages={
            (
                "inventory_pressure_single_period",
                "receivable_pressure_single_period",
            ): "库存与应收同步承压，汽车制造经营质量存在失真风险。",
        },
        summary_when_stable="当前综合评级为 {rating}，汽车消费制造基本面仍应围绕库存、周转效率、现金流与估值匹配持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，汽车制造渠道与营运红线需要优先处理。",
        fallback_highlight="库存、周转效率与现金流暂时维持在可跟踪区间。",
        fallback_risk="后续库存、应收、周转效率与价格竞争压力能否继续匹配当前评分。",
    ),
)


ENERGY_RESOURCE_V1 = SubmodelConfig(
    industry_bucket="energy_resource",
    submodel_id="energy_resource_v1",
    display_name="能源资源",
    version="v1",
    applicable_symbols=("601088",),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "operating_cashflow_to_profit",
            "operating_cashflow_to_profit_history",
            "debt_to_asset",
            "dividend_yield",
            "pe_percentile_5y",
        ),
        optional_manual=(
            "roe_3y_cv",
            "revenue_growth",
            "net_profit_growth",
            "pb",
            "free_cashflow_yield",
            "capex_to_operating_cashflow",
            "unit_cost_position",
            "notes",
        ),
        deferred_v2=(
            "reserve_life_index",
            "commodity_price_sensitivity",
        ),
        disabled_or_deweighted=(
            "inventory_growth",
            "current_ratio",
            "peg",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="cashflow_and_operating_efficiency",
            weight=35,
            primary_metrics=("operating_cashflow_to_profit", "operating_cashflow_to_profit_history"),
            inherited_from_common=False,
            notes="Energy and resource assets should first be judged by cashflow conversion across the cycle.",
        ),
        DimensionConfig(
            name="resource_cycle_resilience",
            weight=25,
            primary_metrics=("debt_to_asset",),
            optional_metrics=("capex_to_operating_cashflow", "unit_cost_position", "reserve_life_index", "commodity_price_sensitivity"),
            inherited_from_common=False,
            notes="This slot uses balance-sheet resilience as the v1 anchor, then adds cost curve, capex pressure, and reserve resilience when available.",
        ),
        DimensionConfig(
            name="profit_quality",
            weight=20,
            primary_metrics=("roe",),
            optional_metrics=("roe_3y_cv", "net_profit_growth"),
            notes="Profitability still matters, but it is secondary to cashflow durability in v1.",
        ),
        DimensionConfig(
            name="yield_and_valuation",
            weight=20,
            primary_metrics=("dividend_yield", "pe_percentile_5y"),
            inherited_from_common=False,
            notes="Yield and valuation percentile are more useful than PEG for cyclical resource names.",
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
            rule_id="capex_pressure_high",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("capex_to_operating_cashflow", "dividend_yield"),
            description="Capex pressure is high while payout remains elevated.",
        ),
        RiskRuleConfig(
            rule_id="unit_cost_position_weak",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("unit_cost_position",),
            description="Unit cost position has weakened below the comfort zone.",
        ),
        RiskRuleConfig(
            rule_id="reserve_life_short",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("reserve_life_index",),
            description="Reserve life index has fallen below the comfort zone.",
        ),
        RiskRuleConfig(
            rule_id="commodity_sensitivity_high",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("commodity_price_sensitivity",),
            description="Commodity price sensitivity is too high for the current cycle position.",
        ),
    ),
    score_overrides={
        "inventory_growth.enabled": "false",
        "current_ratio.enabled": "false",
        "peg.required": "false",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "周期高位赚到的钱能否继续兑现成经营现金流",
            "分红与负债表韧性能否共同穿越商品价格波动",
            "当前估值分位是否已经过度透支本轮景气",
        ),
        strength_messages={
            "cashflow_and_operating_efficiency": "能源资源现金流兑现较好，周期利润已有较强现金流验证。",
            "resource_cycle_resilience": "成本曲线与资本开支压力尚可，周期承压能力仍处于可跟踪区间。",
            "profit_quality": "能源资源盈利质量尚可，当前景气并未完全脱离盈利支撑。",
            "yield_and_valuation": "当前股息率与估值分位匹配较好，周期股的回报保护相对充足。",
        },
        risk_messages={
            "cashflow_and_operating_efficiency": "能源资源现金流兑现偏弱，周期利润的含金量需要继续验证。",
            "resource_cycle_resilience": "成本曲线或资本开支压力偏弱，周期承压能力需要警惕。",
            "profit_quality": "能源资源盈利质量偏弱，当前景气对利润支撑仍不稳固。",
            "yield_and_valuation": "股息率与估值分位保护偏弱，当前周期股安全边际并不充分。",
        },
        bundled_risk_messages={
            (
                "capex_pressure_high",
                "unit_cost_position_weak",
            ): "资本开支压力与成本位置同步转弱，周期下行时的自由现金流韧性需要优先跟踪。",
            (
                "reserve_life_short",
                "commodity_sensitivity_high",
            ): "储量接续能力与价格敏感度同步偏弱，周期波动下的盈利韧性需要优先跟踪。",
        },
        summary_when_stable="当前综合评级为 {rating}，能源资源基本面仍应围绕现金流、分红与负债表韧性持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，能源资源现金流红线需要优先处理。",
        fallback_highlight="现金流、分红与负债表韧性暂时维持在可跟踪区间。",
        fallback_risk="后续商品价格波动下的现金流转换和分红持续性能否继续匹配当前评分。",
    ),
)