from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.source_profiles import available_a_share_source_profiles, describe_source_chain, resolve_a_share_daylike_source_order, resolve_a_share_intraday_source_label, resolve_a_share_intraday_source_order, resolve_hk_minute_source_selection, resolve_source_profile_name


def test_resolve_source_profile_name_accepts_env_style_aliases(monkeypatch) -> None:
    monkeypatch.setenv("CHANLUN_SOURCE_PROFILE", "xueqiu_only")
    assert resolve_source_profile_name() == "xueqiu-only"


def test_resolve_hk_minute_source_selection_uses_profile_defaults() -> None:
    primary_source, fallback_sources, profile = resolve_hk_minute_source_selection(source_profile="mainland")

    assert primary_source == "xueqiu"
    assert fallback_sources == ("akshare",)
    assert profile == "mainland"


def test_resolve_hk_minute_source_selection_preserves_explicit_non_profile_primary() -> None:
    primary_source, fallback_sources, profile = resolve_hk_minute_source_selection(
        primary_source="akshare",
        fallback_sources=None,
        source_profile="mainland",
    )

    assert primary_source == "akshare"
    assert fallback_sources is None
    assert profile == "mainland"


def test_describe_source_chain_deduplicates_sources() -> None:
    assert describe_source_chain("xueqiu", ("xueqiu", "akshare", "akshare")) == "xueqiu->akshare"


def test_resolve_a_share_intraday_source_label_uses_profile_name() -> None:
    source_label, profile = resolve_a_share_intraday_source_label("mainland")

    assert source_label == "tushare->tencent->xueqiu->eastmoney"
    assert profile == "mainland"


def test_resolve_a_share_intraday_source_order_uses_profile_defaults() -> None:
    source_order, profile = resolve_a_share_intraday_source_order("xueqiu-first")

    assert source_order == ("xueqiu", "tencent", "eastmoney")
    assert profile == "xueqiu-first"


def test_resolve_a_share_daylike_source_order_uses_profile_defaults() -> None:
    source_order, profile = resolve_a_share_daylike_source_order("mainland")

    assert source_order == ("tushare", "day_like")
    assert profile == "mainland"


def test_available_a_share_source_profiles_lists_configurable_orders() -> None:
    assert available_a_share_source_profiles() == (
        "mainland",
        "tencent-only",
        "xueqiu-first",
        "eastmoney-first",
        "tushare-first",
        "tushare-only",
    )