from __future__ import annotations

from datetime import date, datetime
import importlib
import importlib.util
from pathlib import Path
import sys

import pandas as pd

from capital_flow.data import cn_flow_fetcher, hk_flow_fetcher
from capital_flow.models import CapitalFlowSnapshot
from capital_flow.reporting import render_capital_flow_text
from capital_flow.services import analyze_capital_flow_snapshot, fetch_and_analyze_cn_flow, fetch_and_analyze_hk_flow


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
batch_capital_flow_spec = importlib.util.spec_from_file_location(
    "batch_generate_capital_flow_reports",
    SCRIPTS / "batch_generate_capital_flow_reports.py",
)
if batch_capital_flow_spec is None or batch_capital_flow_spec.loader is None:
    raise RuntimeError("failed to load batch_generate_capital_flow_reports.py for tests")
batch_capital_flow_module = importlib.util.module_from_spec(batch_capital_flow_spec)
sys.modules[batch_capital_flow_spec.name] = batch_capital_flow_module
batch_capital_flow_spec.loader.exec_module(batch_capital_flow_module)
CapitalFlowTarget = batch_capital_flow_module.CapitalFlowTarget
BatchCapitalFlowResult = batch_capital_flow_module.BatchCapitalFlowResult
discover_capital_flow_targets = batch_capital_flow_module.discover_targets_from_holdings_file
run_capital_flow_batch = batch_capital_flow_module.run_batch
save_capital_flow_batch_summary = batch_capital_flow_module.save_batch_summary

batch_hk_capital_flow_spec = importlib.util.spec_from_file_location(
    "batch_generate_h_share_capital_flow_reports",
    SCRIPTS / "batch_generate_h_share_capital_flow_reports.py",
)
if batch_hk_capital_flow_spec is None or batch_hk_capital_flow_spec.loader is None:
    raise RuntimeError("failed to load batch_generate_h_share_capital_flow_reports.py for tests")
batch_hk_capital_flow_module = importlib.util.module_from_spec(batch_hk_capital_flow_spec)
sys.modules[batch_hk_capital_flow_spec.name] = batch_hk_capital_flow_module
batch_hk_capital_flow_spec.loader.exec_module(batch_hk_capital_flow_module)
HkCapitalFlowTarget = batch_hk_capital_flow_module.CapitalFlowTarget
HkBatchCapitalFlowResult = batch_hk_capital_flow_module.BatchCapitalFlowResult
discover_hk_capital_flow_targets = batch_hk_capital_flow_module.discover_targets_from_holdings_file
save_hk_capital_flow_batch_summary = batch_hk_capital_flow_module.save_batch_summary
run_hk_capital_flow_batch = batch_hk_capital_flow_module.run_batch


def test_capital_flow_snapshot_scoring_and_rendering() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="300124",
        name="汇川技术",
        market="CN",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        main_net_inflow=120_000_000,
        main_net_inflow_5d=260_000_000,
        main_net_inflow_10d=310_000_000,
        volume_ratio=1.6,
        amount_ratio_5d=1.4,
        northbound_holding_change=0.2,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    text = render_capital_flow_text(scorecard, snapshot)

    assert scorecard.total_score >= 80
    assert scorecard.rating == "A"
    assert scorecard.red_flag is False
    assert "资金面评分卡: 300124 汇川技术" in text
    assert "量能速览:" in text
    assert "- 量比: 1.6" in text
    assert "- 成交额/5日均值: 1.4" in text
    assert "数据源: manual" in text
    assert text.index("量能速览:") < text.index("数据源: manual")
    assert "资金方向" in text
    assert "综合判断" in text


def test_capital_flow_scoring_discounts_low_confidence_fallback_source() -> None:
    primary_snapshot = CapitalFlowSnapshot(
        symbol="601328",
        name="交通银行",
        market="CN",
        trade_date=date(2026, 5, 24),
        source="eastmoney.fund_flow",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        main_net_inflow=120_000_000,
        main_net_inflow_5d=260_000_000,
        main_net_inflow_10d=310_000_000,
        large_order_net_inflow=80_000_000,
        amount_ratio_5d=1.4,
    )
    fallback_snapshot = primary_snapshot.model_copy(update={"source": "tencent.tick.fallback"})

    primary_scorecard = analyze_capital_flow_snapshot(primary_snapshot)
    fallback_scorecard = analyze_capital_flow_snapshot(fallback_snapshot)

    assert fallback_scorecard.total_score == round(primary_scorecard.total_score * 0.85, 2)
    rating_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
    assert rating_rank[fallback_scorecard.rating] <= rating_rank[primary_scorecard.rating]
    assert any("低置信度资金流来源" in warning for warning in fallback_scorecard.warnings)
    assert any(rule.rule_id == "low_confidence_source_discount" for rule in fallback_scorecard.triggered_rules)


def test_hk_scoring_uses_more_permissive_volume_confirmation_window() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        volume_ratio=3.0,
        amount_ratio_5d=2.8,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    volume_dimension = next(item for item in scorecard.dimension_scores if item.dimension == "volume_confirmation")

    assert volume_dimension.score == 20.0
    assert any(rule.rule_id == "volume_ratio_confirmed" for rule in volume_dimension.passed_rules)
    assert any(rule.rule_id == "amount_ratio_confirmed" for rule in volume_dimension.passed_rules)


def test_cn_scoring_keeps_original_volume_confirmation_window() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="300124",
        name="汇川技术",
        market="CN",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        volume_ratio=3.0,
        amount_ratio_5d=2.8,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    volume_dimension = next(item for item in scorecard.dimension_scores if item.dimension == "volume_confirmation")

    assert volume_dimension.score == 10.0
    assert not volume_dimension.passed_rules


def test_hk_scoring_raises_volume_overheat_threshold() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        volume_ratio=5.5,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    overheat_dimension = next(item for item in scorecard.dimension_scores if item.dimension == "overheat_risk")

    assert overheat_dimension.score == 15.0
    assert any(rule.rule_id == "no_obvious_overheat" for rule in overheat_dimension.passed_rules)
    assert not any(rule.rule_id == "volume_ratio_extreme" for rule in overheat_dimension.failed_rules)


