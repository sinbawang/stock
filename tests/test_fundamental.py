import pandas as pd

from fundamental.data import cn_snapshot_fetcher
from fundamental.config.registry import get_submodel, get_submodel_for_symbol
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.reporting import render_fundamental_brief, render_scorecard_text
from fundamental.services import analyze_snapshot
from fundamental.services.fetch_and_analyze_cn_snapshot import _relax_missing_cn_dividend_yield
from fundamental.validation import validate_snapshot_against_policy


def make_platform_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "03690",
        "name": "美团",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 18.6,
        "roe_3y_cv": 0.18,
        "operating_cashflow_to_profit": 1.12,
        "operating_cashflow_to_profit_history": [1.12, 1.04],
        "revenue_growth": 21.3,
        "net_profit_growth": 33.8,
        "pe_percentile_5y": 41.0,
        "peg": 0.92,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_semiconductor_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "00981",
        "name": "中芯国际",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 9.8,
        "roe_3y_cv": 0.28,
        "operating_cashflow_to_profit": 0.84,
        "revenue_growth": 8.0,
        "net_profit_growth": 12.0,
        "accounts_receivable_growth": 30.0,
        "inventory_growth": 28.0,
        "pe_percentile_5y": 72.0,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_industrial_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "300124",
        "name": "汇川技术",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 19.4,
        "roe_3y_cv": 0.16,
        "operating_cashflow_to_profit": 1.12,
        "revenue_growth": 18.0,
        "net_profit_growth": 20.5,
        "accounts_receivable_growth": 14.0,
        "inventory_growth": 12.0,
        "pe_percentile_5y": 48.0,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_game_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "002555",
        "name": "三七互娱",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 22.0,
        "operating_cashflow_to_profit": 1.18,
        "operating_cashflow_to_profit_history": [1.18, 1.02],
        "revenue_growth": 16.0,
        "net_profit_growth": 24.0,
        "pe_percentile_5y": 43.0,
        "dividend_yield": 3.1,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_bank_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "601328",
        "name": "交通银行",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 11.8,
        "roe_3y_cv": 0.12,
        "pb": 0.62,
        "dividend_yield": 5.1,
        "core_tier1_ratio": 10.6,
        "npl_ratio": 1.28,
        "provision_coverage_ratio": 242.0,
        "loan_deposit_growth_gap": 1.4,
        "net_interest_margin": 1.82,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_insurance_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "01339",
        "name": "中国人保",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 13.6,
        "roe_3y_cv": 0.14,
        "pb": 0.68,
        "dividend_yield": 4.8,
        "solvency_adequacy_ratio": 228.0,
        "combined_ratio": 97.6,
        "investment_return": 4.7,
        "embedded_value_growth": 10.5,
        "new_business_value_growth": 12.3,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_broker_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "06886",
        "name": "华泰证券",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 12.6,
        "roe_3y_cv": 0.16,
        "pb": 0.79,
        "dividend_yield": 4.0,
        "net_capital_ratio": 218.0,
        "revenue_growth": 18.0,
        "net_profit_growth": 23.0,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_utility_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "600900",
        "name": "长江电力",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 14.2,
        "roe_3y_cv": 0.09,
        "operating_cashflow_to_profit": 1.26,
        "operating_cashflow_to_profit_history": [1.26, 1.08],
        "debt_to_asset": 58.0,
        "dividend_yield": 3.6,
        "pe_percentile_5y": 55.0,
        "revenue_growth": 7.5,
        "net_profit_growth": 8.4,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_digital_infra_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "00728",
        "name": "中国电信",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 8.4,
        "roe_3y_cv": 0.1,
        "operating_cashflow_to_profit": 1.18,
        "operating_cashflow_to_profit_history": [1.18, 1.03],
        "revenue_growth": 6.2,
        "net_profit_growth": 7.1,
        "pb": 0.82,
        "dividend_yield": 5.4,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_home_appliance_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "000651",
        "name": "格力电器",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 24.0,
        "roe_3y_cv": 0.12,
        "operating_cashflow_to_profit": 1.1,
        "revenue_growth": 9.0,
        "net_profit_growth": 11.5,
        "accounts_receivable_growth": 6.0,
        "inventory_growth": 8.0,
        "pb": 2.1,
        "dividend_yield": 4.9,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_auto_manufacturing_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "00175",
        "name": "吉利汽车",
        "market": "HK",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-11T23:30:00",
        "roe": 18.8,
        "roe_3y_cv": 0.03,
        "operating_cashflow_to_profit": 2.8,
        "revenue_growth": 25.1,
        "net_profit_growth": 12.0,
        "accounts_receivable_growth": 1.4,
        "inventory_growth": 8.8,
        "asset_turnover": 1.24,
        "pe_percentile_5y": 16.0,
        "peg": 58.56,
        "pb": 2.24,
        "dividend_yield": 1.37,
        "dupont_driver": "leverage",
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def make_energy_resource_snapshot(**overrides) -> FundamentalSnapshot:
    payload = {
        "symbol": "601088",
        "name": "中国神华",
        "market": "CN",
        "report_period": "2025-12-31",
        "currency": "CNY",
        "source": "manual",
        "updated_at": "2026-05-09T20:30:00",
        "roe": 16.8,
        "roe_3y_cv": 0.18,
        "operating_cashflow_to_profit": 1.22,
        "operating_cashflow_to_profit_history": [1.22, 1.06],
        "debt_to_asset": 34.0,
        "dividend_yield": 6.8,
        "pe_percentile_5y": 46.0,
        "revenue_growth": 5.2,
        "net_profit_growth": 4.4,
        "free_cashflow_yield": 9.4,
        "capex_to_operating_cashflow": 0.38,
        "unit_cost_position": 76.0,
        "reserve_life_index": 14.0,
        "commodity_price_sensitivity": 0.92,
    }
    payload.update(overrides)
    return FundamentalSnapshot(**payload)


