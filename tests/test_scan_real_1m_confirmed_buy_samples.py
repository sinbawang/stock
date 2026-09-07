from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build" / "scan_real_1m_confirmed_buy_samples.py"

spec = importlib.util.spec_from_file_location("scan_real_1m_confirmed_buy_samples", MODULE_PATH)
assert spec is not None and spec.loader is not None
scan_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan_module
spec.loader.exec_module(scan_module)


def test_is_confirmed_buy_match_requires_confirmed_and_buy_points() -> None:
    assert scan_module._is_confirmed_buy_match({"same_level_consumption_level": "confirmed", "buy_points": ["buy3"]}) is True
    assert scan_module._is_confirmed_buy_match({"same_level_consumption_level": "pending", "buy_points": ["buy3"]}) is False
    assert scan_module._is_confirmed_buy_match({"same_level_consumption_level": "confirmed", "buy_points": []}) is False


def test_scan_symbol_collects_first_confirmed_buy_matches(monkeypatch) -> None:
    rows = [{"ts": f"2026-08-01 09:{minute:02d}:00"} for minute in range(10)]

    monkeypatch.setattr(scan_module, "_load_rows", lambda symbol, timeframe: rows)
    monkeypatch.setattr(scan_module, "_select_auto_cutoffs", lambda loaded_rows, start, end: [str(item["ts"]) for item in loaded_rows])

    def fake_replay(symbol: str, name: str, cutoff: str, replay_rows):
        return {
            "cutoff": cutoff,
            "same_level_consumption_level": "confirmed" if cutoff.endswith("05:00") or cutoff.endswith("07:00") else "pending",
            "buy_points": ["buy3"] if cutoff.endswith("05:00") else (["buy2like"] if cutoff.endswith("07:00") else []),
            "conclusion": "偏多，允许轻仓试错。",
        }

    monkeypatch.setattr(scan_module, "_replay", fake_replay)

    payload = scan_module._scan_symbol("01339", "中国人保", None, None, step=1, per_symbol_limit=1)

    assert payload["symbol"] == "01339"
    assert payload["scanned"] == 10
    assert payload["matches"] == [
        {
            "cutoff": "2026-08-01 09:05:00",
            "same_level_consumption_level": "confirmed",
            "buy_points": ["buy3"],
            "conclusion": "偏多，允许轻仓试错。",
        }
    ]


def test_main_writes_json_output_file(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "confirmed-buy-samples.json"
    monkeypatch.setattr(
        scan_module,
        "parse_args",
        lambda: SimpleNamespace(
            symbols=None,
            start=None,
            end=None,
            step=5,
            per_symbol_limit=2,
            output=str(output_path),
        ),
    )
    monkeypatch.setattr(scan_module, "_iter_symbol_dirs", lambda symbol_filters: [Path("data/reports/01339")])
    monkeypatch.setattr(scan_module, "_load_name", lambda symbol_dir: "中国人保")
    monkeypatch.setattr(
        scan_module,
        "_scan_symbol",
        lambda symbol, name, start, end, step, per_symbol_limit: {
            "symbol": symbol,
            "name": name,
            "scanned": 12,
            "matches": [{"cutoff": "2026-08-01 09:05:00", "buy_points": ["buy3"]}],
        },
    )

    exit_code = scan_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "symbols_scanned=1 matched_symbols=1 step=5" in captured.out
    assert "MATCH 01339 中国人保 count=1 first_cutoff=2026-08-01 09:05:00 buy_points=['buy3']" in captured.out
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "symbols_scanned": 1,
        "matched_symbols": 1,
        "start": None,
        "end": None,
        "step": 5,
        "per_symbol_limit": 2,
        "results": [
            {
                "symbol": "01339",
                "name": "中国人保",
                "scanned": 12,
                "matches": [{"cutoff": "2026-08-01 09:05:00", "buy_points": ["buy3"]}],
            }
        ],
    }