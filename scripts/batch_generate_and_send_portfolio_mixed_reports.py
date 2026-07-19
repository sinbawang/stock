from __future__ import annotations

import argparse
import os
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fundamental.data import fetch_cn_available_report_periods, fetch_hk_available_report_periods
from storage_layout import holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_TEXT_CHUNK_CHARS = 320
PRIMARY_TECHNICAL_TIMEFRAME = "30m"
PRIMARY_TECHNICAL_LABEL = "30M"


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


@dataclass(frozen=True)
class ExistingBasePeriods:
    annual: date
    interim: date | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate latest mixed reports and day/30M/5M/1M charts for all holdings.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--limit", type=int, default=None, help="Optional max holding count for validation")
    parser.add_argument("--market", choices=["ALL", "CN", "HK"], default="ALL", help="Optional market filter")
    parser.add_argument(
        "--skip-gen-base",
        "--skipGenBase",
        dest="skip_gen_base",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse an existing base.json instead of regenerating the fundamental report when possible. Use --no-skip-gen-base to force refresh.",
    )
    parser.add_argument(
        "--skip-gen-fund",
        "--skipGenFund",
        dest="skip_gen_fund",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Reuse an existing fund.json instead of regenerating the capital-flow report when possible.",
    )
    parser.add_argument(
        "--pending-reverse-mode",
        choices=("any", "effective_only", "tail_mixed"),
        default="any",
        help="Forwarded to batch_prepare_chanlun_reports.py to control pending reverse fractal handling.",
    )
    parser.add_argument("--day-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for daily K-line fetch count.")
    parser.add_argument("--m60-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 60M K-line fetch count.")
    parser.add_argument("--m30-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 30M K-line fetch count.")
    parser.add_argument("--m15-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 15M K-line fetch count.")
    parser.add_argument("--m5-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 5M K-line fetch count.")
    parser.add_argument("--m1-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 1M K-line fetch count.")
    parser.add_argument("--zhongshu-level", choices=("bi", "segment"), default="bi", help="Forwarded to batch_prepare_chanlun_reports.py to switch between bi and segment zhongshu rendering.")
    parser.add_argument(
        "--tech-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=["day", "30m", "5m", "1m"],
        help="Technical levels to generate through batch_prepare_chanlun_reports.py. Defaults to day/30m/5m/1m.",
    )
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
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        print(line, end="", flush=True)
    process.stdout.close()
    returncode = process.wait()
    combined_output = "".join(output_lines)
    if returncode != 0:
        details: list[str] = [f"Command failed with exit code {returncode}: {command!r}"]
        if combined_output.strip():
            details.append("output:")
            details.append(combined_output.strip())
        raise RuntimeError("\n".join(details))
    return combined_output


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


def _single_holding_payload(holding: Holding) -> dict:
    return {
        "markets": {
            "CN": [
                {"symbol": holding.symbol, "name": holding.name}
            ] if holding.market == "CN" else [],
            "HK": [
                {"symbol": holding.symbol, "name": holding.name}
            ] if holding.market == "HK" else [],
        }
    }