def test_validate_snapshot_against_policy_rejects_missing_required_fields():
    snapshot = make_platform_snapshot(peg=None)
    submodel = get_submodel("platform_internet_v1")

    validation = validate_snapshot_against_policy(snapshot, submodel.field_policy)

    assert validation.is_valid is False
    assert validation.required_missing == ["peg"]


def test_relax_missing_cn_dividend_yield_for_energy_resource_submodel():
    submodel = get_submodel("energy_resource_v1")

    relaxed_submodel, assumptions = _relax_missing_cn_dividend_yield(submodel, missing_dividend_yield=True)

    assert "dividend_yield" not in relaxed_submodel.field_policy.required_core
    assert "dividend_yield" in relaxed_submodel.field_policy.optional_manual
    assert any("dividend_yield is treated as optional" in assumption for assumption in assumptions)


def test_relax_missing_cn_dividend_yield_is_noop_when_present():
    submodel = get_submodel("energy_resource_v1")

    relaxed_submodel, assumptions = _relax_missing_cn_dividend_yield(submodel, missing_dividend_yield=False)

    assert relaxed_submodel == submodel
    assert assumptions == ()


def test_registry_can_resolve_platform_submodel_by_symbol():
    submodel = get_submodel_for_symbol("03690")

    assert submodel is not None
    assert submodel.submodel_id == "platform_internet_v1"


def test_registry_can_resolve_industrial_submodel_by_symbol():
    submodel = get_submodel_for_symbol("300124")

    assert submodel is not None
    assert submodel.submodel_id == "industrial_automation_v1"


def test_registry_can_resolve_game_submodel_by_symbol():
    submodel = get_submodel_for_symbol("002555")

    assert submodel is not None
    assert submodel.submodel_id == "game_content_v1"


