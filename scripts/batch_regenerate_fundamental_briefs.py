from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.reporting import save_fundamental_brief
from fundamental.services import fetch_and_analyze_cn_snapshot, fetch_and_analyze_hk_snapshot


BRIEF_FILE_RE = re.compile(r"^(?P<symbol>\d{5,6})_(?P<name>.+?)_fundamental_brief_\d{8}_\d{6}\.txt$")


@dataclass(frozen=True)
class BriefTarget:
    symbol: str
    name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch regenerate historical fundamental briefs into the current format.")
    parser.add_argument("--meta-dir", default=str(ROOT / "data" / "_meta"), help="Directory containing historical brief files")
    parser.add_argument(
        "--manual-supplement-dir",
        default=str(ROOT / "data" / "_meta" / "manual_supplements"),
        help="Directory containing manual supplement templates",
    )
    parser.add_argument("--output-dir", default=None, help="Output directory, defaults to meta dir")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for regeneration count")
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


def find_manual_supplement_path(symbol: str, supplement_dir: Path) -> str | None:
    candidates = sorted(supplement_dir.glob(f"{symbol}_*.*"))
    if not candidates:
        return None
    return str(candidates[0])


def regenerate_one(target: BriefTarget, output_dir: Path, supplement_dir: Path) -> Path:
    market = infer_market(target.symbol)
    manual_supplement_path = find_manual_supplement_path(target.symbol, supplement_dir)

    if market == "HK":
        result = fetch_and_analyze_hk_snapshot(
            target.symbol,
            name=target.name,
            quote_overlay_source="xueqiu",
            manual_supplement_path=manual_supplement_path,
        )
    else:
        result = fetch_and_analyze_cn_snapshot(
            target.symbol,
            name=target.name,
            manual_supplement_path=manual_supplement_path,
        )

    return save_fundamental_brief(
        scorecard=result.scorecard,
        snapshot=result.fetched.snapshot,
        field_sources=result.fetched.field_sources,
        output_dir=output_dir,
    )


def main() -> None:
    args = parse_args()
    meta_dir = Path(args.meta_dir)
    output_dir = Path(args.output_dir) if args.output_dir else meta_dir
    supplement_dir = Path(args.manual_supplement_dir)

    targets = discover_targets(meta_dir)
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        raise RuntimeError(f"No historical brief targets found under: {meta_dir}")

    generated_paths: list[Path] = []
    for target in targets:
        generated_paths.append(regenerate_one(target, output_dir, supplement_dir))

    for path in generated_paths:
        print(path)


if __name__ == "__main__":
    main()