from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from send_wechat_current_chat_text import send_current_chat_text
from send_wechat_native import _split_message_chunks


DEFAULT_HOLDINGS_FILE = ROOT / "data" / "_meta" / "current_holdings.json"
DEFAULT_TEXT_CHUNK_CHARS = 320


@dataclass(frozen=True)
class Holding:
    market: str
    symbol: str
    name: str


@dataclass(frozen=True)
class GeneratedBundle:
    holding: Holding
    fundamental_brief: Path
    technical_report: Path
    capital_flow_report: Path
    combined_report: Path
    combined_bucket: str
    chart_svg: Path | None = None
    chart_jpg: Path | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate latest mixed reports and 60M charts for all holdings, then send the three raw briefs as text to the current WeChat chat.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--text-chunk-chars", type=int, default=DEFAULT_TEXT_CHUNK_CHARS, help="Max chars per text chunk before adding the message label")
    parser.add_argument("--limit", type=int, default=None, help="Optional max holding count for validation")
    parser.add_argument("--market", choices=["ALL", "CN", "HK"], default="ALL", help="Optional market filter")
    return parser.parse_args()


def load_holdings(path: Path, market_filter: str = "ALL") -> list[Holding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = payload.get("markets", {})
    holdings: list[Holding] = []
    for market in ("CN", "HK"):
        if market_filter != "ALL" and market != market_filter:
            continue
        for entry in markets.get(market, []):
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol") or "").strip()
            name = str(entry.get("name") or "").strip()
            if not symbol or not name:
                continue
            holdings.append(Holding(market=market, symbol=symbol, name=name))
    return holdings


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return completed.stdout


def _extract_value(stdout_text: str, prefix: str) -> str:
    for line in stdout_text.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip() if "=" in line else line.split(":", 1)[1].strip()
    raise RuntimeError(f"Missing expected output prefix: {prefix}\n{stdout_text}")


def _extract_optional_colon_value(stdout_text: str, prefix: str) -> Path | None:
    for line in stdout_text.splitlines():
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip()
            return Path(value) if value else None
    return None


def generate_bundle(holding: Holding) -> GeneratedBundle:
    if holding.market == "CN":
        mixed_stdout = _run_command(
            [
                sys.executable,
                str(SCRIPTS / "generate_a_share_single_mixed_report.py"),
                holding.symbol,
                "--name",
                holding.name,
            ]
        )
        chart_stdout = _run_command(
            [
                sys.executable,
                str(SCRIPTS / "run_cn_60m_chanlun_to_wechat.py"),
                "--symbol",
                holding.symbol,
                "--name",
                holding.name,
                "--render-only",
            ]
        )
    else:
        mixed_stdout = _run_command(
            [
                sys.executable,
                str(SCRIPTS / "generate_h_share_single_mixed_report.py"),
                holding.symbol,
                "--name",
                holding.name,
                "--source",
                "xueqiu",
                "--fallback-source",
                "akshare",
            ]
        )
        chart_stdout = _run_command(
            [
                sys.executable,
                str(SCRIPTS / "run_hk_60m_chanlun_to_wechat.py"),
                "--symbol",
                holding.symbol,
                "--name",
                holding.name,
                "--source",
                "xueqiu",
                "--fallback-source",
                "akshare",
                "--render-only",
            ]
        )

    return GeneratedBundle(
        holding=holding,
        fundamental_brief=Path(_extract_value(mixed_stdout, "fundamental_brief=")),
        technical_report=Path(_extract_value(mixed_stdout, "technical_report=")),
        capital_flow_report=Path(_extract_value(mixed_stdout, "capital_flow_report=")),
        combined_report=Path(_extract_value(mixed_stdout, "combined_report=")),
        combined_bucket=_extract_value(mixed_stdout, "combined_bucket="),
        chart_svg=_extract_optional_colon_value(chart_stdout, "结构图 SVG:"),
        chart_jpg=_extract_optional_colon_value(chart_stdout, "微信 JPG:"),
    )


def _rebalance_chunks(chunks: list[str], max_chars: int) -> list[str]:
    if not chunks:
        return []
    merged: list[str] = []
    current = chunks[0]
    for chunk in chunks[1:]:
        candidate = f"{current}\n\n{chunk}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        merged.append(current)
        current = chunk
    merged.append(current)
    return merged


def _send_labeled_text(label: str, text: str, max_chars: int) -> None:
    chunks = _rebalance_chunks(_split_message_chunks(text.strip(), max_chars=max_chars), max_chars)
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        send_current_chat_text(
            f"【{label} {index}/{total}】\n{chunk}",
            duplicate_send_window_seconds=0,
            disable_dedupe=True,
        )


def send_bundle(bundle: GeneratedBundle, max_chars: int) -> None:
    header = (
        f"【{bundle.holding.symbol} {bundle.holding.name}】最新 mixed 分组: {bundle.combined_bucket}。"
        f"60M 缠论图已生成，本次按文本发送基本面、技术面、资金面三份简报。"
    )
    send_current_chat_text(header, duplicate_send_window_seconds=0, disable_dedupe=True)
    _send_labeled_text(f"{bundle.holding.symbol} {bundle.holding.name} 基本面简报", bundle.fundamental_brief.read_text(encoding="utf-8"), max_chars)
    _send_labeled_text(f"{bundle.holding.symbol} {bundle.holding.name} 技术面简报", bundle.technical_report.read_text(encoding="utf-8"), max_chars)
    _send_labeled_text(f"{bundle.holding.symbol} {bundle.holding.name} 资金面简报", bundle.capital_flow_report.read_text(encoding="utf-8"), max_chars)


def main() -> None:
    args = parse_args()
    holdings = load_holdings(Path(args.holdings_file), market_filter=args.market)
    if args.limit is not None:
        holdings = holdings[: args.limit]
    if not holdings:
        raise RuntimeError("No holdings found for batch generation")

    print(f"holdings={len(holdings)}")
    for index, holding in enumerate(holdings, start=1):
        print(f"generating {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}", flush=True)
        bundle = generate_bundle(holding)
        print(
            f"generated {holding.symbol} bucket={bundle.combined_bucket} chart_svg={bundle.chart_svg} chart_jpg={bundle.chart_jpg}",
            flush=True,
        )
        send_bundle(bundle, max_chars=args.text_chunk_chars)
        print(f"sent {holding.symbol} {holding.name}", flush=True)


if __name__ == "__main__":
    main()