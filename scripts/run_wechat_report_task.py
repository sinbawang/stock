from __future__ import annotations

import argparse
from datetime import datetime
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fundamental.reporting import save_blended_fundamental_brief, save_fundamental_brief
from fundamental.services import (
    fetch_and_analyze_cn_blended_fundamentals,
    fetch_and_analyze_cn_snapshot,
    fetch_and_analyze_hk_blended_fundamentals,
    fetch_and_analyze_hk_snapshot,
)
from chanlun.default_ranges import default_structure_start
from send_wechat_current_chat_text import send_current_chat_text_file
from storage_layout import REPORTS_META_DIR


DEFAULT_MANUAL_SUPPLEMENT_DIR = ROOT / "data" / "_meta" / "manual_supplements"
AUDIT_OUTPUT_DIR = REPORTS_META_DIR


def _infer_market(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.startswith(("SH", "SZ", "BJ")):
        return "CN"
    if normalized.isdigit() and len(normalized) == 5:
        return "HK"
    return "CN"


def _resolve_manual_supplement_path(symbol: str, explicit_path: str | None) -> str | None:
    if explicit_path:
        return explicit_path
    candidates = sorted(DEFAULT_MANUAL_SUPPLEMENT_DIR.glob(f"{symbol}_*.*"))
    if not candidates:
        return None
    return str(candidates[0])


def _format_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_value(item) for item in value)
    return str(value)


def _write_task_manifest(
    *,
    task: str,
    args: argparse.Namespace,
    status: str,
    generated_paths: list[Path] | None = None,
    sent_paths: list[Path] | None = None,
    command: list[str] | None = None,
    stdout_text: str | None = None,
    error_text: str | None = None,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = AUDIT_OUTPUT_DIR / f"wechat_task_manifest_{task}_{stamp}.txt"
    arg_lines: list[str] = []
    for key, value in sorted(vars(args).items()):
        if key == "task":
            continue
        if value is None or value == []:
            continue
        arg_lines.append(f"- {key}: {_format_value(value)}")

    lines = [
        "WeChat Task Manifest",
        "",
        f"time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"task: {task}",
        f"status: {status}",
        "",
        "arguments:",
        *(arg_lines or ["- none"]),
    ]
    if command:
        lines.extend(["", "command:", f"- {' '.join(command)}"])
    if generated_paths:
        lines.extend(["", "generated_paths:", *[f"- {path}" for path in generated_paths]])
    if sent_paths:
        lines.extend(["", "sent_paths:", *[f"- {path}" for path in sent_paths]])
    if stdout_text:
        lines.extend(["", "stdout:", stdout_text.rstrip()])
    if error_text:
        lines.extend(["", "error:", error_text.rstrip()])

    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified task runner for generating and optionally sending common current-chat WeChat reports.",
    )
    subparsers = parser.add_subparsers(dest="task", required=True)

    fundamental = subparsers.add_parser("fundamental", help="Generate a fundamental brief and optionally send it to the current chat")
    fundamental.add_argument("symbol", help="Symbol such as 02208 or 601328")
    fundamental.add_argument("--name", required=True, help="Security name")
    fundamental.add_argument("--market", choices=["auto", "HK", "CN"], default="auto", help="Market routing")
    fundamental.add_argument("--submodel", default=None, help="Optional explicit submodel id")
    fundamental.add_argument("--quote-overlay-source", default=None, help="HK only optional quote overlay source")
    fundamental.add_argument("--manual-supplement-path", default=None, help="Optional JSON or brief txt supplement file")
    fundamental.add_argument("--output-dir", default=str(ROOT / "data" / "_meta"), help="Output directory")
    fundamental.add_argument("--blended-cn", action="store_true", help="Generate blended CN annual/interim brief")
    fundamental.add_argument("--blended-hk", action="store_true", help="Generate blended HK annual/interim brief")
    fundamental.add_argument("--generate-only", action="store_true", help="Only generate the report; do not send to WeChat")
    fundamental.add_argument("--disable-dedupe", action="store_true", help="Disable short-window duplicate-send protection for retries")
    fundamental.add_argument("--duplicate-send-window-seconds", type=float, default=300.0, help="Skip duplicate sends within this many seconds; set to 0 to disable")

    hk60m = subparsers.add_parser("hk60m", help="Run the HK 60M Chanlun workflow and optionally send to the current chat")
    hk60m.add_argument("--symbol", required=True, help="HK symbol such as 02208")
    hk60m.add_argument("--name", required=True, help="Security name")
    hk60m.add_argument("--start", default=default_structure_start("60m"), help="Start time")
    hk60m.add_argument("--end", default=None, help="End time")
    hk60m.add_argument("--adjust", default="", choices=["qfq", "hfq", ""], help="Adjustment mode; defaults to raw/no adjustment")
    hk60m.add_argument("--source", default="xueqiu", choices=["xueqiu", "akshare"], help="HK minute source")
    hk60m.add_argument("--fallback-source", action="append", choices=["xueqiu", "akshare"], default=None, help="Allowed fallback source; repeatable")
    hk60m.add_argument("--generate-only", action="store_true", help="Only generate the outputs; do not send to WeChat")

    cn60m = subparsers.add_parser("cn60m", help="Run the CN 60M Chanlun workflow and optionally send to the current chat")
    cn60m.add_argument("--symbol", required=True, help="CN symbol such as 300124 or sz300124")
    cn60m.add_argument("--name", required=True, help="Security name")
    cn60m.add_argument("--start", default=default_structure_start("60m"), help="Start time")
    cn60m.add_argument("--end", default=None, help="End time")
    cn60m.add_argument("--adjust", default="", choices=["qfq", "hfq", ""], help="Adjustment mode; defaults to raw/no adjustment")
    cn60m.add_argument("--generate-only", action="store_true", help="Only generate the outputs; do not send to WeChat")

    return parser


