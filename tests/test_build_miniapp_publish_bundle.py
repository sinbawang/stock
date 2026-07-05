from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
module_spec = importlib.util.spec_from_file_location(
    "build_miniapp_publish_bundle",
    SCRIPTS / "build_miniapp_publish_bundle.py",
)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("failed to load build_miniapp_publish_bundle.py for tests")
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_parse_combined_group_file_extracts_mobile_sections(tmp_path: Path) -> None:
    path = tmp_path / "group_a_share_combined_overview_20260530_200533.txt"
    path.write_text(
        """# A股持仓三轴综合概览

Generated at: 2026-05-30T20:05:33
清单分布: 今日动作=0, 观察池=1, 风险池=0

## 持仓管理清单

### 今日动作

- 暂无

### 观察池

| priority | action | symbol | name | bucket | fundamental | technical | capital_flow | comment |
|---|---|---|---|---|---|---|---|---|
| P2 | 等待触发 | 000651 | 格力电器 | watch | 54.8/C | 偏强，持有为主。 | 51.4/C/fallback | 观察：60M 技术节奏偏积极 |

## 口径说明

- priority/action 只用于排序
""",
        encoding="utf-8",
    )

    payload = module.parse_combined_group_file(path, "a_share")

    assert payload["group"] == "a_share"
    assert payload["counts"]["watch_pool"] == 1
    assert payload["sections"][1]["items"][0]["symbol"] == "000651"
    assert payload["notes"] == ["priority/action 只用于排序"]


