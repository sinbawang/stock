from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_h_share_single_compact_report as module
import batch_generate_single_compact_reports as batch_module


def test_compact_capital_flow_omits_non_operational_sections() -> None:
    text = """# 资金面评分卡: 00700 腾讯

- 市场: HK
- 交易日: 2026-05-22
- 总分: 52.5/100
- 评级: C
- 数据源: eastmoney.southbound_net_buy
- 原始引用: raw.csv
- 口径说明: very long source note

关键资金指标:
- 南向净买入: -1
- 3日南向净买入: -2

维度得分:
- 资金方向: 8.5/25

正向线索:
- 未见明显过热信号

风险线索:
- 关键资金指标出现净流出

综合判断:
资金面存在风险信号，技术面结论需要降低确认度。
"""

    lines = module._compact_capital_flow(text)
    output = "\n".join(lines)

    assert "日期: 2026-05-22" in output
    assert "评级: C / 52.5/100" in output
    assert "南向净买入" in output
    assert "资金面存在风险信号" in output
    assert "数据源" not in output
    assert "原始引用" not in output
    assert "口径说明" not in output
    assert "维度得分" not in output
    assert "资金方向" not in output


def test_generate_report_writes_compact_single_stock_text(tmp_path: Path, monkeypatch) -> None:
    report_root = tmp_path / "reports"
    stock_dir = report_root / "00700"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 86.1,
                    "rating": "A",
                    "comment": "当前综合评级为 A，平台基本面整体处于可跟踪区间。",
                },
                "blended": {
                    "annual_anchor": {
                        "scorecard": {
                            "dimension_scores": [
                                {"dimension": "profit_quality", "score": 34.57, "missing_metrics": []},
                                {"dimension": "growth_delivery", "score": 15.27, "missing_metrics": ["guidance_attainment"]},
                            ]
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 52.5,
                    "rating": "C",
                    "comment": "资金面存在风险信号。",
                },
                "scorecard": {
                    "trade_date": "2026-05-22",
                    "dimension_scores": [
                        {"missing_metrics": ["short_sell_ratio", "amount_ratio_5d"]},
                    ],
                },
                "snapshot": {
                    "southbound_net_buy": -1,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "summary": {
                    "conclusion": "偏空，优先减仓或兑现。",
                    "suggestion": "反抽不过 479.60 以减仓为主。",
                    "precision_entry": {
                        "operation_level": "5M",
                        "timeframe": "5m",
                        "pending_reverse_mode": "effective_only",
                        "status": "watch",
                        "window_basis_label": "中枢到锚点窗口",
                        "note": "5M 已出现顶部趋势背驰，等待次级别卖点确认后再精确执行。窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
                    },
                    "signal_catalog": [
                        {
                            "point": "sell3",
                            "active": True,
                            "time": "2026-05-22T14:30:00",
                            "price": 479.60,
                            "basis": "leave_zs_then_rebound_fails_lower_edge",
                        }
                    ],
                },
                "analysis_text": "概览：\n- 时间区间：2026-05-01 到 2026-05-22\n\n结构：\n- 未确认向下笔。\n\n信号：\n- 卖点：sell_3\n",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "overview.txt").write_text("canonical overview", encoding="utf-8")
    monkeypatch.setattr(module, "_find_latest_chart", lambda symbol, name: Path("chart.jpg"))

    path = module.generate_report(
        symbol="00700",
        name="腾讯",
        report_root=report_root,
        output_dir=stock_dir,
    )

    output = path.read_text(encoding="utf-8")
    assert "腾讯 00700｜三轴操盘摘要" in output
    assert "【基本面】" in output
    assert "【资金面】" in output
    assert "【技术面】" in output
    assert "30M图: chart.jpg" in output
    assert "概览原文:" in output
    assert "guidance_attainment" in output
    assert "short_sell_ratio" in output
    assert "买卖点: 三卖(active)@2026-05-22T14:30:00/479.60 [跌破中枢后反抽下沿失败]" in output
    assert "5M区间套: 5M 已出现顶部趋势背驰，等待次级别卖点确认后再精确执行。窗口依据：" in output
    assert "5M窗口: 中枢到锚点窗口" in output


def test_generate_report_writes_a_share_human_signal_text(tmp_path: Path, monkeypatch) -> None:
    report_root = tmp_path / "reports"
    stock_dir = report_root / "300124"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 78.2,
                    "rating": "B",
                    "comment": "基本面处于可继续跟踪区间。",
                },
                "blended": {
                    "annual_anchor": {
                        "scorecard": {
                            "dimension_scores": [
                                {"dimension": "profit_quality", "score": 20.0, "missing_metrics": []},
                            ]
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps(
            {
                "summary": {
                    "score": 61.5,
                    "rating": "B",
                    "comment": "资金面中性偏稳。",
                },
                "scorecard": {
                    "trade_date": "2026-05-22",
                    "dimension_scores": [],
                },
                "snapshot": {
                    "main_net_inflow": 10,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "summary": {
                    "conclusion": "偏多，允许轻仓试错。",
                    "suggestion": "分批试仓，跌破 72.30 则严格止损。",
                    "precision_entry": {
                        "operation_level": "5M",
                        "timeframe": "5m",
                        "pending_reverse_mode": "effective_only",
                        "status": "actionable",
                        "window_basis_label": "中枢到锚点窗口",
                        "note": "5M 已出现二买，可按 effective_only 口径用于区间套精确定位。窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
                    },
                    "signal_catalog": [
                        {
                            "point": "buy2",
                            "active": True,
                            "time": "2026-05-22T14:30:00",
                            "price": 72.30,
                            "basis": "buy1_pullback_confirmation",
                        }
                    ],
                },
                "analysis_text": "概览：\n- 时间区间：2026-05-01 到 2026-05-22\n\n结构：\n- 最新确认向上笔。\n\n信号：\n- 买点：buy_2\n",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "overview.txt").write_text("canonical overview", encoding="utf-8")
    monkeypatch.setattr(module, "_find_latest_chart", lambda symbol, name: Path("chart.jpg"))

    path = module.generate_report(
        symbol="300124",
        name="汇川技术",
        report_root=report_root,
        output_dir=stock_dir,
    )

    output = path.read_text(encoding="utf-8")
    assert "汇川技术 300124｜三轴操盘摘要" in output
    assert "买卖点: 二买(active)@2026-05-22T14:30:00/72.30 [一买后回抽确认，低点未再跌破前低]" in output
    assert "5M区间套: 5M 已出现二买，可按 effective_only 口径用于区间套精确定位。窗口依据：" in output
    assert "5M窗口: 中枢到锚点窗口" in output


def test_batch_main_writes_symbol_compacts_and_group_summary(tmp_path: Path, monkeypatch) -> None:
    holdings_path = tmp_path / "stock_holdings.json"
    holdings_path.write_text(
        json.dumps(
            {
                "markets": {
                    "HK": [{"symbol": "00700", "name": "腾讯"}],
                    "CN": [{"symbol": "300124", "name": "汇川技术"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_root = tmp_path / "reports"
    output_dir = tmp_path / "reports" / "_meta"

    def fake_generate_report(*, symbol: str, name: str, report_root: Path, output_dir: Path, chart_note: str | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{symbol}_{name}_single_compact_20260530_210000.txt"
        path.write_text(f"{name} {symbol}\n", encoding="utf-8")
        return path

    monkeypatch.setattr(batch_module, "generate_report", fake_generate_report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "batch_generate_single_compact_reports.py",
            "--holdings-file",
            str(holdings_path),
            "--report-root",
            str(report_root),
            "--output-dir",
            str(output_dir),
        ],
    )

    batch_module.main()

    assert (report_root / "00700" / "00700_腾讯_single_compact_20260530_210000.txt").exists()
    assert (report_root / "300124" / "300124_汇川技术_single_compact_20260530_210000.txt").exists()
    summaries = list(output_dir.glob("group888_single_compact_*.txt"))
    assert len(summaries) == 1
    summary_text = summaries[0].read_text(encoding="utf-8")
    assert "腾讯 00700" in summary_text
    assert "汇川技术 300124" in summary_text