def test_hk_scoring_uses_southbound_net_buy_windows_for_persistence() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        southbound_net_buy_3d=200_000_000,
        southbound_net_buy_5d=350_000_000,
        southbound_net_buy_10d=520_000_000,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    persistence_dimension = next(item for item in scorecard.dimension_scores if item.dimension == "flow_persistence")

    assert persistence_dimension.score == 20.0
    assert any(rule.rule_id == "flow_persistence_positive" for rule in persistence_dimension.passed_rules)
    assert any(rule.rule_id == "flow_persistence_confirmed" for rule in persistence_dimension.passed_rules)


def test_hk_scoring_uses_southbound_holding_change_5d_for_institutional_hint() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        southbound_holding_change_5d=800_000_000,
        short_sell_ratio=12.0,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)
    institutional_dimension = next(item for item in scorecard.dimension_scores if item.dimension == "institutional_hint")

    assert institutional_dimension.score == 16.0
    assert any(rule.rule_id == "institutional_channel_positive" for rule in institutional_dimension.passed_rules)


def test_hk_scorecard_strong_sample_reaches_a_rating() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        main_net_inflow=300_000_000,
        southbound_net_buy=420_000_000,
        main_net_inflow_3d=500_000_000,
        main_net_inflow_5d=800_000_000,
        main_net_inflow_10d=1_100_000_000,
        volume_ratio=3.0,
        amount_ratio_5d=2.8,
        southbound_holding_change=320_000_000,
        short_sell_ratio=7.5,
        turnover_rate=1.8,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)

    assert scorecard.total_score == 96.0
    assert scorecard.rating == "A"
    assert scorecard.red_flag is False
    assert scorecard.combined_comment == "资金面呈正向确认，适合用于提高技术面信号置信度。"


def test_hk_scorecard_mid_tier_sample_reaches_b_rating() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00981",
        name="中芯国际",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        volume_ratio=3.0,
        amount_ratio_5d=2.8,
        southbound_holding_change=180_000_000,
        short_sell_ratio=11.0,
        turnover_rate=2.4,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)

    assert scorecard.total_score == 67.0
    assert scorecard.rating == "B"
    assert scorecard.red_flag is False
    assert scorecard.combined_comment == "资金面信号中性，暂不构成强确认。"
    assert any(rule.rule_id == "amount_ratio_confirmed" for rule in scorecard.triggered_rules)
    assert any(rule.rule_id == "institutional_channel_positive" for rule in scorecard.triggered_rules)


def test_hk_scorecard_weaker_sample_reaches_c_rating() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="01024",
        name="快手",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        main_net_inflow=120_000_000,
        southbound_net_buy=-100_000_000,
        main_net_inflow_3d=150_000_000,
        volume_ratio=2.2,
        short_sell_ratio=22.0,
        turnover_rate=2.0,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)

    assert scorecard.total_score == 62.0
    assert scorecard.rating == "C"
    assert scorecard.red_flag is False
    assert scorecard.combined_comment == "资金面存在风险信号，技术面结论需要降低确认度。"
    assert any(rule.rule_id == "flow_direction_negative" for rule in scorecard.triggered_rules)
    assert any(rule.rule_id == "volume_ratio_confirmed" for rule in scorecard.triggered_rules)
    assert any(rule.rule_id == "short_sell_ratio_high" for rule in scorecard.triggered_rules)


def test_hk_scorecard_overheated_sample_falls_to_d_rating() -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="03690",
        name="美团",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="manual",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        southbound_net_buy=-180_000_000,
        volume_ratio=6.2,
        amount_ratio_5d=4.0,
        southbound_holding_change=-90_000_000,
        short_sell_ratio=22.0,
        turnover_rate=18.0,
    )

    scorecard = analyze_capital_flow_snapshot(snapshot)

    assert scorecard.total_score == 25.5
    assert scorecard.rating == "D"
    assert scorecard.red_flag is False
    assert scorecard.combined_comment == "资金面存在风险信号，技术面结论需要降低确认度。"
    assert any(rule.rule_id == "short_sell_ratio_high" for rule in scorecard.triggered_rules)
    assert any(rule.rule_id == "volume_ratio_extreme" for rule in scorecard.triggered_rules)


def test_fetch_cn_capital_flow_snapshot_maps_akshare_frames(monkeypatch, tmp_path) -> None:
    fund_flow_df = pd.DataFrame(
        [
            {
                "日期": "2026-05-18",
                "主力净流入-净额": -10_000_000,
                "超大单净流入-净额": -2_000_000,
                "大单净流入-净额": -8_000_000,
                "中单净流入-净额": 1_000_000,
                "小单净流入-净额": 9_000_000,
            },
            {
                "日期": "2026-05-19",
                "主力净流入-净额": 20_000_000,
                "超大单净流入-净额": 11_000_000,
                "大单净流入-净额": 9_000_000,
                "中单净流入-净额": -3_000_000,
                "小单净流入-净额": -17_000_000,
            },
            {
                "日期": "2026-05-20",
                "主力净流入-净额": 30_000_000,
                "超大单净流入-净额": 13_000_000,
                "大单净流入-净额": 17_000_000,
                "中单净流入-净额": -4_000_000,
                "小单净流入-净额": -26_000_000,
            },
        ]
    )
    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-18", "成交额": 100_000_000, "成交量": 10_000_000, "换手率": 1.0},
            {"日期": "2026-05-19", "成交额": 150_000_000, "成交量": 12_000_000, "换手率": 1.2},
            {"日期": "2026-05-20", "成交额": 200_000_000, "成交量": 18_000_000, "换手率": 1.5},
        ]
    )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: fund_flow_df)
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="SZ300124",
        name="汇川技术",
        trade_date=date(2026, 5, 20),
        cache_dir=tmp_path,
    )

    assert snapshot.symbol == "300124"
    assert snapshot.market == "CN"
    assert snapshot.trade_date == date(2026, 5, 20)
    assert snapshot.main_net_inflow == 30_000_000
    assert snapshot.main_net_inflow_3d == 40_000_000
    assert snapshot.super_large_net_inflow == 13_000_000
    assert snapshot.large_order_net_inflow == 17_000_000
    assert snapshot.turnover == 200_000_000
    assert snapshot.turnover_rate == 1.5
    assert snapshot.volume_ratio == 18_000_000 / ((10_000_000 + 12_000_000 + 18_000_000) / 3)
    assert snapshot.amount_ratio_5d == 200_000_000 / 150_000_000
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.fund_flow" in snapshot.raw_payload_ref
    assert (tmp_path / "300124_eastmoney_fund_flow.csv").exists()


