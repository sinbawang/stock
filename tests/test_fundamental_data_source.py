from __future__ import annotations

from datetime import date
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

from fundamental.config.registry import get_submodel_for_symbol
from fundamental.data import cn_snapshot_fetcher as cn_fetcher
from fundamental.data import hk_snapshot_fetcher as fetcher
from fundamental.models.blended import AnnualAnchorScore, BlendedFundamentalScoreCard, InterimOverlayScore, OverlayComponent
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.reporting import render_blended_fundamental_brief, render_blended_scorecard_text, render_fundamental_brief, render_scorecard_text
from fundamental.services import fetch_and_analyze_cn_blended_fundamentals, fetch_and_analyze_hk_blended_fundamentals
from fundamental.services.fetch_and_analyze_cn_snapshot import fetch_and_analyze_cn_snapshot
from fundamental.services.fetch_and_analyze_hk_snapshot import fetch_and_analyze_hk_snapshot
from fundamental.services.manual_supplement_helpers import apply_manual_supplement, resolve_manual_supplement
from fundamental.services.source_warning_helpers import build_manual_supplement_warning, get_manual_supplement_fields, normalize_warnings
from fundamental.services.manual_supplement_loader import load_manual_supplement_file, parse_manual_supplement_text


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
batch_regenerate_spec = importlib.util.spec_from_file_location(
    "batch_regenerate_fundamental_briefs",
    SCRIPTS / "batch_regenerate_fundamental_briefs.py",
)
if batch_regenerate_spec is None or batch_regenerate_spec.loader is None:
    raise RuntimeError("failed to load batch_regenerate_fundamental_briefs.py for tests")
batch_regenerate_module = importlib.util.module_from_spec(batch_regenerate_spec)
sys.modules[batch_regenerate_spec.name] = batch_regenerate_module
batch_regenerate_spec.loader.exec_module(batch_regenerate_module)
discover_targets = batch_regenerate_module.discover_targets
discover_targets_from_holdings_file = batch_regenerate_module.discover_targets_from_holdings_file
find_manual_supplement_path = batch_regenerate_module.find_manual_supplement_path
regenerate_one = batch_regenerate_module.regenerate_one

batch_prepare_spec = importlib.util.spec_from_file_location(
    "batch_prepare_chanlun_reports",
    SCRIPTS / "batch_prepare_chanlun_reports.py",
)
if batch_prepare_spec is None or batch_prepare_spec.loader is None:
    raise RuntimeError("failed to load batch_prepare_chanlun_reports.py for tests")
batch_prepare_module = importlib.util.module_from_spec(batch_prepare_spec)
sys.modules[batch_prepare_spec.name] = batch_prepare_module
batch_prepare_spec.loader.exec_module(batch_prepare_module)
load_batch_prepare_securities = batch_prepare_module.load_securities

send_wechat_spec = importlib.util.spec_from_file_location(
    "send_wechat_native",
    SCRIPTS / "send_wechat_native.py",
)
if send_wechat_spec is None or send_wechat_spec.loader is None:
    raise RuntimeError("failed to load send_wechat_native.py for tests")
send_wechat_module = importlib.util.module_from_spec(send_wechat_spec)
sys.modules[send_wechat_spec.name] = send_wechat_module
send_wechat_spec.loader.exec_module(send_wechat_module)

generate_brief_spec = importlib.util.spec_from_file_location(
    "generate_fundamental_brief",
    SCRIPTS / "generate_fundamental_brief.py",
)
if generate_brief_spec is None or generate_brief_spec.loader is None:
    raise RuntimeError("failed to load generate_fundamental_brief.py for tests")
generate_brief_module = importlib.util.module_from_spec(generate_brief_spec)
sys.modules[generate_brief_spec.name] = generate_brief_module
generate_brief_spec.loader.exec_module(generate_brief_module)

fetch_service_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_snapshot")
cn_fetch_service_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_snapshot")


def test_source_warning_helpers_build_shared_manual_warning():
    field_sources = {
        "dividend_yield": "manual.supplement",
        "reserve_life_index": "manual.supplement",
        "notes": "manual.supplement",
        "roe": "unit-test",
    }

    manual_fields = get_manual_supplement_fields(field_sources)
    warning = build_manual_supplement_warning(field_sources)
    normalized = normalize_warnings([warning or "", "", warning or ""])

    assert manual_fields == ["dividend_yield", "reserve_life_index"]
    assert warning == "以下字段当前使用手工补充口径: 股息率、储量寿命指数。"
    assert normalized == ("以下字段当前使用手工补充口径: 股息率、储量寿命指数。",)


def test_manual_supplement_helpers_resolve_and_apply_shared_logic(tmp_path):
    supplement_path = tmp_path / "supplement.txt"
    supplement_path.write_text(
        """手工补充字段:
- dividend_yield=6.3
- notes=annual report
""",
        encoding="utf-8",
    )
    fetched = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601088",
            name="中国神华",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=12.8,
            operating_cashflow_to_profit=1.22,
            operating_cashflow_to_profit_history=[1.22, 1.15],
            debt_to_asset=29.0,
            pe_percentile_5y=68.0,
        ),
        assumptions=("unit-test",),
        raw_payload_refs=("unit-test:601088",),
    )
    submodel = get_submodel_for_symbol("601088")
    assert submodel is not None

    resolved = resolve_manual_supplement({"reserve_life_index": 14.5}, str(supplement_path))
    updated = apply_manual_supplement(fetched, submodel, resolved)

    assert resolved == {"dividend_yield": 6.3, "notes": "annual report", "reserve_life_index": 14.5}
    assert updated.snapshot.dividend_yield == 6.3
    assert updated.snapshot.reserve_life_index == 14.5
    assert updated.field_sources is not None
    assert updated.field_sources["dividend_yield"] == "manual.supplement"
    assert "manual-supplement:601088" in updated.raw_payload_refs


def test_batch_regenerate_helpers_discover_targets_and_find_supplement(tmp_path):
    meta_dir = tmp_path / "_meta"
    supplement_dir = meta_dir / "manual_supplements"
    supplement_dir.mkdir(parents=True)

    (meta_dir / "300124_汇川技术_fundamental_brief_20260510_014554.txt").write_text("brief", encoding="utf-8")
    (meta_dir / "300124_汇川技术_fundamental_brief_20260511_010101.txt").write_text("brief", encoding="utf-8")
    (meta_dir / "00700_腾讯_fundamental_brief_20260510_013550.txt").write_text("brief", encoding="utf-8")
    (supplement_dir / "601088_中国神华_energy_resource_v1_latest.txt").write_text("supplement", encoding="utf-8")

    targets = discover_targets(meta_dir)
    supplement_path = find_manual_supplement_path("601088", supplement_dir)

    assert targets == [
        type(targets[0])(symbol="00700", name="腾讯"),
        type(targets[0])(symbol="300124", name="汇川技术"),
    ]
    assert supplement_path is not None
    assert supplement_path.endswith("601088_中国神华_energy_resource_v1_latest.txt")


def test_batch_regenerate_helpers_discover_targets_supports_submodel_brief_filenames(tmp_path):
    meta_dir = tmp_path / "_meta"
    meta_dir.mkdir(parents=True)

    (
        meta_dir / "601088_中国神华_energy_resource_v1_fundamental_brief_20260516_104035.txt"
    ).write_text("brief", encoding="utf-8")

    targets = discover_targets(meta_dir)

    assert targets == [type(targets[0])(symbol="601088", name="中国神华")]


def test_batch_regenerate_helpers_discover_targets_supports_mixed_brief_filename_formats(tmp_path):
    meta_dir = tmp_path / "_meta"
    meta_dir.mkdir(parents=True)

    (meta_dir / "00700_腾讯_fundamental_brief_20260510_013550.txt").write_text("brief", encoding="utf-8")
    (meta_dir / "00700_腾讯_platform_internet_v1_fundamental_brief_20260516_104035.txt").write_text(
        "brief",
        encoding="utf-8",
    )
    (meta_dir / "601088_中国神华_energy_resource_v1_fundamental_brief_20260516_104035.txt").write_text(
        "brief",
        encoding="utf-8",
    )

    targets = discover_targets(meta_dir)

    assert targets == [
        type(targets[0])(symbol="00700", name="腾讯"),
        type(targets[0])(symbol="601088", name="中国神华"),
    ]


def test_batch_regenerate_helpers_discover_targets_from_combined_holdings_file(tmp_path):
        holdings_file = tmp_path / "current_holdings.json"
        holdings_file.write_text(
                """
{
    "markets": {
        "CN": [
            {"symbol": "600900", "name": "长江电力"},
            {"symbol": "601328", "name": "交通银行"}
        ],
        "HK": [
            {"symbol": "00700", "name": "腾讯"},
            {"symbol": "03690", "name": "美团"}
        ]
    }
}
""".strip(),
                encoding="utf-8",
        )

        targets = discover_targets_from_holdings_file(holdings_file)

        assert targets == [
                type(targets[0])(symbol="600900", name="长江电力"),
                type(targets[0])(symbol="601328", name="交通银行"),
                type(targets[0])(symbol="00700", name="腾讯"),
                type(targets[0])(symbol="03690", name="美团"),
        ]


def test_batch_regenerate_helpers_discover_targets_from_single_market_holdings_file(tmp_path):
        holdings_file = tmp_path / "current_a_share_holdings.json"
        holdings_file.write_text(
                """
{
    "market": "CN",
    "holdings": [
        {"symbol": "000591", "name": "太阳能"},
        {"symbol": "000651", "name": "格力电器"}
    ]
}
""".strip(),
                encoding="utf-8",
        )

        targets = discover_targets_from_holdings_file(holdings_file)

        assert targets == [
                type(targets[0])(symbol="000591", name="太阳能"),
                type(targets[0])(symbol="000651", name="格力电器"),
        ]


def test_batch_prepare_load_securities_from_combined_holdings_file(tmp_path):
        holdings_file = tmp_path / "current_holdings.json"
        holdings_file.write_text(
                """
{
    "markets": {
        "CN": [
            {"symbol": "600900", "name": "长江电力"}
        ],
        "HK": [
            {"symbol": "00700", "name": "腾讯"}
        ]
    }
}
""".strip(),
                encoding="utf-8",
        )

        securities = load_batch_prepare_securities(holdings_file)

        assert securities == [
                batch_prepare_module.Security(symbol="600900", name="长江电力", market="A"),
                batch_prepare_module.Security(symbol="00700", name="腾讯", market="HK"),
        ]


def test_batch_prepare_load_securities_falls_back_to_default_when_missing(tmp_path):
        securities = load_batch_prepare_securities(tmp_path / "missing.json")

        assert securities == batch_prepare_module.SECURITIES


def test_batch_regenerate_helpers_regenerate_one_returns_brief_and_scorecard_paths(monkeypatch, tmp_path):
    target = batch_regenerate_module.BriefTarget(symbol="601088", name="中国神华")
    output_dir = tmp_path / "briefs"
    scorecard_output_dir = tmp_path / "scorecards"
    supplement_dir = tmp_path / "manual_supplements"
    supplement_dir.mkdir(parents=True)
    (supplement_dir / "601088_中国神华_energy_resource_v1_latest.txt").write_text("supplement", encoding="utf-8")

    fake_result = SimpleNamespace(
        scorecard=SimpleNamespace(submodel_id="energy_resource_v1"),
        fetched=SimpleNamespace(snapshot=object(), field_sources={"market_cap": "unit-test"}),
    )
    calls: dict[str, object] = {}

    def fake_fetch_cn_snapshot(symbol: str, name: str, manual_supplement_path: str | None = None):
        calls["fetch"] = (symbol, name, manual_supplement_path)
        return fake_result

    def fake_save_fundamental_brief(*, scorecard, snapshot, field_sources, output_dir):
        calls["brief"] = (scorecard, snapshot, field_sources, output_dir)
        return Path(output_dir) / "brief.txt"

    def fake_save_scorecard_text(*, scorecard, snapshot, output_dir):
        calls["scorecard"] = (scorecard, snapshot, output_dir)
        return Path(output_dir) / "scorecard.txt"

    monkeypatch.setattr(batch_regenerate_module, "fetch_and_analyze_cn_snapshot", fake_fetch_cn_snapshot)
    monkeypatch.setattr(batch_regenerate_module, "save_fundamental_brief", fake_save_fundamental_brief)
    monkeypatch.setattr(batch_regenerate_module, "save_scorecard_text", fake_save_scorecard_text)

    generated_paths = regenerate_one(
        target,
        output_dir=output_dir,
        supplement_dir=supplement_dir,
        save_scorecard=True,
        scorecard_output_dir=scorecard_output_dir,
    )

    assert calls["fetch"] == (
        "601088",
        "中国神华",
        str(supplement_dir / "601088_中国神华_energy_resource_v1_latest.txt"),
    )
    assert calls["brief"] == (
        fake_result.scorecard,
        fake_result.fetched.snapshot,
        fake_result.fetched.field_sources,
        output_dir,
    )
    assert calls["scorecard"] == (
        fake_result.scorecard,
        fake_result.fetched.snapshot,
        scorecard_output_dir,
    )
    assert generated_paths == [output_dir / "brief.txt", scorecard_output_dir / "scorecard.txt"]


def test_batch_regenerate_helpers_regenerate_one_can_emit_blended_cn_outputs(monkeypatch, tmp_path):
    target = batch_regenerate_module.BriefTarget(symbol="601088", name="中国神华")
    output_dir = tmp_path / "briefs"
    scorecard_output_dir = tmp_path / "scorecards"
    supplement_dir = tmp_path / "manual_supplements"
    supplement_dir.mkdir(parents=True)

    fake_result = SimpleNamespace(blended=SimpleNamespace(submodel_id="energy_resource_v1"))
    calls: dict[str, object] = {}

    def fake_fetch_blended(symbol: str, name: str, manual_supplement_path: str | None = None):
        calls["fetch"] = (symbol, name, manual_supplement_path)
        return fake_result

    def fake_save_blended_brief(*, blended, output_dir):
        calls["brief"] = (blended, output_dir)
        return Path(output_dir) / "blended-brief.txt"

    def fake_save_blended_scorecard(*, blended, output_dir):
        calls["scorecard"] = (blended, output_dir)
        return Path(output_dir) / "blended-scorecard.txt"

    monkeypatch.setattr(batch_regenerate_module, "fetch_and_analyze_cn_blended_fundamentals", fake_fetch_blended)
    monkeypatch.setattr(batch_regenerate_module, "save_blended_fundamental_brief", fake_save_blended_brief)
    monkeypatch.setattr(batch_regenerate_module, "save_blended_scorecard_text", fake_save_blended_scorecard)

    generated_paths = regenerate_one(
        target,
        output_dir=output_dir,
        supplement_dir=supplement_dir,
        save_scorecard=True,
        scorecard_output_dir=scorecard_output_dir,
        blended_cn=True,
    )

    assert calls["fetch"] == ("601088", "中国神华", None)
    assert calls["brief"] == (fake_result.blended, output_dir)
    assert calls["scorecard"] == (fake_result.blended, scorecard_output_dir)
    assert generated_paths == [output_dir / "blended-brief.txt", scorecard_output_dir / "blended-scorecard.txt"]


