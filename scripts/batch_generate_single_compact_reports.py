from __future__ import annotations

import argparse
import json
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

from generate_h_share_single_compact_report import generate_report
from report_retention import prune_older_outputs

DEFAULT_HOLDINGS_FILE = ROOT / "data" / "_meta" / "current_holdings.json"
DEFAULT_META_DIR = ROOT / "data" / "_meta"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch generate compact three-axis single-stock reports for all current holdings.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Directory containing source reports")
    parser.add_argument("--output-dir", default=str(DEFAULT_META_DIR), help="Output directory")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of holdings")
    return parser.parse_args()


def _load_targets(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets: list[dict[str, str]] = []
    markets = payload.get("markets", {})
    for market in ("CN", "HK"):
        for item in markets.get(market, []):
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").strip()
            name = str(item.get("name") or "").strip()
            if symbol and name:
                targets.append({"market": market, "symbol": symbol, "name": name})
    return targets


def _read_report_body(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def save_batch_compact_report(report_paths: list[Path], output_dir: Path) -> Path:
    generated_at = datetime.now()
    file_prefix = "group888_single_compact_"
    path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"
    sections = [
        "持仓三轴操盘摘要",
        f"时间: {generated_at.strftime('%Y-%m-%d %H:%M')}",
        f"数量: {len(report_paths)}",
    ]
    for index, report_path in enumerate(report_paths, start=1):
        sections.extend(["", f"===== {index}/{len(report_paths)} =====", _read_report_body(report_path)])
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=path)
    return path


def main() -> None:
    args = parse_args()
    holdings_file = Path(args.holdings_file)
    meta_dir = Path(args.meta_dir)
    output_dir = Path(args.output_dir)
    targets = _load_targets(holdings_file)
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        raise RuntimeError(f"No holdings found in {holdings_file}")

    report_paths: list[Path] = []
    for target in targets:
        report_paths.append(
            generate_report(
                symbol=target["symbol"].zfill(5) if target["market"] == "HK" else target["symbol"],
                name=target["name"],
                meta_dir=meta_dir,
                output_dir=output_dir,
            )
        )
        print(f"{target['symbol']} {target['name']} -> {report_paths[-1]}")
    summary_path = save_batch_compact_report(report_paths, output_dir)
    print(f"summary= {summary_path}")


if __name__ == "__main__":
    main()