def test_registry_can_resolve_bank_submodel_by_symbol():
    submodel = get_submodel_for_symbol("601328")

    assert submodel is not None
    assert submodel.submodel_id == "bank_v1"


def test_registry_can_resolve_insurance_submodel_by_symbol():
    submodel = get_submodel_for_symbol("01339")

    assert submodel is not None
    assert submodel.submodel_id == "insurance_v1"


def test_registry_can_resolve_broker_submodel_by_symbol():
    submodel = get_submodel_for_symbol("06886")

    assert submodel is not None
    assert submodel.submodel_id == "broker_v1"


def test_registry_can_resolve_utility_submodel_by_symbol():
    assert get_submodel_for_symbol("600900").submodel_id == "utility_operator_v1"
    assert get_submodel_for_symbol("000591").submodel_id == "utility_operator_v1"


def test_registry_can_resolve_digital_infra_submodel_by_symbol():
    submodel = get_submodel_for_symbol("00728")

    assert submodel is not None
    assert submodel.submodel_id == "digital_infra_v1"


def test_registry_can_resolve_home_appliance_submodel_by_symbol():
    submodel = get_submodel_for_symbol("000651")

    assert submodel is not None
    assert submodel.submodel_id == "home_appliance_v1"


def test_registry_can_resolve_auto_manufacturing_submodel_by_symbol():
    submodel = get_submodel_for_symbol("00175")

    assert submodel is not None
    assert submodel.submodel_id == "auto_manufacturing_v1"


def test_registry_can_resolve_aviation_industrial_submodel_by_symbol():
    submodel = get_submodel_for_symbol("02357")

    assert submodel is not None
    assert submodel.submodel_id == "industrial_automation_v1"


def test_registry_can_resolve_energy_resource_submodel_by_symbol():
    submodel = get_submodel_for_symbol("601088")

    assert submodel is not None
    assert submodel.submodel_id == "energy_resource_v1"


