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

import fetch_kline as module


def test_main_passes_source_profile_to_fetch_kline(monkeypatch, tmp_path: Path, capsys) -> None:
    args = argparse.Namespace(
        symbol="sz000001",
        start="2026-01-01 09:30",
        end=None,
        interval="60m",
        adjust="qfq",
        limit=1200,
        source_profile="xueqiu-first",
        output=str(tmp_path / "rows.csv"),
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)

    captured: dict[str, object] = {}

    def fake_fetch_kline(**kwargs):
        captured.update(kwargs)
        return [{"ts": "2026-06-01 10:30", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr(module, "fetch_kline", fake_fetch_kline)
    monkeypatch.setattr(module, "get_last_fetch_metadata", lambda: {"actual_source": "tushare"})
    monkeypatch.setattr(module, "save_to_csv", lambda rows, filepath: None)

    module.main()

    assert captured["source_profile"] == "xueqiu-first"
    assert captured["limit"] == 1200
    output = capsys.readouterr().out
    assert "source_profile=xueqiu-first" in output
    assert "实际命中源: tushare" in output