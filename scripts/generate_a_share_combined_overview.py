from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report_retention import prune_older_outputs
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_META_DIR = REPORTS_META_DIR


@dataclass(frozen=True)
class CombinedTarget:
    symbol: str
    name: str


@dataclass(frozen=True)
class FundamentalBriefRef:
    score: float | None = None
    rating: str | None = None
    submodel: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class TechnicalRef:
    conclusion: str | None = None
    suggestion: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class CapitalFlowRef:
    score: float | None = None
    rating: str | None = None
    source: str | None = None
    bucket: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class CombinedOverviewRow:
    target: CombinedTarget
    fundamental: FundamentalBriefRef
    technical: TechnicalRef
    capital_flow: CapitalFlowRef
    combined_bucket: str
    combined_comment: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a combined A-share overview from technical, fundamental, and capital-flow reports.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="A-share holdings JSON file")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Directory containing generated report text files")
    parser.add_argument("--output-dir", default=str(DEFAULT_META_DIR), help="Directory for the combined overview output")
    parser.add_argument("--limit", type=int, default=None, help="Optional target count limit")
    return parser.parse_args()


def discover_targets_from_holdings_file(holdings_file: Path) -> list[CombinedTarget]:
    payload = json.loads(holdings_file.read_text(encoding="utf-8"))
    entries = payload.get("holdings", [])
    if isinstance(payload.get("markets"), dict):
        entries = payload["markets"].get("CN", [])

    targets: list[CombinedTarget] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").strip().zfill(6)
        name = str(entry.get("name") or "").strip()
        if not symbol or not name or symbol in seen:
            continue
        seen.add(symbol)
        targets.append(CombinedTarget(symbol=symbol, name=name))
    return targets


