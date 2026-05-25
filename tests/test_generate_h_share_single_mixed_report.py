from __future__ import annotations

import argparse
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


def test_main_passes_default_minute_fallback_to_technical_step(monkeypatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        symbol="00700",
        name="腾讯",
        start="2026-01-01 09:30",
        end=None,
        source="xueqiu",
        fallback_source=None,
        quote_overlay_source=None,
        output_dir=str(tmp_path),
        cache_dir=str(tmp_path / "cache"),
        max_cache_age_days=7,
        send_wechat=False,
        disable_dedupe=False,
        duplicate_send_window_seconds=300.0,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)

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
    monkeypatch.setattr(
        module,
        "save_blended_fundamental_brief",
        lambda blended, output_dir: Path(output_dir) / "fundamental.txt",
    )

    captured: dict[str, tuple[str, ...] | None] = {}

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
