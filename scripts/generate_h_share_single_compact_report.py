from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chanlun.analysis import SIGNAL_BASIS_LABELS, build_precision_window_display, format_signal_point_label
from report_retention import prune_older_outputs
from storage_layout import REPORTS_DIR, stock_report_dir, stock_overview_report_path

DEFAULT_REPORT_ROOT = REPORTS_DIR
DEFAULT_BUILD_DIR = ROOT / "build" / "wechat"
PRIMARY_TECHNICAL_TIMEFRAME = "30m"
PRIMARY_TECHNICAL_LABEL = "30M"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact single H-share report with fundamental, capital-flow, technical, and 30M chart refs.")
    parser.add_argument("symbol", help="HK symbol such as 00700")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT), help="Canonical reports root directory")
    parser.add_argument("--output-dir", default=None, help="Optional output directory for compact report")
    parser.add_argument("--refresh-chart", action="store_true", help="Try refreshing the 30M chart before rendering compact report")
    parser.add_argument("--source", default="xueqiu", choices=["xueqiu", "akshare"], help="Primary HK minute source when refreshing chart")
    parser.add_argument("--fallback-source", action="append", choices=["xueqiu", "akshare"], default=None, help="Fallback HK minute source when refreshing chart")
    return parser.parse_args()


def _latest_file(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _read(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_text(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _extract_section_lines(text: str, title: str) -> list[str]:
    pattern = rf"^{re.escape(title)}\s*\n(?P<body>.*?)(?=\n(?:[\u4e00-\u9fffA-Za-z0-9_ /]+[:：]|##\s)|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    lines = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if line.startswith("- "):
            lines.append(line)
    return lines


def _limit_lines(lines: list[str], limit: int) -> list[str]:
    return lines[:limit]


def _strip_bullet(line: str) -> str:
    return line[2:] if line.startswith("- ") else line


def _join_short(lines: list[str], limit: int) -> str:
    return "；".join(_strip_bullet(line) for line in _limit_lines(lines, limit))


def _compact_fundamental(text: str) -> list[str]:
    if not text:
        return ["评级: missing"]
    rating = _extract_text(text, r"^- 评级:\s*([A-D])") or _extract_text(text, r"评级:\s*([A-D])") or "missing"
    score = _extract_text(text, r"^- 总分:\s*([0-9.]+)") or _extract_text(text, r"总分:\s*([0-9.]+)") or "missing"
    conclusion = _extract_text(text, r"^- 综合说明:\s*(.+)$") or _extract_text(text, r"综合说明:\s*(.+)$")
    highlights = _limit_lines(_extract_section_lines(text, "亮点:"), 3)
    missing = _limit_lines(_extract_section_lines(text, "当前缺失字段:"), 3)

    lines = [f"评级: {rating} / {score}"]
    if conclusion:
        lines.append(f"判断: {conclusion}")
    if highlights:
        lines.append("亮点: " + _join_short(highlights, 2))
    if missing:
        lines.append("跟踪: " + " / ".join(_strip_bullet(line) for line in missing))
    return lines


def _compact_capital_flow(text: str) -> list[str]:
    if not text:
        return ["评级: missing"]
    trade_date = _extract_text(text, r"^- 交易日:\s*(.+)$") or "missing"
    score = _extract_text(text, r"^- 总分:\s*([0-9.]+/100)") or "missing"
    rating = _extract_text(text, r"^- 评级:\s*([A-D])") or "missing"
    judgment = _extract_text(text, r"^综合判断:\s*\n(.+)$")
    key_metrics = _limit_lines(_extract_section_lines(text, "关键资金指标:"), 7)
    positives = _limit_lines(_extract_section_lines(text, "正向线索:"), 3)
    risks = _limit_lines(_extract_section_lines(text, "风险线索:"), 4)
    missing = _limit_lines(_extract_section_lines(text, "缺失指标:"), 4)

    lines = [f"日期: {trade_date}", f"评级: {rating} / {score}"]
    if key_metrics:
        lines.append("关键指标:")
        lines.extend(f"  {index}. {_strip_bullet(line)}" for index, line in enumerate(key_metrics, start=1))
    if positives:
        lines.append("正向: " + _join_short(positives, 2))
    if risks:
        lines.append("风险: " + _join_short(risks, 3))
    if judgment:
        lines.append(f"操盘: {judgment.strip()}")
    if missing:
        lines.append("缺口: " + " / ".join(_strip_bullet(line) for line in missing))
    return lines


def _compact_technical(text: str) -> list[str]:
    if not text:
        return ["结论: missing"]
    conclusion = _extract_text(text, r"^- 结论:\s*(.+)$") or _extract_text(text, r"^结论：\s*(.+)$") or "missing"
    suggestion = _extract_text(text, r"^- 建议:\s*(.+)$") or _extract_text(text, r"^建议：\s*(.+)$") or "missing"
    overview = _limit_lines(_extract_section_lines(text, "概览："), 4)
    structure = _limit_lines(_extract_section_lines(text, "结构："), 3)
    signals = _limit_lines(_extract_section_lines(text, "信号："), 4)
    focus = _limit_lines(_extract_section_lines(text, "观察重点："), 2)

    lines = [f"结论: {conclusion}", f"建议: {suggestion}"]
    if overview:
        lines.append("概览: " + _join_short(overview, 3))
    if structure:
        lines.append("结构: " + _join_short(structure, 3))
    if signals:
        lines.append("信号: " + _join_short(signals, 4))
    if focus:
        lines.append("重点: " + _join_short(focus, 1))
    return lines


def _append_section(lines: list[str], title: str, body: list[str]) -> None:
    lines.extend(["", title])
    lines.extend(body)


def _compact_fundamental_payload(payload: dict) -> list[str]:
    summary = payload.get("summary") or {}
    if not summary:
        return ["评级: missing"]
    lines = [f"评级: {summary.get('rating') or 'missing'} / {summary.get('score') or 'missing'}"]
    comment = summary.get("comment")
    if comment:
        lines.append(f"判断: {comment}")

    blended = payload.get("blended") or {}
    dimension_scores = (blended.get("annual_anchor") or {}).get("scorecard", {}).get("dimension_scores") or []
    if dimension_scores:
        top_dimensions = sorted(dimension_scores, key=lambda item: item.get("score", 0), reverse=True)[:2]
        highlights = [f"{item.get('dimension', 'unknown')}: {item.get('score', 'missing')}" for item in top_dimensions]
        lines.append("亮点: " + "；".join(highlights))

    missing_metrics = []
    for item in dimension_scores:
        missing_metrics.extend(item.get("missing_metrics") or [])
    if missing_metrics:
        unique_missing = []
        for metric in missing_metrics:
            if metric not in unique_missing:
                unique_missing.append(metric)
        lines.append("跟踪: " + " / ".join(unique_missing[:3]))
    return lines


def _compact_capital_flow_payload(payload: dict) -> list[str]:
    summary = payload.get("summary") or {}
    scorecard = payload.get("scorecard") or {}
    if not summary and not scorecard:
        return ["评级: missing"]
    trade_date = scorecard.get("trade_date") or "missing"
    score = summary.get("score")
    score_text = f"{score}/100" if score is not None else "missing"
    lines = [f"日期: {trade_date}", f"评级: {summary.get('rating') or scorecard.get('rating') or 'missing'} / {score_text}"]

    key_metrics = []
    snapshot = payload.get("snapshot") or {}
    metric_map = [
        ("southbound_net_buy", "南向净买入"),
        ("southbound_net_buy_5d", "5日南向净买入"),
        ("southbound_holding_change", "南向持股变化"),
        ("short_sell_ratio", "沽空比例"),
    ]
    for key, label in metric_map:
        value = snapshot.get(key)
        if value is not None:
            key_metrics.append(f"{label}: {value}")
    if key_metrics:
        lines.append("关键指标:")
        lines.extend(f"  {index}. {value}" for index, value in enumerate(key_metrics[:4], start=1))

    comment = summary.get("comment")
    if comment:
        lines.append(f"操盘: {comment}")

    missing = []
    for item in scorecard.get("dimension_scores") or []:
        missing.extend(item.get("missing_metrics") or [])
    if missing:
        unique_missing = []
        for metric in missing:
            if metric not in unique_missing:
                unique_missing.append(metric)
        lines.append("缺口: " + " / ".join(unique_missing[:4]))
    return lines


def _compact_technical_payload(payload: dict) -> list[str]:
    summary = payload.get("summary") or {}
    if not summary:
        return ["结论: missing"]
    analysis_text = payload.get("analysis_text") or ""
    precision_entry = summary.get("precision_entry") or payload.get("precision_entry") or {}
    lines = [
        f"操作级别: {summary.get('operation_level') or payload.get('timeframe') or 'missing'}",
        f"结论: {summary.get('conclusion') or 'missing'}",
        f"建议: {summary.get('suggestion') or 'missing'}",
    ]
    signal_points = summary.get("signal_catalog") or summary.get("signal_points") or []
    if signal_points:
        formatted_points = []
        for item in signal_points[:6]:
            point = format_signal_point_label(str(item.get("point") or "unknown"))
            active = item.get("active")
            time_text = item.get("time") or "missing"
            price = item.get("price")
            price_text = f"{price:.2f}" if isinstance(price, (int, float)) else "missing"
            status = "active" if active is not False else "inactive"
            basis = SIGNAL_BASIS_LABELS.get(str(item.get("basis") or "")) if active is not False else None
            detail = f" [{basis}]" if basis else ""
            formatted_points.append(f"{point}({status})@{time_text}/{price_text}{detail}")
        lines.append("买卖点: " + "；".join(formatted_points))
    overview = _limit_lines(_extract_section_lines(analysis_text, "概览："), 3)
    structure = _limit_lines(_extract_section_lines(analysis_text, "结构："), 3)
    signals = _limit_lines(_extract_section_lines(analysis_text, "信号："), 4)
    if overview:
        lines.append("概览: " + _join_short(overview, 3))
    if structure:
        lines.append("结构: " + _join_short(structure, 3))
    if signals:
        lines.append("信号: " + _join_short(signals, 4))
    if precision_entry:
        lower_level = precision_entry.get("operation_level") or precision_entry.get("timeframe") or "5M"
        note = precision_entry.get("note") or "missing"
        precision_window_display = build_precision_window_display(precision_entry)
        lines.append(f"{lower_level}区间套: {note}")
        if precision_window_display and precision_window_display.get("label"):
            lines.append(f"{lower_level}窗口: {precision_window_display['label']}")
    return lines


def _find_latest_chart(symbol: str, name: str) -> Path | None:
    patterns = [
        DEFAULT_BUILD_DIR / "data" / symbol / PRIMARY_TECHNICAL_TIMEFRAME / "structure.jpg",
        ROOT / "data" / "reports" / symbol / PRIMARY_TECHNICAL_TIMEFRAME / "structure.svg",
    ]
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(path for path in pattern.parent.glob(pattern.name) if path.exists())
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _refresh_chart(args: argparse.Namespace) -> str | None:
    command = [
        sys.executable,
        str(SCRIPTS / "run_hk_60m_chanlun_report.py"),
        "--symbol",
        args.symbol,
        "--name",
        args.name,
        "--source",
        args.source,
        "--render-only",
    ]
    for source in args.fallback_source or []:
        command.extend(["--fallback-source", source])
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or f"exit={result.returncode}").strip()


def generate_report(
    *,
    symbol: str,
    name: str,
    report_root: Path,
    output_dir: Path,
    chart_note: str | None = None,
) -> Path:
    stock_dir = report_root / symbol
    fundamental_path = stock_dir / "base.json"
    capital_path = stock_dir / "fund.json"
    technical_path = stock_dir / PRIMARY_TECHNICAL_TIMEFRAME / "tech.json"
    chart_path = _find_latest_chart(symbol, name)

    generated_at = datetime.now()
    file_prefix = f"{symbol}_{name}_single_compact_"
    output_path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"

    lines = [
        f"{name} {symbol}｜三轴操盘摘要",
        f"时间: {generated_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    _append_section(lines, "【基本面】", _compact_fundamental_payload(_read_json(fundamental_path)))
    _append_section(lines, "【资金面】", _compact_capital_flow_payload(_read_json(capital_path)))
    _append_section(lines, "【技术面】", _compact_technical_payload(_read_json(technical_path)))
    canonical_overview = stock_overview_report_path(symbol)
    if canonical_overview.exists():
        lines.extend(["", f"概览原文: {canonical_overview}"])
    if chart_path is not None:
        lines.extend([f"{PRIMARY_TECHNICAL_LABEL}图: {chart_path}"])
    if chart_note:
        lines.extend(["", "【提示】", f"{PRIMARY_TECHNICAL_LABEL}图刷新失败，已复用最新已有图。原因: {chart_note}"])

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path


def main() -> None:
    args = parse_args()
    chart_note = None
    if args.refresh_chart:
        chart_note = _refresh_chart(args)
    symbol = args.symbol.zfill(5)
    report_root = Path(args.report_root)
    output_dir = Path(args.output_dir) if args.output_dir else stock_report_dir(symbol)
    path = generate_report(
        symbol=symbol,
        name=args.name,
        report_root=report_root,
        output_dir=output_dir,
        chart_note=chart_note,
    )
    print(f"compact_report= {path}")


if __name__ == "__main__":
    main()
