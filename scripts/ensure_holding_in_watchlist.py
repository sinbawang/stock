from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from storage_layout import holdings_file


VALID_MARKETS = {"CN": 6, "HK": 5}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure a symbol exists in config/stock_holdings.json.")
    parser.add_argument("symbol", help="Stock symbol, such as 000651 or 09988")
    parser.add_argument("--name", default=None, help="Stock name, required when appending a new holding")
    parser.add_argument("--market", choices=sorted(VALID_MARKETS), default=None, help="Explicit market override")
    parser.add_argument("--holdings-file", default=str(holdings_file()), help="Combined holdings JSON file")
    return parser.parse_args()


def infer_market(symbol: str, market: str | None) -> str:
    if market:
        return market
    digits = len(symbol)
    if digits <= VALID_MARKETS["HK"]:
        return "HK"
    if digits == VALID_MARKETS["CN"]:
        return "CN"
    raise RuntimeError("Cannot infer market from symbol length; pass --market CN or --market HK.")


def normalize_symbol(symbol: str, market: str) -> str:
    clean = symbol.strip()
    if not clean.isdigit():
        raise RuntimeError("Symbol must be numeric.")
    return clean.zfill(VALID_MARKETS[market])


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_existing_market(markets: dict[str, list[dict]], normalized_symbol: str) -> str | None:
    for market, entries in markets.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            candidate = str(entry.get("symbol", "")).strip()
            if candidate == normalized_symbol:
                return market
    return None


def ensure_holding(path: Path, raw_symbol: str, name: str | None, market: str | None) -> tuple[str, str, bool]:
    target_market = infer_market(raw_symbol, market)
    normalized_symbol = normalize_symbol(raw_symbol, target_market)
    payload = load_payload(path)
    markets = payload.setdefault("markets", {})
    existing_market = find_existing_market(markets, normalized_symbol)
    if existing_market:
        return existing_market, normalized_symbol, False

    clean_name = (name or "").strip()
    if not clean_name:
        raise RuntimeError("Missing --name for a new holding.")

    target_entries = markets.setdefault(target_market, [])
    if not isinstance(target_entries, list):
        raise RuntimeError(f"Holdings market bucket is not a list: {target_market}")

    target_entries.append({"symbol": normalized_symbol, "name": clean_name})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target_market, normalized_symbol, True


def main() -> None:
    args = parse_args()
    market, normalized_symbol, created = ensure_holding(
        Path(args.holdings_file),
        raw_symbol=args.symbol.strip(),
        name=args.name,
        market=args.market,
    )
    if created:
        print(f"added {market} holding {normalized_symbol}")
        return
    print(f"holding already exists {market} {normalized_symbol}")


if __name__ == "__main__":
    main()