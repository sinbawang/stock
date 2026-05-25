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


DEFAULT_HOLDINGS_FILE = ROOT / "data" / "_meta" / "current_h_share_holdings.json"
DEFAULT_META_DIR = ROOT / "data" / "_meta"


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
    source: str | None = "HK pending"
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
    parser = argparse.ArgumentParser(description="Generate a combined H-share overview from technical, fundamental, and HK capital-flow reports.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="H-share holdings JSON file")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Directory containing generated report text files")
    parser.add_argument("--output-dir", default=str(DEFAULT_META_DIR), help="Directory for the combined overview output")
    parser.add_argument("--limit", type=int, default=None, help="Optional target count limit")
    return parser.parse_args()


def _normalize_hk_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.startswith("HK"):
        text = text[2:]
    if text.endswith(".HK"):
        text = text[:-3]
    text = text.strip(".")
    return text.zfill(5)


def discover_targets_from_holdings_file(holdings_file: Path) -> list[CombinedTarget]:
    payload = json.loads(holdings_file.read_text(encoding="utf-8"))
    entries = payload.get("holdings", [])
    if isinstance(payload.get("markets"), dict):
        entries = payload["markets"].get("HK", [])

    targets: list[CombinedTarget] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        symbol = _normalize_hk_symbol(str(entry.get("symbol") or ""))
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
    path = latest_file(meta_dir, f"{target.symbol}_{target.name}*_fundamental_brief_*.txt")
    if path is None:
        return FundamentalBriefRef()
    text = path.read_text(encoding="utf-8")
    score = _extract_float(text, r"^- 总分:\s*([0-9.]+)")
    if score is None:
        score = _extract_float(text, r"总分:\s*([0-9.]+)")
    rating = _extract_text(text, r"^- 评级:\s*([A-D])")
    if rating is None:
        rating = _extract_text(text, r"评级:\s*([A-D])")
    return FundamentalBriefRef(
        score=score,
        rating=rating,
        submodel=_extract_text(text, r"^- 子模型:\s*([^\n]+)"),
        path=path,
    )


