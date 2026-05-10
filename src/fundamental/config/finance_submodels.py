"""Financial-sector submodel configurations."""

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


BANK_V1 = SubmodelConfig(
    industry_bucket="financial",
    submodel_id="bank_v1",
    display_name="银行",
    version="v1",
    applicable_symbols=("601328",),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "roe_3y_cv",
            "pb",
            "dividend_yield",
            "core_tier1_ratio",
            "npl_ratio",
            "provision_coverage_ratio",
            "loan_deposit_growth_gap",
            "net_interest_margin",
        ),
        optional_manual=(
            "capital_adequacy_ratio",
            "roe_3y_mean",
            "net_profit_growth",
            "notes",
        ),
        disabled_or_deweighted=(
            "debt_to_asset",
            "current_ratio",
            "inventory_growth",
            "peg",
            "pe_percentile_5y",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="capital_safety_and_asset_quality",
            weight=35,
            primary_metrics=("core_tier1_ratio", "npl_ratio", "provision_coverage_ratio"),
            notes="Capital safety and asset quality are the first-order anchors for banks.",
        ),
        DimensionConfig(
            name="profitability_and_stability",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "net_interest_margin"),
            optional_metrics=("roe_3y_mean",),
            notes="Bank profitability should be read with stability and NIM together.",
        ),
        DimensionConfig(
            name="business_growth_and_quality",
            weight=15,
            primary_metrics=("loan_deposit_growth_gap",),
            optional_metrics=("net_profit_growth",),
            inherited_from_common=False,
            notes="Growth matters, but it should not outrun funding quality.",
        ),
        DimensionConfig(
            name="shareholder_return_and_valuation",
            weight=25,
            primary_metrics=("pb", "dividend_yield"),
            inherited_from_common=False,
            notes="PB and dividend yield are more informative than PEG for banks.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="core_tier1_ratio_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("core_tier1_ratio",),
            description="Core tier 1 capital falls below the comfort zone.",
        ),
        RiskRuleConfig(
            rule_id="npl_ratio_high",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("npl_ratio",),
            description="NPL ratio has risen into an uncomfortable range.",
        ),
        RiskRuleConfig(
            rule_id="provision_coverage_low",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("provision_coverage_ratio",),
            description="Provision coverage has weakened below the safety buffer.",
        ),
    ),
    score_overrides={
        "debt_to_asset.enabled": "false",
        "current_ratio.enabled": "false",
        "inventory_growth.enabled": "false",
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "资本充足和资产质量是否仍在安全区间",
            "息差与 ROE 能否维持当前盈利韧性",
            "当前 PB 和股息率是否已经提供安全边际",
        ),
        strength_messages={
            "capital_safety_and_asset_quality": "资本充足与资产质量较稳，银行安全边际处于可跟踪区间。",
            "profitability_and_stability": "银行盈利稳定性较好，ROE 与息差表现仍有韧性。",
            "business_growth_and_quality": "信贷与负债扩张节奏基本匹配，业务质量暂未明显失真。",
            "shareholder_return_and_valuation": "当前 PB 与股息率组合较有吸引力，股东回报保护较好。",
        },
        risk_messages={
            "capital_safety_and_asset_quality": "资本充足或资产质量偏弱，银行安全边际需要优先确认。",
            "profitability_and_stability": "银行盈利稳定性偏弱，ROE 或息差韧性仍需验证。",
            "business_growth_and_quality": "信贷扩张与负债来源匹配度偏弱，业务质量存在压力。",
            "shareholder_return_and_valuation": "PB 与股息率保护偏弱，当前安全边际并不充分。",
        },
        bundled_risk_messages={
            ("npl_ratio_high", "provision_coverage_low"): "不良与拨备缓冲同步转弱，资产质量压力需要优先跟踪。",
        },
        summary_when_stable="当前综合评级为 {rating}，银行基本面仍应以资本安全和估值边际为主线跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，银行资本或资产质量红线需要优先处理。",
        fallback_highlight="资本充足、盈利稳定和股东回报暂时维持在可跟踪区间。",
        fallback_risk="后续资产质量、息差与资本缓冲能否继续支撑当前评分。",
    ),
)