def test_fetch_cn_capital_flow_snapshot_maps_institutional_and_event_fields(monkeypatch, tmp_path) -> None:
    fund_flow_df = pd.DataFrame(
        [
            {
                "日期": "2026-05-20",
                "主力净流入-净额": 30_000_000,
                "超大单净流入-净额": 13_000_000,
                "大单净流入-净额": 17_000_000,
                "中单净流入-净额": -4_000_000,
                "小单净流入-净额": -26_000_000,
            }
        ]
    )
    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-19", "成交额": 150_000_000, "成交量": 12_000_000, "换手率": 1.2},
            {"日期": "2026-05-20", "成交额": 200_000_000, "成交量": 18_000_000, "换手率": 1.5},
        ]
    )
    northbound_df = pd.DataFrame(
        [
            {"持股日期": "2026-05-20", "持股市值变化-1日": 18_000_000},
        ]
    )
    margin_today_df = pd.DataFrame(
        [
            {"标的证券代码": "300124", "融资余额": 520_000_000, "融资买入额": 80_000_000, "融资偿还额": 50_000_000},
        ]
    )
    margin_prev_df = pd.DataFrame(
        [
            {"标的证券代码": "300124", "融资余额": 500_000_000, "融资买入额": 70_000_000, "融资偿还额": 55_000_000},
        ]
    )
    dragon_tiger_df = pd.DataFrame(
        [
            {"代码": "300124", "上榜日": "2026-05-20"},
        ]
    )
    block_trade_df = pd.DataFrame(
        [
            {"证券代码": "300124", "交易日期": "2026-05-20"},
        ]
    )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: fund_flow_df)
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_northbound_holding_df",
        lambda symbol, start_date, end_date: northbound_df,
    )

    def fake_margin_detail(trade_date: date) -> pd.DataFrame:
        if trade_date == date(2026, 5, 20):
            return margin_today_df
        if trade_date == date(2026, 5, 19):
            return margin_prev_df
        return pd.DataFrame(columns=margin_today_df.columns)

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_margin_detail_szse_df", fake_margin_detail)
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_dragon_tiger_detail_df", lambda trade_date: dragon_tiger_df)
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_block_trade_detail_df", lambda trade_date: block_trade_df)

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="300124",
        name="汇川技术",
        trade_date=date(2026, 5, 20),
        cache_dir=tmp_path,
    )

    assert snapshot.northbound_holding_change == 18_000_000
    assert snapshot.margin_balance_change == 20_000_000
    assert snapshot.volume_ratio == 18_000_000 / 15_000_000
    assert snapshot.dragon_tiger_flag is True
    assert snapshot.block_trade_flag is True
    assert snapshot.notes is not None
    assert "北向持股变化来自东方财富沪深港通个股明细" in snapshot.notes
    assert "融资余额变化来自交易所融资融券明细" in snapshot.notes
    assert "出现龙虎榜事件" in snapshot.notes
    assert "出现大宗交易事件" in snapshot.notes
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.hsgt_individual_detail" in snapshot.raw_payload_ref
    assert "margin_detail" in snapshot.raw_payload_ref


def test_fetch_cn_capital_flow_snapshot_uses_cache_after_remote_failure(monkeypatch, tmp_path) -> None:
    cached_fund_flow_df = pd.DataFrame(
        [
            {
                "日期": "2026-05-19",
                "主力净流入-净额": 20_000_000,
                "超大单净流入-净额": 11_000_000,
                "大单净流入-净额": 9_000_000,
                "中单净流入-净额": -3_000_000,
                "小单净流入-净额": -17_000_000,
            },
            {
                "日期": "2026-05-20",
                "主力净流入-净额": 30_000_000,
                "超大单净流入-净额": 13_000_000,
                "大单净流入-净额": 17_000_000,
                "中单净流入-净额": -4_000_000,
                "小单净流入-净额": -26_000_000,
            },
        ]
    )
    cached_fund_flow_df.to_csv(tmp_path / "300124_eastmoney_fund_flow.csv", index=False, encoding="utf-8-sig")
    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-19", "成交额": 150_000_000, "换手率": 1.2},
            {"日期": "2026-05-20", "成交额": 200_000_000, "换手率": 1.5},
        ]
    )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="300124",
        name="汇川技术",
        trade_date=date(2026, 5, 20),
        cache_dir=tmp_path,
        max_cache_age_days=7,
    )

    assert snapshot.source == "akshare.eastmoney.cache"
    assert snapshot.trade_date == date(2026, 5, 20)
    assert snapshot.main_net_inflow == 30_000_000
    assert snapshot.main_net_inflow_3d == 50_000_000
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.fund_flow.cache" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "使用本地缓存" in snapshot.notes


