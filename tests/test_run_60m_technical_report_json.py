from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_cn_60m_chanlun_report as cn_report
import run_cn_60m_chanlun_to_wechat as cn_wechat
import run_hk_60m_chanlun_report as hk_report
import run_hk_60m_chanlun_to_wechat as hk_wechat


@pytest.mark.parametrize(
    ("module", "symbol"),
    [
        (cn_report, "600900"),
        (hk_report, "00700"),
        (cn_wechat, "600900"),
        (hk_wechat, "00700"),
    ],
)
def test_write_technical_report_json_persists_consumption_level(module, symbol: str, tmp_path: Path) -> None:
    output_path = tmp_path / f"{symbol}_tech.json"
    summary_payload = {
        "conclusion": "观察，等待确认。",
        "suggestion": "继续等待结构闭合。",
    }
    signals = {
        "same_level_decomposition_mode": "dual_interpretation_pending",
        "same_level_consumption_level": "pending",
        "oscillation_rhythm_state": "down_bias",
        "zs_monitor_alert": "pre_breakdown",
        "zs_monitor_midline": 10.45,
        "zs_monitor_bias": "weak",
    }

    result = module.write_technical_report_json(
        path=output_path,
        signals=signals,
        symbol=symbol,
        name="示例标的",
        timeframe="60m",
        source="unit-test",
        actual_source="unit-test",
        source_attempts=[{"source": "unit-test", "status": "ok"}],
        analysis_text="analysis",
        advice_text="结论：观察，等待确认。\n建议：继续等待结构闭合。",
        raw_csv=tmp_path / "raw.csv",
        normalized_csv=tmp_path / "normalized.csv",
        chart_svg=tmp_path / "structure.svg",
        chart_png=tmp_path / "structure.png",
        chart_jpg=tmp_path / "structure.jpg",
        fractal_count=1,
        bi_count=2,
        confirmed_bi_count=1,
        zhongshu_count=0,
        actual_bar_count=120,
        requested_min_rows=100,
        zhongshus=[],
        structure_state={"current_ongoing": {"type": "range"}},
        divergence={"trend": {"active": False}, "range": {"active": False}},
        summary_payload=summary_payload,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == output_path
    assert payload["same_level_decomposition_mode"] == "dual_interpretation_pending"
    assert payload["same_level_consumption_level"] == "pending"
    assert payload["oscillation_rhythm_state"] == "down_bias"
    assert payload["zs_monitor_alert"] == "pre_breakdown"
    assert payload["zs_monitor_midline"] == 10.45
    assert payload["zs_monitor_bias"] == "weak"
    assert payload["summary"] == summary_payload
    assert payload["data_fetch"]["fulfilled_min_rows"] is True