from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.reporting import (
    save_blended_fundamental_brief,
    save_blended_scorecard_text,
    save_fundamental_brief,
    save_scorecard_text,
)
from fundamental.services import (
    fetch_and_analyze_cn_blended_fundamentals,
    fetch_and_analyze_cn_snapshot,
    fetch_and_analyze_hk_blended_fundamentals,
    fetch_and_analyze_hk_snapshot,
)


DEFAULT_MANUAL_SUPPLEMENT_DIR = ROOT / "data" / "_meta" / "manual_supplements"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a fundamental brief text file. The per-stock canonical report now lives under reports/<symbol>/base.json.")
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
    parser.add_argument(
        "--blended-cn",
        action="store_true",
        help="For CN only, generate blended annual/interim brief and scorecard outputs",
    )
    parser.add_argument(
        "--blended-hk",
        action="store_true",
        help="For HK POC only, generate blended annual/interim brief and scorecard outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
        output_path = save_blended_fundamental_brief(
            blended=result.blended,
            output_dir=args.output_dir,
        )
    else:
        output_path = save_fundamental_brief(
            scorecard=result.scorecard,
            snapshot=result.fetched.snapshot,
            field_sources=result.fetched.field_sources,
            output_dir=args.output_dir,
        )
    print(output_path)

    if args.save_scorecard_text:
        if blended_mode:
            scorecard_output_path = save_blended_scorecard_text(
                blended=result.blended,
                output_dir=args.scorecard_output_dir or args.output_dir,
            )
        else:
            scorecard_output_path = save_scorecard_text(
                scorecard=result.scorecard,
                snapshot=result.fetched.snapshot,
                output_dir=args.scorecard_output_dir or args.output_dir,
            )
        print(scorecard_output_path)


if __name__ == "__main__":
    main()