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