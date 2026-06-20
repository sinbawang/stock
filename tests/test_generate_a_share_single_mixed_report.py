from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_a_share_single_mixed_report as module


def test_save_combined_report_writes_latest_overview_file(tmp_path: Path) -> None:
    row = SimpleNamespace(
        target=SimpleNamespace(symbol="600900", name="长江电力"),
        fundamental=SimpleNamespace(score=82.0, rating="A"),
        technical=SimpleNamespace(conclusion="偏强", suggestion="耐心持有"),
        capital_flow=SimpleNamespace(bucket="strong", source="eastmoney", score=88.0, rating="A"),
        combined_bucket="P1",
        combined_comment="三轴共振偏强",
    )

    overview_path = module._save_combined_report(
        row=row,
        output_dir=tmp_path,
        fundamental_path=tmp_path / "base.json",
        technical_path=tmp_path / "60m" / "tech.json",
        capital_flow_path=tmp_path / "fund.json",
    )

    assert overview_path == tmp_path / "overview.txt"
    assert overview_path.exists()
    assert "600900 长江电力" in overview_path.read_text(encoding="utf-8")
    assert list(tmp_path.glob("*_mixed_overview_*.txt"))


def test_save_technical_report_writes_chart_artifacts(tmp_path: Path, monkeypatch) -> None:
    rows = [{"ts": "2026-05-01 10:30:00"}, {"ts": "2026-05-29 14:30:00"}]
    raw_bars = [SimpleNamespace(ts="2026-05-01 10:30:00")]
    normalized_bars = [SimpleNamespace(idx=0)]

    monkeypatch.setattr(module, "fetch_kline", lambda *args, **kwargs: rows)
    monkeypatch.setattr(
        module,
        "get_last_fetch_metadata",
        lambda: {
            "actual_source": "xueqiu",
            "source_attempts": [
                {"source": "tushare", "status": "error"},
                {"source": "xueqiu", "status": "ok", "row_count": 2},
            ],
        },
    )
    monkeypatch.setattr(module, "save_cn_kline_csv", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "read_bars_from_csv", lambda *args, **kwargs: raw_bars)
    monkeypatch.setattr(module, "clean_bars", lambda bars: bars)
    monkeypatch.setattr(module, "normalize_bars", lambda bars: normalized_bars)
    monkeypatch.setattr(module, "write_normalized_csv", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "identify_fractals", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "filter_consecutive_fractals", lambda fractals: fractals)
    monkeypatch.setattr(module, "identify_bis", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "identify_zhongshu", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "calculate_macd", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "export_fractals", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_confirmed_fractals", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_bis", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_zhongshus", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "export_macd", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "analyze_current_state", lambda *args, **kwargs: "analysis")
    monkeypatch.setattr(module, "extract_signals", lambda *args, **kwargs: {"bucket": "watch"})
    monkeypatch.setattr(module, "build_advice", lambda *args, **kwargs: "建议：观察")
    monkeypatch.setattr(module, "build_technical_summary", lambda *args, **kwargs: {"conclusion": "偏强", "suggestion": "观察"})

    def fake_save_structure_charts(**kwargs):
        kwargs["svg_path"].write_text("svg", encoding="utf-8")
        kwargs["png_path"].write_text("png", encoding="utf-8")
        kwargs["jpg_path"].write_text("jpg", encoding="utf-8")

    monkeypatch.setattr(module, "save_structure_charts", fake_save_structure_charts)

    _, output_path = module._save_technical_report(
        symbol="600900",
        name="长江电力",
        output_dir=tmp_path,
        start="2026-01-01 09:30",
        end=None,
        adjust="qfq",
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    artifacts = payload["artifacts"]
    data_fetch = payload["data_fetch"]
    assert Path(artifacts["structure_svg"]).exists()
    assert Path(artifacts["structure_png"]).exists()
    assert Path(artifacts["structure_jpg"]).exists()
    assert Path(artifacts["macd_csv"]).name.endswith("_normalized_macd.csv")
    assert payload["source_actual"] == "xueqiu"
    assert data_fetch["source"] == "tushare->tencent->xueqiu->eastmoney"
    assert data_fetch["actual_source"] == "xueqiu"
    assert data_fetch["source_attempts"][0]["source"] == "tushare"
    assert data_fetch["actual_bar_count"] == len(raw_bars)
    assert data_fetch["requested_min_rows"] is None
    assert data_fetch["fulfilled_min_rows"] is None
    assert data_fetch["bar_count_policy"] == "feasible_maximum"
    assert data_fetch["source_probe_min_rows"] == 600