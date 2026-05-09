"""Shared fundamental model type aliases."""

from typing import Literal

MarketCode = Literal["CN", "HK", "US"]
GuidanceAttainment = Literal["beat", "meet", "miss"]
DupontDriver = Literal["margin_turnover", "mixed", "leverage"]
Rating = Literal["A", "B", "C", "D"]
RuleSeverity = Literal["pass", "warning", "risk", "red_flag"]
