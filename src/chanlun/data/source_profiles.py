from __future__ import annotations

import os
from typing import Sequence


DEFAULT_SOURCE_PROFILE = "mainland"
SOURCE_PROFILE_ENV_VAR = "CHANLUN_SOURCE_PROFILE"

_HK_MINUTE_SOURCE_PROFILES: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "mainland": ("xueqiu", ("akshare",)),
    "xueqiu-only": ("xueqiu", None),
    "akshare-only": ("akshare", None),
}

_A_SHARE_INTRADAY_SOURCE_LABELS: dict[str, str] = {
    "mainland": "fetch_kline.a_share_intraday",
    "xueqiu-only": "fetch_kline.a_share_intraday",
    "akshare-only": "fetch_kline.a_share_intraday",
}

_A_SHARE_INTRADAY_SOURCE_PROFILES: dict[str, tuple[str, ...]] = {
    "mainland": ("tushare", "tencent", "xueqiu", "eastmoney"),
    "tencent-only": ("tencent",),
    "xueqiu-first": ("xueqiu", "tencent", "eastmoney"),
    "eastmoney-first": ("eastmoney", "tencent", "xueqiu"),
    "tushare-first": ("tushare", "tencent", "xueqiu", "eastmoney"),
    "tushare-only": ("tushare",),
}

_A_SHARE_DAYLIKE_SOURCE_PROFILES: dict[str, tuple[str, ...]] = {
    "mainland": ("tushare", "day_like"),
    "tencent-only": ("day_like",),
    "xueqiu-first": ("tushare", "day_like"),
    "eastmoney-first": ("tushare", "day_like"),
    "tushare-first": ("tushare", "day_like"),
    "tushare-only": ("tushare",),
}


def available_source_profiles() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*_HK_MINUTE_SOURCE_PROFILES.keys(), *_A_SHARE_INTRADAY_SOURCE_PROFILES.keys())))


def available_hk_source_profiles() -> tuple[str, ...]:
    return tuple(_HK_MINUTE_SOURCE_PROFILES)


def available_a_share_source_profiles() -> tuple[str, ...]:
    return tuple(_A_SHARE_INTRADAY_SOURCE_PROFILES)


def resolve_source_profile_name(source_profile: str | None = None) -> str:
    candidate = source_profile
    if candidate is None:
        candidate = os.getenv(SOURCE_PROFILE_ENV_VAR, DEFAULT_SOURCE_PROFILE)

    normalized = candidate.strip().lower().replace("_", "-")
    if not normalized:
        normalized = DEFAULT_SOURCE_PROFILE

    if normalized not in available_source_profiles():
        allowed = ", ".join(available_source_profiles())
        raise ValueError(f"source_profile 必须是 {allowed} 之一，收到: {candidate}")
    return normalized


def _normalize_fallback_sources(
    primary_source: str,
    fallback_sources: Sequence[str] | None,
) -> tuple[str, ...] | None:
    if fallback_sources is None:
        return None

    normalized: list[str] = []
    for source in fallback_sources:
        if source == primary_source or source in normalized:
            continue
        normalized.append(source)
    return tuple(normalized) or None


def resolve_hk_minute_source_selection(
    *,
    primary_source: str | None = None,
    fallback_sources: Sequence[str] | None = None,
    source_profile: str | None = None,
) -> tuple[str, tuple[str, ...] | None, str]:
    resolved_profile = resolve_source_profile_name(source_profile)
    profile_primary, profile_fallback = _HK_MINUTE_SOURCE_PROFILES[resolved_profile]

    if primary_source is None:
        resolved_primary = profile_primary
        resolved_fallback = profile_fallback
    else:
        resolved_primary = primary_source
        if fallback_sources is not None:
            resolved_fallback = _normalize_fallback_sources(resolved_primary, fallback_sources)
        elif resolved_primary == profile_primary:
            resolved_fallback = _normalize_fallback_sources(resolved_primary, profile_fallback)
        else:
            resolved_fallback = None

    return resolved_primary, resolved_fallback, resolved_profile


def describe_source_chain(primary_source: str, fallback_sources: Sequence[str] | None) -> str:
    chain = [primary_source]
    if fallback_sources:
        for source in fallback_sources:
            if source not in chain:
                chain.append(source)
    return "->".join(chain)


def resolve_a_share_intraday_source_label(source_profile: str | None = None) -> tuple[str, str]:
    resolved_profile = resolve_source_profile_name(source_profile)
    if resolved_profile in _A_SHARE_INTRADAY_SOURCE_PROFILES:
        return describe_source_chain(_A_SHARE_INTRADAY_SOURCE_PROFILES[resolved_profile][0], _A_SHARE_INTRADAY_SOURCE_PROFILES[resolved_profile][1:]), resolved_profile
    return _A_SHARE_INTRADAY_SOURCE_LABELS[resolved_profile], resolved_profile


def resolve_a_share_intraday_source_order(source_profile: str | None = None) -> tuple[tuple[str, ...], str]:
    resolved_profile = resolve_source_profile_name(source_profile)
    if resolved_profile not in _A_SHARE_INTRADAY_SOURCE_PROFILES:
        allowed = ", ".join(available_a_share_source_profiles())
        raise ValueError(f"A股 source_profile 必须是 {allowed} 之一，收到: {source_profile}")
    return _A_SHARE_INTRADAY_SOURCE_PROFILES[resolved_profile], resolved_profile


def resolve_a_share_daylike_source_order(source_profile: str | None = None) -> tuple[tuple[str, ...], str]:
    resolved_profile = resolve_source_profile_name(source_profile)
    if resolved_profile not in _A_SHARE_DAYLIKE_SOURCE_PROFILES:
        allowed = ", ".join(available_a_share_source_profiles())
        raise ValueError(f"A股 source_profile 必须是 {allowed} 之一，收到: {source_profile}")
    return _A_SHARE_DAYLIKE_SOURCE_PROFILES[resolved_profile], resolved_profile