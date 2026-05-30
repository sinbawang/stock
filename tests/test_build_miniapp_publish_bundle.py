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
        (stock_dir / "15m").mkdir(parents=True)
        (stock_dir / "60m" / "structure.jpg").write_text("jpg60", encoding="utf-8")
        (stock_dir / "15m" / "structure.jpg").write_text("jpg15", encoding="utf-8")
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
        (stock_dir / "60m" / "tech.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-05-30T20:33:27",
                    "timeframe": "60m",
                    "source": "akshare.eastmoney",
                    "summary": {"conclusion": "偏强，持有为主。", "suggestion": "继续持有"},
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

    summary_payload = json.loads((latest_dir / "stocks" / "000651" / "summary.json").read_text(encoding="utf-8"))
    assert summary_payload["priority"] == "P2"
    assert summary_payload["jump"]["detail"] == "stocks/000651/detail.json"

    detail_payload = json.loads((latest_dir / "stocks" / "00700" / "detail.json").read_text(encoding="utf-8"))
    assert detail_payload["headline"]["priority"] == "P1"
    assert detail_payload["charts"][0]["path"] == "stocks/00700/charts/60m.jpg"

    a_share_group = json.loads((latest_dir / "groups" / "a_share.json").read_text(encoding="utf-8"))
    assert a_share_group["sections"][1]["items"][0]["symbol"] == "000651"

    portfolio_group = json.loads((latest_dir / "groups" / "portfolio.json").read_text(encoding="utf-8"))
    assert portfolio_group["sections"][0]["items"][0]["symbol"] == "00700"

    assert (latest_dir / "stocks" / "000651" / "charts" / "60m.jpg").exists()
    assert (snapshot_dir / "stocks" / "00700" / "charts" / "15m.jpg").exists()