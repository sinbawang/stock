from __future__ import annotations

import importlib.util
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
combined_spec = importlib.util.spec_from_file_location(
    "generate_a_share_combined_overview",
    SCRIPTS / "generate_a_share_combined_overview.py",
)
if combined_spec is None or combined_spec.loader is None:
    raise RuntimeError("failed to load generate_a_share_combined_overview.py for tests")
combined_module = importlib.util.module_from_spec(combined_spec)
sys.modules[combined_spec.name] = combined_module
combined_spec.loader.exec_module(combined_module)


CombinedTarget = combined_module.CombinedTarget
CapitalFlowRef = combined_module.CapitalFlowRef
FundamentalBriefRef = combined_module.FundamentalBriefRef
TechnicalRef = combined_module.TechnicalRef
_build_combined_view = combined_module._build_combined_view
_action_label = combined_module._action_label
_management_section = combined_module._management_section
build_rows = combined_module.build_rows
discover_targets_from_holdings_file = combined_module.discover_targets_from_holdings_file
render_combined_overview = combined_module.render_combined_overview


def test_combined_a_share_overview_parses_three_axes(tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "market": "CN",
  "holdings": [
    {"symbol": "000591", "name": "太阳能"},
    {"symbol": "601328", "name": "交通银行"}
  ]
}
""",
        encoding="utf-8",
    )
    (tmp_path / "000591_太阳能_utility_operator_v1_blended_fundamental_brief_20260517_174828.txt").write_text(
        """
