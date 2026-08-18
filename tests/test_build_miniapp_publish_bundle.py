from __future__ import annotations

import importlib.util
import json
import os
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
        (stock_dir / "1m").mkdir(parents=True)
        (stock_dir / "60m" / "structure.svg").write_text("<svg>60m</svg>", encoding="utf-8")
        (stock_dir / "30m" / "structure.svg").write_text("<svg>30m</svg>", encoding="utf-8")
        (stock_dir / "15m" / "structure.svg").write_text("<svg>15m</svg>", encoding="utf-8")
        (stock_dir / "5m" / "structure.svg").write_text("<svg>5m</svg>", encoding="utf-8")
        (stock_dir / "1m" / "structure.svg").write_text("<svg>1m</svg>", encoding="utf-8")
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
                    "structure": {
                        "latest_zhongshu": {
                            "zs_id": 3,
                            "entering_bi_id": 29,
                            "exit_bi_id": None,
                            "is_terminated": False,
                            "superseded_by_zs_id": None,
                            "is_reabsorbed_by_larger_expansion": False,
                        },
                        "zhongshus": [
                            {
                                "zs_id": 2,
                                "entering_bi_id": 18,
                                "exit_bi_id": 29,
                                "is_terminated": True,
                                "superseded_by_zs_id": 3,
                                "is_reabsorbed_by_larger_expansion": True,
                            },
                            {
                                "zs_id": 3,
                                "entering_bi_id": 29,
                                "exit_bi_id": None,
                                "is_terminated": False,
                                "superseded_by_zs_id": None,
                                "is_reabsorbed_by_larger_expansion": False,
                            },
                        ],
                    },
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
                            "current_structure_status": "candidate_completed_waiting_stability",
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
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["current_structure_status"] == "candidate_completed_waiting_stability"
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["current_structure_status_label"] == "候选完成待确认"
    assert "边界仍待右侧结构确认稳定" in summary_payload["cards"]["technical"]["same_level_decomposition"]["current_structure_status_note"]
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["debug_context"]["auto_reabsorption_detected"] is True
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["debug_context"]["latest_zhongshu"]["zs_id"] == 3
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["debug_context"]["reabsorbed_predecessor"]["zs_id"] == 2
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["debug_context"]["reabsorbed_predecessor"]["superseded_by_zs_id"] == 3
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["previous"]["type_label"] == "上涨"
    assert summary_payload["cards"]["technical"]["same_level_decomposition"]["current"]["type_label"] == "下跌"
    assert summary_payload["cards"]["technical"]["latest_signal_summary"]["latest_buy"]["label"] == "二买"
    assert summary_payload["cards"]["technical"]["latest_signal_summary"]["latest_sell"]["label"] == "三卖"
    assert summary_payload["cards"]["technical"]["technical_focus_lines"] == [
        "上个已完成走势：上涨 2026-04-01T10:30:00 -> 2026-05-10T10:30:00",
        "当前进行走势：下跌 自 2026-05-15T10:30:00 起，最新 2026-05-29T10:30:00",
        "走势连接：上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。",
        "切分状态：前段走势已具备完成候选，但边界仍待右侧结构确认稳定。",
        "重写说明：前一中枢 ZS2 的走出笔 29 被当前中枢 ZS3 复用为进入笔 29，当前按更大级别扩展吸收处理。",
        "口径说明：当前同级别走势输出为工程结构摘要，非严格递归分解后的最终理论标签。",
        "最近买点：二买 2026-05-29T10:30:00，价格 10.25",
        "最近卖点：三卖 2026-05-27T14:30:00，价格 10.88",
    ]
    assert summary_payload["cards"]["technical"]["segment_tail_interpretations"]
    assert summary_payload["cards"]["technical"]["segment_tail_interpretations"][-1]["kind"] == "pending_confirmation"
    assert summary_payload["cards"]["technical"]["segment_tail_interpretations"][-1]["is_reclaimed"] is False

    detail_payload = json.loads((latest_dir / "stocks" / "00700" / "detail.json").read_text(encoding="utf-8"))
    assert detail_payload["headline"]["priority"] == "P1"
    assert detail_payload["charts"][0]["path"] == "stocks/00700/charts/30m.svg"
    assert [chart["path"] for chart in detail_payload["charts"]] == [
        "stocks/00700/charts/30m.svg",
        "stocks/00700/charts/5m.svg",
        "stocks/00700/charts/1m.svg",
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
    assert detail_payload["sections"][1]["same_level_decomposition"]["current_structure_status"] == "candidate_completed_waiting_stability"
    assert detail_payload["sections"][1]["same_level_decomposition"]["current_structure_status_label"] == "候选完成待确认"
    assert detail_payload["sections"][1]["same_level_decomposition"]["debug_context"]["auto_reabsorption_detected"] is True
    assert detail_payload["sections"][1]["same_level_decomposition"]["debug_context"]["reabsorbed_predecessor"]["zs_id"] == 2
    assert detail_payload["sections"][1]["same_level_decomposition"]["previous"]["type_label"] == "上涨"
    assert detail_payload["sections"][1]["same_level_decomposition"]["current"]["type_label"] == "下跌"
    assert detail_payload["sections"][1]["latest_signal_summary"]["latest_overall"]["label"] == "二买"
    assert detail_payload["sections"][1]["technical_focus_lines"][0].startswith("上个已完成走势：上涨")
    assert any("重写说明：前一中枢 ZS2 的走出笔 29 被当前中枢 ZS3 复用为进入笔 29" in line for line in detail_payload["sections"][1]["technical_focus_lines"])
    assert detail_payload["sections"][1]["segment_tail_interpretations"]
    assert detail_payload["sections"][1]["segment_tail_interpretations"][-1]["kind"] == "pending_confirmation"
    assert detail_payload["sections"][1]["segment_tail_interpretations"][-1]["is_reclaimed"] is False
    assert any("候选完成待确认" in line or "边界仍待右侧结构确认稳定" in line for line in detail_payload["sections"][1]["technical_focus_lines"])
    assert any("工程结构摘要" in line for line in detail_payload["sections"][1]["technical_focus_lines"])
    assert any("停驻原因：" in line for line in detail_payload["sections"][1]["technical_focus_lines"])

    a_share_group = json.loads((latest_dir / "groups" / "a_share.json").read_text(encoding="utf-8"))
    assert a_share_group["sections"][1]["items"][0]["symbol"] == "000651"

    portfolio_group = json.loads((latest_dir / "groups" / "portfolio.json").read_text(encoding="utf-8"))
    assert portfolio_group["counts"]["items"] == 2
    assert portfolio_group["sections"][0]["items"][0]["symbol"] == "00700"
    assert portfolio_group["sections"][0]["items"][0]["technical_score"] == 78
    assert portfolio_group["sections"][0]["items"][0]["technical_rating"] == "B"
    assert portfolio_group["sections"][0]["items"][0]["technical_bias"] == "偏强"

    assert outputs["bundle_integrity"]["index_present"] is True
    assert outputs["bundle_integrity"]["portfolio_group_present"] is True
    assert outputs["bundle_integrity"]["stock_dir_count"] == 2
    assert outputs["bundle_integrity"]["summary_json_count"] == 2
    assert outputs["bundle_integrity"]["detail_json_count"] == 2
    assert outputs["snapshot_bundle_integrity"]["index_present"] is True

    assert (latest_dir / "stocks" / "000651" / "charts" / "30m.svg").exists()
    assert (latest_dir / "stocks" / "000651" / "charts" / "5m.svg").exists()
    assert (latest_dir / "stocks" / "000651" / "charts" / "1m.svg").exists()
    assert not (latest_dir / "stocks" / "000651" / "charts" / "60m.svg").exists()
    assert not (snapshot_dir / "stocks" / "00700" / "charts" / "15m.svg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "30m.svg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "5m.svg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "1m.svg").exists()


def test_build_latest_segment_reclaim_line_exposes_absorbed_segment_ids() -> None:
    line = module.build_latest_segment_reclaim_line(
        [
            {
                "segment_id": 3,
                "kind": "pending_confirmation",
                "is_reclaimed": True,
                "absorbed_segment_ids": [1, 2],
            }
        ],
        "30m",
    )

    assert line == "30M S3 线段重写吸收：已吸收旧段 S1、S2，当前尾段继续按待确认结构观察。"


def test_stock_payload_updated_at_uses_latest_available_technical_timeframe(tmp_path: Path) -> None:
    stock_dir = tmp_path / "03690"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "5m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps({"generated_at": "2026-08-17T09:00:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps({"generated_at": "2026-08-17T09:05:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-17T09:30:00",
                "timeframe": "30m",
                "summary": {
                    "score": 60,
                    "rating": "C",
                    "bias": "中性",
                    "score_breakdown": {},
                    "conclusion": "30M 观察中",
                    "suggestion": "等待确认",
                    "buy_points": [],
                    "sell_points": [],
                    "signal_points": [],
                    "signal_catalog": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stock_dir / "5m" / "tech.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-17T10:05:00",
                "timeframe": "5m",
                "summary": {
                    "score": 61,
                    "rating": "C",
                    "bias": "偏多",
                    "score_breakdown": {},
                    "conclusion": "5M 已刷新",
                    "suggestion": "继续跟踪",
                    "buy_points": [],
                    "sell_points": [],
                    "signal_points": [],
                    "signal_catalog": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    holding = module.Holding(symbol="03690", name="美团", market="HK")

    summary_payload = module.build_summary_payload(holding, stock_dir, None)
    detail_payload, _ = module.build_detail_payload(holding, stock_dir, None)

    assert summary_payload["updated_at"] == "2026-08-17T10:05:00"
    assert detail_payload["updated_at"] == "2026-08-17T10:05:00"


def test_build_same_level_decomposition_labels_same_type_extension_as_confirmed_slice() -> None:
    decomposition = module.build_same_level_decomposition(
        {
            "summary": {
                "structure_state": {
                    "last_completed": {
                        "type": "down",
                        "status": "completed",
                        "start_ts": "2026-06-01T10:30:00",
                        "end_ts": "2026-06-10T10:30:00",
                        "zs_count": 2,
                    },
                    "current_ongoing": {
                        "type": "down",
                        "status": "ongoing",
                        "start_ts": "2026-06-15T10:30:00",
                        "latest_ts": "2026-06-30T10:30:00",
                        "zs_count_so_far": 1,
                    },
                    "relationship": {
                        "kind": "same_type_extension",
                        "note": "当前结构更接近前一走势类型的同类延伸，暂未看到清晰的新类型完成边界。",
                    },
                    "current_structure_status": "ongoing_same_type",
                }
            }
        }
    )

    assert decomposition["previous"]["type_label"] == "下跌"
    assert decomposition["current"]["type_label"] == "下跌"
    assert decomposition["lines"][0].startswith("前段已确认同型片段：下跌")


def test_build_latest_signal_summary_includes_pending_zs_monitor_line() -> None:
    summary = module.build_latest_signal_summary(
        {
            "summary": {
                "signal_points": [],
                "signal_catalog": [],
                "oscillation_rhythm_state": "down_bias",
                "zs_monitor_alert": "pre_breakdown",
                "zs_monitor_midline": 10.45,
                "zs_monitor_bias": "weak",
            }
        }
    )

    assert summary["latest_overall"] is None
    assert any("中枢预警：向下预警，当前不构成确认三卖（中线 10.45，节奏偏弱）" in line for line in summary["lines"])
    assert any("节奏监视：节奏偏弱，当前只作辅助观察" in line for line in summary["lines"])


def test_build_summary_and_detail_payload_preserve_30m_pre_breakdown_publish_anchor(tmp_path: Path) -> None:
    stock_dir = tmp_path / "601328"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps({"generated_at": "2026-08-18T09:00:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps({"generated_at": "2026-08-18T09:05:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-18T09:30:00",
                "timeframe": "30m",
                "source": "akshare.eastmoney",
                "zhongshu_level": "segment",
                "structure": {
                    "primary_zhongshu_level": "segment",
                    "latest_zhongshu": {
                        "zs_id": 7,
                        "entering_bi_id": 51,
                        "exit_bi_id": None,
                        "is_terminated": False,
                        "superseded_by_zs_id": None,
                        "is_reabsorbed_by_larger_expansion": False,
                    },
                    "zhongshus": [
                        {
                            "zs_id": 7,
                            "entering_bi_id": 51,
                            "exit_bi_id": None,
                            "is_terminated": False,
                            "superseded_by_zs_id": None,
                            "is_reabsorbed_by_larger_expansion": False,
                        }
                    ],
                },
                "summary": {
                    "score": 61,
                    "rating": "C",
                    "bias": "偏弱",
                    "score_breakdown": {},
                    "conclusion": "出现向下预警，但当前不构成确认三卖。",
                    "suggestion": "继续观察首次回抽是否回中枢。",
                    "buy_points": [],
                    "sell_points": [],
                    "signal_points": [],
                    "signal_catalog": [],
                    "structure_state": {
                        "last_completed": None,
                        "current_ongoing": {
                            "type": "range",
                            "status": "ongoing",
                            "start_ts": "2026-08-01T10:30:00",
                            "latest_ts": "2026-08-18T09:30:00",
                            "zs_count_so_far": 1,
                            "confirmation_basis": "single_active_zhongshu",
                        },
                        "relationship": {
                            "kind": "undetermined",
                            "note": "当前只有一个同级别中枢，按工程口径先视为盘整进行中。",
                        },
                        "current_structure_status": "ongoing_same_type",
                    },
                    "same_level_decomposition_mode": "dual_interpretation_pending",
                    "oscillation_rhythm_state": "down_bias",
                    "post_divergence_route": "higher_level_range",
                    "route_level_from": "30m",
                    "route_level_to": "day",
                    "zs_monitor_alert": "pre_breakdown",
                    "zs_monitor_midline": 10.45,
                    "zs_monitor_bias": "weak",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    holding = module.Holding(symbol="601328", name="交通银行", market="CN")

    summary_payload = module.build_summary_payload(holding, stock_dir, None)
    detail_payload, _ = module.build_detail_payload(holding, stock_dir, None)

    technical_card = summary_payload["cards"]["technical"]
    technical_section = detail_payload["sections"][1]

    assert technical_card["conclusion"] == "出现向下预警，但当前不构成确认三卖。"
    assert technical_card["suggestion"] == "继续观察首次回抽是否回中枢。"
    assert technical_card["same_level_decomposition"]["current"]["type_label"] == "盘整"
    assert technical_card["oscillation_rhythm_state"] == "down_bias"
    assert technical_card["post_divergence_route"] == "higher_level_range"
    assert technical_card["route_level_from"] == "30m"
    assert technical_card["route_level_to"] == "day"
    assert any("中枢预警：向下预警，当前不构成确认三卖（中线 10.45，节奏偏弱）" in line for line in technical_card["technical_focus_lines"])
    assert any("去向候选：更大级别盘整（30m -> day），当前只按观察态处理" in line for line in technical_card["technical_focus_lines"])
    assert any("节奏监视：节奏偏弱，当前只作辅助观察" in line for line in technical_card["technical_focus_lines"])
    assert technical_section["conclusion"] == "出现向下预警，但当前不构成确认三卖。"
    assert technical_section["oscillation_rhythm_state"] == "down_bias"
    assert technical_section["post_divergence_route"] == "higher_level_range"
    assert technical_section["route_level_from"] == "30m"
    assert technical_section["route_level_to"] == "day"
    assert any("中枢预警：向下预警，当前不构成确认三卖（中线 10.45，节奏偏弱）" in line for line in technical_section["technical_focus_lines"])
    assert any("去向候选：更大级别盘整（30m -> day），当前只按观察态处理" in line for line in technical_section["technical_focus_lines"])
    assert any("节奏监视：节奏偏弱，当前只作辅助观察" in line for line in technical_section["technical_focus_lines"])


def test_build_summary_and_detail_payload_preserve_30m_pre_breakout_publish_anchor(tmp_path: Path) -> None:
    stock_dir = tmp_path / "002594"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(
        json.dumps({"generated_at": "2026-08-18T09:00:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "fund.json").write_text(
        json.dumps({"generated_at": "2026-08-18T09:05:00", "summary": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-18T09:30:00",
                "timeframe": "30m",
                "source": "akshare.eastmoney",
                "zhongshu_level": "segment",
                "structure": {
                    "primary_zhongshu_level": "segment",
                    "latest_zhongshu": {
                        "zs_id": 8,
                        "entering_bi_id": 61,
                        "exit_bi_id": None,
                        "is_terminated": False,
                        "superseded_by_zs_id": None,
                        "is_reabsorbed_by_larger_expansion": False,
                    },
                    "zhongshus": [
                        {
                            "zs_id": 8,
                            "entering_bi_id": 61,
                            "exit_bi_id": None,
                            "is_terminated": False,
                            "superseded_by_zs_id": None,
                            "is_reabsorbed_by_larger_expansion": False,
                        }
                    ],
                },
                "summary": {
                    "score": 63,
                    "rating": "C",
                    "bias": "偏强",
                    "score_breakdown": {},
                    "conclusion": "出现向上预警，但当前不构成确认三买。",
                    "suggestion": "继续观察首次回试是否回中枢。",
                    "buy_points": [],
                    "sell_points": [],
                    "signal_points": [],
                    "signal_catalog": [],
                    "structure_state": {
                        "last_completed": None,
                        "current_ongoing": {
                            "type": "range",
                            "status": "ongoing",
                            "start_ts": "2026-08-01T10:30:00",
                            "latest_ts": "2026-08-18T09:30:00",
                            "zs_count_so_far": 1,
                            "confirmation_basis": "single_active_zhongshu",
                        },
                        "relationship": {
                            "kind": "undetermined",
                            "note": "当前只有一个同级别中枢，按工程口径先视为盘整进行中。",
                        },
                        "current_structure_status": "ongoing_same_type",
                    },
                    "same_level_decomposition_mode": "dual_interpretation_pending",
                    "oscillation_rhythm_state": "balanced",
                    "post_divergence_route": "higher_level_reverse_trend",
                    "route_level_from": "30m",
                    "route_level_to": "day",
                    "zs_monitor_alert": "pre_breakout",
                    "zs_monitor_midline": 18.25,
                    "zs_monitor_bias": "strong",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    holding = module.Holding(symbol="002594", name="比亚迪", market="CN")

    summary_payload = module.build_summary_payload(holding, stock_dir, None)
    detail_payload, _ = module.build_detail_payload(holding, stock_dir, None)

    technical_card = summary_payload["cards"]["technical"]
    technical_section = detail_payload["sections"][1]

    assert technical_card["conclusion"] == "出现向上预警，但当前不构成确认三买。"
    assert technical_card["suggestion"] == "继续观察首次回试是否回中枢。"
    assert technical_card["same_level_decomposition"]["current"]["type_label"] == "盘整"
    assert technical_card["oscillation_rhythm_state"] == "balanced"
    assert technical_card["post_divergence_route"] == "higher_level_reverse_trend"
    assert technical_card["route_level_from"] == "30m"
    assert technical_card["route_level_to"] == "day"
    assert any("中枢预警：向上预警，当前不构成确认三买（中线 18.25，节奏偏强）" in line for line in technical_card["technical_focus_lines"])
    assert any("去向候选：更大级别反趋势（30m -> day），当前只按观察态处理" in line for line in technical_card["technical_focus_lines"])
    assert any("节奏监视：节奏平衡，当前只作辅助观察" in line for line in technical_card["technical_focus_lines"])
    assert technical_section["conclusion"] == "出现向上预警，但当前不构成确认三买。"
    assert technical_section["oscillation_rhythm_state"] == "balanced"
    assert technical_section["post_divergence_route"] == "higher_level_reverse_trend"
    assert technical_section["route_level_from"] == "30m"
    assert technical_section["route_level_to"] == "day"
    assert any("中枢预警：向上预警，当前不构成确认三买（中线 18.25，节奏偏强）" in line for line in technical_section["technical_focus_lines"])
    assert any("去向候选：更大级别反趋势（30m -> day），当前只按观察态处理" in line for line in technical_section["technical_focus_lines"])
    assert any("节奏监视：节奏平衡，当前只作辅助观察" in line for line in technical_section["technical_focus_lines"])


def test_generate_bundle_preserves_previous_latest_when_build_fails(tmp_path: Path, monkeypatch) -> None:
    holdings_path = tmp_path / "stock_holdings.json"
    holdings_path.write_text(
        json.dumps({"markets": {"CN": [{"symbol": "000651", "name": "格力电器"}]}} , ensure_ascii=False),
        encoding="utf-8",
    )

    reports_root = tmp_path / "reports"
    meta_dir = reports_root / "_meta"
    meta_dir.mkdir(parents=True)
    stock_dir = reports_root / "000651"
    (stock_dir / "30m").mkdir(parents=True)
    (stock_dir / "base.json").write_text(json.dumps({"summary": {}}, ensure_ascii=False), encoding="utf-8")
    (stock_dir / "fund.json").write_text(json.dumps({"summary": {}}, ensure_ascii=False), encoding="utf-8")
    (stock_dir / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-18T10:00:00",
                "timeframe": "30m",
                "summary": {
                    "score": 60,
                    "rating": "C",
                    "bias": "中性",
                    "score_breakdown": {},
                    "conclusion": "观察中",
                    "suggestion": "等待确认",
                    "buy_points": [],
                    "sell_points": [],
                    "signal_points": [],
                    "signal_catalog": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    publish_root = tmp_path / "publish"
    latest_dir = publish_root / "latest"
    latest_dir.mkdir(parents=True)
    (latest_dir / "index.json").write_text(json.dumps({"marker": "previous-latest"}, ensure_ascii=False), encoding="utf-8")

    def fail_build_detail_payload(*args, **kwargs):
        raise RuntimeError("simulated build failure")

    monkeypatch.setattr(module, "build_detail_payload", fail_build_detail_payload)

    try:
        module.generate_bundle(
            holdings_path=holdings_path,
            reports_root=reports_root,
            publish_root=publish_root,
            snapshot_stamp="20260818_120000",
            latest_only=True,
        )
    except RuntimeError as error:
        assert "simulated build failure" in str(error)
    else:
        raise AssertionError("expected generate_bundle to fail")

    preserved = json.loads((latest_dir / "index.json").read_text(encoding="utf-8"))
    assert preserved["marker"] == "previous-latest"


def test_build_segment_records_backfills_stop_reason_label_when_missing() -> None:
    segment_records = [
        {
            "segment_id": 0,
            "direction": "up",
            "start_bi_id": 1,
            "end_bi_id": 3,
            "start_ts": "2024-01-01 10:30",
            "end_ts": "2024-01-03 14:00",
            "start_price": 10.0,
            "end_price": 12.5,
            "high": 12.5,
            "low": 9.8,
            "start_norm_idx": 4,
            "end_norm_idx": 12,
            "bi_ids": "1,2,3",
            "last_same_extreme": 12.5,
            "last_reverse_extreme": 10.8,
            "break_bi_id": 4,
            "stop_reason": "same_direction_not_extending",
            "is_confirmed": False,
            "status": "preprocessing",
            "note": "auto_generated",
        }
    ]

    records = module.build_segment_records([], segment_records)

    assert len(records) == 1
    assert records[0]["stop_reason"] == "same_direction_not_extending"
    assert records[0]["theory_candidate_end_bi_id"] == 3
    assert records[0]["theory_candidate_end_ts"] == "2024-01-03 14:00"
    assert records[0]["theory_candidate_end_price"] == 12.5
    assert records[0]["stop_reason_label"] == "出现同向笔，但没有继续创新高或新低"
    assert records[0]["stop_category"] == "pending"
    assert records[0]["is_theory_confirmed_stop"] is False
    assert records[0]["is_fallback_confirmed_stop"] is False
    assert records[0]["is_pending_stop"] is True


def test_build_latest_segment_stop_reason_line_from_csv_records(tmp_path: Path) -> None:
    stock_dir = tmp_path / "000651"
    analyze_dir = stock_dir / "30m" / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    bars_csv = analyze_dir / "000651_30m_20260101_to_20260131.csv"
    bars_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-01-02 10:30,10.0,10.5,9.8,10.2,1000\n",
        encoding="utf-8",
    )

    segments_csv = analyze_dir / "000651_30m_20260101_to_20260131_normalized_segments.csv"
    segments_csv.write_text(
        "segment_id,direction,start_bi_id,end_bi_id,start_ts,end_ts,start_price,end_price,high,low,start_norm_idx,end_norm_idx,bi_ids,last_same_extreme,last_reverse_extreme,break_bi_id,stop_reason,is_confirmed,status,note\n"
        "0,up,1,3,2026-01-01 10:30,2026-01-03 14:00,10.0,12.5,12.5,9.8,4,12,\"1,2,3\",12.5,10.8,4,same_direction_not_extending,False,preprocessing,auto_generated\n",
        encoding="utf-8",
    )

    line = module.build_latest_segment_stop_reason_line(stock_dir, "30m")

    assert line.startswith("30M S0 停驻原因：")
    assert "出现同向笔，但没有继续创新高或新低" in line


def test_find_latest_chart_bars_csv_prefers_filename_date_range_over_mtime(tmp_path: Path) -> None:
    timeframe_dir = tmp_path / "1m"
    analyze_dir = timeframe_dir / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    earlier_range_csv = analyze_dir / "01024_1m_20260803_to_20260805.csv"
    earlier_range_csv.write_text("ts,open,high,low,close,volume\n", encoding="utf-8")
    later_range_csv = analyze_dir / "01024_1m_20260804_to_20260807.csv"
    later_range_csv.write_text("ts,open,high,low,close,volume\n", encoding="utf-8")

    os.utime(earlier_range_csv, (2000000000, 2000000000))
    os.utime(later_range_csv, (1000000000, 1000000000))

    selected = module.find_latest_chart_bars_csv(timeframe_dir, "1m")

    assert selected is not None
    assert selected.name == later_range_csv.name


def test_find_latest_chart_bars_csv_prefers_earlier_start_when_end_date_matches(tmp_path: Path) -> None:
    timeframe_dir = tmp_path / "5m"
    analyze_dir = timeframe_dir / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    wider_window_csv = analyze_dir / "00981_5m_20260722_to_20260813.csv"
    wider_window_csv.write_text("ts,open,high,low,close,volume\n", encoding="utf-8")
    narrower_window_csv = analyze_dir / "00981_5m_20260803_to_20260813.csv"
    narrower_window_csv.write_text("ts,open,high,low,close,volume\n", encoding="utf-8")

    # Keep modification times equal to make date-range ordering decisive.
    os.utime(wider_window_csv, (1500000000, 1500000000))
    os.utime(narrower_window_csv, (1500000000, 1500000000))

    selected = module.find_latest_chart_bars_csv(timeframe_dir, "5m")

    assert selected is not None
    assert selected.name == wider_window_csv.name


def test_build_chart_data_payload_includes_segment_stop_reason_annotations(tmp_path: Path) -> None:
    analyze_dir = tmp_path / "30m" / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    bars_csv = analyze_dir / "000651_30m_20260101_to_20260131.csv"
    bars_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-01-02 10:30,10.0,10.5,9.8,10.2,1000\n",
        encoding="utf-8",
    )

    segments_csv = analyze_dir / "000651_30m_20260101_to_20260131_normalized_segments.csv"
    segments_csv.write_text(
        "segment_id,direction,start_bi_id,end_bi_id,start_ts,end_ts,start_price,end_price,high,low,start_norm_idx,end_norm_idx,bi_ids,last_same_extreme,last_reverse_extreme,break_bi_id,stop_reason,is_confirmed,status,note\n"
        "0,up,1,3,2026-01-01 10:30,2026-01-03 14:00,10.0,12.5,12.5,9.8,4,12,\"1,2,3\",12.5,10.8,4,same_direction_not_extending,False,preprocessing,auto_generated\n",
        encoding="utf-8",
    )

    payload = module.build_chart_data_payload(
        {
            "timeframe": "30m",
            "label": "30M 结构图",
            "data_source_path": str(bars_csv),
        }
    )

    assert payload is not None
    annotations = payload["segment_stop_reason_annotations"]
    assert annotations["latest"] is not None
    assert annotations["latest"]["segment_id"] == 0
    assert annotations["latest"]["stop_reason_label"] == "出现同向笔，但没有继续创新高或新低"
    assert annotations["latest"]["stop_category"] == "pending"
    assert annotations["latest"]["stop_outcome_bucket"] == "pending"
    assert annotations["latest"]["stop_outcome_label"] == "pending"
    assert annotations["latest"]["is_theory_confirmed_stop"] is False
    assert annotations["latest"]["is_fallback_confirmed_stop"] is False
    assert annotations["latest"]["is_pending_stop"] is True
    assert annotations["latest"]["text"].startswith("30M S0 停驻原因：")


def test_build_chart_data_payload_uses_precision_entry_pending_reverse_mode(tmp_path: Path) -> None:
    analyze_dir = tmp_path / "30m" / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    bars_csv = analyze_dir / "000651_30m_20260101_to_20260131.csv"
    bars_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-01-02 10:30,10.0,10.5,9.8,10.2,1000\n",
        encoding="utf-8",
    )

    (tmp_path / "30m" / "tech.json").write_text(
        json.dumps(
            {
                "summary": {
                    "precision_entry": {
                        "pending_reverse_mode": "strict",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = module.build_chart_data_payload(
        {
            "timeframe": "30m",
            "label": "30M 结构图",
            "data_source_path": str(bars_csv),
        }
    )

    assert payload is not None
    assert payload["pending_reverse_mode"] == "strict"


def test_build_chart_data_payload_enriches_bis_with_endpoint_prices(tmp_path: Path) -> None:
    analyze_dir = tmp_path / "1m" / "analyze"
    analyze_dir.mkdir(parents=True, exist_ok=True)

    bars_csv = analyze_dir / "01024_1m_20260806_to_20260806.csv"
    bars_csv.write_text(
        "ts,open,high,low,close,volume\n"
        "2026-08-06 11:13,44.60,44.76,44.58,44.62,100\n",
        encoding="utf-8",
    )

    (analyze_dir / "01024_1m_20260806_to_20260806_normalized_fractals.csv").write_text(
        "fx_id,fx_type,ts,price,center_bar_idx,high,low,is_confirmed,status,note\n"
        "148,bottom,2026-08-06 11:13,44.58,275,44.76,44.58,True,confirmed,confirmed\n"
        "151,top,2026-08-06 11:21,44.672,280,44.672,44.62,True,confirmed,confirmed\n",
        encoding="utf-8",
    )
    (analyze_dir / "01024_1m_20260806_to_20260806_normalized_bis.csv").write_text(
        "bi_id,direction,start_fx_id,end_fx_id,start_ts,end_ts,high,low,start_norm_idx,end_norm_idx,is_confirmed,status,note\n"
        "36,up,148,151,2026-08-06 11:13,2026-08-06 11:21,44.76,44.58,275,280,True,confirmed,auto_generated\n",
        encoding="utf-8",
    )
    (analyze_dir / "01024_1m_20260806_to_20260806_normalized_segments.csv").write_text(
        "segment_id,direction,start_bi_id,end_bi_id,start_ts,end_ts,start_price,end_price,high,low,start_norm_idx,end_norm_idx,bi_ids,last_same_extreme,last_reverse_extreme,break_bi_id,stop_reason,is_confirmed,status,note\n",
        encoding="utf-8",
    )

    payload = module.build_chart_data_payload(
        {
            "timeframe": "1m",
            "label": "1M 结构图",
            "data_source_path": str(bars_csv),
        }
    )

    assert payload is not None
    assert payload["bis"][0]["start_price"] == 44.58
    assert payload["bis"][0]["end_price"] == 44.672
    assert payload["bis"][0]["start_fx_type"] == "bottom"
    assert payload["bis"][0]["end_fx_type"] == "top"


def test_normalize_chart_zhongshu_records_segment_removes_bi_keys() -> None:
    records = [
        {
            "structure_level": "segment",
            "start_bi_id": 1,
            "end_bi_id": 3,
            "core_bi_ids": "1,2,3",
            "start_segment_id": 1,
            "end_segment_id": 3,
            "core_segment_ids": "1,2,3",
        }
    ]

    normalized = module.normalize_chart_zhongshu_records(records)

    assert len(normalized) == 1
    assert normalized[0]["start_segment_id"] == 1
    assert normalized[0]["end_segment_id"] == 3
    assert normalized[0]["core_segment_ids"] == "1,2,3"
    assert "start_bi_id" not in normalized[0]
    assert "end_bi_id" not in normalized[0]
    assert "core_bi_ids" not in normalized[0]


def test_normalize_chart_zhongshu_records_bi_removes_segment_keys() -> None:
    records = [
        {
            "structure_level": "bi",
            "start_bi_id": 9,
            "end_bi_id": 12,
            "core_bi_ids": "9,10,11",
            "start_segment_id": 3,
            "end_segment_id": 4,
            "core_segment_ids": "3,4,5",
        }
    ]

    normalized = module.normalize_chart_zhongshu_records(records)

    assert len(normalized) == 1
    assert normalized[0]["start_bi_id"] == 9
    assert normalized[0]["end_bi_id"] == 12
    assert normalized[0]["core_bi_ids"] == "9,10,11"
    assert "start_segment_id" not in normalized[0]
    assert "end_segment_id" not in normalized[0]
    assert "core_segment_ids" not in normalized[0]