def test_fetch_cn_capital_flow_snapshot_uses_ths_fallback_without_cache(monkeypatch, tmp_path) -> None:
    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-19", "成交额": 150_000_000, "换手率": 1.2},
            {"日期": "2026-05-20", "成交额": 200_000_000, "换手率": 1.5},
        ]
    )

    def fake_ths(period: str) -> pd.DataFrame:
        if period == "即时":
            return pd.DataFrame(
                [
                    {
                        "股票代码": "300124",
                        "股票简称": "汇川技术",
                        "最新价": 78.99,
                        "涨跌幅": "1.57%",
                        "换手率": "2.05%",
                        "流入资金": "19.33亿",
                        "流出资金": "19.39亿",
                        "净额": "-611.80万",
                        "成交额": "38.72亿",
                    }
                ]
            )
        value_by_period = {"3日排行": "3.32亿", "5日排行": "3.91亿", "10日排行": "2.20亿"}
        return pd.DataFrame(
            [
                {
                    "股票代码": "300124",
                    "股票简称": "汇川技术",
                    "资金流入净额": value_by_period[period],
                }
            ]
        )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_ths_individual_fund_flow_df", fake_ths)
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="300124",
        name="汇川技术",
        trade_date=date(2026, 5, 20),
        cache_dir=tmp_path,
    )

    assert snapshot.source == "ths.fund_flow.fallback"
    assert snapshot.trade_date == date(2026, 5, 20)
    assert snapshot.main_net_inflow == -6_118_000
    assert snapshot.main_net_inflow_3d == 332_000_000
    assert snapshot.main_net_inflow_5d == 391_000_000
    assert abs((snapshot.main_net_inflow_10d or 0) - 220_000_000) < 1
    assert snapshot.raw_payload_ref is not None
    assert "ths.fund_flow.fallback" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "低置信度fallback" in snapshot.notes


def test_fetch_cn_capital_flow_snapshot_uses_ths_disk_cache_after_remote_failure(monkeypatch, tmp_path) -> None:
    cn_flow_fetcher._write_ths_cache(
        pd.DataFrame(
            [
                {
                    "股票代码": "600900",
                    "股票简称": "长江电力",
                    "最新价": 28.35,
                    "涨跌幅": "0.25%",
                    "净额": "1860.50万",
                }
            ]
        ),
        period="即时",
        cache_dir=tmp_path,
    )
    for period, value in (("3日排行", "4200.00万"), ("5日排行", "1.35亿"), ("10日排行", "2.20亿")):
        cn_flow_fetcher._write_ths_cache(
            pd.DataFrame(
                [
                    {
                        "股票代码": "600900",
                        "股票简称": "长江电力",
                        "资金流入净额": value,
                    }
                ]
            ),
            period=period,
            cache_dir=tmp_path,
        )

    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-20", "成交额": 100_000_000, "换手率": 0.5},
            {"日期": "2026-05-21", "成交额": 120_000_000, "换手率": 0.6},
        ]
    )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_ths_individual_fund_flow_df", lambda period: (_ for _ in ()).throw(RuntimeError("ths down")))
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="600900",
        name="长江电力",
        trade_date=date(2026, 5, 21),
        cache_dir=tmp_path,
    )

    assert snapshot.source == "ths.fund_flow.fallback"
    assert snapshot.trade_date == date(2026, 5, 21)
    assert snapshot.main_net_inflow == 18_605_000
    assert snapshot.main_net_inflow_3d == 42_000_000
    assert snapshot.main_net_inflow_5d == 135_000_000
    assert abs((snapshot.main_net_inflow_10d or 0) - 220_000_000) < 1
    assert snapshot.notes is not None
    assert "同花顺本地缓存" in snapshot.notes
    assert "低置信度fallback" in snapshot.notes


def test_fetch_cn_capital_flow_snapshot_uses_tencent_tick_fallback_after_ths_failure(monkeypatch, tmp_path) -> None:
    daily_df = pd.DataFrame(
        [
            {"日期": "2026-05-20", "成交额": 100_000_000, "换手率": 0.5},
            {"日期": "2026-05-21", "成交额": 120_000_000, "换手率": 0.6},
        ]
    )
    tick_df = pd.DataFrame(
        [
            {"成交时间": "09:31:00", "成交价格": 28.10, "成交金额": 300_000, "性质": "买盘"},
            {"成交时间": "09:32:00", "成交价格": 28.08, "成交金额": 120_000, "性质": "卖盘"},
            {"成交时间": "09:33:00", "成交价格": 28.12, "成交金额": 50_000, "性质": "买盘"},
            {"成交时间": "09:34:00", "成交价格": 28.06, "成交金额": 250_000, "性质": "卖盘"},
            {"成交时间": "09:35:00", "成交价格": 28.07, "成交金额": 80_000, "性质": "中性盘"},
        ]
    )

    monkeypatch.setattr(cn_flow_fetcher, "_fetch_cn_fund_flow_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_ths_individual_fund_flow_df", lambda period: (_ for _ in ()).throw(RuntimeError("ths down")))
    monkeypatch.setattr(cn_flow_fetcher, "_fetch_tencent_tick_df", lambda symbol: tick_df)
    monkeypatch.setattr(
        cn_flow_fetcher,
        "_fetch_cn_daily_price_df",
        lambda symbol, start_date, end_date: daily_df,
    )

    snapshot = cn_flow_fetcher.fetch_cn_capital_flow_snapshot(
        symbol="600900",
        name="长江电力",
        trade_date=date(2026, 5, 21),
        cache_dir=tmp_path,
    )

    assert snapshot.source == "tencent.tick.fallback"
    assert snapshot.trade_date == date(2026, 5, 21)
    assert snapshot.main_net_inflow == -20_000
    assert snapshot.large_order_net_inflow == 50_000
    assert snapshot.raw_payload_ref is not None
    assert "tencent.tick.fallback" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "腾讯分笔低置信度fallback" in snapshot.notes
    assert (tmp_path / "600900_tencent_tick_fallback.csv").exists()


def test_fetch_and_analyze_cn_flow_uses_fetched_snapshot(monkeypatch) -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="300124",
        name="汇川技术",
        market="CN",
        trade_date=date(2026, 5, 20),
        source="unit-test",
        updated_at=datetime(2026, 5, 20, 12, 0, 0),
        main_net_inflow=30_000_000,
        main_net_inflow_5d=40_000_000,
        main_net_inflow_10d=50_000_000,
        volume_ratio=1.4,
    )

    service_module = importlib.import_module("capital_flow.services.fetch_and_analyze_cn_flow")
    monkeypatch.setattr(service_module, "fetch_cn_capital_flow_snapshot", lambda **kwargs: snapshot)

    result = fetch_and_analyze_cn_flow("300124", "汇川技术", trade_date=date(2026, 5, 20))

    assert result.snapshot is snapshot
    assert result.scorecard.symbol == "300124"
    assert result.scorecard.total_score > 0