def latest_file(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _extract_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_text(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def load_fundamental_ref(target: CombinedTarget, meta_dir: Path) -> FundamentalBriefRef:
    json_path = meta_dir / target.symbol / "base.json" if (meta_dir / target.symbol / "base.json").exists() else REPORTS_DIR / target.symbol / "base.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        summary = payload.get("summary", {})
        return FundamentalBriefRef(
            score=summary.get("score"),
            rating=summary.get("rating"),
            submodel=summary.get("submodel"),
            path=json_path,
        )
    path = latest_file(meta_dir, f"{target.symbol}_{target.name}*_fundamental_brief_*.txt")
    if path is None:
        return FundamentalBriefRef()
    text = path.read_text(encoding="utf-8")
    return FundamentalBriefRef(
        score=_extract_float(text, r"^- 总分:\s*([0-9.]+)"),
        rating=_extract_text(text, r"^- 评级:\s*([A-D])"),
        submodel=_extract_text(text, r"^- 子模型:\s*([^\n]+)"),
        path=path,
    )


def load_latest_technical_map(meta_dir: Path) -> tuple[dict[str, TechnicalRef], Path | None]:
    path = latest_file(meta_dir, "group888_60m_operation_summary_*.txt")
    if path is None:
        refs: dict[str, TechnicalRef] = {}
        candidate_roots = [meta_dir, REPORTS_DIR]
        for root in candidate_roots:
            if not root.exists():
                continue
            for symbol_dir in [item for item in root.iterdir() if item.is_dir() and item.name != "_meta"]:
                tech_path = symbol_dir / "60m" / "tech.json"
                if not tech_path.exists():
                    continue
                payload = json.loads(tech_path.read_text(encoding="utf-8"))
                summary = payload.get("summary", {})
                refs[symbol_dir.name.zfill(6)] = TechnicalRef(
                    conclusion=summary.get("conclusion"),
                    suggestion=summary.get("suggestion"),
                    path=tech_path,
                )
        return refs, None
    refs: dict[str, TechnicalRef] = {}
    line_re = re.compile(r"^-\s*(?P<name>.+?)\((?P<symbol>\d{5,6})\)：(?P<conclusion>.*?)\s+建议：(?P<suggestion>.*)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = line_re.match(line.strip())
        if not match:
            continue
        refs[match.group("symbol").zfill(6)] = TechnicalRef(
            conclusion=match.group("conclusion").strip(),
            suggestion=match.group("suggestion").strip(),
            path=path,
        )
    return refs, path


def _parse_capital_flow_overview(path: Path) -> dict[str, CapitalFlowRef]:
    refs: dict[str, CapitalFlowRef] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "symbol" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 9:
            continue
        symbol, _name, status, _trade_date, score_text, rating, source, bucket, report = cells[:9]
        if status != "ok":
            refs[symbol.zfill(6)] = CapitalFlowRef(source=source or None, bucket="failed", path=None)
            continue
        try:
            score = float(score_text) if score_text else None
        except ValueError:
            score = None
        refs[symbol.zfill(6)] = CapitalFlowRef(
            score=score,
            rating=rating or None,
            source=source or None,
            bucket=bucket or None,
            path=Path(report) if report else None,
        )
    return refs


def load_latest_capital_flow_map(meta_dir: Path, target_symbols: set[str] | None = None) -> tuple[dict[str, CapitalFlowRef], Path | None]:
    candidates = sorted(meta_dir.glob("group_a_share_capital_flow_overview_*.txt"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        refs: dict[str, CapitalFlowRef] = {}
        symbols = target_symbols or set()
        for symbol in symbols:
            for json_path in (meta_dir / symbol / "fund.json", REPORTS_DIR / symbol / "fund.json"):
                if not json_path.exists():
                    continue
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                summary = payload.get("summary", {})
                refs[symbol] = CapitalFlowRef(
                    score=summary.get("score"),
                    rating=summary.get("rating"),
                    source=summary.get("source"),
                    bucket=summary.get("bucket"),
                    path=json_path,
                )
                break
        return refs, None

    best_refs: dict[str, CapitalFlowRef] = {}
    best_path: Path | None = None
    best_coverage = -1
    for path in candidates:
        refs = _parse_capital_flow_overview(path)
        if target_symbols:
            coverage = len(target_symbols.intersection(refs.keys()))
            if coverage > best_coverage:
                best_refs = refs
                best_path = path
                best_coverage = coverage
            if coverage == len(target_symbols):
                return refs, path
        else:
            return refs, path
    return best_refs, best_path


def _is_technical_positive(conclusion: str | None) -> bool:
    return bool(conclusion and any(keyword in conclusion for keyword in ("偏多", "偏强", "持有为主", "允许轻仓试错")))


def _is_technical_negative(conclusion: str | None) -> bool:
    return bool(conclusion and any(keyword in conclusion for keyword in ("偏空", "偏弱", "减仓", "兑现")))


def _classify_fundamental(fundamental: FundamentalBriefRef) -> str:
    if fundamental.rating in {"A", "B"} or (fundamental.score is not None and fundamental.score >= 65):
        return "support"
    if fundamental.rating == "D" or (fundamental.score is not None and fundamental.score < 50):
        return "weak"
    return "neutral"


def _classify_technical(technical: TechnicalRef) -> str:
    if _is_technical_positive(technical.conclusion):
        return "support"
    if _is_technical_negative(technical.conclusion):
        return "weak"
    return "neutral"


def _classify_capital_flow(capital_flow: CapitalFlowRef) -> str:
    if capital_flow.bucket in {"strong", "watch"} or (capital_flow.score is not None and capital_flow.score >= 65):
        return "support"
    if capital_flow.bucket == "weak" or (capital_flow.score is not None and capital_flow.score < 50):
        return "weak"
    return "neutral"


def _join_comment(prefix: str, reasons: list[str]) -> str:
    return prefix + "：" + "；".join(reasons)


def _build_combined_view(fundamental: FundamentalBriefRef, technical: TechnicalRef, capital_flow: CapitalFlowRef) -> tuple[str, str]:
    weak_reasons: list[str] = []
    support_reasons: list[str] = []

    fundamental_signal = _classify_fundamental(fundamental)
    technical_signal = _classify_technical(technical)
    capital_signal = _classify_capital_flow(capital_flow)

    if fundamental_signal == "support":
        support_reasons.append("基本面质量较好")
    elif fundamental_signal == "weak":
        weak_reasons.append("基本面偏弱")

    if technical_signal == "support":
        support_reasons.append("60M 技术节奏偏积极")
    elif technical_signal == "weak":
        weak_reasons.append("60M 技术节奏偏弱")

    if capital_signal == "support":
        support_reasons.append("资金面有一定确认")
    elif capital_signal == "weak":
        weak_reasons.append("资金面偏弱")

    weak_count = sum(signal == "weak" for signal in (fundamental_signal, technical_signal, capital_signal))
    support_count = sum(signal == "support" for signal in (fundamental_signal, technical_signal, capital_signal))
    technical_and_capital_risk = technical_signal == "weak" and capital_signal == "weak"

    if weak_count >= 2 or technical_and_capital_risk:
        return "cautious", _join_comment("谨慎", weak_reasons)
    if fundamental_signal == "support" and technical_signal == "support" and capital_signal == "neutral":
        return "confirming", _join_comment("可跟踪试仓", support_reasons + ["资金面尚未强确认"])
    if support_count >= 2 and not weak_reasons:
        return "confirming", _join_comment("确认度较高", support_reasons)
    if weak_reasons and support_reasons:
        return "mixed", _join_comment("分化", support_reasons + weak_reasons)
    if support_reasons:
        return "watch", _join_comment("观察", support_reasons)
    if weak_reasons:
        return "cautious", _join_comment("谨慎", weak_reasons)
    return "neutral", "中性：三轴暂无明确共振"


def _management_priority(row: CombinedOverviewRow) -> int:
    bucket_order = {
        "confirming": 1,
        "watch": 2,
        "mixed": 3,
        "neutral": 4,
        "cautious": 5,
    }
    return bucket_order.get(row.combined_bucket, 4)


def _action_label(row: CombinedOverviewRow) -> str:
    if row.combined_bucket == "confirming":
        if row.combined_comment.startswith("可跟踪试仓"):
            return "跟踪试仓"
        return "优先跟踪"
    if row.combined_bucket == "watch":
        return "等待触发"
    if row.combined_bucket == "mixed":
        return "等待冲突缓解"
    if row.combined_bucket == "cautious":
        return "暂停加仓"
    return "补齐数据"


def _management_sort_key(row: CombinedOverviewRow) -> tuple[int, str]:
    return _management_priority(row), row.target.symbol


def _management_section(row: CombinedOverviewRow) -> str:
    priority = _management_priority(row)
    if priority == 1:
        return "今日动作"
    if priority == 5:
        return "风险池"
    return "观察池"


def _render_management_row(row: CombinedOverviewRow) -> str:
    fundamental_text = _compact_score(row.fundamental.score, row.fundamental.rating)
    technical_text = row.technical.conclusion or "missing"
    capital_text = _compact_score(row.capital_flow.score, row.capital_flow.rating)
    if row.capital_flow.source:
        capital_text += f"/{row.capital_flow.source}"
    return (
        "| "
        + " | ".join(
            [
                f"P{_management_priority(row)}",
                _action_label(row),
                row.target.symbol,
                row.target.name,
                row.combined_bucket,
                fundamental_text,
                technical_text.replace("|", "/"),
                capital_text.replace("|", "/"),
                row.combined_comment.replace("|", "/"),
            ]
        )
        + " |"
    )


def _append_management_section(lines: list[str], title: str, rows: list[CombinedOverviewRow]) -> None:
    lines.extend(["", f"### {title}", ""])
    if not rows:
        lines.append("- 暂无")
        return
    lines.extend(
        [
            "| priority | action | symbol | name | bucket | fundamental | technical | capital_flow | comment |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(_render_management_row(row))


def build_rows(targets: list[CombinedTarget], meta_dir: Path) -> tuple[list[CombinedOverviewRow], Path | None, Path | None]:
    technical_map, technical_summary_path = load_latest_technical_map(meta_dir)
    capital_map, capital_summary_path = load_latest_capital_flow_map(meta_dir, {target.symbol for target in targets})
    rows: list[CombinedOverviewRow] = []
    for target in targets:
        fundamental = load_fundamental_ref(target, meta_dir)
        technical = technical_map.get(target.symbol, TechnicalRef())
        capital_flow = capital_map.get(target.symbol, CapitalFlowRef())
        bucket, comment = _build_combined_view(fundamental, technical, capital_flow)
        rows.append(
            CombinedOverviewRow(
                target=target,
                fundamental=fundamental,
                technical=technical,
                capital_flow=capital_flow,
                combined_bucket=bucket,
                combined_comment=comment,
            )
        )
    return rows, technical_summary_path, capital_summary_path


def render_combined_overview(rows: list[CombinedOverviewRow], technical_summary_path: Path | None, capital_summary_path: Path | None) -> str:
    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket_counts[row.combined_bucket] = bucket_counts.get(row.combined_bucket, 0) + 1

    sorted_rows = sorted(rows, key=_management_sort_key)
    section_order = ["今日动作", "观察池", "风险池"]
    section_rows = {title: [row for row in sorted_rows if _management_section(row) == title] for title in section_order}

    lines = [
        "# A股持仓三轴综合概览",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Total: {len(rows)}",
        "技术面来源: " + (str(technical_summary_path) if technical_summary_path else "missing"),
        "资金面来源: " + (str(capital_summary_path) if capital_summary_path else "missing"),
        "分组分布: " + ", ".join(f"{key}={value}" for key, value in sorted(bucket_counts.items())),
        "清单分布: " + ", ".join(f"{title}={len(section_rows[title])}" for title in section_order),
        "",
        "## 持仓管理清单",
    ]
    for title in section_order:
        _append_management_section(lines, title, section_rows[title])

    lines.extend(["", "## 逐只动作提示", ""])
    for row in sorted_rows:
        suggestion = row.technical.suggestion or "等待技术面、基本面和资金面数据进一步补齐。"
        lines.append(f"- P{_management_priority(row)} {_action_label(row)} | {row.target.symbol} {row.target.name}: {row.combined_comment}；技术面建议：{suggestion}")

    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "- fundamental 优先读取 reports/<symbol>/base.json，缺失时回退到旧版基本面简报文本。",
            "- technical 优先读取 reports/<symbol>/60m/tech.json；存在组合摘要时仍复用最新 group888 60M 缠论综合操作建议。",
            "- capital_flow 读取最新 A 股资金面批量概览；若为 fallback 来源，已在资金面评分中保守折减。",
            "- 若单股批量概览暂缺，则回退读取 reports/<symbol>/fund.json。",
            "- priority/action 是三轴对照后的管理标签，只用于观察清单排序；今日动作/观察池/风险池按 priority 派生。",
            "- 本报告用于三轴对照，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def _compact_score(score: float | None, rating: str | None) -> str:
    if score is None and not rating:
        return "missing"
    if score is None:
        return rating or "missing"
    if not rating:
        return f"{score:.1f}"
    return f"{score:.1f}/{rating}"


def save_combined_overview(text: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = "group_a_share_combined_overview_"
    path = output_dir / f"{file_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path.write_text(text, encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=path)
    return path


def main() -> None:
    args = parse_args()
    targets = discover_targets_from_holdings_file(Path(args.holdings_file))
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        raise RuntimeError(f"No valid A-share holdings found in: {args.holdings_file}")

    rows, technical_summary_path, capital_summary_path = build_rows(targets, Path(args.meta_dir))
    output_text = render_combined_overview(rows, technical_summary_path, capital_summary_path)
    output_path = save_combined_overview(output_text, Path(args.output_dir))
    print(output_path)


if __name__ == "__main__":
    main()