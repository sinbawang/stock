from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.reporting import save_fundamental_brief, save_scorecard_text
from fundamental.services import fetch_and_analyze_cn_snapshot, fetch_and_analyze_hk_snapshot


def _infer_market(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.startswith(("SH", "SZ", "BJ")):
        return "CN"
    if normalized.isdigit() and len(normalized) == 5:
        return "HK"
    return "CN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a fundamental brief text file under data/_meta.")
    parser.add_argument("symbol", help="Symbol such as 00700 or 601088")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--market", choices=["auto", "HK", "CN"], default="auto", help="Market routing")
    parser.add_argument("--submodel", default=None, help="Optional explicit submodel id")
    parser.add_argument("--quote-overlay-source", default=None, help="HK only optional quote overlay source")
    parser.add_argument("--manual-supplement-path", default=None, help="Optional JSON or brief txt supplement file")
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "_meta"), help="Output directory")
    parser.add_argument(
        "--save-scorecard-text",
        action="store_true",
        help="Also save a pure text scorecard report alongside the brief output",
    )
    parser.add_argument(
        "--scorecard-output-dir",
        default=None,
        help="Optional scorecard text output directory, defaults to --output-dir",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    market = args.market if args.market != "auto" else _infer_market(args.symbol)
    if market == "HK":
        result = fetch_and_analyze_hk_snapshot(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            quote_overlay_source=args.quote_overlay_source,
            manual_supplement_path=args.manual_supplement_path,
        )
    else:
        result = fetch_and_analyze_cn_snapshot(
            args.symbol,
            name=args.name,
            submodel=args.submodel,
            manual_supplement_path=args.manual_supplement_path,
        )

    output_path = save_fundamental_brief(
        scorecard=result.scorecard,
        snapshot=result.fetched.snapshot,
        field_sources=result.fetched.field_sources,
        output_dir=args.output_dir,
    )
    print(output_path)

    if args.save_scorecard_text:
        scorecard_output_path = save_scorecard_text(
            scorecard=result.scorecard,
            snapshot=result.fetched.snapshot,
            output_dir=args.scorecard_output_dir or args.output_dir,
        )
        print(scorecard_output_path)


if __name__ == "__main__":
    main()