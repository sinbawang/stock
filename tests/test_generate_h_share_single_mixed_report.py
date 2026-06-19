from __future__ import annotations

import argparse
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

import generate_h_share_single_mixed_report as module


def test_resolve_minute_fallback_sources_defaults_to_akshare_for_xueqiu() -> None:
    assert module._resolve_minute_fallback_sources("xueqiu", None) == ("akshare",)


def test_resolve_minute_fallback_sources_respects_explicit_sources() -> None:
    assert module._resolve_minute_fallback_sources("xueqiu", ("xueqiu", "akshare")) == ("akshare",)
    assert module._resolve_minute_fallback_sources("akshare", None) is None
    assert module._resolve_minute_fallback_sources("akshare", ("xueqiu",)) == ("xueqiu",)


def test_resolve_manual_supplement_path_prefers_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / "manual.json"
    explicit.write_text("{}", encoding="utf-8")
    assert module._resolve_manual_supplement_path("01339", str(explicit)) == str(explicit)


def test_resolve_manual_supplement_path_finds_symbol_template(monkeypatch, tmp_path: Path) -> None:
    candidate = tmp_path / "01339_中国人保_insurance_v1_latest.json"
    candidate.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_MANUAL_SUPPLEMENT_DIR", tmp_path)
    assert module._resolve_manual_supplement_path("01339", None) == str(candidate)


def test_main_passes_default_minute_fallback_to_technical_step(monkeypatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        symbol="00700",
        name="腾讯",
        start="2026-01-01 09:30",
        end=None,
        source="xueqiu",
        fallback_source=None,
        quote_overlay_source=None,
        manual_supplement_path=None,
        output_dir=str(tmp_path),
        cache_dir=str(tmp_path / "cache"),
        max_cache_age_days=7,
        skip_gen_base=True,
        send_wechat=False,
        disable_dedupe=False,
        duplicate_send_window_seconds=300.0,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "_resolve_manual_supplement_path", lambda symbol, explicit_path: str(tmp_path / "00700.json"))

    blended = SimpleNamespace(
        blended_total_score=86.1,
        blended_rating="A",
        submodel_id="platform_internet_v1",
    )
    monkeypatch.setattr(
        module,
        "fetch_and_analyze_hk_blended_fundamentals",
        lambda *args, **kwargs: SimpleNamespace(blended=blended),
    )

    captured: dict[str, tuple[str, ...] | None] = {}
    captured_manual: dict[str, str | None] = {}

    def fake_fetch_and_analyze_hk_blended_fundamentals(*args, **kwargs):
        captured_manual["path"] = kwargs.get("manual_supplement_path")
        return SimpleNamespace(blended=blended)

    monkeypatch.setattr(module, "fetch_and_analyze_hk_blended_fundamentals", fake_fetch_and_analyze_hk_blended_fundamentals)
    monkeypatch.setattr(module, "write_base_text", lambda blended, output_dir: Path(output_dir) / "base.txt")
    monkeypatch.setattr(module, "build_fundamental_presentation", lambda blended, base_text_path: {"brief_path": str(base_text_path)})

    def fake_save_technical_report(**kwargs):
        captured["fallback_sources"] = kwargs["fallback_sources"]
        return module.TechnicalRef(conclusion="偏空", suggestion="等待", path=Path(tmp_path / "tech.txt")), Path(tmp_path / "tech.txt")

    monkeypatch.setattr(module, "_save_technical_report", fake_save_technical_report)

    scorecard = SimpleNamespace(total_score=52.5, rating="C")
    snapshot = SimpleNamespace(source="eastmoney.southbound_net_buy+eastmoney.southbound_holding.cache")
    monkeypatch.setattr(
        module,
        "fetch_and_analyze_hk_flow",
        lambda *args, **kwargs: SimpleNamespace(scorecard=scorecard, snapshot=snapshot),
    )
    monkeypatch.setattr(
        module,
        "save_capital_flow_text",
        lambda scorecard, snapshot, output_dir: Path(output_dir) / "capital.txt",
    )
    monkeypatch.setattr(
        module,
        "_save_combined_report",
        lambda **kwargs: Path(tmp_path / "mixed.txt"),
    )

    module.main()

    assert captured["fallback_sources"] == ("akshare",)
    assert captured_manual["path"] == str(tmp_path / "00700.json")


def test_save_combined_report_writes_latest_overview_file(tmp_path: Path) -> None:
    row = SimpleNamespace(
        target=SimpleNamespace(symbol="00700", name="腾讯"),
        fundamental=SimpleNamespace(score=86.1, rating="A"),
        technical=SimpleNamespace(conclusion="偏多", suggestion="继续观察"),
        capital_flow=SimpleNamespace(bucket="watch", source="eastmoney", score=52.5, rating="C"),
        combined_bucket="P2",
        combined_comment="三轴维持观察",
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
    assert "00700 腾讯" in overview_path.read_text(encoding="utf-8")
    assert list(tmp_path.glob("*_mixed_overview_*.txt"))


def test_save_technical_report_respects_custom_output_dir_and_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    rows = [{"ts": "2026-05-01 10:30:00"}, {"ts": "2026-05-29 14:30:00"}]
    raw_bars = [SimpleNamespace(ts="2026-05-01 10:30:00")]
    normalized_bars = [SimpleNamespace(idx=0)]

    monkeypatch.setattr(module, "fetch_hk_minute_with_policy", lambda *args, **kwargs: (rows, "xueqiu"))
    monkeypatch.setattr(module, "save_hk_minute_csv", lambda *args, **kwargs: None)
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
        symbol="00700",
        name="腾讯",
        output_dir=tmp_path,
        start="2026-01-01 09:30",
        end=None,
        primary_source="xueqiu",
        fallback_sources=("akshare",),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    artifacts = payload["artifacts"]
    data_fetch = payload["data_fetch"]
    assert output_path == tmp_path / "60m" / "tech.json"
    assert Path(artifacts["structure_svg"]).exists()
    assert Path(artifacts["structure_png"]).exists()
    assert Path(artifacts["structure_jpg"]).exists()
    assert Path(artifacts["raw_csv"]).parent == tmp_path / "60m" / "analyze"
    assert data_fetch["source"] == "xueqiu"
    assert data_fetch["actual_bar_count"] == len(raw_bars)
    assert data_fetch["requested_min_rows"] is None
    assert data_fetch["fulfilled_min_rows"] is None
    assert data_fetch["bar_count_policy"] == "feasible_maximum"
    assert data_fetch["source_probe_min_rows"] == 600
