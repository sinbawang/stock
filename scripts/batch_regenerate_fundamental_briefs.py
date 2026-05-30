from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
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
from fundamental.services import fetch_and_analyze_cn_blended_fundamentals, fetch_and_analyze_cn_snapshot, fetch_and_analyze_hk_snapshot


BRIEF_FILE_RE = re.compile(
    r"^(?P<symbol>\d{5,6})_"
    r"(?P<name>.+?)"
    r"(?:_(?P<submodel>[a-z0-9]+(?:_[a-z0-9]+)*_v\d+))?"
    r"_fundamental_brief_\d{8}_\d{6}\.txt$"
)


@dataclass(frozen=True)
class BriefTarget:
    symbol: str
    name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch regenerate historical fundamental briefs into the current format.")
    parser.add_argument("--meta-dir", default=str(ROOT / "data" / "_meta"), help="Directory containing historical brief files")
    parser.add_argument(
        "--holdings-file",
        default=None,
        help="Optional JSON holdings file such as data/stock_holdings.json; when provided, targets are loaded from it instead of historical brief files.",
    )
    parser.add_argument(
        "--manual-supplement-dir",
        default=str(ROOT / "data" / "_meta" / "manual_supplements"),
        help="Directory containing manual supplement templates",
    )
    parser.add_argument("--output-dir", default=None, help="Output directory, defaults to meta dir")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for regeneration count")
    parser.add_argument(
        "--save-scorecard-text",
        action="store_true",
        help="Also save a pure text scorecard report for each regenerated target",
    )
    parser.add_argument(
        "--scorecard-output-dir",
        default=None,
        help="Optional scorecard text output directory, defaults to --output-dir or --meta-dir",
    )
    parser.add_argument(
        "--blended-cn",
        action="store_true",
        help="For CN targets only, regenerate blended annual/interim reports",
    )
    return parser.parse_args()


def infer_market(symbol: str) -> str:
    return "HK" if len(symbol) == 5 else "CN"


def discover_targets(meta_dir: Path) -> list[BriefTarget]:
    dedup: dict[str, BriefTarget] = {}
    for path in sorted(meta_dir.glob("*_fundamental_brief_*.txt")):
        match = BRIEF_FILE_RE.match(path.name)
        if not match:
            continue
        symbol = match.group("symbol")
        name = match.group("name")
        dedup[f"{symbol}:{name}"] = BriefTarget(symbol=symbol, name=name)
    return list(dedup.values())


def discover_targets_from_holdings_file(holdings_file: Path) -> list[BriefTarget]:
    payload = json.loads(holdings_file.read_text(encoding="utf-8"))

    if isinstance(payload.get("markets"), dict):
        raw_entries = [
            entry
            for market_holdings in payload["markets"].values()
            if isinstance(market_holdings, list)
            for entry in market_holdings
        ]
    else:
        raw_entries = payload.get("holdings", [])

    dedup: dict[str, BriefTarget] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        symbol = entry.get("symbol")
        name = entry.get("name")
        if not symbol or not name:
            continue
        dedup[f"{symbol}:{name}"] = BriefTarget(symbol=str(symbol), name=str(name))
    return list(dedup.values())


def find_manual_supplement_path(symbol: str, supplement_dir: Path) -> str | None:
    candidates = sorted(supplement_dir.glob(f"{symbol}_*.*"))
    if not candidates:
        return None
    return str(candidates[0])


def regenerate_one(
    target: BriefTarget,
    output_dir: Path,
    supplement_dir: Path,
    save_scorecard: bool = False,
    scorecard_output_dir: Path | None = None,
    blended_cn: bool = False,
) -> list[Path]:
    market = infer_market(target.symbol)
    manual_supplement_path = find_manual_supplement_path(target.symbol, supplement_dir)

    if market == "HK":
        result = fetch_and_analyze_hk_snapshot(
            target.symbol,
            name=target.name,
            quote_overlay_source="xueqiu",
            manual_supplement_path=manual_supplement_path,
        )
    elif blended_cn:
        result = fetch_and_analyze_cn_blended_fundamentals(
            target.symbol,
            name=target.name,
            manual_supplement_path=manual_supplement_path,
        )
    else:
        result = fetch_and_analyze_cn_snapshot(
            target.symbol,
            name=target.name,
            manual_supplement_path=manual_supplement_path,
        )

    if blended_cn and market == "CN":
        generated_paths = [
            save_blended_fundamental_brief(
                blended=result.blended,
                output_dir=output_dir,
            )
        ]
    else:
        generated_paths = [
            save_fundamental_brief(
                scorecard=result.scorecard,
                snapshot=result.fetched.snapshot,
                field_sources=result.fetched.field_sources,
                output_dir=output_dir,
            )
        ]

    if save_scorecard:
        if blended_cn and market == "CN":
            generated_paths.append(
                save_blended_scorecard_text(
                    blended=result.blended,
                    output_dir=scorecard_output_dir or output_dir,
                )
            )
        else:
            generated_paths.append(
                save_scorecard_text(
                    scorecard=result.scorecard,
                    snapshot=result.fetched.snapshot,
                    output_dir=scorecard_output_dir or output_dir,
                )
            )

    return generated_paths


def main() -> None:
    args = parse_args()
    meta_dir = Path(args.meta_dir)
    output_dir = Path(args.output_dir) if args.output_dir else meta_dir
    scorecard_output_dir = Path(args.scorecard_output_dir) if args.scorecard_output_dir else output_dir
    supplement_dir = Path(args.manual_supplement_dir)

    targets = (
        discover_targets_from_holdings_file(Path(args.holdings_file))
        if args.holdings_file
        else discover_targets(meta_dir)
    )
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        if args.holdings_file:
            raise RuntimeError(f"No valid holdings targets found in: {args.holdings_file}")
        raise RuntimeError(f"No historical brief targets found under: {meta_dir}")

    generated_paths: list[Path] = []
    for target in targets:
        generated_paths.extend(
            regenerate_one(
                target,
                output_dir,
                supplement_dir,
                save_scorecard=args.save_scorecard_text,
                scorecard_output_dir=scorecard_output_dir,
                blended_cn=args.blended_cn,
            )
        )

    for path in generated_paths:
        print(path)


if __name__ == "__main__":
    main()