def _generate_fundamental_report(args: argparse.Namespace) -> Path:
    market = args.market if args.market != "auto" else _infer_market(args.symbol)
    manual_supplement_path = _resolve_manual_supplement_path(args.symbol, args.manual_supplement_path)
    if args.blended_cn and market != "CN":
        raise RuntimeError("--blended-cn currently supports CN only")
    if args.blended_hk and market != "HK":
        raise RuntimeError("--blended-hk currently supports HK only")
    if args.blended_cn and args.blended_hk:
        raise RuntimeError("--blended-cn and --blended-hk are mutually exclusive")

    blended_mode = args.blended_cn or args.blended_hk
    if args.blended_hk:
        result = fetch_and_analyze_hk_blended_fundamentals(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            quote_overlay_source=args.quote_overlay_source,
            manual_supplement_path=manual_supplement_path,
        )
    elif market == "HK":
        result = fetch_and_analyze_hk_snapshot(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            quote_overlay_source=args.quote_overlay_source,
            manual_supplement_path=manual_supplement_path,
        )
    elif args.blended_cn:
        result = fetch_and_analyze_cn_blended_fundamentals(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            manual_supplement_path=manual_supplement_path,
        )
    else:
        result = fetch_and_analyze_cn_snapshot(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            manual_supplement_path=manual_supplement_path,
        )

    if blended_mode:
        return save_blended_fundamental_brief(blended=result.blended, output_dir=args.output_dir)

    return save_fundamental_brief(
        scorecard=result.scorecard,
        snapshot=result.fetched.snapshot,
        field_sources=result.fetched.field_sources,
        output_dir=args.output_dir,
    )


def _run_script(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("Running:", " ".join(command))
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed


def _handle_fundamental(args: argparse.Namespace) -> None:
    output_path = _generate_fundamental_report(args)
    print(output_path)
    if args.generate_only:
        manifest_path = _write_task_manifest(
            task="fundamental",
            args=args,
            status="generated",
            generated_paths=[output_path],
        )
        print(f"Manifest: {manifest_path}")
        return
    sent_path = send_current_chat_text_file(
        output_path,
        duplicate_send_window_seconds=args.duplicate_send_window_seconds,
        disable_dedupe=args.disable_dedupe,
    )
    print(f"Sent to current chat: {sent_path}")
    manifest_path = _write_task_manifest(
        task="fundamental",
        args=args,
        status="sent",
        generated_paths=[output_path],
        sent_paths=[sent_path],
    )
    print(f"Manifest: {manifest_path}")


def _parse_generated_paths(stdout_text: str) -> list[Path]:
    prefixes = (
        "原始 CSV:",
        "标准化 CSV:",
        "结构图 SVG:",
        "完整 PNG:",
        "微信 JPG:",
        "分析文本:",
        "分钟数据源:",
    )
    generated: list[Path] = []
    for line in stdout_text.splitlines():
        if any(line.startswith(prefix) for prefix in prefixes[:-2]):
            _, value = line.split(":", 1)
            candidate = value.strip()
            if candidate:
                generated.append(Path(candidate))
    return generated


def _handle_hk60m(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        str(SCRIPTS / "run_hk_60m_chanlun_to_wechat.py"),
        "--symbol",
        args.symbol,
        "--name",
        args.name,
        "--start",
        args.start,
        "--adjust",
        args.adjust,
    ]
    if args.end:
        command.extend(["--end", args.end])
    if args.source:
        command.extend(["--source", args.source])
    for source in args.fallback_source or []:
        command.extend(["--fallback-source", source])
    if args.generate_only:
        command.append("--render-only")
    else:
        command.extend(["--contact", "current-chat", "--current-chat-only"])
    completed = _run_script(command)
    generated_paths = _parse_generated_paths(completed.stdout)
    manifest_path = _write_task_manifest(
        task="hk60m",
        args=args,
        status="generated" if args.generate_only else "sent",
        generated_paths=generated_paths,
        sent_paths=[path for path in generated_paths if path.suffix.lower() in {".jpg", ".txt"}] if not args.generate_only else None,
        command=command,
        stdout_text=completed.stdout,
    )
    print(f"Manifest: {manifest_path}")


def _handle_cn60m(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        str(SCRIPTS / "run_cn_60m_chanlun_to_wechat.py"),
        "--symbol",
        args.symbol,
        "--name",
        args.name,
        "--start",
        args.start,
        "--adjust",
        args.adjust,
    ]
    if args.end:
        command.extend(["--end", args.end])
    if args.generate_only:
        command.append("--render-only")
    else:
        command.extend(["--contact", "current-chat", "--current-chat-only"])
    completed = _run_script(command)
    generated_paths = _parse_generated_paths(completed.stdout)
    manifest_path = _write_task_manifest(
        task="cn60m",
        args=args,
        status="generated" if args.generate_only else "sent",
        generated_paths=generated_paths,
        sent_paths=[path for path in generated_paths if path.suffix.lower() in {".jpg", ".txt"}] if not args.generate_only else None,
        command=command,
        stdout_text=completed.stdout,
    )
    print(f"Manifest: {manifest_path}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.task == "fundamental":
        _handle_fundamental(args)
        return
    if args.task == "hk60m":
        _handle_hk60m(args)
        return
    if args.task == "cn60m":
        _handle_cn60m(args)
        return
    raise RuntimeError(f"unsupported task: {args.task}")


if __name__ == "__main__":
    main()