def test_generate_fundamental_brief_main_routes_blended_cn_outputs(monkeypatch, tmp_path, capsys):
    fake_result = SimpleNamespace(blended=SimpleNamespace(submodel_id="utility_operator_v1"))
    calls: dict[str, object] = {}

    def fake_fetch_blended(symbol: str, name: str, submodel: str | None = None, manual_supplement_path: str | None = None):
        calls["fetch"] = (symbol, name, submodel, manual_supplement_path)
        return fake_result

    def fake_save_blended_brief(*, blended, output_dir):
        calls["brief"] = (blended, output_dir)
        return Path(output_dir) / "blended-brief.txt"

    def fake_save_blended_scorecard(*, blended, output_dir):
        calls["scorecard"] = (blended, output_dir)
        return Path(output_dir) / "blended-scorecard.txt"

    monkeypatch.setattr(generate_brief_module, "fetch_and_analyze_cn_blended_fundamentals", fake_fetch_blended)
    monkeypatch.setattr(generate_brief_module, "save_blended_fundamental_brief", fake_save_blended_brief)
    monkeypatch.setattr(generate_brief_module, "save_blended_scorecard_text", fake_save_blended_scorecard)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_fundamental_brief.py",
            "600900",
            "--name",
            "长江电力",
            "--blended-cn",
            "--output-dir",
            str(tmp_path),
            "--save-scorecard-text",
        ],
    )

    generate_brief_module.main()

    assert calls["fetch"] == ("600900", "长江电力", None, None)
    assert calls["brief"] == (fake_result.blended, str(tmp_path))
    assert calls["scorecard"] == (fake_result.blended, str(tmp_path))
    stdout = capsys.readouterr().out
    assert "blended-brief.txt" in stdout
    assert "blended-scorecard.txt" in stdout


def test_generate_fundamental_brief_main_routes_blended_hk_outputs(monkeypatch, tmp_path, capsys):
    fake_result = SimpleNamespace(blended=SimpleNamespace(submodel_id="platform_internet_v1"))
    calls: dict[str, object] = {}

    def fake_fetch_blended(
        symbol: str,
        name: str,
        submodel: str | None = None,
        quote_overlay_source: str | None = None,
        manual_supplement_path: str | None = None,
    ):
        calls["fetch"] = (symbol, name, submodel, quote_overlay_source, manual_supplement_path)
        return fake_result

    def fake_save_blended_brief(*, blended, output_dir):
        calls["brief"] = (blended, output_dir)
        return Path(output_dir) / "blended-brief.txt"

    def fake_save_blended_scorecard(*, blended, output_dir):
        calls["scorecard"] = (blended, output_dir)
        return Path(output_dir) / "blended-scorecard.txt"

    monkeypatch.setattr(generate_brief_module, "fetch_and_analyze_hk_blended_fundamentals", fake_fetch_blended)
    monkeypatch.setattr(generate_brief_module, "save_blended_fundamental_brief", fake_save_blended_brief)
    monkeypatch.setattr(generate_brief_module, "save_blended_scorecard_text", fake_save_blended_scorecard)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_fundamental_brief.py",
            "00700",
            "--name",
            "腾讯",
            "--blended-hk",
            "--output-dir",
            str(tmp_path),
            "--save-scorecard-text",
        ],
    )

    generate_brief_module.main()

    assert calls["fetch"] == ("00700", "腾讯", None, None, None)
    assert calls["brief"] == (fake_result.blended, str(tmp_path))
    assert calls["scorecard"] == (fake_result.blended, str(tmp_path))
    stdout = capsys.readouterr().out
    assert "blended-brief.txt" in stdout
    assert "blended-scorecard.txt" in stdout


def test_generate_fundamental_brief_main_auto_resolves_manual_supplement(monkeypatch, tmp_path, capsys):
    fake_result = SimpleNamespace(blended=SimpleNamespace(submodel_id="insurance_v1"))
    calls: dict[str, object] = {}

    def fake_fetch_blended(
        symbol: str,
        name: str,
        submodel: str | None = None,
        quote_overlay_source: str | None = None,
        manual_supplement_path: str | None = None,
    ):
        calls["fetch"] = (symbol, name, submodel, quote_overlay_source, manual_supplement_path)
        return fake_result

    def fake_save_blended_brief(*, blended, output_dir):
        calls["brief"] = (blended, output_dir)
        return Path(output_dir) / "blended-brief.txt"

    def fake_save_blended_scorecard(*, blended, output_dir):
        calls["scorecard"] = (blended, output_dir)
        return Path(output_dir) / "blended-scorecard.txt"

    monkeypatch.setattr(generate_brief_module, "fetch_and_analyze_hk_blended_fundamentals", fake_fetch_blended)
    monkeypatch.setattr(generate_brief_module, "save_blended_fundamental_brief", fake_save_blended_brief)
    monkeypatch.setattr(generate_brief_module, "save_blended_scorecard_text", fake_save_blended_scorecard)
    monkeypatch.setattr(generate_brief_module, "_resolve_manual_supplement_path", lambda symbol, explicit_path: "manual.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_fundamental_brief.py",
            "01339",
            "--name",
            "中国人保",
            "--blended-hk",
            "--output-dir",
            str(tmp_path),
            "--save-scorecard-text",
        ],
    )

    generate_brief_module.main()

    assert calls["fetch"] == ("01339", "中国人保", None, None, "manual.json")
    assert calls["brief"] == (fake_result.blended, str(tmp_path))
    assert calls["scorecard"] == (fake_result.blended, str(tmp_path))
    stdout = capsys.readouterr().out
    assert "blended-brief.txt" in stdout
    assert "blended-scorecard.txt" in stdout


def test_parse_manual_supplement_text_extracts_key_value_lines():
    parsed = parse_manual_supplement_text(
        """中国神华基本面简报

补充说明:
- pe_ttm=12.4, pb=1.8
- dividend_yield=6.3
- capex_to_operating_cashflow=0.42
- notes=2025 annual report p.34, p.112
"""
    )

    assert parsed["pe_ttm"] == 12.4
    assert parsed["pb"] == 1.8
    assert parsed["dividend_yield"] == 6.3
    assert parsed["capex_to_operating_cashflow"] == 0.42
    assert parsed["notes"] == "2025 annual report p.34, p.112"


def test_load_manual_supplement_file_reads_brief_text(tmp_path):
    brief_path = tmp_path / "601088_中国神华_fundamental_brief.txt"
    brief_path.write_text(
        """中国神华基本面简报

手工补充字段:
- dividend_yield=6.3
- reserve_life_index=14.5
- notes=annual report and operating data
""",
        encoding="utf-8",
    )

    parsed = load_manual_supplement_file(brief_path)

    assert parsed == {
        "dividend_yield": 6.3,
        "reserve_life_index": 14.5,
        "notes": "annual report and operating data",
    }


