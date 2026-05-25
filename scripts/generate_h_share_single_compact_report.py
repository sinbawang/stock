from __future__ import annotations

import argparse
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

from report_retention import prune_older_outputs

DEFAULT_META_DIR = ROOT / "data" / "_meta"
DEFAULT_BUILD_DIR = ROOT / "build" / "wechat"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact single H-share report with fundamental, capital-flow, technical, and 60M chart refs.")
    parser.add_argument("symbol", help="HK symbol such as 00700")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Directory containing generated report files")
    parser.add_argument("--output-dir", default=str(DEFAULT_META_DIR), help="Output directory for compact report")
    parser.add_argument("--refresh-chart", action="store_true", help="Try refreshing the 60M chart before rendering compact report")
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


def _find_latest_chart(symbol: str, name: str) -> Path | None:
    patterns = [
        DEFAULT_BUILD_DIR / "data" / f"{symbol}_{name}" / "60m" / "*_with_boxes_wechat.jpg",
        ROOT / "data" / f"{symbol}_{name}" / "60m" / "*_with_boxes.svg",
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
        str(SCRIPTS / "run_hk_60m_chanlun_to_wechat.py"),
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
    meta_dir: Path,
    output_dir: Path,
    chart_note: str | None = None,
) -> Path:
    fundamental_path = _latest_file(meta_dir, f"{symbol}_{name}*_fundamental_brief_*.txt")
    capital_path = _latest_file(meta_dir, f"{symbol}_{name}_capital_flow_*.txt")
    technical_path = _latest_file(meta_dir, f"{symbol}_{name}_tech_60m_*.txt")
    chart_path = _find_latest_chart(symbol, name)

    generated_at = datetime.now()
    file_prefix = f"{symbol}_{name}_single_compact_"
    output_path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"

    lines = [
        f"{name} {symbol}｜三轴操盘摘要",
        f"时间: {generated_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    _append_section(lines, "【基本面】", _compact_fundamental(_read(fundamental_path)))
    _append_section(lines, "【资金面】", _compact_capital_flow(_read(capital_path)))
    _append_section(lines, "【技术面】", _compact_technical(_read(technical_path)))
    if chart_note:
        lines.extend(["", "【提示】", f"60M图刷新失败，已复用最新已有图。原因: {chart_note}"])

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path


def main() -> None:
    args = parse_args()
    chart_note = None
    if args.refresh_chart:
        chart_note = _refresh_chart(args)
    path = generate_report(
        symbol=args.symbol.zfill(5),
        name=args.name,
        meta_dir=Path(args.meta_dir),
        output_dir=Path(args.output_dir),
        chart_note=chart_note,
    )
    print(f"compact_report= {path}")


if __name__ == "__main__":
    main()
