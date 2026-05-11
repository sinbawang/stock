from __future__ import annotations

from datetime import date
import importlib
import importlib.util
from pathlib import Path
import sys

import pandas as pd

from fundamental.config.registry import get_submodel_for_symbol
from fundamental.data import cn_snapshot_fetcher as cn_fetcher
from fundamental.data import hk_snapshot_fetcher as fetcher
from fundamental.reporting import render_fundamental_brief, render_scorecard_text
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
find_manual_supplement_path = batch_regenerate_module.find_manual_supplement_path

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
        "accounts_receivable_growth": "eastmoney.analysis",
        "inventory_growth": "eastmoney.analysis",
        "pe_ttm": "eastmoney+akshare.valuation",
        "pe_percentile_5y": "eastmoney+akshare.valuation",
        "pb": "eastmoney+akshare.valuation",
        "ps_ttm": "eastmoney+akshare.valuation",
    }
    assert any("net profit growth" in item for item in result.assumptions)


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
    assert result.field_sources is not None
    assert result.field_sources["peg"] == "derived.pe_ttm+net_profit_growth"
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
        "market_capital": 518976727454.3,
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

    assert result.snapshot.market_cap == 518976727454.3
    assert result.snapshot.dividend_yield == 0.7
    assert result.snapshot.pe_ttm == -12.0
    assert result.snapshot.pb == 3.2
    assert result.snapshot.ps_ttm == 1.28
    assert result.field_sources is not None
    assert result.field_sources["market_cap"] == "xueqiu.quote"
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
    report_text = render_scorecard_text(result.scorecard)
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
        ]
    )
    cash_df = pd.DataFrame(
        [
            {"report_date": "2024-12-31", "metric_name": "act_cash_flow_net", "value": 9_000_000_000.0},
            {"report_date": "2025-12-31", "metric_name": "act_cash_flow_net", "value": 10_800_000_000.0},
            {"report_date": "2026-03-31", "metric_name": "act_cash_flow_net", "value": 3_500_000_000.0},
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
    assert result.snapshot.net_margin == 8.5714
    assert result.snapshot.dupont_driver == "margin_turnover"
    assert result.snapshot.equity_multiplier == 1.6129
    assert result.snapshot.asset_turnover == 1.5913
    assert result.field_sources is not None
    assert result.field_sources["accounts_receivable_growth"] == "ths.debt"
    assert result.field_sources["inventory_growth"] == "ths.debt"
    assert result.field_sources["peg"] == "derived.pe_ttm+net_profit_growth"
    assert result.field_sources["dupont_driver"] == "derived.roe+net_margin+debt_to_asset"
    assert result.field_sources["equity_multiplier"] == "derived.debt_to_asset"
    assert result.field_sources["asset_turnover"] == "derived.roe+net_margin+debt_to_asset"
    assert any("latest annual report period" in item for item in result.assumptions)


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
    report_text = render_scorecard_text(result.scorecard)
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

    report_text = render_scorecard_text(result.scorecard)
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
    assert result.fetched.field_sources["solvency_adequacy_ratio"] == "eastmoney.financial_indicator"
    assert any("Financial-sector fields are supplemented" in item for item in result.assumptions)
    report_text = render_scorecard_text(result.scorecard)
    assert "计算:" in report_text
    assert "综合偿付能力充足率 218.00" in report_text
    assert "×30/100=" in report_text


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
    report_text = render_scorecard_text(result.scorecard)

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
    report_text = render_scorecard_text(result.scorecard)
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
    report_text = render_scorecard_text(result.scorecard)

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
    assert result.fetched.field_sources["net_capital_ratio"] == "eastmoney.financial_indicator"
    report_text = render_scorecard_text(result.scorecard)
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