def test_fetch_hk_fundamental_snapshot_builds_snapshot(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": -14.4296,
                "OPERATE_INCOME": 180000000000.0,
                "OPERATE_INCOME_YOY": 8.0758,
                "HOLDER_PROFIT_YOY": -165.2244,
                "DEBT_ASSET_RATIO": 56.4764,
                "CURRENT_RATIO": 1.8217,
                "HOLDER_PROFIT": -23355015000.0,
            },
            {
                "REPORT_DATE": "2024-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 22.0572,
                "OPERATE_INCOME": 165000000000.0,
                "OPERATE_INCOME_YOY": 21.9865,
                "HOLDER_PROFIT_YOY": 158.4268,
                "DEBT_ASSET_RATIO": 46.7854,
                "CURRENT_RATIO": 1.9431,
                "HOLDER_PROFIT": 35807180000.0,
            },
            {
                "REPORT_DATE": "2023-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 9.8697,
                "OPERATE_INCOME": 135000000000.0,
                "OPERATE_INCOME_YOY": 25.8189,
                "HOLDER_PROFIT_YOY": 307.2330,
                "DEBT_ASSET_RATIO": 48.1430,
                "CURRENT_RATIO": 1.8153,
                "HOLDER_PROFIT": 13855830000.0,
            },
        ]
    )
    valuation_df = pd.DataFrame([["03690", "美团", -20.0706, 45.0, -20.0706, 45.0, 3.1034, 62.0, 3.1034, 61.0, 1.2848, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": -13815001000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 57146784000.0},
            {"REPORT_DATE": "2023-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 40521850000.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 6039356000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 5032796666.67},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 21265800000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 19332545454.55},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004011010", "AMOUNT": 1500.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004011010", "AMOUNT": 1200.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004020001", "AMOUNT": 3300.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004020001", "AMOUNT": 3000.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)

    result = fetcher.fetch_hk_fundamental_snapshot("03690", name="美团")

    assert result.snapshot.symbol == "03690"
    assert result.snapshot.name == "美团"
    assert result.snapshot.report_period == date(2025, 12, 31)
    assert result.snapshot.pe_percentile_5y == 45.0
    assert result.snapshot.peg is None
    assert result.snapshot.net_margin == -12.975
    assert result.snapshot.dupont_driver is None
    assert result.snapshot.equity_multiplier == 2.2976
    assert result.snapshot.asset_turnover is None
    assert result.snapshot.operating_cashflow_to_profit_history == [0.5915, 1.596, 2.9245]
    assert result.snapshot.interest_bearing_debt_growth == 14.2857
    assert result.snapshot.operating_cashflow_growth == -124.1746
    assert result.snapshot.accounts_receivable_growth == 0.2
    assert result.snapshot.inventory_growth == 0.1
    assert result.field_sources == {
        "roe": "eastmoney.analysis",
        "revenue_growth": "eastmoney.analysis",
        "net_profit_growth": "eastmoney.analysis",
        "net_margin": "eastmoney.analysis",
        "debt_to_asset": "eastmoney.analysis",
        "current_ratio": "eastmoney.analysis",
        "equity_multiplier": "derived.debt_to_asset",
        "operating_cashflow_to_profit": "eastmoney.cashflow",
        "operating_cashflow_to_profit_history": "eastmoney.cashflow",
        "interest_bearing_debt_growth": "derived.eastmoney.balance",
        "operating_cashflow_growth": "derived.eastmoney.cashflow",
        "accounts_receivable_growth": "eastmoney.analysis",
        "inventory_growth": "eastmoney.analysis",
        "pe_ttm": "eastmoney+akshare.valuation",
        "pe_percentile_5y": "eastmoney+akshare.valuation",
        "pb": "eastmoney+akshare.valuation",
        "ps_ttm": "eastmoney+akshare.valuation",
    }


def test_fetch_hk_period_snapshots_returns_newer_interim_when_available(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-03-31 00:00:00",
                "DATE_TYPE_CODE": "003",
                "CURRENCY": "HKD",
                "ROE_AVG": 4.5,
                "OPERATE_INCOME": 50000000000.0,
                "OPERATE_INCOME_YOY": 12.0,
                "HOLDER_PROFIT_YOY": 18.0,
                "DEBT_ASSET_RATIO": 40.0,
                "CURRENT_RATIO": 1.2,
                "HOLDER_PROFIT": 12000000000.0,
            },
            {
                "REPORT_DATE": "2024-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 18.0,
                "OPERATE_INCOME": 190000000000.0,
                "OPERATE_INCOME_YOY": 9.0,
                "HOLDER_PROFIT_YOY": 22.0,
                "DEBT_ASSET_RATIO": 39.0,
                "CURRENT_RATIO": 1.25,
                "HOLDER_PROFIT": 41000000000.0,
            },
            {
                "REPORT_DATE": "2023-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 16.0,
                "OPERATE_INCOME": 175000000000.0,
                "OPERATE_INCOME_YOY": 7.0,
                "HOLDER_PROFIT_YOY": 15.0,
                "DEBT_ASSET_RATIO": 38.0,
                "CURRENT_RATIO": 1.28,
                "HOLDER_PROFIT": 35000000000.0,
            },
        ]
    )
    valuation_df = pd.DataFrame([["00700", "腾讯", 18.0, 41.0, 18.0, 41.0, 3.2, 62.0, 3.2, 61.0, 1.28, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-03-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 14000000000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 65000000000.0},
            {"REPORT_DATE": "2023-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 59000000000.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-03-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 22000000000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 21000000000.0},
            {"REPORT_DATE": "2025-03-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 3000000000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 2800000000.0},
            {"REPORT_DATE": "2025-03-31 00:00:00", "STD_ITEM_CODE": "004011010", "AMOUNT": 5000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004011010", "AMOUNT": 4500.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_dividend_payout_df", lambda symbol: pd.DataFrame())

    result = fetcher.fetch_hk_period_snapshots("00700", name="腾讯")

    assert result.annual.snapshot.report_period == date(2024, 12, 31)
    assert result.interim is not None
    assert result.interim.snapshot.report_period == date(2025, 3, 31)
    assert result.interim.snapshot.period_type == "report"


def test_fetch_hk_broker_latest_interim_does_not_use_annual_report_proxy(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2026-03-31 00:00:00",
                "DATE_TYPE_CODE": "003",
                "CURRENCY": "HKD",
                "ROE_AVG": 2.3,
                "OPERATE_INCOME": 12000000000.0,
                "OPERATE_INCOME_YOY": 41.5,
                "HOLDER_PROFIT_YOY": 31.8,
                "DEBT_ASSET_RATIO": 82.7,
                "CURRENT_RATIO": 1.08,
                "HOLDER_PROFIT": 3200000000.0,
            },
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 8.2,
                "OPERATE_INCOME": 38000000000.0,
                "OPERATE_INCOME_YOY": 1.9,
                "HOLDER_PROFIT_YOY": 6.7,
                "DEBT_ASSET_RATIO": 80.8,
                "CURRENT_RATIO": 1.17,
                "HOLDER_PROFIT": 8600000000.0,
            },
            {
                "REPORT_DATE": "2024-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 8.3,
                "OPERATE_INCOME": 37000000000.0,
                "OPERATE_INCOME_YOY": -5.0,
                "HOLDER_PROFIT_YOY": -7.0,
                "DEBT_ASSET_RATIO": 79.2,
                "CURRENT_RATIO": 1.14,
                "HOLDER_PROFIT": 7900000000.0,
            },
        ]
    )
    valuation_df = pd.DataFrame([["06886", "华泰证券", 7.4, 31.0, 7.4, 31.0, 0.72, 28.0, 0.72, 28.0, 2.6, 29.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-03-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 24000000000.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": -33000000000.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 18000000000.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-03-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 95.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 90.0},
            {"REPORT_DATE": "2026-03-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 88.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 85.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 3.53}])

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_dividend_payout_df", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(
        fetcher,
        "_fetch_hk_official_financial_fields",
        lambda symbol: (
            {"net_capital_ratio": 298.67},
            ("official broker annual proxy",),
            ("official-broker",),
            {"net_capital_ratio": "official.annual_report_proxy"},
        ),
    )

    annual = fetcher.fetch_hk_fundamental_snapshot("06886", name="华泰证券", report_period_preference="annual_preferred")
    interim = fetcher.fetch_hk_fundamental_snapshot("06886", name="华泰证券", report_period_preference="latest_interim")

    assert annual.snapshot.net_capital_ratio == 298.67
    assert annual.field_sources.get("net_capital_ratio") == "official.annual_report_proxy"
    assert interim.snapshot.period_type == "report"
    assert interim.snapshot.net_capital_ratio is None
    assert "net_capital_ratio" not in interim.field_sources


def test_fetch_and_analyze_hk_blended_fundamentals_combines_platform_interim_overlay(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00700",
            name="腾讯",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=18.0,
            roe_3y_cv=0.15,
            operating_cashflow_to_profit=1.4,
            operating_cashflow_to_profit_history=[1.4, 1.3, 1.2],
            revenue_growth=9.0,
            net_profit_growth=18.0,
            pe_percentile_5y=45.0,
            peg=1.1,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00700",
            name="腾讯",
            market="HK",
            report_period=date(2025, 3, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=5.2,
            roe_3y_cv=0.15,
            operating_cashflow_to_profit=0.92,
            operating_cashflow_to_profit_history=[0.92, 1.08, 1.16],
            revenue_growth=12.0,
            net_profit_growth=16.0,
            pe_percentile_5y=45.0,
            peg=1.0,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    monkeypatch.setattr(
        importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended"),
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=80.0,
            rating="A",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("00700", name="腾讯")

    assert result.annual_anchor.scorecard.total_score == 80.0
    assert result.interim_overlay is not None
    assert result.interim_overlay.overlay_score > 0
    assert result.blended.annual_weight == 0.8
    assert result.blended.interim_weight == 0.2
    assert result.blended.blended_total_score < 80.0
    assert result.blended.submodel_id == "platform_internet_v1"


def test_fetch_and_analyze_hk_blended_fundamentals_supports_digital_infra(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00728",
            name="中国电信",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=8.8,
            operating_cashflow_to_profit=1.12,
            operating_cashflow_to_profit_history=[1.12, 1.05, 1.08],
            revenue_growth=4.5,
            net_profit_growth=7.8,
            pb=0.82,
            dividend_yield=5.9,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00728",
            name="中国电信",
            market="HK",
            report_period=date(2025, 6, 30),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=4.7,
            operating_cashflow_to_profit=1.18,
            operating_cashflow_to_profit_history=[1.18, 1.1, 1.06],
            revenue_growth=5.2,
            net_profit_growth=8.4,
            pb=0.79,
            dividend_yield=6.1,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=76.0,
            rating="B",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("00728", name="中国电信")

    assert result.interim_overlay is not None
    assert result.blended.submodel_id == "digital_infra_v1"
    assert result.blended.annual_weight == 0.65
    assert result.blended.interim_weight == 0.35
    assert {component.component for component in result.interim_overlay.components} == {
        "growth_refresh",
        "cashflow_refresh",
        "shareholder_return_refresh",
    }
    assert result.interim_overlay.overlay_score > 0


def test_fetch_and_analyze_hk_snapshot_defaults_xueqiu_overlay_for_digital_infra(monkeypatch):
    calls: dict[str, object] = {}

    fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00728",
            name="中国电信",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=9.0,
            operating_cashflow_to_profit=1.1,
            operating_cashflow_to_profit_history=[1.1, 1.0],
            revenue_growth=4.0,
            net_profit_growth=6.0,
            pb=0.8,
            dividend_yield=5.8,
            period_type="annual",
        ),
        assumptions=("unit-test",),
        raw_payload_refs=("unit-test:00728",),
        field_sources={},
    )

    def fake_fetch(symbol, name=None, quote_overlay_source=None):
        calls["args"] = (symbol, name, quote_overlay_source)
        return fetched

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=70.0,
            rating="B",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(fetch_service_module, "fetch_hk_fundamental_snapshot", fake_fetch)
    monkeypatch.setattr(fetch_service_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_snapshot("00728", name="中国电信")

    assert calls["args"] == ("00728", "中国电信", "xueqiu")
    assert result.scorecard.submodel_id == "digital_infra_v1"


def test_fetch_and_analyze_hk_blended_fundamentals_supports_semiconductor_hardtech(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00981",
            name="中芯国际",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="USD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=5.4,
            roe_3y_cv=0.28,
            operating_cashflow_to_profit=1.26,
            operating_cashflow_to_profit_history=[1.26, 1.18, 1.12],
            revenue_growth=14.0,
            net_profit_growth=11.0,
            accounts_receivable_growth=0.08,
            inventory_growth=0.11,
            pe_percentile_5y=22.0,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00981",
            name="中芯国际",
            market="HK",
            report_period=date(2025, 3, 31),
            currency="USD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=1.8,
            roe_3y_cv=0.32,
            operating_cashflow_to_profit=1.34,
            operating_cashflow_to_profit_history=[1.34, 1.21, 1.09],
            revenue_growth=12.0,
            net_profit_growth=7.0,
            accounts_receivable_growth=0.09,
            inventory_growth=0.12,
            pe_percentile_5y=18.0,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=68.0,
            rating="B",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("00981", name="中芯国际")

    assert result.interim_overlay is not None
    assert result.blended.submodel_id == "semiconductor_hardtech_v1"
    assert result.blended.annual_weight == 0.8
    assert result.blended.interim_weight == 0.2
    assert {component.component for component in result.interim_overlay.components} == {
        "growth_refresh",
        "cashflow_refresh",
        "operating_cycle_refresh",
    }
    assert result.interim_overlay.overlay_score > 0


def test_fetch_and_analyze_hk_blended_fundamentals_supports_auto_manufacturing(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00175",
            name="吉利汽车",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=16.0,
            roe_3y_cv=0.12,
            operating_cashflow_to_profit=1.5,
            operating_cashflow_to_profit_history=[1.5, 1.32, 1.21],
            revenue_growth=18.0,
            net_profit_growth=9.0,
            accounts_receivable_growth=0.05,
            inventory_growth=0.08,
            asset_turnover=1.18,
            pe_percentile_5y=19.0,
            overseas_revenue_share=22.0,
            price_war_pressure="medium",
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00175",
            name="吉利汽车",
            market="HK",
            report_period=date(2025, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=3.8,
            roe_3y_cv=0.18,
            operating_cashflow_to_profit=1.34,
            operating_cashflow_to_profit_history=[1.34, 1.26, 1.1],
            revenue_growth=16.0,
            net_profit_growth=6.0,
            accounts_receivable_growth=0.06,
            inventory_growth=0.09,
            asset_turnover=1.15,
            pe_percentile_5y=17.0,
            overseas_revenue_share=24.0,
            price_war_pressure="high",
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=72.0,
            rating="B",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("00175", name="吉利汽车")

    assert result.interim_overlay is not None
    assert result.blended.submodel_id == "auto_manufacturing_v1"
    assert result.blended.annual_weight == 0.8
    assert result.blended.interim_weight == 0.2
    assert {component.component for component in result.interim_overlay.components} == {
        "growth_refresh",
        "cashflow_refresh",
        "inventory_channel_refresh",
    }
    assert result.interim_overlay.overlay_score > 0


def test_auto_manufacturing_interim_overlay_uses_single_ocf_history_point():
    from fundamental.services.fetch_and_analyze_cn_blended import _build_interim_overlay_components

    snapshot = fetcher.FundamentalSnapshot(
        symbol="00175",
        name="吉利汽车",
        market="HK",
        report_period=date(2025, 3, 31),
        currency="CNY",
        source="unit-test",
        updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
        revenue_growth=15.0,
        net_profit_growth=-20.0,
        operating_cashflow_to_profit=None,
        operating_cashflow_to_profit_history=[None, None, 1.6184],
        accounts_receivable_growth=0.06,
        inventory_growth=0.09,
        asset_turnover=1.15,
        overseas_revenue_share=21.41,
        price_war_pressure="high",
        period_type="report",
    )

    submodel = get_submodel_for_symbol("00175")
    assert submodel is not None

    components = _build_interim_overlay_components(snapshot, submodel)
    component_names = {component.component for component in components}

    assert "cashflow_refresh" in component_names


def test_fetch_and_analyze_hk_blended_fundamentals_supports_insurance_with_sparse_interim_fields(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=15.9,
            roe_3y_cv=0.02,
            pb=0.66,
            dividend_yield=3.9,
            solvency_adequacy_ratio=249.9,
            combined_ratio=97.6,
            investment_return=4.9,
            embedded_value_growth=4.0,
            new_business_value_growth=64.5,
            net_profit_growth=9.6,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2025, 3, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=2.8,
            roe_3y_cv=0.57,
            pb=0.66,
            dividend_yield=3.9,
            solvency_adequacy_ratio=275.7,
            combined_ratio=None,
            investment_return=None,
            embedded_value_growth=None,
            new_business_value_growth=None,
            net_profit_growth=-31.4,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=83.0,
            rating="A",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("01339", name="中国人保")

    assert result.interim_overlay is not None
    assert result.blended.submodel_id == "insurance_v1"
    assert result.blended.annual_weight == 0.8
    assert result.blended.interim_weight == 0.2
    assert {component.component for component in result.interim_overlay.components} == {
        "capital_refresh",
        "profitability_refresh",
        "business_growth_refresh",
    }
    assert result.interim_overlay.overlay_score > 0


def test_fetch_and_analyze_hk_blended_does_not_apply_manual_supplement_to_interim(monkeypatch, tmp_path):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2024, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=15.9,
            roe_3y_cv=0.02,
            pb=0.66,
            dividend_yield=3.9,
            solvency_adequacy_ratio=249.9,
            net_profit_growth=9.6,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2025, 3, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=2.8,
            roe_3y_cv=0.57,
            pb=0.66,
            dividend_yield=3.9,
            solvency_adequacy_ratio=275.7,
            combined_ratio=None,
            investment_return=None,
            embedded_value_growth=None,
            new_business_value_growth=None,
            net_profit_growth=-31.4,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )
    supplement_path = tmp_path / "01339_insurance.json"
    supplement_path.write_text(
        json.dumps(
            {
                "combined_ratio": 97.6,
                "investment_return": 4.9,
                "embedded_value_growth": 4.0,
                "new_business_value_growth": 64.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=83.0,
            rating="A",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals(
        "01339",
        name="中国人保",
        manual_supplement_path=str(supplement_path),
    )

    profitability_component = next(
        component for component in result.interim_overlay.components if component.component == "profitability_refresh"
    )
    growth_component = next(
        component for component in result.interim_overlay.components if component.component == "business_growth_refresh"
    )
    assert profitability_component.covered_metrics == ("roe",)
    assert growth_component.covered_metrics == ("net_profit_growth",)
    assert growth_component.note.endswith("先用净利增速做保守业务刷新代理，避免把未披露字段误当成恶化。")


def test_fetch_and_analyze_hk_blended_fundamentals_supports_broker_with_sparse_interim_fields(monkeypatch):
    annual_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="06886",
            name="华泰证券",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=10.2,
            roe_3y_cv=0.14,
            pb=0.88,
            dividend_yield=4.2,
            net_capital_ratio=298.67,
            revenue_growth=11.3,
            net_profit_growth=13.1,
            period_type="annual",
        ),
        assumptions=("annual",),
        raw_payload_refs=("unit-test:annual",),
        field_sources={},
    )
    interim_fetched = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="06886",
            name="华泰证券",
            market="HK",
            report_period=date(2026, 3, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
            roe=2.1,
            roe_3y_cv=0.22,
            pb=0.81,
            dividend_yield=4.0,
            net_capital_ratio=None,
            revenue_growth=7.8,
            net_profit_growth=-12.5,
            period_type="report",
        ),
        assumptions=("interim",),
        raw_payload_refs=("unit-test:interim",),
        field_sources={},
    )

    hk_blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_blended")
    monkeypatch.setattr(
        hk_blended_module,
        "fetch_hk_period_snapshots",
        lambda symbol, name=None, quote_overlay_source=None: SimpleNamespace(annual=annual_fetched, interim=interim_fetched),
    )

    def fake_analyze_snapshot(snapshot, submodel):
        return FundamentalScoreCard(
            symbol=snapshot.symbol,
            name=snapshot.name,
            market=snapshot.market,
            report_period=snapshot.report_period,
            industry_bucket=submodel.industry_bucket,
            submodel_id=submodel.submodel_id,
            submodel_version=submodel.version,
            total_score=67.0,
            rating="B",
            red_flag=False,
            dimension_scores=[],
            warnings=[],
        )

    monkeypatch.setattr(hk_blended_module, "analyze_snapshot", fake_analyze_snapshot)

    result = fetch_and_analyze_hk_blended_fundamentals("06886", name="华泰证券")

    assert result.interim_overlay is not None
    assert result.blended.submodel_id == "broker_v1"
    assert {component.component for component in result.interim_overlay.components} == {
        "profitability_refresh",
        "business_growth_refresh",
        "shareholder_return_refresh",
    }
    profitability_component = next(
        component for component in result.interim_overlay.components if component.component == "profitability_refresh"
    )
    growth_component = next(
        component for component in result.interim_overlay.components if component.component == "business_growth_refresh"
    )
    shareholder_component = next(
        component for component in result.interim_overlay.components if component.component == "shareholder_return_refresh"
    )
    assert profitability_component.covered_metrics == ("roe",)
    assert growth_component.covered_metrics == ("revenue_growth", "net_profit_growth")
    assert shareholder_component.covered_metrics == ("pb", "dividend_yield")
    assert result.interim_overlay.overlay_score > 0


def test_render_blended_broker_reports_mark_missing_overlay_component():
    annual_snapshot = fetcher.FundamentalSnapshot(
        symbol="06886",
        name="华泰证券",
        market="HK",
        report_period=date(2025, 12, 31),
        currency="HKD",
        source="unit-test",
        updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
        period_type="annual",
        net_capital_ratio=298.67,
    )
    interim_snapshot = fetcher.FundamentalSnapshot(
        symbol="06886",
        name="华泰证券",
        market="HK",
        report_period=date(2026, 3, 31),
        currency="HKD",
        source="unit-test",
        updated_at=pd.Timestamp("2026-05-16T00:00:00").to_pydatetime(),
        period_type="report",
        roe=2.29,
        revenue_growth=41.48,
        net_profit_growth=31.79,
        pb=0.72,
        dividend_yield=3.53,
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="06886",
        name="华泰证券",
        market="HK",
        report_period=annual_snapshot.report_period,
        industry_bucket="financial",
        submodel_id="broker_v1",
        submodel_version="v1",
        total_score=67.82,
        rating="B",
        red_flag=False,
        dimension_scores=[],
        warnings=[],
    )
    interim_overlay = InterimOverlayScore(
        snapshot=interim_snapshot,
        components=(
            OverlayComponent("profitability_refresh", 17.21, 0.3, covered_metrics=("roe",)),
            OverlayComponent(
                "business_growth_refresh",
                100.0,
                0.2,
                covered_metrics=("revenue_growth", "net_profit_growth"),
            ),
            OverlayComponent(
                "shareholder_return_refresh",
                86.91,
                0.15,
                covered_metrics=("pb", "dividend_yield"),
            ),
        ),
        overlay_score=38.2,
        rating_hint="D",
        covered_metrics=("roe", "revenue_growth", "net_profit_growth", "pb", "dividend_yield"),
        missing_metrics=(),
    )
    blended = BlendedFundamentalScoreCard(
        symbol="06886",
        name="华泰证券",
        market="HK",
        submodel_id="broker_v1",
        annual_anchor=AnnualAnchorScore(snapshot=annual_snapshot, scorecard=annual_scorecard),
        interim_overlay=interim_overlay,
        annual_weight=0.8,
        interim_weight=0.2,
        blended_total_score=61.9,
        blended_rating="C",
        freshness_label="q1_refresh",
    )

    brief_text = render_blended_fundamental_brief(blended)
    scorecard_text = render_blended_scorecard_text(blended)

    assert "刷新覆盖率: 65%（缺失权重 35%）。" in brief_text
    assert "缺失刷新组件: capital_refresh（缺失 net_capital_ratio）。" in brief_text
    assert "刷新覆盖率: 65%（缺失权重 35%）。" in scorecard_text
    assert "缺失刷新组件: capital_refresh（缺失 net_capital_ratio）。" in scorecard_text


def test_send_wechat_native_send_message_retries_window_attach(monkeypatch):
    calls: list[tuple[str | None, list[str] | None]] = []
    activation_attempts = {"count": 0}

    monkeypatch.setattr(send_wechat_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(send_wechat_module, "find_wechat_window", lambda: 123)

    def fake_activate_window(_hwnd: int):
        activation_attempts["count"] += 1
        if activation_attempts["count"] == 1:
            raise RuntimeError("未找到微信主窗口")
        return (0, 0, 1000, 800)

    monkeypatch.setattr(send_wechat_module, "activate_window", fake_activate_window)
    monkeypatch.setattr(send_wechat_module, "switch_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(send_wechat_module, "_send_text_via_uia_current_chat", lambda _message: (_ for _ in ()).throw(RuntimeError("uia disabled in test")))
    monkeypatch.setattr(send_wechat_module, "_ensure_wechat_foreground", lambda _hwnd: None)
    monkeypatch.setattr(send_wechat_module, "click_ratio", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        send_wechat_module,
        "send_to_current_chat",
        lambda message=None, filepaths=None, hwnd=None: calls.append((message, filepaths)),
    )

    send_wechat_module.send_message(message="hello", current_chat_only=False)

    assert activation_attempts["count"] == 2
    assert calls == [("hello", None)]


def test_send_wechat_native_send_message_sends_files_one_by_one(monkeypatch):
    focus_calls: list[tuple[float, float]] = []
    sent_calls: list[tuple[str | None, list[str] | None]] = []

    monkeypatch.setattr(send_wechat_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(send_wechat_module, "find_wechat_window", lambda: 123)
    monkeypatch.setattr(send_wechat_module, "activate_window", lambda _hwnd: (0, 0, 1000, 800))
    monkeypatch.setattr(send_wechat_module, "switch_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(send_wechat_module, "_ensure_wechat_foreground", lambda _hwnd: None)
    monkeypatch.setattr(send_wechat_module, "click_ratio", lambda _rect, rx, ry: focus_calls.append((rx, ry)))
    monkeypatch.setattr(
        send_wechat_module,
        "send_to_current_chat",
        lambda message=None, filepaths=None, hwnd=None: sent_calls.append((message, filepaths)),
    )

    send_wechat_module.send_message(filepaths=["a.txt", "b.txt"], current_chat_only=True)

    assert focus_calls == [(0.67, 0.9), (0.67, 0.9)]
    assert sent_calls == [(None, ["a.txt"]), (None, ["b.txt"])]


def test_send_wechat_native_switch_chat_selects_first_search_result(monkeypatch):
    taps: list[int] = []
    typed: list[str] = []

    monkeypatch.setattr(send_wechat_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(send_wechat_module, "click_ratio", lambda *args, **kwargs: None)
    monkeypatch.setattr(send_wechat_module, "hotkey", lambda *args, **kwargs: None)
    monkeypatch.setattr(send_wechat_module, "type_by_clipboard", lambda text: typed.append(text))
    monkeypatch.setattr(send_wechat_module, "tap", lambda key: taps.append(key))

    send_wechat_module.switch_chat(
        (0, 0, 1000, 800),
        contact="888",
        result_index=1,
        allow_search_switch=True,
    )

    assert typed == ["888"]
    assert taps == [send_wechat_module.win32con.VK_BACK, send_wechat_module.win32con.VK_DOWN, send_wechat_module.win32con.VK_RETURN]


def test_send_wechat_native_send_shortcut_only_uses_enter(monkeypatch):
    taps: list[int] = []
    ensured: list[int] = []

    monkeypatch.setattr(send_wechat_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(send_wechat_module, "tap", lambda key: taps.append(key))
    monkeypatch.setattr(send_wechat_module, "_ensure_wechat_foreground", lambda hwnd: ensured.append(hwnd))

    send_wechat_module.send_shortcut(hwnd=123)

    assert ensured == [123]
    assert taps == [send_wechat_module.win32con.VK_RETURN]


def test_send_wechat_native_click_ratio_restores_cursor(monkeypatch):
    positions: list[tuple[int, int]] = []

    monkeypatch.setattr(send_wechat_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(send_wechat_module.win32api, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(send_wechat_module.win32api, "SetCursorPos", lambda pos: positions.append(pos))
    monkeypatch.setattr(send_wechat_module.win32api, "mouse_event", lambda *args, **kwargs: None)

    send_wechat_module.click_ratio((0, 0, 100, 100), 0.5, 0.5)

    assert positions == [(50, 50), (10, 20)]


def test_send_wechat_native_send_message_prefers_uia_for_current_chat_text(monkeypatch):
    sent: list[str] = []

    monkeypatch.setattr(send_wechat_module, "_send_text_via_uia_current_chat", lambda message: sent.append(message))
    monkeypatch.setattr(send_wechat_module, "find_wechat_window", lambda: (_ for _ in ()).throw(AssertionError("should not use win32 path")))

    send_wechat_module.send_message(message="hello", current_chat_only=True)

    assert sent == ["hello"]


def test_send_wechat_native_split_message_chunks_preserves_paragraphs():
    message = "第一段" + "a" * 220 + "\n\n第二段" + "b" * 220 + "\n\n第三段" + "c" * 220

    chunks = send_wechat_module._split_message_chunks(message, max_chars=260)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 260 for chunk in chunks)
    assert "第一段" in chunks[0]
    assert any("第二段" in chunk for chunk in chunks)
    assert any("第三段" in chunk for chunk in chunks)


def test_fetch_hk_fundamental_snapshot_derives_peg_and_dupont_driver_when_inputs_available(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 18.6,
                "OPERATE_INCOME": 1000.0,
                "OPERATE_INCOME_YOY": 21.3,
                "HOLDER_PROFIT_YOY": 20.0,
                "DEBT_ASSET_RATIO": 45.0,
                "CURRENT_RATIO": 1.82,
                "HOLDER_PROFIT": 120.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["03690", "美团", 16.0, 41.0, 16.0, 41.0, 3.2, 62.0, 3.2, 61.0, 1.28, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 224.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "005005", "AMOUNT": 84.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "005007", "AMOUNT": 16.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)

    result = fetcher.fetch_hk_fundamental_snapshot("03690", name="美团")

    assert result.snapshot.peg == 0.8
    assert result.snapshot.net_margin == 12.0
    assert result.snapshot.dupont_driver == "margin_turnover"
    assert result.snapshot.equity_multiplier == 1.8182
    assert result.snapshot.asset_turnover == 0.8525
    assert result.snapshot.operating_cashflow_growth is None
    assert result.field_sources is not None
    assert result.field_sources["peg"] == "derived.pe_ttm+net_profit_growth"
    assert "operating_cashflow_growth" not in result.field_sources
    assert result.field_sources["dupont_driver"] == "derived.roe+net_margin+debt_to_asset"
    assert result.field_sources["equity_multiplier"] == "derived.debt_to_asset"
    assert result.field_sources["asset_turnover"] == "derived.roe+net_margin+debt_to_asset"


def test_fetch_hk_fundamental_snapshot_falls_back_to_latest_available_period_when_annual_unavailable(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2026-06-30 00:00:00",
                "DATE_TYPE_CODE": "003",
                "CURRENCY": "HKD",
                "ROE_AVG": 12.6,
                "OPERATE_INCOME": 1100.0,
                "OPERATE_INCOME_YOY": 18.2,
                "HOLDER_PROFIT_YOY": 16.5,
                "DEBT_ASSET_RATIO": 47.0,
                "CURRENT_RATIO": 1.72,
                "HOLDER_PROFIT": 132.0,
                "GROSS_PROFIT_RATIO": 15.9,
            },
            {
                "REPORT_DATE": "2025-06-30 00:00:00",
                "DATE_TYPE_CODE": "003",
                "CURRENCY": "HKD",
                "ROE_AVG": 10.8,
                "OPERATE_INCOME": 960.0,
                "OPERATE_INCOME_YOY": 9.4,
                "HOLDER_PROFIT_YOY": 8.1,
                "DEBT_ASSET_RATIO": 45.5,
                "CURRENT_RATIO": 1.69,
                "HOLDER_PROFIT": 118.0,
                "GROSS_PROFIT_RATIO": 15.2,
            },
        ]
    )
    valuation_df = pd.DataFrame([["03690", "美团", 18.0, 41.0, 18.0, 41.0, 3.2, 62.0, 3.2, 61.0, 1.28, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-06-30 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 180.0},
            {"REPORT_DATE": "2025-06-30 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 130.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-06-30 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2025-06-30 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2026-06-30 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 108.0},
            {"REPORT_DATE": "2025-06-30 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)

    result = fetcher.fetch_hk_fundamental_snapshot("03690", name="美团")

    assert result.snapshot.report_period == date(2026, 6, 30)
    assert result.snapshot.period_type == "report"
    assert result.snapshot.operating_cashflow_to_profit_history == [1.3636, 1.1017]
    assert any("annual rows unavailable" in item for item in result.assumptions)


def test_fetch_hk_fundamental_snapshot_can_overlay_xueqiu_quote(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 18.6,
                "OPERATE_INCOME_YOY": 21.3,
                "HOLDER_PROFIT_YOY": 33.8,
                "DEBT_ASSET_RATIO": 45.0,
                "CURRENT_RATIO": 1.82,
                "HOLDER_PROFIT": 200.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["03690", "美团", -12.0, 41.0, -12.0, 41.0, 3.2, 62.0, 3.2, 61.0, 1.28, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 224.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "005005", "AMOUNT": 84.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "005007", "AMOUNT": 16.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    xueqiu_quote = {
        "market_capital": 2400.0,
        "pe_ttm": -19.9634,
        "pb": 3.0092,
        "psr": 1.252,
        "dividend_yield": 0.7,
    }

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_quote_xueqiu", lambda symbol: xueqiu_quote)

    result = fetcher.fetch_hk_fundamental_snapshot("03690", name="美团", quote_overlay_source="xueqiu")

    assert result.snapshot.market_cap == 2400.0
    assert result.snapshot.dividend_yield == 0.7
    assert result.snapshot.pe_ttm == -12.0
    assert result.snapshot.pb == 3.2
    assert result.snapshot.ps_ttm == 1.28
    assert result.snapshot.capex_to_operating_cashflow == 0.4464
    assert result.snapshot.free_cashflow_yield == 5.1667
    assert result.field_sources is not None
    assert result.field_sources["market_cap"] == "xueqiu.quote"
    assert result.field_sources["capex_to_operating_cashflow"] == "derived.eastmoney.cashflow"
    assert result.field_sources["free_cashflow_yield"] == "derived.eastmoney.cashflow+xueqiu.quote"
    assert result.field_sources["dividend_yield"] == "xueqiu.quote"
    assert result.field_sources["pe_ttm"] == "eastmoney+akshare.valuation"
    assert result.field_sources["pb"] == "eastmoney+akshare.valuation"
    assert result.field_sources["ps_ttm"] == "eastmoney+akshare.valuation"
    assert any("Xueqiu quote overlay supplemented missing fields" in item for item in result.assumptions)
    assert "xueqiu-quote:03690" in result.raw_payload_refs


def test_fetch_hk_fundamental_snapshot_can_supplement_dividend_yield_from_direct_payout_rows(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 18.6,
                "OPERATE_INCOME_YOY": 21.3,
                "HOLDER_PROFIT_YOY": 33.8,
                "DEBT_ASSET_RATIO": 45.0,
                "CURRENT_RATIO": 1.82,
                "HOLDER_PROFIT": 200.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["03690", "美团", -12.0, 41.0, -12.0, 41.0, 3.2, 62.0, 3.2, 61.0, 1.28, 62.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 224.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    dividend_payout_df = pd.DataFrame(
        [
            {
                "UPDATE_DATE": "2026-05-09",
                "PLAN_EXPLAIN": "末期息，股息率 5.8%",
            }
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_dividend_payout_df", lambda symbol: dividend_payout_df)

    result = fetcher.fetch_hk_fundamental_snapshot("03690", name="美团")

    assert result.snapshot.dividend_yield == 5.8
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "eastmoney.hk_dividend_payout"
    assert "eastmoney-hk-dividend-payout:03690" in result.raw_payload_refs
    assert any("Dividend yield is supplemented from the Eastmoney HK dividend payout table" in item for item in result.assumptions)


def test_fetch_hk_fundamental_snapshot_keeps_existing_dividend_yield_over_direct_payout_rows(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
                "综合偿付能力充足率": 218.0,
                "综合成本率": 97.8,
                "总投资收益率": 5.4,
                "内含价值增长率": 8.2,
                "新业务价值增长率": 12.6,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 6.1}])
    dividend_payout_df = pd.DataFrame(
        [
            {
                "UPDATE_DATE": "2026-05-09",
                "PLAN_EXPLAIN": "末期息，股息率 5.4%",
            }
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_dividend_payout_df", lambda symbol: dividend_payout_df)

    result = fetcher.fetch_hk_fundamental_snapshot("01339", name="中国人保")

    assert result.snapshot.dividend_yield == 6.1
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "eastmoney.financial_indicator"
    assert "eastmoney-hk-dividend-payout:01339" not in result.raw_payload_refs


def test_fetch_hk_fundamental_snapshot_can_supplement_broker_net_capital_ratio_from_official_report(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 8.2,
                "OPERATE_INCOME_YOY": 1.9,
                "HOLDER_PROFIT_YOY": 6.7,
                "DEBT_ASSET_RATIO": 82.5,
                "CURRENT_RATIO": 1.08,
                "HOLDER_PROFIT": 100.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["06886", "华泰证券", 7.5, 40.0, 7.5, 40.0, 0.73, 31.0, 0.73, 31.0, 1.1, 28.0]])
    cashflow_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 120.0},
        ]
    )
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 3.47}])

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(
        fetcher,
        "_fetch_hk_official_financial_fields",
        lambda symbol: (
            {"net_capital_ratio": 298.67},
            (
                "Huatai official annual report fallback mapped 风险覆盖率 to net_capital_ratio because current public HK APIs do not expose a direct broker net capital ratio field.",
            ),
            ("official-annual-report:06886:https://example.com/report.pdf",),
            {"net_capital_ratio": "official.annual_report_proxy"},
        ),
    )

    result = fetcher.fetch_hk_fundamental_snapshot("06886", name="华泰证券")

    assert result.snapshot.net_capital_ratio == 298.67
    assert result.field_sources is not None
    assert result.field_sources["net_capital_ratio"] == "official.annual_report_proxy"
    assert "official-annual-report:06886:https://example.com/report.pdf" in result.raw_payload_refs
    assert any("Huatai official annual report fallback mapped 风险覆盖率" in item for item in result.assumptions)


def test_fetch_hk_fundamental_snapshot_can_supplement_insurance_solvency_from_official_report(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 6.1}])

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(
        fetcher,
        "_fetch_hk_official_financial_fields",
        lambda symbol: (
            {"solvency_adequacy_ratio": 275.7},
            (
                "PICC official solvency report fallback supplemented solvency_adequacy_ratio from the latest public solvency report disclosure; this official source can lag the annual report period.",
                "Latest PICC solvency report disclosure date used for fallback: 2025-09-24.",
            ),
            (
                "official-solvency-listing:01339:https://www.picc.com.cn/xwzx/gkxx/zxxx/jtcfnl/",
                "official-solvency-report:01339:https://example.com/solvency.pdf",
            ),
            {"solvency_adequacy_ratio": "official.solvency_report"},
        ),
    )

    result = fetcher.fetch_hk_fundamental_snapshot("01339", name="中国人保")

    assert result.snapshot.solvency_adequacy_ratio == 275.7
    assert result.field_sources is not None
    assert result.field_sources["solvency_adequacy_ratio"] == "official.solvency_report"
    assert "official-solvency-report:01339:https://example.com/solvency.pdf" in result.raw_payload_refs
    assert any("PICC official solvency report fallback supplemented solvency_adequacy_ratio" in item for item in result.assumptions)


def test_fetch_hk_fundamental_snapshot_keeps_broker_analysis_fields_when_indicator_fetch_fails(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 10.2,
                "OPERATE_INCOME_YOY": 11.3,
                "HOLDER_PROFIT_YOY": 13.1,
                "DEBT_ASSET_RATIO": 72.0,
                "CURRENT_RATIO": 1.05,
                "HOLDER_PROFIT": 18000000000.0,
                "净资本比率": 182.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["06886", "华泰证券", 8.1, 36.0, 8.1, 36.0, 0.88, 48.0, 0.88, 48.0, 1.02, 46.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 20000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 90.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 80.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 85.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 80.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)

    def boom(symbol: str) -> pd.DataFrame:
        raise RuntimeError("indicator endpoint unavailable")

    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", boom)
    monkeypatch.setattr(fetcher, "_fetch_hk_official_financial_fields", lambda symbol: ({}, (), (), {}))

    result = fetcher.fetch_hk_fundamental_snapshot("06886", name="华泰证券")

    assert result.snapshot.net_capital_ratio == 182.0
    assert result.field_sources is not None
    assert result.field_sources["net_capital_ratio"] == "eastmoney.analysis"
    assert any("indicator endpoint unavailable" in item for item in result.assumptions)


def test_fetch_and_analyze_hk_snapshot_relaxes_platform_peg(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="03690",
            name="美团",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=18.6,
            roe_3y_cv=0.18,
            operating_cashflow_to_profit=1.12,
            operating_cashflow_to_profit_history=[1.12, 1.04],
            revenue_growth=21.3,
            net_profit_growth=33.8,
            pe_percentile_5y=41.0,
            pe_ttm=-12.0,
        ),
        assumptions=("PEG is omitted because current TTM PE is non-positive or unavailable.",),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot("03690", name="美团", submodel="platform_internet_v1")

    assert result.scorecard.submodel_id == "platform_internet_v1"
    assert result.scorecard.rating == "A"
    assert any("Runtime relaxation" in item for item in result.assumptions)


def test_fetch_and_analyze_hk_snapshot_accepts_manual_supplement_for_insurance_fields(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=11.8,
            roe_3y_cv=0.16,
            pb=0.72,
        ),
        assumptions=("public live fetch is missing insurance regulatory fields.",),
        field_sources={
            "roe": "unit-test",
            "roe_3y_cv": "unit-test",
            "pb": "unit-test",
        },
        raw_payload_refs=("unit-test:01339",),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot(
        "01339",
        name="中国人保",
        manual_supplement={
            "dividend_yield": 5.9,
            "solvency_adequacy_ratio": 218.0,
            "combined_ratio": 97.8,
            "investment_return": 5.4,
            "embedded_value_growth": 8.2,
            "new_business_value_growth": 12.6,
            "notes": "manual supplement from company disclosure",
        },
    )

    assert result.scorecard.submodel_id == "insurance_v1"
    assert result.fetched.snapshot.solvency_adequacy_ratio == 218.0
    assert result.fetched.snapshot.new_business_value_growth == 12.6
    assert result.fetched.snapshot.notes == "manual supplement from company disclosure"
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["solvency_adequacy_ratio"] == "manual.supplement"
    assert result.fetched.field_sources["dividend_yield"] == "manual.supplement"
    assert "manual-supplement:01339" in result.fetched.raw_payload_refs
    assert any("Manual supplement applied before analysis" in item for item in result.assumptions)
    assert any("以下字段当前使用手工补充口径" in item for item in result.scorecard.warnings)
    assert any("投资收益率当前为手工补充/代理值" in item for item in result.scorecard.warnings)
    assert any("保险手工补充字段可能存在跨主体口径" in item for item in result.scorecard.warnings)
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "警告" in report_text
    assert "以下字段当前使用手工补充口径" in report_text


def test_fetch_and_analyze_hk_snapshot_rejects_disallowed_manual_supplement_fields(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=11.8,
            roe_3y_cv=0.16,
            pb=0.72,
        ),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    try:
        fetch_and_analyze_hk_snapshot(
            "01339",
            name="中国人保",
            manual_supplement={"market_cap": 1000.0},
        )
    except ValueError as exc:
        assert "Manual supplement fields are not allowed for insurance_v1: market_cap" == str(exc)
    else:
        raise AssertionError("expected ValueError for disallowed manual supplement field")


def test_fetch_and_analyze_hk_snapshot_accepts_manual_auto_specialist_fields(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="00175",
            name="吉利汽车",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-11T00:00:00").to_pydatetime(),
            roe=18.8,
            roe_3y_cv=0.03,
            operating_cashflow_to_profit=2.8,
            revenue_growth=25.1,
            net_profit_growth=12.0,
            accounts_receivable_growth=1.4,
            inventory_growth=8.8,
            asset_turnover=1.24,
            pe_percentile_5y=16.0,
        ),
        assumptions=("public live fetch is missing auto specialist fields.",),
        field_sources={
            "roe": "unit-test",
            "roe_3y_cv": "unit-test",
            "operating_cashflow_to_profit": "unit-test",
            "revenue_growth": "unit-test",
            "net_profit_growth": "unit-test",
            "accounts_receivable_growth": "unit-test",
            "inventory_growth": "unit-test",
            "asset_turnover": "unit-test",
            "pe_percentile_5y": "unit-test",
        },
        raw_payload_refs=("unit-test:00175",),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot(
        "00175",
        name="吉利汽车",
        manual_supplement={
            "gross_margin_trend": "improving",
            "price_war_pressure": "low",
            "overseas_revenue_share": 31.5,
            "notes": "manual supplement from operating data",
        },
    )

    assert result.scorecard.submodel_id == "auto_manufacturing_v1"
    assert result.fetched.snapshot.gross_margin_trend == "improving"
    assert result.fetched.snapshot.price_war_pressure == "low"
    assert result.fetched.snapshot.overseas_revenue_share == 31.5
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["gross_margin_trend"] == "manual.supplement"
    assert result.fetched.field_sources["price_war_pressure"] == "manual.supplement"
    assert result.fetched.field_sources["overseas_revenue_share"] == "manual.supplement"
    assert any("Manual supplement applied before analysis" in item for item in result.assumptions)
    assert any("以下字段当前使用手工补充口径" in item for item in result.scorecard.warnings)
    dimension_basis = "\n".join(score.score_basis or "" for score in result.scorecard.dimension_scores)
    assert "毛利率趋势 improving" in dimension_basis
    assert "价格战压力 low" in dimension_basis
    assert "海外收入占比 31.50" in dimension_basis


def test_extract_geely_auto_official_fields_from_text_parses_overseas_share_and_price_pressure():
    text = """
    Revenue from external customers The PRC 271,312,369 218,391,667 Eastern Europe 29,220,482 30,296,260
    Pan Europe 17,690,647 13,074,768 Asia Pacific (excluding the PRC) 14,685,375 5,788,947 Middle East 8,174,495 5,739,285
    Latin America 3,011,736 2,047,644 Africa 1,050,762 488,151 Other countries 86,335 83,762 345,232,201 275,910,484
    Specified non-current assets
    Despite the fierce price competition in the industry, the gross profit margin was 16.6%.
    """

    extracted = fetcher._extract_geely_auto_official_fields_from_text(text)

    assert extracted["overseas_revenue_share"] == 21.41
    assert extracted["price_war_pressure"] == "high"


def test_fetch_hk_fundamental_snapshot_auto_populates_geely_specialist_fields(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 18.8359,
                "OPERATE_INCOME": 345232201000.0,
                "OPERATE_INCOME_YOY": 25.1247,
                "HOLDER_PROFIT_YOY": 0.24,
                "DEBT_ASSET_RATIO": 67.7645,
                "CURRENT_RATIO": 0.8883,
                "HOLDER_PROFIT": 16850000000.0,
                "GROSS_PROFIT_RATIO": 16.611061,
            },
            {
                "REPORT_DATE": "2024-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 15.2,
                "OPERATE_INCOME": 275910484000.0,
                "OPERATE_INCOME_YOY": 34.0343,
                "HOLDER_PROFIT_YOY": 213.0,
                "DEBT_ASSET_RATIO": 65.0,
                "CURRENT_RATIO": 0.91,
                "HOLDER_PROFIT": 16632000000.0,
                "GROSS_PROFIT_RATIO": 15.904147,
            },
        ]
    )
    valuation_df = pd.DataFrame([["00175", "吉利汽车", 14.0557, 16.0, 14.0557, 16.0, 2.2439, 45.0, 2.2439, 45.0, 0.6079, 20.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 47300000000.0},
        {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 30000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 120.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(
        fetcher,
        "_fetch_geely_official_auto_fields",
        lambda: (
            {"overseas_revenue_share": 21.41, "price_war_pressure": "high"},
            (
                "overseas_revenue_share is computed from Geely official annual report geographical revenue disclosure as (total revenue - PRC revenue) / total revenue.",
                "price_war_pressure is proxied from Geely official annual report wording about industry price competition intensity.",
            ),
            ("official-annual-report:00175:https://example.com/report.pdf",),
            {
                "overseas_revenue_share": "official.annual_report_geo_revenue",
                "price_war_pressure": "official.annual_report_text_proxy",
            },
        ),
    )

    result = fetcher.fetch_hk_fundamental_snapshot("00175", name="吉利汽车")

    assert result.snapshot.gross_margin == 16.611061
    assert result.snapshot.gross_margin_trend == "improving"
    assert result.snapshot.overseas_revenue_share == 21.41
    assert result.snapshot.price_war_pressure == "high"
    assert result.field_sources is not None
    assert result.field_sources["gross_margin"] == "eastmoney.analysis"
    assert result.field_sources["gross_margin_trend"] == "derived.eastmoney.gross_margin_history"
    assert result.field_sources["overseas_revenue_share"] == "official.annual_report_geo_revenue"
    assert result.field_sources["price_war_pressure"] == "official.annual_report_text_proxy"
    assert any("gross_margin_trend is derived" in item for item in result.assumptions)
    assert any("overseas_revenue_share is computed" in item for item in result.assumptions)


def test_fetch_cn_fundamental_snapshot_builds_snapshot(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2024-12-31", "8.00亿", "20.0%", "7.50亿", "18.0%", "100.00亿", "10.0%", "1.00", "5.00", "1.20", "2.30", "0.50", "20.0%", "45.0%", "8.0%", "7.5%", "120.0", "4.0", "90.0", "45.0", "1.50", "1.10", "1.00", "1.80", "40.0%"],
            ["2025-12-31", "9.60亿", "15.0%", "9.00亿", "20.0%", "112.00亿", "12.0%", "1.20", "6.00", "1.40", "3.00", "0.60", "22.0%", "47.0%", "8.5%", "8.0%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "38.0%"],
            ["2026-03-31", "3.00亿", "25.0%", "2.80亿", "22.0%", "30.00亿", "8.0%", "0.35", "6.20", "1.45", "3.20", "0.18", "21.0%", "46.0%", "8.2%", "7.8%", "115.0", "4.1", "88.0", "40.0", "1.55", "1.18", "1.05", "1.85", "39.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 10_000_000_000.0, "yoy": 0.10},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 11_200_000_000.0, "yoy": 0.12},
            {"report_date": "2026-03-31", "metric_name": "accounts_receivable", "value": 12_000_000_000.0, "yoy": 0.15},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 8_000_000_000.0, "yoy": 0.08},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 8_800_000_000.0, "yoy": 0.10},
            {"report_date": "2026-03-31", "metric_name": "inventory", "value": 9_200_000_000.0, "yoy": 0.11},
            {"report_date": "2024-12-31", "metric_name": "short_term_loans", "value": 10_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "short_term_loans", "value": 12_000_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "short_term_loans", "value": 12_500_000_000.0},
            {"report_date": "2024-12-31", "metric_name": "long_term_loan", "value": 20_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "long_term_loan", "value": 21_000_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "long_term_loan", "value": 21_500_000_000.0},
            {"report_date": "2024-12-31", "metric_name": "bonds_payable", "value": 5_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "bonds_payable", "value": 7_000_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "bonds_payable", "value": 7_200_000_000.0},
            {"report_date": "2024-12-31", "metric_name": "lease_debt", "value": 2_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "lease_debt", "value": 2_500_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "lease_debt", "value": 2_600_000_000.0},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2024-12-31", "metric_name": "pay_fixed_assets_etc_cash", "value": 3_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "pay_fixed_assets_etc_cash", "value": 3_600_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "act_cash_flow_net", "value": 3_500_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "pay_fixed_assets_etc_cash", "value": 1_000_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "parent_holder_net_profit", "value": 3_000_000_000.0},
        ]
    )
    pe_series = pd.DataFrame(
        [
            {"date": "2024-01-01", "value": 12.0},
            {"date": "2025-01-01", "value": 18.0},
            {"date": "2026-05-09", "value": 15.0},
        ]
    )
    pb_series = pd.DataFrame(
        [
            {"date": "2026-05-09", "value": 3.2},
        ]
    )
    market_cap_series = pd.DataFrame(
        [
            {"date": "2026-05-09", "value": 520.0},
        ]
    )

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot("300124", name="汇川技术")

    assert result.snapshot.symbol == "300124"
    assert result.snapshot.market == "CN"
    assert result.snapshot.report_period == date(2025, 12, 31)
    assert result.snapshot.roe == 22.0
    assert result.snapshot.roe_3y_cv is not None
    assert result.snapshot.accounts_receivable_growth == 0.12
    assert result.snapshot.inventory_growth == 0.10
    assert result.snapshot.pe_ttm == 15.0
    assert result.snapshot.peg == 1.0
    assert result.snapshot.pb == 3.2
    assert result.snapshot.market_cap == 520.0
    assert result.snapshot.gross_margin == 47.0
    assert result.snapshot.gross_margin_trend == "improving"
    assert result.snapshot.net_margin == 8.5714
    assert result.snapshot.dupont_driver == "margin_turnover"
    assert result.snapshot.equity_multiplier == 1.6129
    assert result.snapshot.asset_turnover == 1.5913
    assert result.snapshot.interest_bearing_debt_growth == 14.8649
    assert result.snapshot.operating_cashflow_growth == 20.0
    assert result.snapshot.capex_to_operating_cashflow == 0.3333
    assert result.snapshot.free_cashflow_yield == 13.8462
    assert result.field_sources is not None
    assert result.field_sources["accounts_receivable_growth"] == "ths.debt"
    assert result.field_sources["inventory_growth"] == "ths.debt"
    assert result.field_sources["interest_bearing_debt_growth"] == "derived.ths.debt"
    assert result.field_sources["peg"] == "derived.pe_ttm+net_profit_growth"
    assert result.field_sources["gross_margin"] == "ths.abstract"
    assert result.field_sources["gross_margin_trend"] == "derived.ths.abstract.gross_margin_history"
    assert result.field_sources["operating_cashflow_growth"] == "derived.ths.cash"
    assert result.field_sources["capex_to_operating_cashflow"] == "derived.ths.cash"
    assert result.field_sources["free_cashflow_yield"] == "derived.ths.cash+baidu.valuation"
    assert result.field_sources["dupont_driver"] == "derived.roe+net_margin+debt_to_asset"
    assert result.field_sources["equity_multiplier"] == "derived.debt_to_asset"
    assert result.field_sources["asset_turnover"] == "derived.roe+net_margin+debt_to_asset"
    assert any("gross_margin_trend is derived" in item for item in result.assumptions)
    assert any("latest annual report period" in item for item in result.assumptions)


def test_fetch_cn_fundamental_snapshot_supplements_dividend_yield_for_nonfinancial_symbol(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2024-12-31", "8.00亿", "20.0%", "7.50亿", "18.0%", "100.00亿", "10.0%", "1.00", "5.00", "1.20", "2.30", "0.50", "20.0%", "45.0%", "8.0%", "7.5%", "120.0", "4.0", "90.0", "45.0", "1.50", "1.10", "1.00", "1.80", "40.0%"],
            ["2025-12-31", "9.60亿", "15.0%", "9.00亿", "20.0%", "112.00亿", "12.0%", "1.20", "6.00", "1.40", "3.00", "0.60", "22.0%", "47.0%", "8.5%", "8.0%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "38.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 10_000_000_000.0, "yoy": 0.10},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 11_200_000_000.0, "yoy": 0.12},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 8_000_000_000.0, "yoy": 0.08},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 8_800_000_000.0, "yoy": 0.10},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 15.0}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 3.2}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 520.0}])
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM": 4.8}])

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot("600900", name="长江电力")

    assert result.snapshot.dividend_yield == 4.8
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "eastmoney.analysis_indicator"
    assert any("dividend_yield" in item for item in result.assumptions)


def test_fetch_cn_fundamental_snapshot_falls_back_to_cninfo_dividend_yield_when_indicator_missing(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2024-12-31", "8.00亿", "20.0%", "7.50亿", "18.0%", "100.00亿", "10.0%", "1.00", "5.00", "1.20", "2.30", "0.50", "20.0%", "45.0%", "8.0%", "7.5%", "120.0", "4.0", "90.0", "45.0", "1.50", "1.10", "1.00", "1.80", "40.0%"],
            ["2025-12-31", "9.60亿", "15.0%", "9.00亿", "20.0%", "112.00亿", "12.0%", "1.20", "6.00", "1.40", "3.00", "0.60", "22.0%", "47.0%", "8.5%", "8.0%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "38.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 10_000_000_000.0, "yoy": 0.10},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 11_200_000_000.0, "yoy": 0.12},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 8_000_000_000.0, "yoy": 0.08},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 8_800_000_000.0, "yoy": 0.10},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 15.0}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 3.2}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 520.0}])
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31"}])
    dividend_history_df = pd.DataFrame(
        [
            {"报告时间": "2025年报", "派息比例": 12.0, "除权日": "2026-05-10"},
            {"报告时间": "2024年报", "派息比例": 8.0, "除权日": "2025-08-01"},
            {"报告时间": "2023年报", "派息比例": 6.0, "除权日": "2024-07-01"},
        ]
    )
    daily_price_df = pd.DataFrame([{"日期": "2026-05-15", "收盘": 40.0}])

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_dividend_history_df", lambda symbol: dividend_history_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_daily_price_df", lambda symbol: daily_price_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot("600900", name="长江电力")

    assert result.snapshot.dividend_yield == 5.0
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "cninfo.dividend_history+eastmoney.daily_price"
    assert any("CNInfo cash dividend records" in item for item in result.assumptions)


def test_fetch_cn_fundamental_snapshot_falls_back_to_cninfo_dividend_yield_for_financial_symbol(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2025-12-31", "80.00亿", "2.18%", "78.50亿", "2.02%", "980.00亿", "2.02%", "1.10", "10.20", "1.20", "2.80", "0.60", "8.38%", "36.41%", "8.0%", "7.5%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "90.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 1.0, "yoy": 0.0},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 1.0, "yoy": 0.0},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 1.0, "yoy": 0.0},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 1.0, "yoy": 0.0},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 6.2}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 0.51}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 1800.0}])
    financial_indicator_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31",
                "核心一级资本充足率": 11.43,
                "不良贷款率": 1.28,
                "拨备覆盖率": 208.38,
                "净息差": 1.20,
            }
        ]
    )
    dividend_history_df = pd.DataFrame(
        [
            {"报告时间": "2025年报", "派息比例": 3.8, "除权日": "2026-03-30"},
            {"报告时间": "2024年报", "派息比例": 3.2, "除权日": "2025-07-15"},
        ]
    )
    daily_price_df = pd.DataFrame([{"日期": "2026-05-15", "收盘": 8.75}])

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_dividend_history_df", lambda symbol: dividend_history_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_daily_price_df", lambda symbol: daily_price_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot("601328", name="交通银行")

    assert result.snapshot.dividend_yield == 8.0
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "cninfo.dividend_history+eastmoney.daily_price"
    assert result.snapshot.core_tier1_ratio == 11.43


def test_fetch_cn_fundamental_snapshot_falls_back_to_pb_implied_price_when_daily_price_unavailable(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2025-12-31", "9.60亿", "15.0%", "9.00亿", "20.0%", "112.00亿", "12.0%", "1.20", "6.00", "1.40", "3.00", "0.60", "22.0%", "47.0%", "8.5%", "8.0%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "38.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 11_200_000_000.0, "yoy": 0.12},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 8_800_000_000.0, "yoy": 0.10},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 15.0}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 4.0}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 520.0}])
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31"}])
    dividend_history_df = pd.DataFrame(
        [
            {"报告时间": "2025年报", "派息比例": 12.0, "除权日": "2026-05-10"},
            {"报告时间": "2024年报", "派息比例": 8.0, "除权日": "2025-08-01"},
        ]
    )

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_dividend_history_df", lambda symbol: dividend_history_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_daily_price_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("price unavailable")))
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot("600900", name="长江电力")

    assert result.snapshot.dividend_yield == 8.3333
    assert result.field_sources is not None
    assert result.field_sources["dividend_yield"] == "cninfo.dividend_history+baidu.pb+ths.abstract.book_value_per_share"
    assert any("daily price fetch for dividend_yield fallback failed" in item for item in result.assumptions)


def test_fetch_cn_fundamental_snapshot_can_select_latest_interim_report_period(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2025-12-31", "9.60亿", "15.0%", "9.00亿", "20.0%", "112.00亿", "12.0%", "1.20", "6.00", "1.40", "3.00", "0.60", "22.0%", "47.0%", "8.5%", "8.0%", "118.0", "4.2", "87.0", "42.0", "1.60", "1.20", "1.10", "1.90", "38.0%"],
            ["2026-03-31", "2.60亿", "8.0%", "2.40亿", "7.0%", "30.00亿", "5.5%", "0.32", "6.40", "1.45", "3.05", "0.18", "23.0%", "48.0%", "8.6%", "8.1%", "118.0", "4.2", "87.0", "42.0", "1.62", "1.22", "1.11", "1.92", "37.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 11_200_000_000.0, "yoy": 0.12},
            {"report_date": "2026-03-31", "metric_name": "accounts_receivable", "value": 11_500_000_000.0, "yoy": 0.09},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 8_800_000_000.0, "yoy": 0.10},
            {"report_date": "2026-03-31", "metric_name": "inventory", "value": 8_700_000_000.0, "yoy": 0.04},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "act_cash_flow_net", "value": 2_800_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 9_600_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "parent_holder_net_profit", "value": 2_600_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 15.0}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 3.2}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 520.0}])
    financial_indicator_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31", "股息率TTM": 4.8},
        {"REPORT_DATE": "2026-03-31", "股息率TTM": 5.1},
    ])

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_dividend_history_df", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_daily_price_df", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = cn_fetcher.fetch_cn_fundamental_snapshot(
        "600900",
        name="长江电力",
        report_period_preference="latest_interim",
    )

    assert result.snapshot.report_period == date(2026, 3, 31)
    assert result.snapshot.period_type == "report"
    assert result.snapshot.revenue_growth == 5.5
    assert result.snapshot.dividend_yield == 5.1


