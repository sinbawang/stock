from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_REPORTS_ROOT = REPORTS_DIR
DEFAULT_PUBLISH_ROOT = ROOT / "build" / "miniapp-publish"


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    market: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a miniapp-native publish bundle from canonical reports.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT), help="Canonical reports root")
    parser.add_argument("--publish-root", default=str(DEFAULT_PUBLISH_ROOT), help="Publish bundle root")
    parser.add_argument("--snapshot-stamp", default=None, help="Optional explicit snapshot stamp such as 20260530_210500")
    parser.add_argument("--latest-only", action="store_true", help="Only write the latest bundle and skip snapshots/<stamp>")
    return parser.parse_args()


def load_holdings(path: Path) -> list[Holding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = payload.get("markets") or {}
    holdings: list[Holding] = []
    for market in ("CN", "HK"):
        for item in markets.get(market, []):
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").strip()
            if not symbol:
                continue
            normalized = symbol.zfill(5) if market == "HK" else symbol.zfill(6)
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            holdings.append(Holding(symbol=normalized, name=name, market=market))
    return holdings


def latest_file(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_section_lines(text: str, title: str) -> list[str]:
    pattern = rf"^{re.escape(title)}\s*\n(?P<body>.*?)(?=\n(?:[\u4e00-\u9fffA-Za-z0-9_ /]+[:：]|##\s)|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    lines: list[str] = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if line.startswith("- "):
            lines.append(line[2:])
    return lines


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def priority_rank(priority: str | None) -> int:
    mapping = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
    return mapping.get((priority or "").strip(), 99)


def parse_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_combined_group_file(path: Path, group_key: str) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    generated_at = ""
    counts: dict[str, int] = {"today_action": 0, "watch_pool": 0, "risk_pool": 0}
    notes: list[str] = []
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    in_notes = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Generated at:"):
            generated_at = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("清单分布:"):
            payload = stripped.split(":", 1)[1].strip()
            for part in payload.split(","):
                key, _, value = part.strip().partition("=")
                normalized = {
                    "今日动作": "today_action",
                    "观察池": "watch_pool",
                    "风险池": "risk_pool",
                }.get(key.strip())
                if normalized:
                    try:
                        counts[normalized] = int(value.strip())
                    except ValueError:
                        counts[normalized] = 0
        elif stripped.startswith("### "):
            mapping = {
                "今日动作": "today_action",
                "观察池": "watch_pool",
                "风险池": "risk_pool",
            }
            title = stripped[4:].strip()
            current_section = {"key": mapping.get(title, title), "title": title, "items": []}
            sections.append(current_section)
            in_notes = False
        elif stripped == "## 口径说明":
            in_notes = True
            current_section = None
        elif in_notes and stripped.startswith("- "):
            notes.append(stripped[2:])
        elif current_section and stripped.startswith("| P"):
            cells = parse_markdown_table_row(stripped)
            if len(cells) >= 9:
                current_section["items"].append(
                    {
                        "priority": cells[0],
                        "action": cells[1],
                        "symbol": cells[2].zfill(5) if len(cells[2]) == 5 else cells[2].zfill(6),
                        "name": cells[3],
                        "bucket": cells[4],
                        "fundamental": cells[5],
                        "technical": cells[6],
                        "capital_flow": cells[7],
                        "comment": cells[8],
                    }
                )

    return {
        "schema_version": "v1",
        "group": group_key,
        "generated_at": generated_at,
        "counts": counts,
        "sections": sections,
        "notes": notes,
        "source_file": path.name,
    }


def load_group_payloads(meta_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    file_map = {
        "a_share": latest_file(meta_dir, "group_a_share_combined_overview_*.txt"),
        "h_share": latest_file(meta_dir, "group_h_share_combined_overview_*.txt"),
    }
    for group_key, path in file_map.items():
        if path is not None:
            payloads[group_key] = parse_combined_group_file(path, group_key)
    return payloads


def collect_group_item_map(group_payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    item_map: dict[str, dict[str, Any]] = {}
    for payload in group_payloads.values():
        for section in payload.get("sections", []):
            for item in section.get("items", []):
                item_map[item["symbol"]] = item
    return item_map


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def build_fundamental_section(base_payload: dict[str, Any]) -> dict[str, Any]:
    summary = base_payload.get("summary") or {}
    blended = base_payload.get("blended") or {}
    annual_anchor = blended.get("annual_anchor") or {}
    scorecard = annual_anchor.get("scorecard") or {}
    snapshot = annual_anchor.get("snapshot") or {}
    return {
        "key": "fundamental",
        "title": "基本面",
        "rating": summary.get("rating"),
        "score": summary.get("score"),
        "submodel": summary.get("submodel"),
        "report_period": snapshot.get("report_period"),
        "summary": first_non_empty(scorecard.get("combined_comment"), summary.get("comment")),
        "highlights": (scorecard.get("strengths") or [])[:3],
        "risks": (scorecard.get("risks") or [])[:3],
        "follow_ups": (scorecard.get("focus_questions") or [])[:3],
        "warnings": (scorecard.get("warnings") or [])[:3],
    }


def build_capital_flow_section(fund_payload: dict[str, Any]) -> dict[str, Any]:
    summary = fund_payload.get("summary") or {}
    scorecard = fund_payload.get("scorecard") or {}
    snapshot = fund_payload.get("snapshot") or {}
    metrics: list[dict[str, str]] = []
    label_map = [
        ("main_net_inflow", "主力净流入"),
        ("main_net_inflow_5d", "5日主力净流入"),
        ("southbound_net_buy", "南向净买入"),
        ("southbound_holding_change", "南向持股变化"),
        ("short_sell_ratio", "沽空比例"),
    ]
    for key, label in label_map:
        value = snapshot.get(key)
        if value is not None:
            metrics.append({"label": label, "value": str(value)})
    return {
        "key": "capital_flow",
        "title": "资金面",
        "rating": summary.get("rating"),
        "score": summary.get("score"),
        "source": summary.get("source"),
        "trade_date": scorecard.get("trade_date"),
        "summary": first_non_empty(summary.get("comment"), scorecard.get("combined_comment")),
        "strengths": (scorecard.get("strengths") or [])[:3],
        "risks": (scorecard.get("risks") or [])[:3],
        "warnings": (scorecard.get("warnings") or [])[:3],
        "metrics": metrics[:5],
    }


def build_technical_section(tech_payload: dict[str, Any]) -> dict[str, Any]:
    summary = tech_payload.get("summary") or {}
    analysis_text = safe_text(tech_payload.get("analysis_text"))
    return {
        "key": "technical",
        "title": "技术面",
        "timeframe": tech_payload.get("timeframe") or "60m",
        "source": tech_payload.get("source"),
        "conclusion": summary.get("conclusion"),
        "suggestion": summary.get("suggestion"),
        "overview": extract_section_lines(analysis_text, "概览：")[:4],
        "structure": extract_section_lines(analysis_text, "结构：")[:4],
        "signals": extract_section_lines(analysis_text, "信号：")[:4],
        "focus": extract_section_lines(analysis_text, "观察重点：")[:2],
    }


def build_chart_specs(stock_dir: Path) -> list[dict[str, str]]:
    charts: list[dict[str, str]] = []
    for timeframe in ("60m", "15m", "day"):
        chart_path = stock_dir / timeframe / "structure.jpg"
        if chart_path.exists():
            charts.append({
                "timeframe": timeframe,
                "source_path": str(chart_path),
                "relative_path": f"charts/{timeframe}.jpg",
                "label": f"{timeframe.upper()} 结构图",
            })
    return charts


def build_summary_payload(holding: Holding, stock_dir: Path, group_item: dict[str, Any] | None) -> dict[str, Any]:
    base_payload = read_json(stock_dir / "base.json")
    fund_payload = read_json(stock_dir / "fund.json")
    tech_payload = read_json(stock_dir / "60m" / "tech.json")
    base_summary = base_payload.get("summary") or {}
    fund_summary = fund_payload.get("summary") or {}
    tech_summary = tech_payload.get("summary") or {}
    charts = build_chart_specs(stock_dir)
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        safe_text(tech_payload.get("generated_at")),
    )
    return {
        "schema_version": "v1",
        "symbol": holding.symbol,
        "name": holding.name,
        "market": holding.market,
        "updated_at": updated_at,
        "priority": group_item.get("priority") if group_item else None,
        "action": group_item.get("action") if group_item else None,
        "bucket": group_item.get("bucket") if group_item else None,
        "comment": group_item.get("comment") if group_item else first_non_empty(fund_summary.get("comment"), fund_summary.get("summary")),
        "cards": {
            "fundamental": {
                "score": base_summary.get("score"),
                "rating": base_summary.get("rating"),
                "summary": first_non_empty(base_summary.get("comment"), (base_payload.get("blended") or {}).get("annual_anchor", {}).get("scorecard", {}).get("combined_comment")),
            },
            "technical": {
                "timeframe": tech_payload.get("timeframe") or "60m",
                "conclusion": tech_summary.get("conclusion"),
                "suggestion": tech_summary.get("suggestion"),
            },
            "capital_flow": {
                "score": fund_summary.get("score"),
                "rating": fund_summary.get("rating"),
                "source": fund_summary.get("source"),
                "summary": first_non_empty(fund_summary.get("comment"), (fund_payload.get("scorecard") or {}).get("combined_comment")),
            },
        },
        "cover_chart": {"timeframe": "60m", "path": f"stocks/{holding.symbol}/charts/60m.jpg"} if any(chart["timeframe"] == "60m" for chart in charts) else None,
        "jump": {"detail": f"stocks/{holding.symbol}/detail.json"},
        "tags": [value for value in [group_item.get("bucket") if group_item else None, group_item.get("priority") if group_item else None, group_item.get("action") if group_item else None] if value],
    }


def build_detail_payload(holding: Holding, stock_dir: Path, group_item: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base_payload = read_json(stock_dir / "base.json")
    fund_payload = read_json(stock_dir / "fund.json")
    tech_payload = read_json(stock_dir / "60m" / "tech.json")
    charts = build_chart_specs(stock_dir)
    fundamental = build_fundamental_section(base_payload)
    technical = build_technical_section(tech_payload)
    capital_flow = build_capital_flow_section(fund_payload)
    overview_bullets = [
        f"基本面 {safe_text(fundamental.get('score'), 'missing')}/{safe_text(fundamental.get('rating'), 'missing')}",
        f"60M 技术面 {safe_text(technical.get('conclusion'), 'missing')}",
        f"资金面 {safe_text(capital_flow.get('score'), 'missing')}/{safe_text(capital_flow.get('rating'), 'missing')}",
    ]
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        safe_text(tech_payload.get("generated_at")),
    )
    payload = {
        "schema_version": "v1",
        "symbol": holding.symbol,
        "name": holding.name,
        "market": holding.market,
        "updated_at": updated_at,
        "headline": {
            "title": f"{holding.name} {holding.symbol}",
            "subtitle": "三轴综合观察",
            "priority": group_item.get("priority") if group_item else None,
            "action": group_item.get("action") if group_item else None,
            "bucket": group_item.get("bucket") if group_item else None,
        },
        "overview": {
            "summary": group_item.get("comment") if group_item else first_non_empty(technical.get("conclusion"), fundamental.get("summary")),
            "bullets": overview_bullets,
        },
        "sections": [fundamental, technical, capital_flow],
        "charts": [
            {"timeframe": chart["timeframe"], "path": f"stocks/{holding.symbol}/{chart['relative_path']}", "label": chart["label"]}
            for chart in charts
        ],
        "disclaimer": "本页面仅用于持仓跟踪与研究，不构成投资建议。",
    }
    return payload, charts


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_chart_assets(chart_specs: list[dict[str, str]], stock_target_dir: Path) -> None:
    for chart in chart_specs:
        source_path = Path(chart["source_path"])
        target_path = stock_target_dir / chart["relative_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def build_portfolio_group(group_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for payload in group_payloads.values():
        for section in payload.get("sections", []):
            items.extend(section.get("items", []))
    items.sort(key=lambda item: (priority_rank(item.get("priority")), item.get("symbol", "")))
    return {
        "schema_version": "v1",
        "group": "portfolio",
        "generated_at": max((payload.get("generated_at") or "") for payload in group_payloads.values()) if group_payloads else "",
        "counts": {"items": len(items)},
        "sections": [{"key": "portfolio", "title": "全部持仓", "items": items}],
        "notes": ["由 A 股与港股组合概览合并生成，仅用于原生小程序展示。"],
    }


def build_index_payload(summary_payloads: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    ordered = sorted(summary_payloads, key=lambda item: (priority_rank(item.get("priority")), item.get("market", ""), item.get("symbol", "")))
    return {
        "schema_version": "v1",
        "generated_at": generated_at,
        "source_root": "data/reports",
        "markets": ["CN", "HK"],
        "counts": {
            "stocks": len(summary_payloads),
            "cn": sum(1 for item in summary_payloads if item.get("market") == "CN"),
            "hk": sum(1 for item in summary_payloads if item.get("market") == "HK"),
        },
        "groups": {
            "portfolio": "groups/portfolio.json",
            "a_share": "groups/a_share.json",
            "h_share": "groups/h_share.json",
        },
        "stocks": [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": item["market"],
                "updated_at": item["updated_at"],
                "summary": f"stocks/{item['symbol']}/summary.json",
                "detail": f"stocks/{item['symbol']}/detail.json",
                "cover_chart": item.get("cover_chart", {}).get("path") if item.get("cover_chart") else None,
                "tags": item.get("tags", []),
            }
            for item in ordered
        ],
    }


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def generate_bundle(holdings_path: Path, reports_root: Path, publish_root: Path, snapshot_stamp: str | None, latest_only: bool) -> dict[str, Path]:
    stamp = snapshot_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_dir = publish_root / "latest"
    snapshot_dir = publish_root / "snapshots" / stamp
    meta_dir = reports_root / "_meta"
    holdings = load_holdings(holdings_path)
    group_payloads = load_group_payloads(meta_dir)
    group_item_map = collect_group_item_map(group_payloads)

    targets = [latest_dir] if latest_only else [latest_dir, snapshot_dir]
    for target in targets:
        ensure_clean_dir(target)

    summary_payloads: list[dict[str, Any]] = []
    for holding in holdings:
        stock_dir = reports_root / holding.symbol
        if not stock_dir.exists():
            continue
        summary_payload = build_summary_payload(holding, stock_dir, group_item_map.get(holding.symbol))
        detail_payload, chart_specs = build_detail_payload(holding, stock_dir, group_item_map.get(holding.symbol))
        summary_payloads.append(summary_payload)
        for target in targets:
            stock_target_dir = target / "stocks" / holding.symbol
            write_json(stock_target_dir / "summary.json", summary_payload)
            write_json(stock_target_dir / "detail.json", detail_payload)
            copy_chart_assets(chart_specs, stock_target_dir)

    portfolio_payload = build_portfolio_group(group_payloads)
    generated_at = datetime.now().isoformat(timespec="seconds")
    index_payload = build_index_payload(summary_payloads, generated_at)
    for target in targets:
        write_json(target / "index.json", index_payload)
        if "a_share" in group_payloads:
            write_json(target / "groups" / "a_share.json", group_payloads["a_share"])
        if "h_share" in group_payloads:
            write_json(target / "groups" / "h_share.json", group_payloads["h_share"])
        write_json(target / "groups" / "portfolio.json", portfolio_payload)
    return {"latest": latest_dir, "snapshot": snapshot_dir}


def main() -> None:
    args = parse_args()
    outputs = generate_bundle(
        holdings_path=Path(args.holdings_file),
        reports_root=Path(args.reports_root),
        publish_root=Path(args.publish_root),
        snapshot_stamp=args.snapshot_stamp,
        latest_only=args.latest_only,
    )
    print(f"latest= {outputs['latest']}")
    if not args.latest_only:
        print(f"snapshot= {outputs['snapshot']}")


if __name__ == "__main__":
    main()