def test_generate_bundle_writes_index_groups_and_stock_payloads(tmp_path: Path) -> None:
    holdings_path = tmp_path / "stock_holdings.json"
    holdings_path.write_text(
        json.dumps(
            {
                "markets": {
                    "CN": [{"symbol": "000651", "name": "格力电器"}],
                    "HK": [{"symbol": "00700", "name": "腾讯"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    reports_root = tmp_path / "reports"
    meta_dir = reports_root / "_meta"
    meta_dir.mkdir(parents=True)

    def write_stock(symbol: str, name: str, market: str) -> None:
        stock_dir = reports_root / symbol
        (stock_dir / "60m").mkdir(parents=True)
        (stock_dir / "30m").mkdir(parents=True)
        (stock_dir / "15m").mkdir(parents=True)
        (stock_dir / "5m").mkdir(parents=True)
        (stock_dir / "60m" / "structure.svg").write_text("<svg>60m</svg>", encoding="utf-8")
        (stock_dir / "30m" / "structure.svg").write_text("<svg>30m</svg>", encoding="utf-8")
        (stock_dir / "15m" / "structure.svg").write_text("<svg>15m</svg>", encoding="utf-8")
        (stock_dir / "5m" / "structure.svg").write_text("<svg>5m</svg>", encoding="utf-8")
        (stock_dir / "base.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-05-30T20:33:27",
                    "summary": {"score": 54.78, "rating": "C", "submodel": "home_appliance_v1", "comment": "基本面可跟踪"},
                    "blended": {
                        "annual_anchor": {
                            "snapshot": {"report_period": "2025-12-31"},
                            "scorecard": {
                                "combined_comment": "基本面综合说明",
                                "strengths": [f"{name} 亮点"],
                                "risks": [f"{name} 风险"],
                                "focus_questions": [f"{name} 跟踪点"],
                                "warnings": [],
                            },
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
                    "generated_at": "2026-05-30T20:35:15",
                    "summary": {"score": 51.42, "rating": "C", "source": "fallback", "comment": "资金面说明"},
                    "scorecard": {"trade_date": "2026-05-30", "strengths": ["资金亮点"], "risks": ["资金风险"], "warnings": ["资金警告"]},
                    "snapshot": {"main_net_inflow": 123, "main_net_inflow_5d": 456},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (stock_dir / "30m" / "tech.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-05-30T20:33:27",
                    "timeframe": "30m",
                    "source": "akshare.eastmoney",
                    "summary": {
                        "score": 78,
                        "rating": "B",
                        "bias": "偏强",
                        "score_breakdown": {
                            "structure": 24,
                            "location": 15,
                            "signal": 22,
                            "divergence": 11,
                            "execution": 6,
                        },
                        "conclusion": "偏强，持有为主。",
                        "suggestion": "继续持有",
                        "buy_points": ["buy2"],
                        "signal_catalog": [
                            {
                                "point": "buy2",
                                "active": True,
                                "time": "2026-05-29T10:30:00",
                                "price": 10.25,
                                "basis": "buy1_pullback_confirmation",
                            },
                            {
                                "point": "sell3",
                                "active": True,
                                "time": "2026-05-27T14:30:00",
                                "price": 10.88,
                                "basis": "leave_zs_then_rebound_fails_lower_edge",
                            },
                        ],
                        "structure_state": {
                            "last_completed": {
                                "type": "up",
                                "status": "completed",
                                "start_ts": "2026-04-01T10:30:00",
                                "end_ts": "2026-05-10T10:30:00",
                                "zs_count": 2,
                            },
                            "current_ongoing": {
                                "type": "down",
                                "status": "ongoing",
                                "start_ts": "2026-05-15T10:30:00",
                                "latest_ts": "2026-05-29T10:30:00",
                                "zs_count": 1,
                            },
                            "relationship": {
                                "kind": "completed_then_new_type_ongoing",
                                "note": "上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。",
                            },
                        },
                        "precision_entry": {
                            "operation_level": "5M",
                            "timeframe": "5m",
                            "pending_reverse_mode": "effective_only",
                            "status": "actionable",
                            "window_basis_label": "中枢到锚点窗口",
                            "window_basis_description": "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
                            "note": "5M 已出现二买，可按 effective_only 口径用于区间套精确定位。窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
                            "signal_descriptions": ["二买，一买后回抽确认，参考价 10.25"],
                        },
                        "signal_points": [
                            {
                                "point": "buy2",
                                "active": True,
                                "price": 10.25,
                                "basis": "buy1_pullback_confirmation",
                                "related_zs_id": 2,
                            }
                        ],
                    },
                    "analysis_text": "概览：\n- 时间区间：2026-01-26 到 2026-05-29\n\n结构：\n- 最新确认向上笔：...\n\n信号：\n- buy_3\n\n观察重点：\n- 是否突破\n",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    write_stock("000651", "格力电器", "CN")
    write_stock("00700", "腾讯", "HK")

    (meta_dir / "group_a_share_combined_overview_20260530_200533.txt").write_text(
        """# A股持仓三轴综合概览

Generated at: 2026-05-30T20:05:33
清单分布: 今日动作=0, 观察池=1, 风险池=0

## 持仓管理清单

### 今日动作

- 暂无

### 观察池

| priority | action | symbol | name | bucket | fundamental | technical | capital_flow | comment |
|---|---|---|---|---|---|---|---|---|
| P2 | 等待触发 | 000651 | 格力电器 | watch | 54.8/C | 偏强，持有为主。 | 51.4/C/fallback | 观察：60M 技术节奏偏积极 |

## 口径说明

- A股说明
""",
        encoding="utf-8",
    )
    (meta_dir / "group_h_share_combined_overview_20260530_200552.txt").write_text(
        """# 港股持仓三轴综合概览

Generated at: 2026-05-30T20:05:52
清单分布: 今日动作=1, 观察池=0, 风险池=0

## 持仓管理清单

### 今日动作

| priority | action | symbol | name | bucket | fundamental | technical | capital_flow | comment |
|---|---|---|---|---|---|---|---|---|
| P1 | 优先跟踪 | 00700 | 腾讯 | confirming | 86.3/A | 偏强，持有为主。 | 60.5/C/cache | 确认：基本面与技术面同向 |

### 观察池

- 暂无

### 风险池

- 暂无

## 口径说明

- 港股说明
""",
        encoding="utf-8",
    )

    publish_root = tmp_path / "publish"
    outputs = module.generate_bundle(
        holdings_path=holdings_path,
        reports_root=reports_root,
        publish_root=publish_root,
        snapshot_stamp="20260530_210500",
        latest_only=False,
    )

    latest_dir = outputs["latest"]
    snapshot_dir = outputs["snapshot"]
    assert latest_dir.exists()
    assert snapshot_dir.exists()

    index_payload = json.loads((latest_dir / "index.json").read_text(encoding="utf-8"))
    assert index_payload["counts"]["stocks"] == 2
    assert index_payload["stocks"][0]["symbol"] == "00700"
    assert index_payload["stocks"][0]["technical_score"] == 78
    assert index_payload["stocks"][0]["technical_rating"] == "B"
    assert index_payload["stocks"][0]["technical_bias"] == "偏强"

    summary_payload = json.loads((latest_dir / "stocks" / "000651" / "summary.json").read_text(encoding="utf-8"))
    assert summary_payload["priority"] == "P2"
    assert summary_payload["jump"]["detail"] == "stocks/000651/detail.json"
    assert summary_payload["cards"]["technical"]["buy_point_labels"] == ["二买"]
    assert summary_payload["cards"]["technical"]["signal_descriptions"][0].startswith("二买，一买后回抽确认")
    assert summary_payload["cards"]["technical"]["timeframe"] == "30m"
    assert summary_payload["cards"]["technical"]["timeframe_label"] == "30M"
    assert summary_payload["cards"]["technical"]["score"] == 78
    assert summary_payload["cards"]["technical"]["rating"] == "B"
    assert summary_payload["cards"]["technical"]["bias"] == "偏强"
    assert summary_payload["cards"]["technical"]["score_breakdown"]["signal"] == 22
    assert summary_payload["cover_chart"]["timeframe"] == "30m"
    assert summary_payload["cards"]["technical"]["precision_entry"]["operation_level"] == "5M"
    assert summary_payload["cards"]["technical"]["precision_note"].startswith("5M 已出现二买")
    assert "窗口依据：" in summary_payload["cards"]["technical"]["precision_note"]
    assert summary_payload["cards"]["technical"]["precision_window_basis_label"] == "中枢到锚点窗口"
    assert summary_payload["cards"]["technical"]["precision_window_basis_description"] == "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    assert summary_payload["cards"]["technical"]["precision_window_display"]["title"] == "5M区间套窗口"
    assert summary_payload["cards"]["technical"]["precision_window_display"]["label"] == "中枢到锚点窗口"
    assert summary_payload["cards"]["technical"]["precision_window_display"]["description"] == "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    assert summary_payload["cards"]["technical"]["precision_window_display"]["lines"] == [
        "5M窗口：中枢到锚点窗口",
        "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
    ]
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["mode"] == "engineering_summary"
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["is_strict_theory_equivalent"] is False
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["summary_note"].startswith("当前同级别走势输出为工程结构摘要")
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["previous"]["type_label"] == "上涨"
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["current"]["type_label"] == "下跌"
    assert summary_payload["cards"]["technical"]["latest_signal_summary"]["latest_buy"]["label"] == "二买"
    assert summary_payload["cards"]["technical"]["latest_signal_summary"]["latest_sell"]["label"] == "三卖"
    assert summary_payload["cards"]["technical"]["technical_focus_lines"] == [
        "上个已完成走势：上涨 2026-04-01T10:30:00 -> 2026-05-10T10:30:00",
        "当前进行走势：下跌 自 2026-05-15T10:30:00 起，最新 2026-05-29T10:30:00",
        "走势连接：上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。",
        "口径说明：当前同级别走势输出为工程结构摘要，非严格递归分解后的最终理论标签。",
        "最近买点：二买 2026-05-29T10:30:00，价格 10.25",
        "最近卖点：三卖 2026-05-27T14:30:00，价格 10.88",
    ]

    detail_payload = json.loads((latest_dir / "stocks" / "00700" / "detail.json").read_text(encoding="utf-8"))
    assert detail_payload["headline"]["priority"] == "P1"
    assert detail_payload["charts"][0]["path"] == "stocks/00700/charts/30m.svg"
    assert [chart["path"] for chart in detail_payload["charts"]] == [
        "stocks/00700/charts/30m.svg",
        "stocks/00700/charts/60m.svg",
        "stocks/00700/charts/15m.svg",
        "stocks/00700/charts/5m.svg",
    ]
    assert detail_payload["sections"][1]["buy_point_labels"] == ["二买"]
    assert detail_payload["sections"][1]["signal_descriptions"][0].startswith("二买，一买后回抽确认")
    assert detail_payload["sections"][1]["score"] == 78
    assert detail_payload["sections"][1]["rating"] == "B"
    assert detail_payload["sections"][1]["bias"] == "偏强"
    assert detail_payload["overview"]["bullets"][1].startswith("30M 技术面")
    assert detail_payload["sections"][1]["precision_entry"]["timeframe"] == "5m"
    assert detail_payload["sections"][1]["precision_window_basis_label"] == "中枢到锚点窗口"
    assert detail_payload["sections"][1]["precision_window_basis_description"] == "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    assert detail_payload["sections"][1]["precision_window_display"]["title"] == "5M区间套窗口"
    assert detail_payload["sections"][1]["precision_window_display"]["lines"] == [
        "5M窗口：中枢到锚点窗口",
        "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。",
    ]
    assert detail_payload["sections"][1]["same_level_decomposition"]["mode"] == "engineering_summary"
    assert detail_payload["sections"][1]["same_level_decomposition"]["is_strict_theory_equivalent"] is False
    assert detail_payload["sections"][1]["same_level_decomposition"]["summary_note"].startswith("当前同级别走势输出为工程结构摘要")
    assert detail_payload["sections"][1]["same_level_decomposition"]["previous"]["type_label"] == "上涨"
    assert detail_payload["sections"][1]["same_level_decomposition"]["current"]["type_label"] == "下跌"
    assert detail_payload["sections"][1]["latest_signal_summary"]["latest_overall"]["label"] == "二买"
    assert detail_payload["sections"][1]["technical_focus_lines"][0].startswith("上个已完成走势：上涨")
    assert any("工程结构摘要" in line for line in detail_payload["sections"][1]["technical_focus_lines"])

    a_share_group = json.loads((latest_dir / "groups" / "a_share.json").read_text(encoding="utf-8"))
    assert a_share_group["sections"][1]["items"][0]["symbol"] == "000651"

    portfolio_group = json.loads((latest_dir / "groups" / "portfolio.json").read_text(encoding="utf-8"))
    assert portfolio_group["counts"]["items"] == 2
    assert portfolio_group["sections"][0]["items"][0]["symbol"] == "00700"
    assert portfolio_group["sections"][0]["items"][0]["technical_score"] == 78
    assert portfolio_group["sections"][0]["items"][0]["technical_rating"] == "B"
    assert portfolio_group["sections"][0]["items"][0]["technical_bias"] == "偏强"

    assert (latest_dir / "stocks" / "000651" / "charts" / "60m.svg").exists()
    assert (latest_dir / "stocks" / "000651" / "charts" / "30m.svg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "15m.svg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "5m.svg").exists()