def test_fetch_cn_period_snapshots_returns_newer_interim_when_available(monkeypatch):
    annual = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="600900",
            name="长江电力",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
        )
    )
    interim = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="600900",
            name="长江电力",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
        )
    )

    def fake_fetch(symbol: str, name: str | None = None, report_period_preference: str = "annual_preferred"):
        return annual if report_period_preference == "annual_preferred" else interim

    monkeypatch.setattr(cn_fetcher, "fetch_cn_fundamental_snapshot", fake_fetch)

    result = cn_fetcher.fetch_cn_period_snapshots("600900", name="长江电力")

    assert result.annual.snapshot.report_period == date(2025, 12, 31)
    assert result.interim is not None
    assert result.interim.snapshot.report_period == date(2026, 3, 31)


def test_fetch_and_analyze_cn_blended_fundamentals_combines_annual_and_q1_scores(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="600900",
            name="长江电力",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=14.2,
            roe_3y_cv=0.09,
            operating_cashflow_to_profit=1.26,
            revenue_growth=7.5,
            net_profit_growth=8.4,
            dividend_yield=3.6,
            pe_percentile_5y=55.0,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="600900",
        name="长江电力",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="utility",
        submodel_id="utility_operator_v1",
        submodel_version="v1",
        total_score=70.0,
        rating="B",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="600900",
            name="长江电力",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            revenue_growth=12.0,
            net_profit_growth=10.0,
            operating_cashflow_to_profit=1.1,
            debt_to_asset=56.0,
        ),
        assumptions=("interim",),
    )

    monkeypatch.setattr(
        importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended"),
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended"),
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("600900", name="长江电力")

    assert result.blended.annual_weight == 0.8
    assert result.blended.interim_weight == 0.2
    assert result.interim_overlay is not None
    assert result.interim_overlay.overlay_score > 0
    assert result.blended.blended_total_score > 56.0
    assert result.blended.freshness_label == "q1_refresh"


def test_fetch_and_analyze_cn_blended_fundamentals_smooths_utility_q1_cashflow_refresh(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="000591",
            name="太阳能",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=3.47,
            roe_3y_cv=0.2789,
            operating_cashflow_to_profit=5.0246,
            operating_cashflow_to_profit_history=[5.0246, 1.5422, 1.506],
            revenue_growth=-17.91,
            net_profit_growth=-32.87,
            dividend_yield=2.0024,
            pe_percentile_5y=100.0,
            debt_to_asset=53.89,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="000591",
        name="太阳能",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="utility",
        submodel_id="utility_operator_v1",
        submodel_version="v1",
        total_score=44.76,
        rating="D",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="000591",
            name="太阳能",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            revenue_growth=-18.4,
            net_profit_growth=-36.51,
            operating_cashflow_to_profit=0.1304,
            operating_cashflow_to_profit_history=[0.1304, 5.0246, 2.7351],
            debt_to_asset=56.32,
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("000591", name="太阳能")

    assert result.interim_overlay is not None
    component_scores = {component.component: component.score for component in result.interim_overlay.components}
    assert component_scores["growth_refresh"] == 0.0
    assert component_scores["cashflow_refresh"] > 0.0
    assert round(component_scores["resilience_refresh"], 2) == 45.60
    assert result.interim_overlay.overlay_score > 11.0


def test_fetch_and_analyze_cn_blended_fundamentals_supports_industrial_automation_overlay(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="300124",
            name="汇川技术",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=19.4,
            roe_3y_cv=0.16,
            operating_cashflow_to_profit=1.12,
            revenue_growth=18.0,
            net_profit_growth=20.5,
            accounts_receivable_growth=14.0,
            inventory_growth=12.0,
            pe_percentile_5y=48.0,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="300124",
        name="汇川技术",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="technology",
        submodel_id="industrial_automation_v1",
        submodel_version="v1",
        total_score=67.81,
        rating="B",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="300124",
            name="汇川技术",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            revenue_growth=21.0,
            net_profit_growth=18.0,
            operating_cashflow_to_profit=1.05,
            operating_cashflow_to_profit_history=[1.05, 1.12, 1.08],
            accounts_receivable_growth=9.0,
            inventory_growth=7.0,
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("300124", name="汇川技术")

    assert result.interim_overlay is not None
    assert result.blended.freshness_label == "q1_refresh"
    assert {component.component for component in result.interim_overlay.components} == {
        "growth_refresh",
        "cashflow_refresh",
        "operating_cycle_refresh",
    }
    assert result.blended.interim_weight == 0.2


def test_fetch_and_analyze_cn_blended_fundamentals_smooths_industrial_q1_cashflow_refresh(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="300124",
            name="汇川技术",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=16.34,
            roe_3y_cv=0.1357,
            operating_cashflow_to_profit=1.323,
            operating_cashflow_to_profit_history=[1.323, 1.6802, 0.7107],
            revenue_growth=21.77,
            net_profit_growth=17.84,
            accounts_receivable_growth=0.08,
            inventory_growth=0.16,
            pe_percentile_5y=73.41,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="300124",
        name="汇川技术",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="technology",
        submodel_id="industrial_automation_v1",
        submodel_version="v1",
        total_score=67.81,
        rating="B",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="300124",
            name="汇川技术",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            revenue_growth=12.98,
            net_profit_growth=-23.39,
            operating_cashflow_to_profit=0.0928,
            operating_cashflow_to_profit_history=[0.0928, 1.323, 0.924],
            accounts_receivable_growth=-6.53,
            inventory_growth=-6.45,
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("300124", name="汇川技术")

    assert result.interim_overlay is not None
    component_scores = {component.component: component.score for component in result.interim_overlay.components}
    assert component_scores["growth_refresh"] < 40.0
    assert component_scores["cashflow_refresh"] > 0.0
    assert component_scores["operating_cycle_refresh"] == 100.0
    assert result.interim_overlay.overlay_score > 54.73


def test_fetch_and_analyze_cn_blended_fundamentals_annualizes_bank_q1_roe_refresh(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601328",
            name="交通银行",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=8.38,
            core_tier1_ratio=11.43,
            npl_ratio=1.28,
            provision_coverage_ratio=208.38,
            net_interest_margin=1.2,
            loan_deposit_growth_gap=-0.5398,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="601328",
        name="交通银行",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="financial",
        submodel_id="bank_v1",
        submodel_version="v1",
        total_score=64.22,
        rating="C",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601328",
            name="交通银行",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            roe=2.27,
            core_tier1_ratio=11.25,
            npl_ratio=1.3,
            provision_coverage_ratio=202.8,
            net_interest_margin=1.23,
            loan_deposit_growth_gap=-0.5398,
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("601328", name="交通银行")

    assert result.interim_overlay is not None
    components = {component.component: component for component in result.interim_overlay.components}
    profitability_refresh = components["profitability_refresh"]
    assert profitability_refresh.score > 1.75
    assert profitability_refresh.covered_metrics == ("roe", "net_interest_margin")
    assert profitability_refresh.note is not None
    assert "年化 ROE" in profitability_refresh.note


def test_fetch_and_analyze_cn_blended_fundamentals_supports_game_content_overlay(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=22.0,
            operating_cashflow_to_profit=1.18,
            operating_cashflow_to_profit_history=[1.18, 1.02],
            revenue_growth=16.0,
            net_profit_growth=24.0,
            pe_percentile_5y=43.0,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="002555",
        name="三七互娱",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="technology",
        submodel_id="game_content_v1",
        submodel_version="v1",
        total_score=62.36,
        rating="C",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            roe=18.0,
            revenue_growth=12.0,
            net_profit_growth=10.0,
            operating_cashflow_to_profit=1.01,
            operating_cashflow_to_profit_history=[1.01, 1.18, 1.05],
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("002555", name="三七互娱")

    assert result.interim_overlay is not None
    assert result.blended.freshness_label == "q1_refresh"
    assert {component.component for component in result.interim_overlay.components} == {
        "growth_refresh",
        "cashflow_refresh",
        "profit_quality_refresh",
    }
    assert result.blended.interim_weight == 0.2


def test_fetch_and_analyze_cn_blended_fundamentals_smooths_game_q1_overlay(monkeypatch):
    annual_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="annual",
            roe=21.73,
            operating_cashflow_to_profit=1.22,
            operating_cashflow_to_profit_history=[1.22, 1.1216, 1.1837],
            revenue_growth=-8.46,
            net_profit_growth=8.5,
            pe_percentile_5y=38.95,
        ),
        assumptions=("annual",),
    )
    annual_scorecard = FundamentalScoreCard(
        symbol="002555",
        name="三七互娱",
        market="CN",
        report_period=date(2025, 12, 31),
        industry_bucket="technology",
        submodel_id="game_content_v1",
        submodel_version="v1",
        total_score=62.36,
        rating="C",
        red_flag=False,
        dimension_scores=[],
        strengths=[],
        risks=[],
        warnings=[],
        focus_questions=[],
        missing_metrics=[],
        triggered_rules=[],
    )
    interim_fetch = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            period_type="report",
            roe=6.22,
            revenue_growth=-12.32,
            net_profit_growth=59.02,
            operating_cashflow_to_profit=0.4203,
            operating_cashflow_to_profit_history=[0.4203, 1.22, 1.2654],
        ),
        assumptions=("interim",),
    )

    blended_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_blended")
    monkeypatch.setattr(
        blended_module,
        "fetch_cn_period_snapshots",
        lambda symbol, name=None: cn_fetcher.CnPeriodSnapshotsFetchResult(annual=annual_fetch, interim=interim_fetch),
    )
    monkeypatch.setattr(
        blended_module,
        "_analyze_cn_fetched_snapshot",
        lambda fetched, submodel=None, manual_supplement=None, manual_supplement_path=None: SimpleNamespace(
            fetched=annual_fetch,
            scorecard=annual_scorecard,
            assumptions=("annual",),
        ),
    )

    result = fetch_and_analyze_cn_blended_fundamentals("002555", name="三七互娱")

    assert result.interim_overlay is not None
    component_scores = {component.component: component.score for component in result.interim_overlay.components}
    assert component_scores["growth_refresh"] == 50.0
    assert component_scores["cashflow_refresh"] > 0.0
    assert component_scores["profit_quality_refresh"] > 0.0
    assert result.interim_overlay.overlay_score > 20.0


def test_fetch_and_analyze_cn_snapshot_builds_game_content_scorecard(monkeypatch):
    fake_fetch_result = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=23.4,
            operating_cashflow_to_profit=1.18,
            operating_cashflow_to_profit_history=[1.18, 1.05, 1.01],
            revenue_growth=11.5,
            net_profit_growth=18.2,
            pe_percentile_5y=38.0,
            pe_ttm=15.3,
        ),
        assumptions=("unit-test-cn",),
    )
    monkeypatch.setattr(
        cn_fetch_service_module,
        "fetch_cn_fundamental_snapshot",
        lambda symbol, name=None: fake_fetch_result,
    )

    result = fetch_and_analyze_cn_snapshot("002555", name="三七互娱")

    assert result.scorecard.submodel_id == "game_content_v1"
    assert result.scorecard.rating in {"A", "B", "C", "D"}
    assert result.assumptions[0] == "unit-test-cn"


