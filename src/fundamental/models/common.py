"""Shared fundamental model type aliases."""

from typing import Literal, Optional

MarketCode = Literal["CN", "HK", "US"]
GuidanceAttainment = Literal["beat", "meet", "miss"]
DupontDriver = Literal["margin_turnover", "mixed", "leverage"]
Rating = Literal["A", "B", "C", "D"]
RuleSeverity = Literal["pass", "warning", "risk", "red_flag"]


GUIDANCE_ATTAINMENT_LABELS = {
	"beat": "超预期",
	"meet": "符合预期",
	"miss": "低于预期",
}

DUPONT_DRIVER_LABELS = {
	"margin_turnover": "利润率与周转驱动",
	"mixed": "混合驱动",
	"leverage": "杠杆驱动",
}

GROSS_MARGIN_TREND_LABELS = {
	"improving": "改善",
	"up": "改善",
	"stronger": "改善",
	"改善": "改善",
	"提升": "改善",
	"向上": "改善",
	"stable": "稳定",
	"flat": "稳定",
	"steady": "稳定",
	"稳定": "稳定",
	"持平": "稳定",
	"平稳": "稳定",
	"weakening": "承压",
	"down": "承压",
	"compressed": "承压",
	"承压": "承压",
	"下滑": "承压",
	"走弱": "承压",
}

PRICE_WAR_PRESSURE_LABELS = {
	"low": "较低",
	"mild": "较低",
	"可控": "较低",
	"低": "较低",
	"较低": "较低",
	"medium": "中等",
	"moderate": "中等",
	"中": "中等",
	"中等": "中等",
	"high": "较高",
	"severe": "较高",
	"激烈": "较高",
	"高": "较高",
	"较高": "较高",
}


def format_guidance_attainment(value: Optional[str]) -> Optional[str]:
	if value is None:
		return None
	return GUIDANCE_ATTAINMENT_LABELS.get(value, value)


def format_dupont_driver(value: Optional[str]) -> Optional[str]:
	if value is None:
		return None
	return DUPONT_DRIVER_LABELS.get(value, value)


def format_gross_margin_trend(value: Optional[str]) -> Optional[str]:
	if value is None:
		return None
	return GROSS_MARGIN_TREND_LABELS.get(value, value)


def format_price_war_pressure(value: Optional[str]) -> Optional[str]:
	if value is None:
		return None
	return PRICE_WAR_PRESSURE_LABELS.get(value, value)


def format_display_literal(value: Optional[str]) -> Optional[str]:
	if value is None:
		return None
	for formatter in (
		format_guidance_attainment,
		format_dupont_driver,
		format_gross_margin_trend,
		format_price_war_pressure,
	):
		formatted = formatter(value)
		if formatted != value:
			return formatted
	return value