太阳能基本面混合简报
评分概览:
- 评级: C
- 总分: 46.10
- 子模型: utility_operator_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "601328_交通银行_bank_v1_blended_fundamental_brief_20260517_174901.txt").write_text(
        """
交通银行基本面混合简报
评分概览:
- 评级: B
- 总分: 69.20
- 子模型: bank_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group888_60m_operation_summary_20260519_205731.txt").write_text(
        """
【全部持仓 60M 缠论综合操作建议】

逐只建议：
- 太阳能(000591)：偏强，持有为主。 建议：已有仓位可继续持有。
- 交通银行(601328)：震荡，等待方向选择。 建议：中枢内少折腾。
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group_a_share_capital_flow_overview_20260524_202625.txt").write_text(
        """
# A股持仓资金面批量概览

| symbol | name | status | trade_date | score | rating | source | bucket | report |
|---|---|---|---|---:|---|---|---|---|
| 000591 | 太阳能 | ok | 2026-05-24 | 37.8 | D | fallback | weak | C:\\sinba\\stock\\data\\_meta\\000591_report.txt |
| 601328 | 交通银行 | ok | 2026-05-24 | 59.1 | C | fallback | neutral | C:\\sinba\\stock\\data\\_meta\\601328_report.txt |
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group_a_share_capital_flow_overview_20260524_202741.txt").write_text(
        """
# A股持仓资金面批量概览

| symbol | name | status | trade_date | score | rating | source | bucket | report |
|---|---|---|---|---:|---|---|---|---|
| 000591 | 太阳能 | ok | 2026-05-24 | 37.8 | D | fallback | weak | C:\\sinba\\stock\\data\\_meta\\000591_report.txt |
""".strip(),
        encoding="utf-8",
    )

    targets = discover_targets_from_holdings_file(holdings_file)
    rows, technical_path, capital_path = build_rows(targets, tmp_path)
    text = render_combined_overview(rows, technical_path, capital_path)

    assert targets == [CombinedTarget(symbol="000591", name="太阳能"), CombinedTarget(symbol="601328", name="交通银行")]
    assert capital_path is not None
    assert capital_path.name == "group_a_share_capital_flow_overview_20260524_202625.txt"
    assert "# A股持仓三轴综合概览" in text
    assert "## 持仓管理清单" in text
    assert "清单分布: 今日动作=0, 观察池=1, 风险池=1" in text
    assert "### 今日动作\n\n- 暂无" in text
    assert "### 观察池" in text
    assert "### 风险池" in text
    assert "P2 | 等待触发 | 601328 | 交通银行 | watch | 69.2/B | 震荡，等待方向选择。 | 59.1/C/fallback" in text
    assert "P5 | 暂停加仓 | 000591 | 太阳能 | cautious | 46.1/C | 偏强，持有为主。 | 37.8/D/fallback" in text
    assert "capital_flow 读取最新 A 股资金面批量概览" in text
    assert "今日动作/观察池/风险池按 priority 派生" in text


def test_combined_view_marks_technical_and_capital_risk_as_cautious() -> None:
    bucket, comment = _build_combined_view(
        FundamentalBriefRef(score=75.9, rating="B"),
        TechnicalRef(conclusion="偏弱，先观望。"),
        CapitalFlowRef(score=37.8, rating="D", bucket="weak"),
    )

    assert bucket == "cautious"
    assert comment == "谨慎：60M 技术节奏偏弱；资金面偏弱"


def test_combined_view_keeps_base_and_technical_alignment_trackable() -> None:
    bucket, comment = _build_combined_view(
        FundamentalBriefRef(score=72.9, rating="B"),
        TechnicalRef(conclusion="偏多，允许轻仓试错。"),
        CapitalFlowRef(score=52.3, rating="C", bucket="neutral"),
    )

    assert bucket == "confirming"
    assert comment == "可跟踪试仓：基本面质量较好；60M 技术节奏偏积极；资金面尚未强确认"


def test_combined_view_requires_no_weak_axis_for_high_confirmation() -> None:
    bucket, comment = _build_combined_view(
        FundamentalBriefRef(score=80.0, rating="A"),
        TechnicalRef(conclusion="偏强，持有为主。"),
        CapitalFlowRef(score=68.0, rating="B", bucket="watch"),
    )

    assert bucket == "confirming"
    assert comment == "确认度较高：基本面质量较好；60M 技术节奏偏积极；资金面有一定确认"


def test_action_label_distinguishes_tracking_and_risk_actions() -> None:
    tracking_row = combined_module.CombinedOverviewRow(
        target=CombinedTarget(symbol="300124", name="汇川技术"),
        fundamental=FundamentalBriefRef(),
        technical=TechnicalRef(),
        capital_flow=CapitalFlowRef(),
        combined_bucket="confirming",
        combined_comment="可跟踪试仓：基本面质量较好；60M 技术节奏偏积极；资金面尚未强确认",
    )
    cautious_row = combined_module.CombinedOverviewRow(
        target=CombinedTarget(symbol="600900", name="长江电力"),
        fundamental=FundamentalBriefRef(),
        technical=TechnicalRef(),
        capital_flow=CapitalFlowRef(),
        combined_bucket="cautious",
        combined_comment="谨慎：60M 技术节奏偏弱；资金面偏弱",
    )

    assert _action_label(tracking_row) == "跟踪试仓"
    assert _action_label(cautious_row) == "暂停加仓"


def test_management_section_splits_action_watch_and_risk_pools() -> None:
    action_row = combined_module.CombinedOverviewRow(
        target=CombinedTarget(symbol="300124", name="汇川技术"),
        fundamental=FundamentalBriefRef(),
        technical=TechnicalRef(),
        capital_flow=CapitalFlowRef(),
        combined_bucket="confirming",
        combined_comment="可跟踪试仓：基本面质量较好；60M 技术节奏偏积极；资金面尚未强确认",
    )
    watch_row = combined_module.CombinedOverviewRow(
        target=CombinedTarget(symbol="000651", name="格力电器"),
        fundamental=FundamentalBriefRef(),
        technical=TechnicalRef(),
        capital_flow=CapitalFlowRef(),
        combined_bucket="mixed",
        combined_comment="分化：60M 技术节奏偏积极；资金面偏弱",
    )
    risk_row = combined_module.CombinedOverviewRow(
        target=CombinedTarget(symbol="600900", name="长江电力"),
        fundamental=FundamentalBriefRef(),
        technical=TechnicalRef(),
        capital_flow=CapitalFlowRef(),
        combined_bucket="cautious",
        combined_comment="谨慎：60M 技术节奏偏弱；资金面偏弱",
    )

    assert _management_section(action_row) == "今日动作"
    assert _management_section(watch_row) == "观察池"
    assert _management_section(risk_row) == "风险池"


def test_combined_a_share_overview_reads_new_reports_layout_json(tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "market": "CN",
  "holdings": [
    {"symbol": "601328", "name": "交通银行"}
  ]
}
""",
        encoding="utf-8",
    )

    stock_dir = tmp_path / "601328"
    (stock_dir / "60m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 69.2,
                    "rating": "B",
                    "submodel": "bank_v1",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 59.1,
                    "rating": "C",
                    "bucket": "neutral",
                    "source": "fallback",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "60m" / "tech.json").write_text(
        json.dumps(
            {
                "summary": {
                    "conclusion": "偏多，允许轻仓试错。",
                    "suggestion": "分批试仓。",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    targets = discover_targets_from_holdings_file(holdings_file)
    rows, technical_path, capital_path = build_rows(targets, tmp_path)
    text = render_combined_overview(rows, technical_path, capital_path)

    assert len(rows) == 1
    assert rows[0].fundamental.path == stock_dir / "base.json"
    assert rows[0].capital_flow.path == stock_dir / "fund.json"
    assert rows[0].technical.path == stock_dir / "60m" / "tech.json"
    assert rows[0].combined_bucket == "confirming"
    assert "P1 | 跟踪试仓 | 601328 | 交通银行 | confirming | 69.2/B | 偏多，允许轻仓试错。 | 59.1/C/fallback" in text