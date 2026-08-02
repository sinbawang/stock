"""CLI 入口相关测试。"""

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
    )

    assert seen["kwargs"] == {
        "bootstrap_mode": "skip_left_edge",
        "bootstrap_skip_confirmed_bis": 3,
    }