def _generate_all_timeframe_charts(
    holding: Holding,
    *,
    pending_reverse_mode: str = "any",
    day_bars: int = 600,
    m60_bars: int = 600,
    m30_bars: int = 600,
    m15_bars: int = 600,
    m5_bars: int = 600,
    m1_bars: int = 600,
    zhongshu_level: str = "bi",
    tech_timeframes: tuple[str, ...] = ("day", "30m", "5m", "1m"),
) -> None:
    requested_timeframes = tuple(
        timeframe
        for timeframe in dict.fromkeys(tech_timeframes)
        if timeframe != PRIMARY_TECHNICAL_TIMEFRAME
    )
    if not requested_timeframes:
        return
    with tempfile.TemporaryDirectory(prefix="single_holding_", dir=str(ROOT / "data" / "_meta")) as temp_dir:
        holdings_path = Path(temp_dir) / "holdings.json"
        holdings_path.write_text(
            json.dumps(_single_holding_payload(holding), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _run_command(
            [
                sys.executable,
                "-u",
                str(SCRIPTS / "batch_prepare_chanlun_reports.py"),
                "--holdings-file",
                str(holdings_path),
                "--pending-reverse-mode",
                pending_reverse_mode,
                "--day-bars",
                str(day_bars),
                "--m60-bars",
                str(m60_bars),
                "--m30-bars",
                str(m30_bars),
                "--m15-bars",
                str(m15_bars),
                "--m5-bars",
                str(m5_bars),
                "--m1-bars",
                str(m1_bars),
                "--zhongshu-level",
                zhongshu_level,
                "--timeframes",
                *requested_timeframes,
            ]
        )


def _existing_base_path(holding: Holding) -> Path:
    symbol = holding.symbol.zfill(5) if holding.market == "HK" else holding.symbol
    return ROOT / "data" / "reports" / symbol / "base.json"


def _load_existing_base_periods(base_path: Path) -> ExistingBasePeriods | None:
    if not base_path.exists():
        return None
    payload = json.loads(base_path.read_text(encoding="utf-8"))
    blended = payload.get("blended") or {}
    annual_snapshot = ((blended.get("annual_anchor") or {}).get("snapshot") or {})
    interim_snapshot = ((blended.get("interim_overlay") or {}).get("snapshot") or {})
    annual_text = annual_snapshot.get("report_period")
    if not annual_text:
        return None
    annual = date.fromisoformat(str(annual_text))
    interim_text = interim_snapshot.get("report_period")
    interim = date.fromisoformat(str(interim_text)) if interim_text else None
    return ExistingBasePeriods(annual=annual, interim=interim)


def _should_reuse_existing_base(holding: Holding, skip_gen_base: bool) -> bool:
    if not skip_gen_base:
        return False

    base_path = _existing_base_path(holding)
    existing = _load_existing_base_periods(base_path)
    if existing is None:
        return False

    latest = (
        fetch_cn_available_report_periods(holding.symbol)
        if holding.market == "CN"
        else fetch_hk_available_report_periods(holding.symbol)
    )
    return existing.annual == latest.annual and existing.interim == latest.interim


def generate_bundle(
    holding: Holding,
    *,
    skip_gen_base: bool = True,
    trust_existing_base: bool = False,
    skip_gen_fund: bool = False,
    pending_reverse_mode: str = "any",
    day_bars: int = 600,
    m60_bars: int = 600,
    m30_bars: int = 600,
    m15_bars: int = 600,
    m5_bars: int = 600,
    m1_bars: int = 600,
    zhongshu_level: str = "bi",
    tech_timeframes: tuple[str, ...] = ("day", "30m", "5m", "1m"),
) -> GeneratedBundle:
    reuse_existing_base = bool(skip_gen_base and trust_existing_base) or _should_reuse_existing_base(holding, skip_gen_base)
    started_mixed = time.perf_counter()
    if holding.market == "CN":
        mixed_stdout = _run_command(
            [
                sys.executable,
                "-u",
                str(SCRIPTS / "generate_a_share_single_mixed_report.py"),
                holding.symbol,
                "--name",
                holding.name,
                f"--{'skip-gen-base' if reuse_existing_base else 'no-skip-gen-base'}",
                f"--{'skip-gen-fund' if skip_gen_fund else 'no-skip-gen-fund'}",
            ]
        )
    else:
        mixed_stdout = _run_command(
            [
                sys.executable,
                "-u",
                str(SCRIPTS / "generate_h_share_single_mixed_report.py"),
                holding.symbol,
                "--name",
                holding.name,
                "--source",
                "xueqiu",
                "--fallback-source",
                "akshare",
                f"--{'skip-gen-base' if reuse_existing_base else 'no-skip-gen-base'}",
                f"--{'skip-gen-fund' if skip_gen_fund else 'no-skip-gen-fund'}",
            ]
        )
    print(f"timing {holding.symbol} mixed seconds={time.perf_counter() - started_mixed:.2f}", flush=True)

    started_charts = time.perf_counter()
    _generate_all_timeframe_charts(
        holding,
        pending_reverse_mode=pending_reverse_mode,
        day_bars=day_bars,
        m60_bars=m60_bars,
        m30_bars=m30_bars,
        m15_bars=m15_bars,
        m5_bars=m5_bars,
        m1_bars=m1_bars,
        zhongshu_level=zhongshu_level,
        tech_timeframes=tech_timeframes,
    )
    print(f"timing {holding.symbol} extra_charts seconds={time.perf_counter() - started_charts:.2f}", flush=True)

    symbol_dir = ROOT / "data" / "reports" / (holding.symbol.zfill(5) if holding.market == "HK" else holding.symbol)
    primary_chart_dir = symbol_dir / PRIMARY_TECHNICAL_TIMEFRAME

    return GeneratedBundle(
        holding=holding,
        fundamental_brief=Path(_extract_value(mixed_stdout, "fundamental_brief=")),
        technical_report=Path(_extract_value(mixed_stdout, "technical_report=")),
        capital_flow_report=Path(_extract_value(mixed_stdout, "capital_flow_report=")),
        combined_report=Path(_extract_value(mixed_stdout, "combined_report=")),
        combined_bucket=_extract_value(mixed_stdout, "combined_bucket="),
        chart_svg=(primary_chart_dir / "structure.svg") if (primary_chart_dir / "structure.svg").exists() else None,
        chart_jpg=(primary_chart_dir / "structure.jpg") if (primary_chart_dir / "structure.jpg").exists() else None,
    )


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
        bundle = generate_bundle(
            holding,
            skip_gen_base=args.skip_gen_base,
            skip_gen_fund=args.skip_gen_fund,
            pending_reverse_mode=args.pending_reverse_mode,
            day_bars=args.day_bars,
            m60_bars=args.m60_bars,
            m30_bars=args.m30_bars,
            m15_bars=args.m15_bars,
            m5_bars=args.m5_bars,
            m1_bars=args.m1_bars,
            zhongshu_level=args.zhongshu_level,
            tech_timeframes=tuple(args.tech_timeframes),
        )
        print(
            f"generated {holding.symbol} bucket={bundle.combined_bucket} chart_svg={bundle.chart_svg} chart_jpg={bundle.chart_jpg}",
            flush=True,
        )
        print(f"prepared {holding.symbol} {holding.name}", flush=True)


if __name__ == "__main__":
    main()