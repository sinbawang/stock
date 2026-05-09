from __future__ import annotations

from datetime import date
import importlib

import pandas as pd

from fundamental.data import cn_snapshot_fetcher as cn_fetcher
from fundamental.data import hk_snapshot_fetcher as fetcher
from fundamental.services.fetch_and_analyze_cn_snapshot import fetch_and_analyze_cn_snapshot
from fundamental.services.fetch_and_analyze_hk_snapshot import fetch_and_analyze_hk_snapshot

fetch_service_module = importlib.import_module("fundamental.services.fetch_and_analyze_hk_snapshot")
cn_fetch_service_module = importlib.import_module("fundamental.services.fetch_and_analyze_cn_snapshot")


def test_fetch_hk_fundamental_snapshot_builds_snapshot(monkeypatch):
    analysis_df = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "DATE_TYPE_CODE": "001",
                "CURRENCY": "HKD",
                "ROE_AVG": -14.4296,
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
    assert result.snapshot.operating_cashflow_to_profit_history == [0.5915, 1.596, 2.9245]
    assert result.snapshot.accounts_receivable_growth == 0.2
    assert result.snapshot.inventory_growth == 0.1
    assert result.field_sources == {
        "roe": "eastmoney.analysis",
        "revenue_growth": "eastmoney.analysis",
        "net_profit_growth": "eastmoney.analysis",
        "debt_to_asset": "eastmoney.analysis",
        "current_ratio": "eastmoney.analysis",
        "operating_cashflow_to_profit": "eastmoney.cashflow",
        "operating_cashflow_to_profit_history": "eastmoney.cashflow",
        "accounts_receivable_growth": "eastmoney.analysis",
        "inventory_growth": "eastmoney.analysis",
        "pe_ttm": "eastmoney+akshare.valuation",
        "pe_percentile_5y": "eastmoney+akshare.valuation",
        "pb": "eastmoney+akshare.valuation",
        "ps_ttm": "eastmoney+akshare.valuation",
    }
    assert any("PEG is omitted" in item for item in result.assumptions)


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
    assert result.snapshot.report_period == date(2026, 3, 31)
    assert result.snapshot.roe == 21.0
    assert result.snapshot.roe_3y_cv is not None
    assert result.snapshot.accounts_receivable_growth == 0.15
    assert result.snapshot.inventory_growth == 0.11
    assert result.snapshot.pe_ttm == 15.0
    assert result.snapshot.pb == 3.2
    assert result.snapshot.market_cap == 520.0
    assert result.field_sources is not None
    assert result.field_sources["accounts_receivable_growth"] == "ths.debt"
    assert result.field_sources["inventory_growth"] == "ths.debt"


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