INSURANCE_V1 = SubmodelConfig(
    industry_bucket="financial",
    submodel_id="insurance_v1",
    display_name="保险",
    version="v1",
    applicable_symbols=("01339",),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "roe_3y_cv",
            "pb",
            "dividend_yield",
            "solvency_adequacy_ratio",
            "combined_ratio",
            "investment_return",
            "embedded_value_growth",
            "new_business_value_growth",
        ),
        optional_manual=(
            "net_profit_growth",
            "notes",
        ),
        disabled_or_deweighted=(
            "debt_to_asset",
            "current_ratio",
            "inventory_growth",
            "peg",
            "pe_percentile_5y",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="capital_safety_and_asset_quality",
            weight=30,
            primary_metrics=("solvency_adequacy_ratio", "combined_ratio"),
            notes="Insurance capital quality should be read with underwriting discipline.",
        ),
        DimensionConfig(
            name="profitability_and_stability",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv", "investment_return"),
            notes="Investment return quality matters as much as accounting profit.",
        ),
        DimensionConfig(
            name="business_growth_and_quality",
            weight=20,
            primary_metrics=("embedded_value_growth", "new_business_value_growth"),
            optional_metrics=("net_profit_growth",),
            inherited_from_common=False,
            notes="EV and NBV growth are the main growth anchors in v1.",
        ),
        DimensionConfig(
            name="shareholder_return_and_valuation",
            weight=25,
            primary_metrics=("pb", "dividend_yield"),
            inherited_from_common=False,
            notes="PB and dividend yield remain the first-pass valuation lens for insurers.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="solvency_adequacy_ratio_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("solvency_adequacy_ratio",),
            description="Solvency adequacy falls below the comfort zone.",
        ),
        RiskRuleConfig(
            rule_id="combined_ratio_high",
            severity="risk",
            enabled=True,
            automated=True,
            required_metrics=("combined_ratio",),
            description="Combined ratio weakens above the underwriting comfort range.",
        ),
    ),
    score_overrides={
        "debt_to_asset.enabled": "false",
        "current_ratio.enabled": "false",
        "inventory_growth.enabled": "false",
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "偿付能力和综合成本率是否仍在安全区间",
            "投资收益与 ROE 能否持续支撑利润质量",
            "内含价值增长能否兑现成长期股东回报",
        ),
        strength_messages={
            "capital_safety_and_asset_quality": "保险资本缓冲与承保纪律较稳，安全边际处于可跟踪区间。",
            "profitability_and_stability": "保险盈利稳定性较好，投资收益与 ROE 表现仍有韧性。",
            "business_growth_and_quality": "内含价值与新业务价值增长较稳，业务扩张质量尚可。",
            "shareholder_return_and_valuation": "当前 PB 与股息率组合较有吸引力，估值与回报匹配度较好。",
        },
        risk_messages={
            "capital_safety_and_asset_quality": "保险资本缓冲或承保纪律偏弱，安全边际需要优先确认。",
            "profitability_and_stability": "保险盈利稳定性偏弱，投资收益或 ROE 韧性仍需验证。",
            "business_growth_and_quality": "内含价值或新业务价值增长偏弱，长期业务质量需要继续确认。",
            "shareholder_return_and_valuation": "估值与股东回报保护偏弱，当前安全边际并不充分。",
        },
        summary_when_stable="当前综合评级为 {rating}，保险基本面仍应围绕资本缓冲、承保纪律与估值边际持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，保险资本或承保红线需要优先处理。",
        fallback_highlight="资本缓冲、盈利稳定和估值边际暂时维持在可跟踪区间。",
        fallback_risk="后续偿付能力、综合成本率和内含价值增长能否继续匹配当前评分。",
    ),
)


