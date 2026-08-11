"""CLI 入口相关测试。"""

from types import SimpleNamespace

import chanlun.cli as cli_module


def test_analyze_passes_bootstrap_options_to_segment_identification(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("open,high,low,close,volume\n1,1,1,1,1\n", encoding="utf-8")

    seen = {}

    def fake_identify_segments(bis, **kwargs):
        seen["kwargs"] = kwargs
        return []

    monkeypatch.setattr(cli_module, "read_bars_from_csv", lambda path: [])
    monkeypatch.setattr(cli_module, "clean_bars", lambda bars: bars)
    monkeypatch.setattr(cli_module, "normalize_bars", lambda bars: bars)
    monkeypatch.setattr(cli_module, "identify_fractals", lambda bars: [])
    monkeypatch.setattr(cli_module, "filter_consecutive_fractals", lambda fractals: fractals)
    monkeypatch.setattr(cli_module, "identify_bis", lambda fractals, bars: [])
    monkeypatch.setattr(cli_module, "identify_segments", fake_identify_segments)
    monkeypatch.setattr(cli_module, "identify_zhongshu", lambda bis: [])

    cli_module.analyze(
        str(csv_path),
        output_dir=None,
        bootstrap_mode="skip_left_edge",
        bootstrap_skip_confirmed_bis=3,
        strict_segment_rules=False,
    )

    assert seen["kwargs"] == {
        "bootstrap_mode": "skip_left_edge",
        "bootstrap_skip_confirmed_bis": 3,
        "strict_segment_rules": False,
    }


def test_analyze_emits_segment_stop_contract_line(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("open,high,low,close,volume\n1,1,1,1,1\n", encoding="utf-8")

    segment = SimpleNamespace(
        direction=SimpleNamespace(value="up"),
        segment_id=0,
        start_ts="2024-01-01 10:30",
        end_ts="2024-01-03 14:00",
        stop_reason="same_direction_not_extending",
    )
    emitted: list[str] = []

    monkeypatch.setattr(cli_module, "read_bars_from_csv", lambda path: [])
    monkeypatch.setattr(cli_module, "clean_bars", lambda bars: bars)
    monkeypatch.setattr(cli_module, "normalize_bars", lambda bars: bars)
    monkeypatch.setattr(cli_module, "identify_fractals", lambda bars: [])
    monkeypatch.setattr(cli_module, "filter_consecutive_fractals", lambda fractals: fractals)
    monkeypatch.setattr(cli_module, "identify_bis", lambda fractals, bars: [])
    monkeypatch.setattr(cli_module, "identify_segments", lambda bis, **kwargs: [segment])
    monkeypatch.setattr(cli_module, "identify_zhongshu", lambda bis: [])
    monkeypatch.setattr(cli_module.typer, "echo", lambda message, **kwargs: emitted.append(str(message)))

    cli_module.analyze(
        str(csv_path),
        output_dir=None,
    )

    assert any(
        "stop=出现同向笔，但没有继续创新高或新低 (pending) | outcome=pending" in line
        for line in emitted
    )