def test_fetch_and_analyze_cn_snapshot_warns_when_forced_to_quarterly_period(monkeypatch):
    fake_fetch_result = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="002555",
            name="三七互娱",
            market="CN",
            report_period=date(2026, 3, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-12T00:00:00").to_pydatetime(),
            roe=6.22,
            roe_3y_cv=0.43,
            operating_cashflow_to_profit=0.42,
            operating_cashflow_to_profit_history=[0.42, 0.81, 1.13],
            revenue_growth=-12.32,
            net_profit_growth=59.02,
            pe_percentile_5y=48.03,
            peg=0.26,
            net_margin=23.4677,
            asset_turnover=0.1728,
            equity_multiplier=1.5335,
            dupont_driver="margin_turnover",
            period_type="report",
        ),
        assumptions=("unit-test-cn-quarter",),
    )
    monkeypatch.setattr(
        cn_fetch_service_module,
        "fetch_cn_fundamental_snapshot",
        lambda symbol, name=None: fake_fetch_result,
    )

    result = fetch_and_analyze_cn_snapshot("002555", name="三七互娱")

    assert any("2026-03-31 的一季报口径" in item for item in result.scorecard.warnings)
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "警告" in report_text
    assert "一季报口径" in report_text
    brief_text = render_fundamental_brief(result.scorecard, result.fetched.snapshot)
    assert "警告:" in brief_text
    assert "不要直接与年报口径标的横向比较" in brief_text


