from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from batch_generate_and_send_portfolio_mixed_reports import generate_bundle, load_holdings
from storage_layout import REPORTS_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
REQUIRED_TOP_LEVEL_FILES = ("base.json", "fund.json", "overview.txt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate per-holding mixed report artifacts without sending WeChat messages.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--market", choices=["ALL", "CN", "HK"], default="ALL", help="Optional market filter")
    parser.add_argument("--limit", type=int, default=None, help="Optional max holding count for validation")
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only regenerate holdings missing base.json, fund.json, or overview.txt",
    )
    return parser.parse_args()


def _report_symbol_dir(symbol: str, market: str) -> Path:
    normalized_symbol = symbol.zfill(5) if market == "HK" else symbol
    return REPORTS_DIR / normalized_symbol


def _is_missing_top_level_artifact(symbol: str, market: str) -> bool:
    symbol_dir = _report_symbol_dir(symbol, market)
    return any(not (symbol_dir / file_name).exists() for file_name in REQUIRED_TOP_LEVEL_FILES)


def main() -> None:
    args = parse_args()
    holdings = load_holdings(Path(args.holdings_file), market_filter=args.market)
    if args.limit is not None:
        holdings = holdings[: args.limit]
    if args.missing_only:
        holdings = [holding for holding in holdings if _is_missing_top_level_artifact(holding.symbol, holding.market)]
    if not holdings:
        print("no_holdings_to_regenerate")
        return

    failures: list[str] = []
    for index, holding in enumerate(holdings, start=1):
        try:
            bundle = generate_bundle(holding)
            print(
                f"ok {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name} "
                f"base={bundle.fundamental_brief} fund={bundle.capital_flow_report} overview={bundle.combined_report}",
                flush=True,
            )
        except Exception as exc:  # pragma: no cover - operational batch script
            failures.append(f"{holding.market} {holding.symbol} {holding.name}: {exc}")
            print(f"failed {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}: {exc}", flush=True)

    if failures:
        raise RuntimeError("Failed holdings:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()