BROKER_V1 = SubmodelConfig(
    industry_bucket="financial",
    submodel_id="broker_v1",
    display_name="券商",
    version="v1",
    applicable_symbols=("06886",),
    output_style="risk_first",
    field_policy=FieldPolicy(
        required_core=V1_BASE_REQUIRED_FIELDS
        + (
            "roe",
            "roe_3y_cv",
            "pb",
            "dividend_yield",
            "net_capital_ratio",
            "revenue_growth",
            "net_profit_growth",
        ),
        optional_manual=(
            "notes",
        ),
        disabled_or_deweighted=(
            "debt_to_asset",
            "current_ratio",
            "inventory_growth",
            "peg",
            "pe_percentile_5y",
        ),
    ),
    dimensions=(
        DimensionConfig(
            name="capital_safety_and_asset_quality",
            weight=30,
            primary_metrics=("net_capital_ratio",),
            notes="Regulatory capital remains the main balance-sheet anchor for brokers.",
        ),
        DimensionConfig(
            name="profitability_and_stability",
            weight=25,
            primary_metrics=("roe", "roe_3y_cv"),
            notes="Broker profitability should be read with cycle-adjusted stability.",
        ),
        DimensionConfig(
            name="business_growth_and_quality",
            weight=20,
            primary_metrics=("revenue_growth", "net_profit_growth"),
            inherited_from_common=False,
            notes="Broker growth is cyclical, but weak revenue quality still needs to be penalized.",
        ),
        DimensionConfig(
            name="shareholder_return_and_valuation",
            weight=25,
            primary_metrics=("pb", "dividend_yield"),
            inherited_from_common=False,
            notes="PB and dividend yield are the more stable valuation anchors for brokers.",
        ),
    ),
    risk_rules=(
        RiskRuleConfig(
            rule_id="net_capital_ratio_low",
            severity="red_flag",
            enabled=True,
            automated=True,
            required_metrics=("net_capital_ratio",),
            description="Net capital ratio falls below the comfort zone.",
        ),
    ),
    score_overrides={
        "debt_to_asset.enabled": "false",
        "current_ratio.enabled": "false",
        "inventory_growth.enabled": "false",
        "pb.priority": "true",
    },
    explanation=ExplanationConfig(
        focus_questions=(
            "净资本约束是否仍给业务扩张留下空间",
            "ROE 与利润弹性能否穿越交易周期波动",
            "当前 PB 和股息率是否已经反映周期波动风险",
        ),
        strength_messages={
            "capital_safety_and_asset_quality": "券商净资本缓冲较稳，业务扩张的安全垫仍然充足。",
            "profitability_and_stability": "券商盈利稳定性较好，ROE 韧性仍处于可跟踪区间。",
            "business_growth_and_quality": "券商收入与利润增长较好，业务扩张质量尚可。",
            "shareholder_return_and_valuation": "当前 PB 与股息率组合较有吸引力，估值透支压力有限。",
        },
        risk_messages={
            "capital_safety_and_asset_quality": "券商净资本缓冲偏弱，业务安全垫需要优先确认。",
            "profitability_and_stability": "券商盈利稳定性偏弱，ROE 韧性仍需更多周期验证。",
            "business_growth_and_quality": "券商收入与利润增长偏弱，业务扩张质量需要继续确认。",
            "shareholder_return_and_valuation": "PB 与股息率保护偏弱，当前估值安全边际并不充分。",
        },
        summary_when_stable="当前综合评级为 {rating}，券商基本面仍应围绕净资本、盈利韧性与估值边际持续跟踪。",
        summary_when_red_flag="当前综合评级为 {rating}，券商资本红线需要优先处理。",
        fallback_highlight="资本缓冲、盈利稳定和估值边际暂时维持在可跟踪区间。",
        fallback_risk="后续净资本、盈利波动与估值安全边际能否继续支撑当前评分。",
    ),
)