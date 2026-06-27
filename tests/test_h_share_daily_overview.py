from __future__ import annotations

from datetime import date
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

daily_spec = importlib.util.spec_from_file_location(
    "run_h_share_daily_overview",
    SCRIPTS / "run_h_share_daily_overview.py",
)
if daily_spec is None or daily_spec.loader is None:
    raise RuntimeError("failed to load run_h_share_daily_overview.py for tests")
daily_module = importlib.util.module_from_spec(daily_spec)
sys.modules[daily_spec.name] = daily_module
daily_spec.loader.exec_module(daily_module)


def test_run_hk_daily_overview_generates_capital_and_combined_reports(monkeypatch, tmp_path) -> None:
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        """
{
  "markets": {
    "HK": [
      {"symbol": "00700", "name": "腾讯"}
    ]
  }
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
    (tmp_path / "group888_30m_operation_summary_20260519_205731.txt").write_text(
        """
【全部持仓 30M 缠论综合操作建议】

逐只建议：
- 腾讯(00700)：偏多，允许轻仓试错。 建议：分批试仓，跌破 445.80 则严格止损。
""".strip(),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_batch(**kwargs):
        captured.update(kwargs)
        target = kwargs["targets"][0]
        return [
            daily_module.capital_batch.BatchCapitalFlowResult(
                target=target,
                status="ok",
                report_path=tmp_path / "00700_capital_flow.txt",
                total_score=72.3,
                rating="B",
                trade_date=date(2026, 5, 24),
                source="eastmoney.southbound_net_buy",
            )
        ]

    monkeypatch.setattr(daily_module.capital_batch, "run_batch", fake_run_batch)

    result = daily_module.run_daily_overview(
        holdings_file=holdings_file,
        meta_dir=tmp_path,
        trade_date=date(2026, 5, 24),
        cache_dir=tmp_path / "cache",
        max_cache_age_days=3,
    )

    assert result.capital_flow_succeeded == 1
    assert result.capital_flow_failed == 0
    assert result.capital_flow_summary_path.exists()
    assert result.combined_overview_path.exists()
    assert result.manifest_path is not None
    assert result.manifest_path.exists()
    assert captured["trade_date"] == date(2026, 5, 24)
    assert captured["cache_dir"] == tmp_path / "cache"
    assert captured["max_cache_age_days"] == 3

    combined_text = result.combined_overview_path.read_text(encoding="utf-8")
    assert "## 持仓管理清单" in combined_text
    assert "P1 | 跟踪试仓 | 00700 | 腾讯 | confirming" in combined_text
    assert f"资金面来源: {result.capital_flow_summary_path}" in combined_text

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["task"] == "h_share_daily_overview"
    assert manifest["inputs"]["holdings_file"] == str(holdings_file)
    assert manifest["inputs"]["trade_date"] == "2026-05-24"
    assert manifest["outputs"]["capital_flow_summary"] == str(result.capital_flow_summary_path)
    assert manifest["outputs"]["combined_overview"] == str(result.combined_overview_path)
    assert manifest["capital_flow"] == {"succeeded": 1, "failed": 0}