def test_fetch_hk_capital_flow_snapshot_maps_connect_components(monkeypatch, tmp_path) -> None:
    components_df = pd.DataFrame(
        [
            {"代码": "00700", "名称": "腾讯", "成交额": 8_800_000_000, "换手率": 0.42},
            {"代码": "03690", "名称": "美团", "成交额": 2_100_000_000, "换手率": 1.35},
        ]
    )
    minute_df = pd.DataFrame(
        [
            {"时间": "2026-05-20 09:31:00", "成交量": 20_000},
            {"时间": "2026-05-20 09:32:00", "成交量": 100_000},
            {"时间": "2026-05-21 09:31:00", "成交量": 25_000},
            {"时间": "2026-05-21 09:32:00", "成交量": 120_000},
            {"时间": "2026-05-22 09:31:00", "成交量": 30_000},
            {"时间": "2026-05-22 09:32:00", "成交量": 140_000},
            {"时间": "2026-05-23 09:31:00", "成交量": 35_000},
            {"时间": "2026-05-23 09:32:00", "成交量": 160_000},
            {"时间": "2026-05-24 09:31:00", "成交量": 40_000},
            {"时间": "2026-05-24 09:32:00", "成交量": 180_000},
        ]
    )
    hist_df = pd.DataFrame(
        [
            {"日期": date(2026, 5, 20), "成交额": 6_000_000_000},
            {"日期": date(2026, 5, 21), "成交额": 7_000_000_000},
            {"日期": date(2026, 5, 22), "成交额": 8_000_000_000},
            {"日期": date(2026, 5, 23), "成交额": 9_000_000_000},
            {"日期": date(2026, 5, 24), "成交额": 10_000_000_000},
        ]
    )

    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: components_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_minute_hist_df", lambda symbol: minute_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_daily_hist_df", lambda symbol, start_date, end_date: hist_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: (_ for _ in ()).throw(RuntimeError("southbound down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(
        symbol="HK.00700",
        name="腾讯",
        trade_date=date(2026, 5, 24),
        cache_dir=tmp_path,
    )

    assert snapshot.symbol == "00700"
    assert snapshot.market == "HK"
    assert snapshot.trade_date == date(2026, 5, 24)
    assert snapshot.source == "eastmoney.hk_connect_components"
    assert snapshot.turnover == 8_800_000_000
    assert snapshot.turnover_rate == 0.42
    assert snapshot.volume_ratio == 180_000 / ((100_000 + 120_000 + 140_000 + 160_000 + 180_000) / 5)
    assert snapshot.amount_ratio_5d == 10_000_000_000 / 8_000_000_000
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.hk_connect_components" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "量比来自东方财富港股最近5日同一时刻分钟成交量对比" in snapshot.notes
    assert "成交额/5日均值来自东方财富港股日线历史" in snapshot.notes
    assert "个股南向净买额缺失时" in snapshot.notes
    assert (tmp_path / "hk_eastmoney_hk_connect_components.csv").exists()


def test_fetch_hk_capital_flow_snapshot_uses_hist_cache_for_amount_ratio(monkeypatch, tmp_path) -> None:
    cached_components_df = pd.DataFrame(
        [
            {"代码": "01024", "名称": "快手", "成交额": 1_500_000_000, "换手率": 2.1},
        ]
    )
    cached_hist_df = pd.DataFrame(
        [
            {"日期": date(2026, 5, 20), "成交额": 1_000_000_000},
            {"日期": date(2026, 5, 21), "成交额": 1_200_000_000},
            {"日期": date(2026, 5, 22), "成交额": 1_300_000_000},
            {"日期": date(2026, 5, 23), "成交额": 1_400_000_000},
            {"日期": date(2026, 5, 24), "成交额": 1_500_000_000},
        ]
    )
    cached_components_df.to_csv(tmp_path / "hk_eastmoney_hk_connect_components.csv", index=False, encoding="utf-8-sig")
    cached_hist_df.to_csv(tmp_path / "hk_eastmoney_hk_daily_hist_01024.csv", index=False, encoding="utf-8-sig")
    cached_minute_df = pd.DataFrame(
        [
            {"时间": "2026-05-20 09:31:00", "成交量": 10_000},
            {"时间": "2026-05-20 09:32:00", "成交量": 50_000},
            {"时间": "2026-05-21 09:31:00", "成交量": 12_000},
            {"时间": "2026-05-21 09:32:00", "成交量": 60_000},
            {"时间": "2026-05-22 09:31:00", "成交量": 14_000},
            {"时间": "2026-05-22 09:32:00", "成交量": 70_000},
            {"时间": "2026-05-23 09:31:00", "成交量": 16_000},
            {"时间": "2026-05-23 09:32:00", "成交量": 80_000},
            {"时间": "2026-05-24 09:31:00", "成交量": 18_000},
            {"时间": "2026-05-24 09:32:00", "成交量": 90_000},
        ]
    )
    cached_minute_df.to_csv(tmp_path / "hk_eastmoney_hk_minute_hist_01024.csv", index=False, encoding="utf-8-sig")
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_minute_hist_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("minute down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_daily_hist_df", lambda symbol, start_date, end_date: (_ for _ in ()).throw(RuntimeError("hist down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: (_ for _ in ()).throw(RuntimeError("southbound down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(
        symbol="01024.HK",
        name="快手",
        trade_date=date(2026, 5, 24),
        cache_dir=tmp_path,
        max_cache_age_days=7,
    )

    assert snapshot.source == "eastmoney.hk_connect_components.cache"
    assert snapshot.volume_ratio == 90_000 / ((50_000 + 60_000 + 70_000 + 80_000 + 90_000) / 5)
    assert snapshot.amount_ratio_5d == 1_500_000_000 / ((1_000_000_000 + 1_200_000_000 + 1_300_000_000 + 1_400_000_000 + 1_500_000_000) / 5)
    assert snapshot.notes is not None
    assert "港股分钟历史远端抓取失败，使用本地缓存" in snapshot.notes
    assert "港股日线历史远端抓取失败，使用本地缓存" in snapshot.notes


def test_fetch_hk_capital_flow_snapshot_maps_southbound_net_buy(monkeypatch, tmp_path) -> None:
    components_df = pd.DataFrame(
        [
            {"代码": "00700", "名称": "腾讯", "成交额": 8_800_000_000, "换手率": 0.42},
        ]
    )
    net_buy_df = pd.DataFrame(
        [
            {
                "日期": [date(2026, 5, 22), date(2026, 5, 21), date(2026, 5, 20)],
                "港股通净买额": [420_000_000, -50_000_000, 130_000_000],
                "港股通成交额": [5_100_000_000, 4_600_000_000, 4_200_000_000],
            }
        ]
    ).explode(["日期", "港股通净买额", "港股通成交额"], ignore_index=True)

    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: components_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_net_buy_df", lambda symbol: net_buy_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: (_ for _ in ()).throw(RuntimeError("southbound holding down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(symbol="00700", name="腾讯", cache_dir=tmp_path)

    assert snapshot.trade_date == date(2026, 5, 22)
    assert snapshot.source == "eastmoney.hk_connect_components+eastmoney.southbound_net_buy"
    assert snapshot.southbound_net_buy == 420_000_000
    assert snapshot.southbound_net_buy_3d == 500_000_000
    assert snapshot.southbound_net_buy_5d == 500_000_000
    assert snapshot.southbound_net_buy_10d == 500_000_000
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.southbound_net_buy" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "南向净买额来自东方财富港股通个股成交榜历史" in snapshot.notes
    assert "南向净买额支持3/5/10日累计窗口" in snapshot.notes
    assert (tmp_path / "hk_eastmoney_southbound_net_buy_00700.csv").exists()


def test_fetch_hk_southbound_net_buy_df_remote_maps_api_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        hk_flow_fetcher,
        "_fetch_datacenter_rows",
        lambda params: [
            {
                "SECURITY_CODE": "00700",
                "TRADE_DATE": "2026-05-22 00:00:00",
                "CLOSE_PRICE": 441.4,
                "CHANGE_RATE": 0.55,
                "HK_NET_BUYAMT": -1_726_407_044,
                "HKSH_NET_BUYAMT": -701_313_991,
                "HKSH_BUY_AMT": 1_049_931_780,
                "HKSH_SELL_AMT": 1_751_245_771,
                "HKSZ_NET_BUYAMT": -1_025_093_053,
                "HKSZ_BUY_AMT": 774_897_860,
                "HKSZ_SELL_AMT": 1_799_990_913,
                "HK_DEAL_AMT": 5_376_066_324,
            }
        ],
    )

    df = hk_flow_fetcher._fetch_hk_southbound_net_buy_df_remote("00700")

    assert df.iloc[0]["日期"] == date(2026, 5, 22)
    assert df.iloc[0]["港股通净买额"] == -1_726_407_044
    assert df.iloc[0]["港股通(沪)净买额"] == -701_313_991
    assert df.iloc[0]["港股通(深)净买额"] == -1_025_093_053
    assert df.iloc[0]["港股通成交额"] == 5_376_066_324


def test_fetch_html_detects_eastmoney_antibot_marker() -> None:
    assert hk_flow_fetcher._looks_like_eastmoney_blocked_html("拖动下方滑块完成拼图") is True
    assert hk_flow_fetcher._looks_like_eastmoney_blocked_html("正常业务页面") is False
    assert (
        hk_flow_fetcher._looks_like_eastmoney_blocked_html(
            "港股通成交榜 | 2026-05-22 | 持股明细 | 441.40 | 0.55% | -17.26亿 | 拖动下方滑块完成拼图"
        )
        is False
    )


def test_parse_southbound_net_buy_html_falls_back_to_text_rows() -> None:
    html = """
    <html><body>
    | 2026-05-22 | 持股明细 | 441.40 | 0.55% | -17.26亿 | 3 | -7.0131亿 | 10.5亿 | 17.51亿 |
    2 | -10.25亿 | 7.749亿 | 18亿 | 53.76亿 |
    | 2026-05-21 | 持股明细 | 439.00 | -3.56% | -10.85亿 | 1 | -9.5137亿 | 28.98亿 | 38.5亿 |
    1 | -1.3335亿 | 18.8亿 | 20.13亿 | 106.4亿 |
    </body></html>
    """

    df = hk_flow_fetcher._parse_southbound_net_buy_html(html)

    assert list(df.columns) == [
        "日期",
        "收盘价",
        "涨跌幅",
        "港股通净买额",
        "港股通(沪)净买额",
        "港股通(沪)买入额",
        "港股通(沪)卖出额",
        "港股通(深)净买额",
        "港股通(深)买入额",
        "港股通(深)卖出额",
        "港股通成交额",
    ]
    assert df.iloc[0]["日期"] == date(2026, 5, 22)
    assert df.iloc[0]["港股通净买额"] == "-17.26亿"
    assert df.iloc[0]["港股通成交额"] == "53.76亿"
    assert len(df) == 2


def test_fetch_html_retries_with_browser_cookie_after_antibot(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.cookies: dict[str, str] = {}

    sessions = [FakeSession(), FakeSession()]
    calls: list[tuple[FakeSession, str, dict[str, str]]] = []

    monkeypatch.setattr(hk_flow_fetcher, "_new_html_session", lambda referer=None: sessions.pop(0))
    monkeypatch.setattr(hk_flow_fetcher, "_extract_eastmoney_cookie_from_browser", lambda browser=None: {"st_si": "cookie"})

    def fake_request_html(session: FakeSession, url: str) -> str:
        calls.append((session, url, dict(session.cookies)))
        if len(calls) == 1:
            return "拖动下方滑块完成拼图"
        return "<html>real eastmoney page</html>"

    monkeypatch.setattr(hk_flow_fetcher, "_request_html", fake_request_html)

    html = hk_flow_fetcher._fetch_html(
        "https://data.eastmoney.com/hsgt/00700.html",
        referer="https://data.eastmoney.com/hsgt/hsgtV2.html",
    )

    assert html == "<html>real eastmoney page</html>"
    assert len(calls) == 3
    assert calls[1][1] == "https://data.eastmoney.com/hsgt/hsgtV2.html"
    assert calls[1][2] == {"st_si": "cookie"}
    assert calls[2][1] == "https://data.eastmoney.com/hsgt/00700.html"
    assert calls[2][2] == {"st_si": "cookie"}


def test_fetch_hk_capital_flow_snapshot_maps_hkex_short_selling(monkeypatch, tmp_path) -> None:
    components_df = pd.DataFrame(
        [
            {"代码": "00700", "名称": "腾讯", "成交额": 8_000_000_000, "换手率": 0.42},
        ]
    )
    short_df = pd.DataFrame(
        [
            {"日期": "2026-05-22", "股票代码": "00700", "股票简称": "TENCENT", "沽空成交额": 800_000_000},
        ]
    )

    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: components_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_net_buy_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("net buy down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: (_ for _ in ()).throw(RuntimeError("southbound down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: short_df)

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(symbol="00700", name="腾讯", cache_dir=tmp_path)

    assert snapshot.source == "eastmoney.hk_connect_components+hkex.short_selling_turnover"
    assert snapshot.short_sell_turnover == 800_000_000
    assert snapshot.short_sell_ratio == 10.0
    assert snapshot.raw_payload_ref is not None
    assert "hkex.short_selling_turnover" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "沽空成交额来自 HKEX 日终沽空统计" in snapshot.notes


def test_fetch_hk_capital_flow_snapshot_maps_southbound_holding(monkeypatch, tmp_path) -> None:
    components_df = pd.DataFrame(
        [
            {"代码": "00700", "名称": "腾讯", "成交额": 8_800_000_000, "换手率": 0.42},
        ]
    )
    holding_df = pd.DataFrame(
        [
            {
                "持股日期": "2026-05-22",
                "股票代码": "00700",
                "股票简称": "腾讯控股",
                "持股市值变化-1日": 320_000_000,
                "持股市值变化-5日": 1_100_000_000,
                "持股市值变化-10日": 1_600_000_000,
            },
        ]
    )

    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: components_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_net_buy_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("net buy down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: holding_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(symbol="00700", name="腾讯", cache_dir=tmp_path)

    assert snapshot.trade_date == date(2026, 5, 22)
    assert snapshot.source == "eastmoney.hk_connect_components+eastmoney.southbound_holding"
    assert snapshot.turnover == 8_800_000_000
    assert snapshot.southbound_holding_change == 320_000_000
    assert snapshot.southbound_holding_change_5d == 1_100_000_000
    assert snapshot.southbound_holding_change_10d == 1_600_000_000
    assert snapshot.raw_payload_ref is not None
    assert "eastmoney.southbound_holding" in snapshot.raw_payload_ref
    assert snapshot.notes is not None
    assert "南向持股变化来自东方财富沪深港通持股统计" in snapshot.notes
    assert "南向持股变化补充提供5日/10日持股市值变化窗口" in snapshot.notes
    assert (tmp_path / "hk_eastmoney_southbound_holding.csv").exists()


def test_fetch_hk_capital_flow_snapshot_succeeds_with_southbound_when_components_fail(monkeypatch, tmp_path) -> None:
    holding_df = pd.DataFrame(
        [
            {
                "持股日期": "2026-05-22",
                "股票代码": "03690",
                "股票简称": "美团",
                "持股市值变化-1日": -120_000_000,
            },
        ]
    )

    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: (_ for _ in ()).throw(RuntimeError("quote down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_net_buy_df", lambda symbol: (_ for _ in ()).throw(RuntimeError("net buy down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: holding_df)
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(symbol="03690", name="美团", cache_dir=tmp_path)

    assert snapshot.source == "eastmoney.southbound_holding"
    assert snapshot.turnover is None
    assert snapshot.southbound_holding_change == -120_000_000
    assert snapshot.notes is not None
    assert "港股通成份行情不可用" in snapshot.notes


def test_fetch_hk_capital_flow_snapshot_uses_cache_after_remote_failure(monkeypatch, tmp_path) -> None:
    cached_df = pd.DataFrame(
        [
            {"代码": "01024", "名称": "快手", "成交额": 1_500_000_000, "换手率": 2.1},
        ]
    )
    cached_df.to_csv(tmp_path / "hk_eastmoney_hk_connect_components.csv", index=False, encoding="utf-8-sig")
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_connect_components_df", lambda: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hk_southbound_holding_df", lambda: (_ for _ in ()).throw(RuntimeError("southbound down")))
    monkeypatch.setattr(hk_flow_fetcher, "_fetch_hkex_short_selling_df", lambda trade_date=None: (_ for _ in ()).throw(RuntimeError("short down")))

    snapshot = hk_flow_fetcher.fetch_hk_capital_flow_snapshot(
        symbol="01024.HK",
        name="快手",
        trade_date=date(2026, 5, 24),
        cache_dir=tmp_path,
        max_cache_age_days=7,
    )

    assert snapshot.source == "eastmoney.hk_connect_components.cache"
    assert snapshot.turnover == 1_500_000_000
    assert snapshot.turnover_rate == 2.1
    assert snapshot.notes is not None
    assert "使用本地缓存" in snapshot.notes


def test_fetch_and_analyze_hk_flow_uses_fetched_snapshot(monkeypatch) -> None:
    snapshot = CapitalFlowSnapshot(
        symbol="00700",
        name="腾讯",
        market="HK",
        trade_date=date(2026, 5, 24),
        source="unit-test",
        updated_at=datetime(2026, 5, 24, 12, 0, 0),
        turnover=8_800_000_000,
        turnover_rate=0.42,
        short_sell_ratio=7.5,
    )

    service_module = importlib.import_module("capital_flow.services.fetch_and_analyze_hk_flow")
    monkeypatch.setattr(service_module, "fetch_hk_capital_flow_snapshot", lambda **kwargs: snapshot)

    result = fetch_and_analyze_hk_flow("00700", "腾讯", trade_date=date(2026, 5, 24))

    assert result.snapshot is snapshot
    assert result.scorecard.symbol == "00700"
    assert any("港股沽空比例较低" in item for item in result.scorecard.strengths)


def test_batch_capital_flow_discover_targets_filters_cn_holdings(tmp_path) -> None:
    holdings_file = tmp_path / "current_holdings.json"
    holdings_file.write_text(
        """
{
    "markets": {
        "CN": [
            {"symbol": "SZ300124", "name": "汇川技术"},
            {"symbol": "600900", "name": "长江电力"}
        ],
        "HK": [
            {"symbol": "00700", "name": "腾讯"}
        ]
    }
}
""",
        encoding="utf-8",
    )

    targets = discover_capital_flow_targets(holdings_file)

    assert targets == [
        CapitalFlowTarget(symbol="300124", name="汇川技术", market="CN"),
        CapitalFlowTarget(symbol="600900", name="长江电力", market="CN"),
    ]


def test_batch_hk_capital_flow_discover_targets_filters_hk_holdings(tmp_path) -> None:
    holdings_file = tmp_path / "current_holdings.json"
    holdings_file.write_text(
        """
{
    "markets": {
        "CN": [
            {"symbol": "300124", "name": "汇川技术"}
        ],
        "HK": [
            {"symbol": "HK.00700", "name": "腾讯"},
            {"symbol": "01024.HK", "name": "快手"}
        ]
    }
}
""",
        encoding="utf-8",
    )

    targets = discover_hk_capital_flow_targets(holdings_file)

    assert targets == [HkCapitalFlowTarget(symbol="00700", name="腾讯"), HkCapitalFlowTarget(symbol="01024", name="快手")]


def test_batch_hk_capital_flow_summary_marks_volume_only_scope(tmp_path) -> None:
    results = [
        HkBatchCapitalFlowResult(
            target=HkCapitalFlowTarget(symbol="00700", name="腾讯"),
            status="ok",
            report_path=tmp_path / "00700_capital_flow.txt",
            total_score=49.0,
            rating="D",
            trade_date=date(2026, 5, 24),
            source="eastmoney.hk_connect_components",
            notes="港股 V1 使用港股通成份行情的成交额/换手率作为量能线索；南向持股变化来自东方财富沪深港通持股统计",
        )
    ]

    path = save_hk_capital_flow_batch_summary(results, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "# 港股持仓资金面批量概览" in text
    assert "当前 HK V1 已接入成交额/换手率、个股南向净买额、南向持股变化和 HKEX 沽空成交额" in text
    assert "00700 | 腾讯 | ok | 2026-05-24 | 49.0 | D | primary(components) | weak" in text


def test_batch_hk_capital_flow_summary_marks_mixed_source_scope(tmp_path) -> None:
    results = [
        HkBatchCapitalFlowResult(
            target=HkCapitalFlowTarget(symbol="00700", name="腾讯"),
            status="ok",
            report_path=tmp_path / "00700_capital_flow.txt",
            total_score=57.5,
            rating="C",
            trade_date=date(2026, 5, 22),
            source="eastmoney.southbound_net_buy+eastmoney.southbound_holding.cache",
            notes="unit-test",
        )
    ]

    path = save_hk_capital_flow_batch_summary(results, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "数据源分布: mixed=1" in text
    assert "00700 | 腾讯 | ok | 2026-05-22 | 57.5 | C | mixed(net_buy+holding.cache) | neutral" in text


def test_batch_hk_capital_flow_failed_rows_keep_attempted_source(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(batch_hk_capital_flow_module, "generate_one", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("remote down")))

    results = run_hk_capital_flow_batch([HkCapitalFlowTarget(symbol="00700", name="腾讯")], output_dir=tmp_path)
    path = save_hk_capital_flow_batch_summary(results, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert results[0].source == "eastmoney.hk_connect_components+eastmoney.southbound_net_buy+eastmoney.southbound_holding+hkex.short_selling_turnover"
    assert "00700 | 腾讯 | failed |  |  |  | primary(components+net_buy+holding+short_sell) | failed | remote down" in text


def test_batch_capital_flow_continues_after_failed_target(monkeypatch, tmp_path) -> None:
    targets = [
        CapitalFlowTarget(symbol="300124", name="汇川技术"),
        CapitalFlowTarget(symbol="600900", name="长江电力"),
    ]

    def fake_generate_one(
        target,
        output_dir,
        trade_date=None,
        use_cache=True,
        use_fallback=True,
        cache_dir=None,
        max_cache_age_days=7,
    ):
        if target.symbol == "300124":
            raise RuntimeError("network unavailable")
        return BatchCapitalFlowResult(
            target=target,
            status="ok",
            report_path=output_dir / "600900_report.txt",
            total_score=72.5,
            rating="B",
            trade_date=date(2026, 5, 22),
            source="unit-test",
            notes="ok",
        )

    monkeypatch.setattr(batch_capital_flow_module, "generate_one", fake_generate_one)

    results = run_capital_flow_batch(targets, output_dir=tmp_path)
    summary_path = save_capital_flow_batch_summary(results, output_dir=tmp_path)
    summary_text = summary_path.read_text(encoding="utf-8")

    assert [item.status for item in results] == ["failed", "ok"]
    assert "network unavailable" in summary_text
    assert "600900" in summary_text
    assert "72.5" in summary_text
    assert "primary" in summary_text
    assert "## 组合观察" in summary_text
    assert "## 排名表" in summary_text
    assert "## 口径与失败说明" in summary_text