def test_fetch_and_analyze_cn_snapshot_builds_bank_scorecard_with_financial_fields(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            ["2024-12-31", "8.00亿", "8.0%", "7.50亿", "7.0%", "100.00亿", "6.0%", "1.00", "5.00", "1.20", "2.30", "0.50", "10.5%", "45.0%", "8.0%", "7.5%", "120.0", "4.0", "90.0", "45.0", "1.50", "1.10", "1.00", "1.80", "91.0%"],
            ["2025-12-31", "8.80亿", "10.0%", "8.00亿", "9.0%", "105.00亿", "7.0%", "1.10", "5.30", "1.30", "2.50", "0.56", "11.2%", "46.0%", "8.1%", "7.7%", "118.0", "4.1", "88.0", "43.0", "1.55", "1.15", "1.02", "1.85", "90.0%"],
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 10_000_000.0, "yoy": 0.03},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 10_300_000.0, "yoy": 0.03},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 2_000_000.0, "yoy": 0.01},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 2_040_000.0, "yoy": 0.02},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 9_600_000_000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 8_800_000_000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 6.2}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 0.72}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 2300.0}])
    financial_indicator_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31",
                "资本充足率": 13.4,
                "核心一级资本充足率": 9.82,
                "不良贷款率": 1.31,
                "拨备覆盖率": 242.0,
                "净息差": 1.28,
                "贷款增速": 7.4,
                "存款增速": 5.9,
                "股息率TTM": 5.6,
            }
        ]
    )

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = fetch_and_analyze_cn_snapshot("601328", name="交通银行")

    assert result.scorecard.submodel_id == "bank_v1"
    assert result.fetched.snapshot.core_tier1_ratio == 9.82
    assert result.fetched.snapshot.loan_deposit_growth_gap == 1.5
    assert result.fetched.snapshot.dividend_yield == 5.6
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["core_tier1_ratio"] == "eastmoney.analysis_indicator"
    assert any("Financial-sector fields are supplemented" in item for item in result.assumptions)


