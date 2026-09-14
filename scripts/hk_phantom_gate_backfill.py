"""港股分钟线幽灵价闸门：历史回填 / 审计脚本。

用法示例：
    # 干跑（只出报告，不改文件）
    python scripts/hk_phantom_gate_backfill.py

    # 真正修复两个仓库里的全部港股
    python scripts/hk_phantom_gate_backfill.py --apply

    # 只处理指定标的
    python scripts/hk_phantom_gate_backfill.py --symbols 03690,09988,00175 --apply

幂等：修复后重复运行不会产生新的修复事件。按 1m → 5m → 30m 顺序处理，
5m/30m 会用修复后的 1m 成分重聚合得到真实极值。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.hk_phantom_gate import (  # noqa: E402
    DEFAULT_MIN_REPAIR_PCT,
    GATE_TIMEFRAMES,
    run_hk_phantom_gate,
)
from chanlun.data.local_bar_store import load_local_rows, upsert_local_rows  # noqa: E402
from storage_layout import KLINE_CACHE_DIR  # noqa: E402

DEFAULT_STORES = [KLINE_CACHE_DIR, ROOT / "data" / "stock-kline-cache"]


def _list_hk_symbols(store: Path, timeframes: tuple[str, ...]) -> list[str]:
    hk = store / "HK"
    if not hk.is_dir():
        return []
    symbols: set[str] = set()
    for sym_dir in sorted(hk.iterdir()):
        if not sym_dir.is_dir():
            continue
        if any((sym_dir / f"{tf}.csv").exists() for tf in timeframes):
            symbols.add(sym_dir.name)
    return sorted(symbols)


def main() -> None:
    parser = argparse.ArgumentParser(description="港股分钟线幽灵价闸门（历史回填/审计）")
    parser.add_argument("--store-root", action="append", default=None,
                        help="仓库根目录，可重复；默认 pipeline + stock-kline-cache 两个")
    parser.add_argument("--symbols", default=None, help="逗号分隔的港股代码；默认扫描全部")
    parser.add_argument("--timeframes", nargs="+", choices=GATE_TIMEFRAMES, default=list(GATE_TIMEFRAMES))
    parser.add_argument("--min-repair-pct", type=float, default=DEFAULT_MIN_REPAIR_PCT)
    parser.add_argument("--apply", action="store_true", help="写回修复结果（默认干跑）")
    parser.add_argument("--audit", default=str(ROOT / "build" / "hk_phantom_gate_audit.json"))
    args = parser.parse_args()

    stores = [Path(p) for p in (args.store_root or DEFAULT_STORES)]
    timeframes = tuple(args.timeframes)
    symbols_filter = (
        {item.strip() for item in args.symbols.split(",") if item.strip()}
        if args.symbols
        else None
    )

    items: list[dict] = []
    per_symbol: dict[str, int] = {}
    total_repaired_rows = 0
    total_soft = 0

    for store in stores:
        if not store.is_dir():
            print(f"[skip] 仓库不存在: {store}")
            continue
        symbols = _list_hk_symbols(store, timeframes)
        if symbols_filter is not None:
            symbols = [s for s in symbols if s in symbols_filter]
        print(f"== {store} 标的 {len(symbols)} ==")
        for symbol in symbols:
            for timeframe in timeframes:
                rows = load_local_rows(symbol, "HK", timeframe, root=store)
                if not rows:
                    continue
                gated, summary = run_hk_phantom_gate(
                    symbol,
                    timeframe,
                    rows,
                    store_root=store,
                    min_repair_pct=args.min_repair_pct,
                )
                repaired = int(summary.get("repaired") or 0)
                soft = int(summary.get("soft") or 0)
                if not repaired:
                    total_soft += soft
                    continue
                changed_events = list(summary.get("events") or [])
                for event in changed_events:
                    event = dict(event)
                    event["store"] = str(store)
                    items.append(event)
                total_repaired_rows += repaired
                total_soft += soft
                per_symbol[symbol] = per_symbol.get(symbol, 0) + repaired
                if args.apply:
                    upsert_local_rows(symbol, "HK", timeframe, gated, root=store)
                flag = "APPLY" if args.apply else "DRY"
                print(f"  [{flag}] {symbol} {timeframe}: 修复 {repaired} 处（soft {soft}）")

    audit = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "apply": bool(args.apply),
        "min_repair_pct": args.min_repair_pct,
        "stores": [str(store) for store in stores],
        "timeframes": list(timeframes),
        "summary": {
            "repaired_fields": total_repaired_rows,
            "soft_fields": total_soft,
            "symbols_with_repairs": len(per_symbol),
            "per_symbol": dict(sorted(per_symbol.items(), key=lambda kv: kv[1], reverse=True)),
        },
        "items": items,
    }
    audit_path = Path(args.audit)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"修复字段总数: {total_repaired_rows}（soft {total_soft}）")
    print(f"涉及标的: {len(per_symbol)}")
    print(f"审计文件: {audit_path}")


if __name__ == "__main__":
    main()
