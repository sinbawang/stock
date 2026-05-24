from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
h_share_spec = importlib.util.spec_from_file_location(
    "generate_h_share_combined_overview",
    SCRIPTS / "generate_h_share_combined_overview.py",
)
if h_share_spec is None or h_share_spec.loader is None:
    raise RuntimeError("failed to load generate_h_share_combined_overview.py for tests")
h_share_module = importlib.util.module_from_spec(h_share_spec)
sys.modules[h_share_spec.name] = h_share_module
h_share_spec.loader.exec_module(h_share_module)


CombinedTarget = h_share_module.CombinedTarget
build_rows = h_share_module.build_rows
discover_targets_from_holdings_file = h_share_module.discover_targets_from_holdings_file
render_combined_overview = h_share_module.render_combined_overview


def test_h_share_combined_overview_marks_capital_flow_pending(tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "market": "HK",
  "holdings": [
    {"symbol": "HK.00175", "name": "吉利汽车"},
    {"symbol": "03690", "name": "美团"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "00175_吉利汽车_auto_manufacturing_v1_blended_fundamental_brief_20260517_174932.txt").write_text(
        """
吉利汽车基本面混合简报
评分概览:
- 评级: B
- 总分: 68.50
- 子模型: auto_manufacturing_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "03690_美团_platform_internet_v1_blended_fundamental_brief_20260517_174947.txt").write_text(
        """
美团基本面混合简报
时间: 2026-05-17 17:49
标的: 美团(03690)  报告期: 2025-12-31
评级: C  总分: 61.20  红线: 无
子模型: platform_internet_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group888_60m_operation_summary_20260519_205731.txt").write_text(
        """
【全部持仓 60M 缠论综合操作建议】

逐只建议：
- 汇川技术(300124)：偏多，允许轻仓试错。 建议：A 股行不应进入港股技术 map。
- 吉利汽车(00175)：偏多，允许轻仓试错。 建议：分批试仓，跌破 19.98 则严格止损。
- 美团(03690)：偏弱，先观望。 建议：等待重新站回 84.35-87.10 再考虑参与，未站回前不追。
""".strip(),
        encoding="utf-8",
    )

    targets = discover_targets_from_holdings_file(holdings_file)
    rows, technical_path, capital_path = build_rows(targets, tmp_path)
    text = render_combined_overview(rows, technical_path, capital_path)

    assert targets == [CombinedTarget(symbol="00175", name="吉利汽车"), CombinedTarget(symbol="03690", name="美团")]
    assert capital_path is None
    assert "# 港股持仓三轴综合概览" in text
    assert "资金面来源: missing/HK pending" in text
    assert "清单分布: 今日动作=1, 观察池=0, 风险池=1" in text
    assert "P1 | 跟踪试仓 | 00175 | 吉利汽车 | confirming | 68.5/B | 偏多，允许轻仓试错。 | missing/HK pending" in text
    assert "P5 | 暂停加仓 | 03690 | 美团 | cautious | 61.2/C | 偏弱，先观望。 | missing/HK pending" in text
    assert "港股完整资金流尚未确认" in text
    assert "capital_flow 优先读取最新港股资金面批量概览" in text


def test_h_share_combined_overview_uses_latest_capital_flow_overview(tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "market": "HK",
  "holdings": [
    {"symbol": "00700", "name": "腾讯"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "00700_腾讯_platform_internet_v1_blended_fundamental_brief_20260517_174934.txt").write_text(
        """
腾讯基本面混合简报
评分概览:
- 评级: A
- 总分: 86.00
- 子模型: platform_internet_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group888_60m_operation_summary_20260519_205731.txt").write_text(
        """
【全部持仓 60M 缠论综合操作建议】

逐只建议：
- 腾讯(00700)：偏多，允许轻仓试错。 建议：分批试仓，跌破 445.80 则严格止损。
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group_h_share_capital_flow_overview_20260524_210800.txt").write_text(
        """
# 港股持仓资金面批量概览

| symbol | name | status | trade_date | score | rating | source | bucket | report |
|---|---|---|---|---:|---|---|---|---|
| 00700 | 腾讯 | ok | 2026-05-24 | 49.0 | D | primary(components) | weak | C:\\sinba\\stock\\data\\_meta\\00700_report.txt |
""".strip(),
        encoding="utf-8",
    )

    targets = discover_targets_from_holdings_file(holdings_file)
    rows, technical_path, capital_path = build_rows(targets, tmp_path)
    text = render_combined_overview(rows, technical_path, capital_path)

    assert capital_path is not None
    assert capital_path.name == "group_h_share_capital_flow_overview_20260524_210800.txt"
    assert "资金面来源: " in text
    assert "00700 | 腾讯 | cautious | 86.0/A | 偏多，允许轻仓试错。 | 49.0/D/primary(components)" in text
    assert "资金面出现净流出或空头压力，拖累确认度" in text


def test_h_share_combined_overview_shows_failed_capital_flow_status(tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "market": "HK",
  "holdings": [
    {"symbol": "00700", "name": "腾讯"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "00700_腾讯_platform_internet_v1_blended_fundamental_brief_20260517_174934.txt").write_text(
        """
腾讯基本面混合简报
评分概览:
- 评级: A
- 总分: 86.00
- 子模型: platform_internet_v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group888_60m_operation_summary_20260519_205731.txt").write_text(
        """
【全部持仓 60M 缠论综合操作建议】

逐只建议：
- 腾讯(00700)：偏多，允许轻仓试错。 建议：分批试仓。
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "group_h_share_capital_flow_overview_20260524_211728.txt").write_text(
        """
# 港股持仓资金面批量概览

| symbol | name | status | trade_date | score | rating | source | bucket | report |
|---|---|---|---|---:|---|---|---|---|
| 00700 | 腾讯 | failed |  |  |  | primary(components) | failed | remote down |
""".strip(),
        encoding="utf-8",
    )

    targets = discover_targets_from_holdings_file(holdings_file)
    rows, technical_path, capital_path = build_rows(targets, tmp_path)
    text = render_combined_overview(rows, technical_path, capital_path)

    assert "failed/primary(components)" in text
    assert "港股资金面抓取失败，暂按缺口处理" in text