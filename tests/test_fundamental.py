from fundamental.config.registry import get_submodel, get_submodel_for_symbol
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.reporting import render_scorecard_text
from fundamental.services import analyze_snapshot
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


def test_validate_snapshot_against_policy_rejects_missing_required_fields():
    snapshot = make_platform_snapshot(peg=None)
    submodel = get_submodel("platform_internet_v1")

    validation = validate_snapshot_against_policy(snapshot, submodel.field_policy)

    assert validation.is_valid is False
    assert validation.required_missing == ["peg"]


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
    assert rendered.index("关注问题") < rendered.index("维度得分")