def load_latest_technical_map(meta_dir: Path) -> tuple[dict[str, TechnicalRef], Path | None]:
    path = latest_file(meta_dir, "group888_60m_operation_summary_*.txt")
    if path is None:
        return {}, None
    refs: dict[str, TechnicalRef] = {}
    line_re = re.compile(r"^-\s*(?P<name>.+?)\((?P<symbol>\d{5,6})\)：(?P<conclusion>.*?)\s+建议：(?P<suggestion>.*)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = line_re.match(line.strip())
        if not match:
            continue
        symbol = match.group("symbol")
        if len(symbol) == 5:
            refs[symbol] = TechnicalRef(
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
            refs[_normalize_hk_symbol(symbol)] = CapitalFlowRef(source=source or None, bucket="failed", path=None)
            continue
        try:
            score = float(score_text) if score_text else None
        except ValueError:
            score = None
        refs[_normalize_hk_symbol(symbol)] = CapitalFlowRef(
            score=score,
            rating=rating or None,
            source=source or None,
            bucket=bucket or None,
            path=Path(report) if report else None,
        )
    return refs


def load_latest_capital_flow_map(meta_dir: Path, target_symbols: set[str] | None = None) -> tuple[dict[str, CapitalFlowRef], Path | None]:
    candidates = sorted(meta_dir.glob("group_h_share_capital_flow_overview_*.txt"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return {}, None
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
    if capital_flow.bucket == "failed":
        return "failed"
    if capital_flow.bucket in {"strong", "watch"} or capital_flow.rating in {"A", "B"} or (capital_flow.score is not None and capital_flow.score >= 65):
        return "support"
    if capital_flow.bucket == "weak" or capital_flow.rating == "D" or (capital_flow.score is not None and capital_flow.score < 50):
        return "weak"
    if capital_flow.bucket == "neutral" or capital_flow.rating == "C" or capital_flow.score is not None:
        return "neutral"
    return "missing"


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
        support_reasons.append("资金面出现正向确认")
        capital_note = "资金面出现净流入/净买入配合"
    elif capital_signal == "weak":
        weak_reasons.append("资金面偏弱")
        capital_note = "资金面出现净流出或空头压力，拖累确认度"
    elif capital_signal == "neutral":
        capital_note = "资金面已有覆盖，但尚未形成强确认"
    elif capital_signal == "failed":
        capital_note = "港股资金面抓取失败，暂按缺口处理"
    else:
        capital_note = "港股完整资金流尚未确认"

    if fundamental_signal == "support" and technical_signal == "support":
        if capital_signal == "support":
            return "confirming", _join_comment("确认度较高", support_reasons + [capital_note])
        if capital_signal == "weak":
            return "cautious", _join_comment("谨慎", support_reasons + weak_reasons + [capital_note])
        if capital_signal in {"neutral", "failed"}:
            return "mixed", _join_comment("分化", support_reasons + [capital_note])
        return "confirming", _join_comment("可跟踪试仓", support_reasons + [capital_note])
    if weak_reasons and support_reasons:
        return "mixed", _join_comment("分化", support_reasons + weak_reasons + [capital_note])
    if weak_reasons:
        return "cautious", _join_comment("谨慎", weak_reasons + [capital_note])
    if support_reasons:
        return "watch", _join_comment("观察", support_reasons + [capital_note])
    return "neutral", f"中性：基本面和技术面暂无明确共振；{capital_note}"


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
        return "跟踪试仓"
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


def _compact_score(score: float | None, rating: str | None) -> str:
    if score is None and not rating:
        return "missing"
    if score is None:
        return rating or "missing"
    if not rating:
        return f"{score:.1f}"
    return f"{score:.1f}/{rating}"


def _compact_capital_flow(capital_flow: CapitalFlowRef) -> str:
    if capital_flow.bucket == "failed":
        return "failed" + (f"/{capital_flow.source}" if capital_flow.source else "")
    text = _compact_score(capital_flow.score, capital_flow.rating)
    if capital_flow.source:
        text += f"/{capital_flow.source}"
    return text


def _render_management_row(row: CombinedOverviewRow) -> str:
    return (
        "| "
        + " | ".join(
            [
                f"P{_management_priority(row)}",
                _action_label(row),
                row.target.symbol,
                row.target.name,
                row.combined_bucket,
                _compact_score(row.fundamental.score, row.fundamental.rating),
                (row.technical.conclusion or "missing").replace("|", "/"),
                _compact_capital_flow(row.capital_flow).replace("|", "/"),
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


def render_combined_overview(rows: list[CombinedOverviewRow], technical_summary_path: Path | None, capital_summary_path: Path | None = None) -> str:
    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket_counts[row.combined_bucket] = bucket_counts.get(row.combined_bucket, 0) + 1

    sorted_rows = sorted(rows, key=_management_sort_key)
    section_order = ["今日动作", "观察池", "风险池"]
    section_rows = {title: [row for row in sorted_rows if _management_section(row) == title] for title in section_order}

    lines = [
        "# 港股持仓三轴综合概览",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Total: {len(rows)}",
        "技术面来源: " + (str(technical_summary_path) if technical_summary_path else "missing"),
        "资金面来源: " + (str(capital_summary_path) if capital_summary_path else "missing/HK pending"),
        "分组分布: " + ", ".join(f"{key}={value}" for key, value in sorted(bucket_counts.items())),
        "清单分布: " + ", ".join(f"{title}={len(section_rows[title])}" for title in section_order),
        "",
        "## 持仓管理清单",
    ]
    for title in section_order:
        _append_management_section(lines, title, section_rows[title])

    lines.extend(["", "## 逐只动作提示", ""])
    for row in sorted_rows:
        suggestion = row.technical.suggestion or "等待技术面、基本面和港股资金面数据进一步补齐。"
        lines.append(f"- P{_management_priority(row)} {_action_label(row)} | {row.target.symbol} {row.target.name}: {row.combined_comment}；技术面建议：{suggestion}")

    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "- fundamental 读取最新基本面简报中的总分/评级。",
            "- technical 读取最新 group888 60M 缠论综合操作建议中的港股行。",
            "- capital_flow 优先读取最新港股资金面批量概览；HK V1 使用港股通成份行情成交额/换手率、个股南向净买额、南向持股变化和 HKEX 沽空成交额。",
            "- 个股南向净买额来自东方财富港股通个股成交榜历史，仅在个股进入成交榜的交易日可用；沽空比例依赖成交额可用性。",
            "- priority/action 是三轴对照后的管理标签；当前港股资金分会直接影响 confirming/mixed/cautious 分组。",
            "- 本报告用于三轴对照，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def save_combined_overview(text: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = "group_h_share_combined_overview_"
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
        raise RuntimeError(f"No valid H-share holdings found in: {args.holdings_file}")

    rows, technical_summary_path, capital_summary_path = build_rows(targets, Path(args.meta_dir))
    output_text = render_combined_overview(rows, technical_summary_path, capital_summary_path)
    output_path = save_combined_overview(output_text, Path(args.output_dir))
    print(output_path)


if __name__ == "__main__":
    main()