def test_fetch_and_analyze_cn_snapshot_accepts_manual_supplement_for_energy_fields(monkeypatch):
    fake_fetch_result = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601088",
            name="中国神华",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=12.8,
            net_margin=10.5,
            asset_turnover=0.83,
            equity_multiplier=1.4085,
            dupont_driver="margin_turnover",
            operating_cashflow_to_profit=1.22,
            operating_cashflow_to_profit_history=[1.22, 1.15, 1.04],
            debt_to_asset=29.0,
            pe_percentile_5y=68.0,
        ),
        assumptions=("unit-test-cn-energy",),
        field_sources={
            "roe": "unit-test",
                "net_margin": "unit-test",
                "asset_turnover": "unit-test",
                "equity_multiplier": "unit-test",
                "dupont_driver": "unit-test",
            "operating_cashflow_to_profit": "unit-test",
            "operating_cashflow_to_profit_history": "unit-test",
            "debt_to_asset": "unit-test",
            "pe_percentile_5y": "unit-test",
        },
        raw_payload_refs=("unit-test:601088",),
    )
    monkeypatch.setattr(
        cn_fetch_service_module,
        "fetch_cn_fundamental_snapshot",
        lambda symbol, name=None: fake_fetch_result,
    )

    result = fetch_and_analyze_cn_snapshot(
        "601088",
        name="中国神华",
        manual_supplement={
            "dividend_yield": 6.3,
            "capex_to_operating_cashflow": 0.42,
            "unit_cost_position": 0.82,
            "reserve_life_index": 14.5,
            "commodity_price_sensitivity": 0.46,
            "notes": "manual supplement from annual report",
        },
    )

    assert result.scorecard.submodel_id == "energy_resource_v1"
    assert result.fetched.snapshot.dividend_yield == 6.3
    assert result.fetched.snapshot.reserve_life_index == 14.5
    assert result.fetched.snapshot.notes == "manual supplement from annual report"
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["dividend_yield"] == "manual.supplement"
    assert result.fetched.field_sources["commodity_price_sensitivity"] == "manual.supplement"
    assert "manual-supplement:601088" in result.fetched.raw_payload_refs
    assert any("Manual supplement applied before analysis" in item for item in result.assumptions)
    assert any("以下字段当前使用手工补充口径" in item for item in result.scorecard.warnings)
    assert any("能源资源手工补充字段可能包含研究口径或公告摘要口径" in item for item in result.scorecard.warnings)

    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "警告" in report_text
    assert "以下字段当前使用手工补充口径" in report_text

    brief_text = render_fundamental_brief(
        scorecard=result.scorecard,
        snapshot=result.fetched.snapshot,
        field_sources=result.fetched.field_sources,
    )
    assert "警告:" in brief_text
    assert "以下字段当前使用手工补充口径" in brief_text
    assert "杜邦拆解:" in brief_text


def test_fetch_and_analyze_cn_snapshot_rejects_disallowed_manual_supplement_fields(monkeypatch):
    fake_fetch_result = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601088",
            name="中国神华",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=12.8,
            operating_cashflow_to_profit=1.22,
            operating_cashflow_to_profit_history=[1.22, 1.15, 1.04],
            debt_to_asset=29.0,
            pe_percentile_5y=68.0,
        ),
    )
    monkeypatch.setattr(
        cn_fetch_service_module,
        "fetch_cn_fundamental_snapshot",
        lambda symbol, name=None: fake_fetch_result,
    )

    try:
        fetch_and_analyze_cn_snapshot(
            "601088",
            name="中国神华",
            manual_supplement={"market_cap": 1000.0},
        )
    except ValueError as exc:
        assert "Manual supplement fields are not allowed for energy_resource_v1: market_cap" == str(exc)
    else:
        raise AssertionError("expected ValueError for disallowed manual supplement field")


def test_fetch_and_analyze_cn_snapshot_accepts_manual_supplement_path(monkeypatch, tmp_path):
    fake_fetch_result = cn_fetcher.FundamentalSnapshotFetchResult(
        snapshot=cn_fetcher.FundamentalSnapshot(
            symbol="601088",
            name="中国神华",
            market="CN",
            report_period=date(2025, 12, 31),
            currency="CNY",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=12.8,
            operating_cashflow_to_profit=1.22,
            operating_cashflow_to_profit_history=[1.22, 1.15, 1.04],
            debt_to_asset=29.0,
            pe_percentile_5y=68.0,
        ),
        assumptions=("unit-test-cn-energy",),
    )
    monkeypatch.setattr(
        cn_fetch_service_module,
        "fetch_cn_fundamental_snapshot",
        lambda symbol, name=None: fake_fetch_result,
    )

    brief_path = tmp_path / "601088_中国神华_fundamental_brief.txt"
    brief_path.write_text(
        """中国神华基本面简报

手工补充字段:
- dividend_yield=6.3
- capex_to_operating_cashflow=0.42
- unit_cost_position=0.82
- reserve_life_index=14.5
- commodity_price_sensitivity=0.46
- notes=manual supplement from annual report
""",
        encoding="utf-8",
    )

    result = fetch_and_analyze_cn_snapshot(
        "601088",
        name="中国神华",
        manual_supplement_path=str(brief_path),
    )

    assert result.scorecard.submodel_id == "energy_resource_v1"
    assert result.fetched.snapshot.dividend_yield == 6.3
    assert result.fetched.snapshot.reserve_life_index == 14.5
    assert result.fetched.snapshot.notes == "manual supplement from annual report"
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["dividend_yield"] == "manual.supplement"
    assert any("Manual supplement applied before analysis" in item for item in result.assumptions)


def test_fetch_and_analyze_hk_snapshot_builds_insurance_scorecard_with_financial_fields(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
                "综合偿付能力充足率": 218.0,
                "综合成本率": 97.8,
                "总投资收益率": 5.4,
                "内含价值增长率": 8.2,
                "新业务价值增长率": 12.6,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 6.1}])

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)

    result = fetch_and_analyze_hk_snapshot("01339", name="中国人保")

    assert result.scorecard.submodel_id == "insurance_v1"
    assert result.fetched.snapshot.solvency_adequacy_ratio == 218.0
    assert result.fetched.snapshot.dividend_yield == 6.1
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["solvency_adequacy_ratio"] == "eastmoney.analysis"
    assert result.fetched.field_sources["dividend_yield"] == "eastmoney.financial_indicator"
    assert any("Financial-sector fields are supplemented" in item for item in result.assumptions)
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "计算:" in report_text
    assert "综合偿付能力充足率 218.00" in report_text
    assert "×30/100=" in report_text