def test_analyze_snapshot_scores_platform_internet_end_to_end():
    snapshot = make_platform_snapshot()

    result = analyze_snapshot(snapshot, "platform_internet_v1")

    assert result.submodel_id == "platform_internet_v1"
    assert result.industry_bucket == "technology"
    assert result.rating == "A"
    assert result.red_flag is False
    assert len(result.dimension_scores) == 4
    assert result.total_score > 80
    assert any("平台经营利润质量较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "平台基本面整体处于可跟踪区间" in result.combined_comment
    assert result.combined_comment.index("主要亮点是") < result.combined_comment.index("当前最需要跟踪的是")


def test_analyze_snapshot_flags_semiconductor_operating_pressure():
    snapshot = make_semiconductor_snapshot()

    result = analyze_snapshot(snapshot, "semiconductor_hardtech_v1")

    triggered_rule_ids = {rule.rule_id for rule in result.triggered_rules}

    assert result.submodel_id == "semiconductor_hardtech_v1"
    assert "inventory_pressure_single_period" in triggered_rule_ids
    assert "receivable_pressure_single_period" in triggered_rule_ids
    assert any("存货增速显著高于营收增速" in risk for risk in result.risks)
    assert any("应收增速显著高于营收增速" in risk for risk in result.risks)
    assert any("库存与应收压力偏大" in risk for risk in result.risks)
    assert result.combined_comment is not None
    assert "硬科技基本面仍需结合周期继续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_industrial_automation_end_to_end():
    snapshot = make_industrial_snapshot()

    result = analyze_snapshot(snapshot, "industrial_automation_v1")

    assert result.submodel_id == "industrial_automation_v1"
    assert result.industry_bucket == "technology"
    assert result.rating in ("A", "B")
    assert any("工业自动化盈利质量较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "工业自动化基本面仍需围绕订单与营运质量持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_game_content_end_to_end():
    snapshot = make_game_snapshot()

    result = analyze_snapshot(snapshot, "game_content_v1")

    assert result.submodel_id == "game_content_v1"
    assert result.industry_bucket == "technology"
    assert result.rating == "A"
    assert any("游戏现金流兑现较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "游戏与数字内容基本面仍需围绕产品周期与现金流持续跟踪" in result.combined_comment
    assert result.combined_comment.index("主要亮点是") < result.combined_comment.index("当前最需要跟踪的是")


def test_analyze_snapshot_can_auto_resolve_submodel_from_symbol():
    snapshot = make_platform_snapshot()

    result = analyze_snapshot(snapshot)

    assert result.submodel_id == "platform_internet_v1"
    assert result.rating == "A"


def test_analyze_snapshot_scores_bank_end_to_end():
    snapshot = make_bank_snapshot()

    result = analyze_snapshot(snapshot, "bank_v1")

    assert result.submodel_id == "bank_v1"
    assert result.industry_bucket == "financial"
    assert result.rating == "A"
    assert result.red_flag is False
    assert any("资本充足与资产质量较稳" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "银行基本面仍应以资本安全和估值边际为主线跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_insurance_end_to_end():
    snapshot = make_insurance_snapshot()

    result = analyze_snapshot(snapshot, "insurance_v1")

    assert result.submodel_id == "insurance_v1"
    assert result.industry_bucket == "financial"
    assert result.rating == "A"
    assert any("保险资本缓冲与承保纪律较稳" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "保险基本面仍应围绕资本缓冲、承保纪律与估值边际持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_broker_end_to_end():
    snapshot = make_broker_snapshot()

    result = analyze_snapshot(snapshot, "broker_v1")

    assert result.submodel_id == "broker_v1"
    assert result.industry_bucket == "financial"
    assert result.rating == "A"
    assert any("券商净资本缓冲较稳" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "券商基本面仍应围绕净资本、盈利韧性与估值边际持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_utility_operator_end_to_end():
    snapshot = make_utility_snapshot()

    result = analyze_snapshot(snapshot, "utility_operator_v1")

    assert result.submodel_id == "utility_operator_v1"
    assert result.industry_bucket == "utility"
    assert result.rating in ("A", "B")
    assert any("公用事业现金流兑现较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "公用事业与新能源运营基本面仍应围绕现金流、分红与负债表持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_digital_infra_end_to_end():
    snapshot = make_digital_infra_snapshot()

    result = analyze_snapshot(snapshot, "digital_infra_v1")

    assert result.submodel_id == "digital_infra_v1"
    assert result.industry_bucket == "digital_infrastructure"
    assert result.rating in ("A", "B")
    assert any("数字基础设施现金流兑现较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "数字基础设施基本面仍应围绕现金流、分红与云网回报持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_home_appliance_end_to_end():
    snapshot = make_home_appliance_snapshot()

    result = analyze_snapshot(snapshot, "home_appliance_v1")

    assert result.submodel_id == "home_appliance_v1"
    assert result.industry_bucket == "consumer"
    assert result.rating in ("A", "B")
    assert any("家电盈利质量较好" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "家电消费制造基本面仍应围绕渠道健康、现金流与股东回报持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_analyze_snapshot_scores_auto_manufacturing_end_to_end():
    snapshot = make_auto_manufacturing_snapshot()

    result = analyze_snapshot(snapshot, "auto_manufacturing_v1")

    assert result.submodel_id == "auto_manufacturing_v1"
    assert result.industry_bucket == "consumer"
    assert result.rating in ("A", "B")
    assert any("库存、渠道与周转效率匹配尚可" in strength for strength in result.strengths)
    assert result.combined_comment is not None
    assert "汽车消费制造基本面仍应围绕库存、周转效率、现金流与估值匹配持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_auto_manufacturing_specialist_fields_refine_existing_dimensions_when_present():
    baseline = analyze_snapshot(make_auto_manufacturing_snapshot(), "auto_manufacturing_v1")
    enriched = analyze_snapshot(
        make_auto_manufacturing_snapshot(
            gross_margin_trend="improving",
            price_war_pressure="low",
            overseas_revenue_share=31.5,
        ),
        "auto_manufacturing_v1",
    )

    profit_quality = next(score for score in enriched.dimension_scores if score.dimension == "profit_quality")
    growth_delivery = next(score for score in enriched.dimension_scores if score.dimension == "growth_delivery")
    inventory_cycle = next(score for score in enriched.dimension_scores if score.dimension == "inventory_channel_and_turnover")

    assert enriched.total_score > baseline.total_score
    assert "毛利率趋势 improving" in (profit_quality.score_basis or "")
    assert "海外收入占比 31.50" in (growth_delivery.score_basis or "")
    assert "价格战压力 low" in (inventory_cycle.score_basis or "")


def test_analyze_snapshot_scores_energy_resource_end_to_end():
    snapshot = make_energy_resource_snapshot()

    result = analyze_snapshot(snapshot, "energy_resource_v1")

    assert result.submodel_id == "energy_resource_v1"
    assert result.industry_bucket == "energy_resource"
    assert result.rating in ("A", "B")
    assert any("能源资源现金流兑现较好" in strength for strength in result.strengths)
    assert any(score.dimension == "resource_cycle_resilience" for score in result.dimension_scores)
    assert result.combined_comment is not None
    assert "能源资源基本面仍应围绕现金流、分红与负债表韧性持续跟踪" in result.combined_comment
    assert result.combined_comment.index("当前最需要跟踪的是") < result.combined_comment.index("主要亮点是")


def test_energy_resource_cycle_resilience_keeps_v1_anchor_without_specialist_fields():
    snapshot = make_energy_resource_snapshot(
        capex_to_operating_cashflow=None,
        unit_cost_position=None,
        reserve_life_index=None,
        commodity_price_sensitivity=None,
        debt_to_asset=34.0,
    )

    result = analyze_snapshot(snapshot, "energy_resource_v1")
    resilience_dimension = next(score for score in result.dimension_scores if score.dimension == "resource_cycle_resilience")

    assert resilience_dimension.score > 0
    assert "资产负债率" in (resilience_dimension.score_basis or "")


def test_render_fundamental_brief_includes_manual_supplement_block():
    snapshot = make_energy_resource_snapshot(
        symbol="601088",
        name="中国神华",
        dividend_yield=6.3,
        net_margin=11.6,
        asset_turnover=0.94,
        equity_multiplier=1.5152,
        dupont_driver="margin_turnover",
        capex_to_operating_cashflow=0.42,
        unit_cost_position=0.82,
        reserve_life_index=14.5,
        commodity_price_sensitivity=0.46,
        notes="2025 annual report p.34, p.112",
    )

    result = analyze_snapshot(snapshot, "energy_resource_v1")
    rendered = render_fundamental_brief(
        scorecard=result,
        snapshot=snapshot,
        field_sources={
            "dividend_yield": "manual.supplement",
            "capex_to_operating_cashflow": "manual.supplement",
            "unit_cost_position": "manual.supplement",
            "reserve_life_index": "manual.supplement",
            "commodity_price_sensitivity": "manual.supplement",
            "notes": "manual.supplement",
        },
    )

    assert "中国神华基本面简报" in rendered
    assert "- 资源周期韧性 " in rendered
    assert "- 股息与估值 " in rendered
    assert "计算说明:" in rendered
    assert "- 资源周期韧性:" in rendered
    assert "手工补充字段:" in rendered
    assert "杜邦拆解: 净利率=11.6, 总资产周转率=0.94, 权益乘数=1.5152, 杜邦驱动=margin_turnover" in rendered
    assert "- dividend_yield=6.3" in rendered
    assert "- reserve_life_index=14.5" in rendered
    assert '- notes="2025 annual report p.34, p.112"' in rendered


def test_render_fundamental_brief_formats_concise_calculation_summary():
    snapshot = make_platform_snapshot()
    result = analyze_snapshot(snapshot, "platform_internet_v1")

    rendered = render_fundamental_brief(scorecard=result, snapshot=snapshot)

    assert "计算说明:" in rendered
    assert "- 盈利质量: 3/4项" in rendered
    assert "平均" in rendered
    assert "折算" in rendered
    assert "缺失 杜邦驱动" in rendered


def test_safe_cn_valuation_series_returns_empty_frame_on_error(monkeypatch):
    def boom(symbol: str, indicator: str, period: str = "近五年") -> pd.DataFrame:
        raise ValueError("bad payload")

    monkeypatch.setattr(cn_snapshot_fetcher, "_fetch_cn_valuation_series", boom)

    series, assumption = cn_snapshot_fetcher._safe_fetch_cn_valuation_series(
        "601088",
        indicator="总市值",
        period="近一年",
    )

    assert series.empty
    assert assumption is not None
    assert "总市值" in assumption
    assert "bad payload" in assumption


def test_analyze_snapshot_flags_energy_resource_cycle_risks():
    snapshot = make_energy_resource_snapshot(
        capex_to_operating_cashflow=0.91,
        unit_cost_position=28.0,
    )

    result = analyze_snapshot(snapshot, "energy_resource_v1")

    triggered_rule_ids = {rule.rule_id for rule in result.triggered_rules}

    assert "capex_pressure_high" in triggered_rule_ids
    assert "unit_cost_position_weak" in triggered_rule_ids
    assert any("资本开支压力与成本位置同步转弱" in risk for risk in result.risks)


def test_analyze_snapshot_flags_energy_resource_reserve_and_sensitivity_risks():
    snapshot = make_energy_resource_snapshot(
        reserve_life_index=6.5,
        commodity_price_sensitivity=1.48,
    )

    result = analyze_snapshot(snapshot, "energy_resource_v1")

    triggered_rule_ids = {rule.rule_id for rule in result.triggered_rules}

    assert "reserve_life_short" in triggered_rule_ids
    assert "commodity_sensitivity_high" in triggered_rule_ids
    assert any("储量接续能力与价格敏感度同步偏弱" in risk for risk in result.risks)


def test_analyze_snapshot_flags_bank_capital_and_asset_quality_risks():
    snapshot = make_bank_snapshot(core_tier1_ratio=7.9, npl_ratio=2.2, provision_coverage_ratio=142.0)

    result = analyze_snapshot(snapshot, "bank_v1")

    triggered_rule_ids = {rule.rule_id for rule in result.triggered_rules}

    assert result.red_flag is True
    assert result.rating == "D"
    assert "core_tier1_ratio_low" in triggered_rule_ids
    assert "npl_ratio_high" in triggered_rule_ids
    assert "provision_coverage_low" in triggered_rule_ids
    assert any("不良与拨备缓冲同步转弱" in risk for risk in result.risks)


def test_render_scorecard_text_outputs_readable_summary():
    snapshot = make_platform_snapshot(guidance_attainment=None, dupont_driver=None)
    result = analyze_snapshot(snapshot, "platform_internet_v1")

    rendered = render_scorecard_text(result)

    assert "美团 (03690)" in rendered
    assert "总分:" in rendered
    assert "维度得分" in rendered
    assert "评级: A" in rendered
    assert "红线: 否" in rendered
    assert "关注问题" in rendered
    assert "1. 增长有没有兑现成利润" in rendered
    assert "盈利质量" in rendered
    assert "成长兑现" in rendered
    assert "综合说明" in rendered
    assert "当前综合评级为 A" in rendered
    assert "缺失指标" in rendered
    assert "- dupont_driver" in rendered
    assert "- guidance_attainment" in rendered
    assert "缺失[杜邦驱动 NA]" in rendered
    assert "已计分3/4项" in rendered
    assert rendered.index("关注问题") < rendered.index("维度得分")