def test_fetch_hk_fundamental_snapshot_keeps_insurance_analysis_fields_when_indicator_fetch_fails(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
                "综合偿付能力充足率": 218.0,
                "综合成本率": 97.8,
                "总投资收益率": 5.4,
                "内含价值增长率": 8.2,
                "新业务价值增长率": 12.6,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)

    def boom(symbol: str) -> pd.DataFrame:
        raise RuntimeError("indicator endpoint unavailable")

    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", boom)
    monkeypatch.setattr(fetcher, "_fetch_hk_official_financial_fields", lambda symbol: ({}, (), (), {}))

    result = fetcher.fetch_hk_fundamental_snapshot("01339", name="中国人保")

    assert result.snapshot.solvency_adequacy_ratio == 218.0
    assert result.snapshot.combined_ratio == 97.8
    assert result.snapshot.investment_return == 5.4
    assert result.snapshot.embedded_value_growth == 8.2
    assert result.snapshot.new_business_value_growth == 12.6
    assert result.field_sources is not None
    assert result.field_sources["solvency_adequacy_ratio"] == "eastmoney.analysis"
    assert any("indicator endpoint unavailable" in item for item in result.assumptions)


def test_extract_hk_financial_indicator_fields_tracks_per_field_sources():
    analysis_row = pd.Series(
        {
            "REPORT_DATE": "2025-12-31 00:00:00",
            "综合偿付能力充足率": 218.0,
            "综合成本率": 97.8,
            "总投资收益率": 5.4,
            "内含价值增长率": 8.2,
            "新业务价值增长率": 12.6,
        }
    )
    financial_indicator_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31",
                "股息率TTM(%)": 6.1,
            }
        ]
    )

    updates, assumptions, field_sources = fetcher._extract_hk_financial_indicator_fields(
        analysis_row,
        financial_indicator_df,
        date(2025, 12, 31),
    )

    assert assumptions == ()
    assert updates == {
        "solvency_adequacy_ratio": 218.0,
        "combined_ratio": 97.8,
        "investment_return": 5.4,
        "embedded_value_growth": 8.2,
        "new_business_value_growth": 12.6,
        "dividend_yield": 6.1,
    }
    assert field_sources == {
        "solvency_adequacy_ratio": "eastmoney.analysis",
        "combined_ratio": "eastmoney.analysis",
        "investment_return": "eastmoney.analysis",
        "embedded_value_growth": "eastmoney.analysis",
        "new_business_value_growth": "eastmoney.analysis",
        "dividend_yield": "eastmoney.financial_indicator",
    }


def test_extract_hk_financial_indicator_fields_tracks_broker_net_capital_source():
    analysis_row = pd.Series(
        {
            "REPORT_DATE": "2025-12-31 00:00:00",
            "净资本比率": 182.0,
        }
    )
    financial_indicator_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31",
                "股息率TTM(%)": 4.2,
            }
        ]
    )

    updates, assumptions, field_sources = fetcher._extract_hk_financial_indicator_fields(
        analysis_row,
        financial_indicator_df,
        date(2025, 12, 31),
    )

    assert assumptions == ()
    assert updates == {
        "net_capital_ratio": 182.0,
        "dividend_yield": 4.2,
    }
    assert field_sources == {
        "net_capital_ratio": "eastmoney.analysis",
        "dividend_yield": "eastmoney.financial_indicator",
    }


def test_fetch_hk_fundamental_snapshot_prefers_same_period_financial_indicator_row(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-06-30", "股息率TTM(%)": 7.3},
            {"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 6.1},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)

    result = fetcher.fetch_hk_fundamental_snapshot("01339", name="中国人保")

    assert result.snapshot.dividend_yield == 6.1
    assert not any("HK financial indicator fallback" in item for item in result.assumptions)


def test_fetch_hk_fundamental_snapshot_warns_when_financial_indicator_period_falls_back(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 11.8,
                "OPERATE_INCOME_YOY": 8.5,
                "HOLDER_PROFIT_YOY": 14.2,
                "DEBT_ASSET_RATIO": 78.0,
                "CURRENT_RATIO": 1.1,
                "HOLDER_PROFIT": 22000000000.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["01339", "中国人保", 6.8, 32.0, 6.8, 32.0, 0.72, 41.0, 0.72, 41.0, 0.95, 44.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 26000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 110.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 100.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 105.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 100.0},
        ]
    )
    financial_indicator_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2026-06-30", "股息率TTM(%)": 7.3},
        ]
    )

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)

    result = fetcher.fetch_hk_fundamental_snapshot("01339", name="中国人保")

    assert result.snapshot.dividend_yield == 7.3
    assert any("no exact row for 2025-12-31" in item for item in result.assumptions)
    assert any("latest available indicator period 2026-06-30" in item for item in result.assumptions)


def test_fetch_and_analyze_hk_snapshot_warns_when_insurance_uses_official_solvency_disclosure(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=11.8,
            roe_3y_cv=0.16,
            pb=0.72,
            dividend_yield=5.9,
            solvency_adequacy_ratio=275.7,
            combined_ratio=97.8,
            investment_return=5.4,
            embedded_value_growth=8.2,
            new_business_value_growth=12.6,
        ),
        assumptions=(
            "PICC official solvency report fallback supplemented solvency_adequacy_ratio from the latest public solvency report disclosure; this official source can lag the annual report period.",
            "Latest PICC solvency report disclosure date used for fallback: 2025-09-24.",
        ),
        field_sources={
            "roe": "unit-test",
            "roe_3y_cv": "unit-test",
            "pb": "unit-test",
            "dividend_yield": "unit-test",
            "solvency_adequacy_ratio": "official.solvency_report",
            "combined_ratio": "unit-test",
            "investment_return": "unit-test",
            "embedded_value_growth": "unit-test",
            "new_business_value_growth": "unit-test",
        },
        raw_payload_refs=("official-solvency-report:01339:https://example.com/solvency.pdf",),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot("01339", name="中国人保")
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)

    assert any("官网偿付能力报告摘要" in item for item in result.scorecard.warnings)
    assert any("2025-09-24" in item for item in result.scorecard.warnings)
    assert "警告" in report_text
    assert "官网偿付能力报告摘要" in report_text


def test_fetch_and_analyze_hk_snapshot_warns_when_forced_to_non_annual_period(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="01339",
            name="中国人保",
            market="HK",
            report_period=date(2026, 6, 30),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-12T00:00:00").to_pydatetime(),
            roe=11.8,
            roe_3y_cv=0.16,
            pb=0.72,
            dividend_yield=5.9,
            solvency_adequacy_ratio=275.7,
            combined_ratio=97.8,
            investment_return=5.4,
            embedded_value_growth=8.2,
            new_business_value_growth=12.6,
            period_type="report",
        ),
        assumptions=("unit-test-hk-nonannual",),
        field_sources={
            "roe": "unit-test",
            "roe_3y_cv": "unit-test",
            "pb": "unit-test",
            "dividend_yield": "unit-test",
            "solvency_adequacy_ratio": "unit-test",
            "combined_ratio": "unit-test",
            "investment_return": "unit-test",
            "embedded_value_growth": "unit-test",
            "new_business_value_growth": "unit-test",
        },
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot("01339", name="中国人保")

    assert any("2026-06-30 的中报口径" in item for item in result.scorecard.warnings)
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "警告" in report_text
    assert "中报口径" in report_text
    brief_text = render_fundamental_brief(result.scorecard, result.fetched.snapshot)
    assert "警告:" in brief_text
    assert "不要直接与年报口径标的横向比较" in brief_text


def test_fetch_and_analyze_hk_snapshot_warns_when_broker_uses_annual_report_proxy(monkeypatch):
    fake_fetch_result = fetcher.FundamentalSnapshotFetchResult(
        snapshot=fetcher.FundamentalSnapshot(
            symbol="06886",
            name="华泰证券",
            market="HK",
            report_period=date(2025, 12, 31),
            currency="HKD",
            source="unit-test",
            updated_at=pd.Timestamp("2026-05-10T00:00:00").to_pydatetime(),
            roe=10.2,
            roe_3y_cv=0.14,
            pb=0.88,
            dividend_yield=4.2,
            net_capital_ratio=298.67,
            revenue_growth=11.3,
            net_profit_growth=13.1,
        ),
        assumptions=(
            "Huatai official annual report fallback mapped 风险覆盖率 to net_capital_ratio because current public HK APIs do not expose a direct broker net capital ratio field.",
        ),
        field_sources={
            "roe": "unit-test",
            "roe_3y_cv": "unit-test",
            "pb": "unit-test",
            "dividend_yield": "unit-test",
            "net_capital_ratio": "official.annual_report_proxy",
            "revenue_growth": "unit-test",
            "net_profit_growth": "unit-test",
        },
        raw_payload_refs=("official-annual-report:06886:https://example.com/report.pdf",),
    )
    monkeypatch.setattr(
        fetch_service_module,
        "fetch_hk_fundamental_snapshot",
        lambda symbol, name=None, quote_overlay_source=None: fake_fetch_result,
    )

    result = fetch_and_analyze_hk_snapshot("06886", name="华泰证券")
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)

    assert any("风险覆盖率代理映射" in item for item in result.scorecard.warnings)
    assert "警告" in report_text
    assert "风险覆盖率代理映射" in report_text


def test_fetch_and_analyze_hk_snapshot_builds_broker_scorecard_with_financial_fields(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": 10.2,
                "OPERATE_INCOME_YOY": 11.3,
                "HOLDER_PROFIT_YOY": 13.1,
                "DEBT_ASSET_RATIO": 72.0,
                "CURRENT_RATIO": 1.05,
                "HOLDER_PROFIT": 18000000000.0,
                "净资本比率": 182.0,
            }
        ]
    )
    valuation_df = pd.DataFrame([["06886", "华泰证券", 8.1, 36.0, 8.1, 36.0, 0.88, 48.0, 0.88, 48.0, 1.02, 46.0]])
    cashflow_df = pd.DataFrame([
        {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "003999", "AMOUNT": 20000000000.0},
    ])
    balance_df = pd.DataFrame(
        [
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 90.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002003", "AMOUNT": 80.0},
            {"REPORT_DATE": "2025-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 85.0},
            {"REPORT_DATE": "2024-12-31 00:00:00", "STD_ITEM_CODE": "004002001", "AMOUNT": 80.0},
        ]
    )
    financial_indicator_df = pd.DataFrame([{"REPORT_DATE": "2025-12-31", "股息率TTM(%)": 4.2}])

    monkeypatch.setattr(fetcher, "_fetch_hk_analysis_indicator_df", lambda symbol: analysis_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_valuation_comparison_df", lambda symbol: valuation_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_cashflow_df", lambda symbol, report_dates: cashflow_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_balance_df", lambda symbol, report_dates: balance_df)
    monkeypatch.setattr(fetcher, "_fetch_hk_financial_indicator_df", lambda symbol: financial_indicator_df)

    result = fetch_and_analyze_hk_snapshot("06886", name="华泰证券")

    assert result.scorecard.submodel_id == "broker_v1"
    assert result.fetched.snapshot.net_capital_ratio == 182.0
    assert result.fetched.snapshot.dividend_yield == 4.2
    assert result.fetched.field_sources is not None
    assert result.fetched.field_sources["net_capital_ratio"] == "eastmoney.analysis"
    assert result.fetched.field_sources["dividend_yield"] == "eastmoney.financial_indicator"
    report_text = render_scorecard_text(result.scorecard, snapshot=result.fetched.snapshot)
    assert "净资本比率 182.00" in report_text
    assert "已计分" in report_text
    assert "- notes" not in report_text


def test_fetch_and_analyze_cn_snapshot_supports_named_abstract_schema_and_runtime_relaxes_bank_dividend(monkeypatch):
    abstract_df = pd.DataFrame(
        [
            {
                "报告期": "2024-12-31",
                "净利润": "88.00亿",
                "净利润同比增长率": "8.0%",
                "营业总收入": "105.00亿",
                "营业总收入同比增长率": "6.0%",
                "每股经营现金流": "1.20",
                "净资产收益率": "10.5%",
                "流动比率": "1.20",
                "资产负债率": "91.0%",
            },
            {
                "报告期": "2025-12-31",
                "净利润": "95.00亿",
                "净利润同比增长率": "10.0%",
                "营业总收入": "112.00亿",
                "营业总收入同比增长率": "7.0%",
                "每股经营现金流": "1.30",
                "净资产收益率": "11.2%",
                "流动比率": "1.15",
                "资产负债率": "90.0%",
            },
        ]
    )
    debt_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "accounts_receivable", "value": 10000000.0, "yoy": 0.03},
            {"report_date": "2025-12-31", "metric_name": "accounts_receivable", "value": 10300000.0, "yoy": 0.03},
            {"report_date": "2024-12-31", "metric_name": "inventory", "value": 2000000.0, "yoy": 0.01},
            {"report_date": "2025-12-31", "metric_name": "inventory", "value": 2040000.0, "yoy": 0.02},
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9000000000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 9600000000.0},
        ]
    )
    benefit_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "parent_holder_net_profit", "value": 8000000000.0},
            {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": 8800000000.0},
        ]
    )
    pe_series = pd.DataFrame([{"date": "2026-05-09", "value": 6.2}])
    pb_series = pd.DataFrame([{"date": "2026-05-09", "value": 0.72}])
    market_cap_series = pd.DataFrame([{"date": "2026-05-09", "value": 2300.0}])
    financial_indicator_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2024-12-31",
                "NEWCAPITALADER": 16.02,
                "HXYJBCZL": 10.24,
                "NONPERLOAN": 1.31,
                "BLDKBBL": 201.94,
                "NET_INTEREST_MARGIN": 1.27,
                "TOTALDEPOSITS": 8.633243e12,
                "GROSSLOANS": 8.555122e12,
            },
            {
                "REPORT_DATE": "2025-12-31",
                "NEWCAPITALADER": 15.96,
                "HXYJBCZL": 11.43,
                "NONPERLOAN": 1.28,
                "BLDKBBL": 208.38,
                "NET_INTEREST_MARGIN": 1.20,
                "TOTALDEPOSITS": 9.143510e12,
                "GROSSLOANS": 9.123571e12,
            },
        ]
    )

    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_abstract_df", lambda symbol: abstract_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_debt_df", lambda symbol: debt_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_cash_df", lambda symbol: cash_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_benefit_df", lambda symbol: benefit_df)
    monkeypatch.setattr(cn_fetcher, "_fetch_cn_financial_analysis_indicator_df", lambda symbol: financial_indicator_df)
    monkeypatch.setattr(
        cn_fetcher,
        "_fetch_cn_valuation_series",
        lambda symbol, indicator, period="近五年": {
            "市盈率(TTM)": pe_series,
            "市净率": pb_series,
            "总市值": market_cap_series,
        }[indicator],
    )

    result = fetch_and_analyze_cn_snapshot("601328", name="交通银行")

    assert result.scorecard.submodel_id == "bank_v1"
    assert result.fetched.snapshot.debt_to_asset == 90.0
    assert result.fetched.snapshot.core_tier1_ratio == 11.43
    assert result.fetched.snapshot.loan_deposit_growth_gap is not None
    assert result.fetched.snapshot.dividend_yield is None
    assert any("dividend_yield is treated as optional" in item for item in result.assumptions)