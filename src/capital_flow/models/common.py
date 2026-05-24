"""Shared capital-flow model type aliases."""

from typing import Literal

MarketCode = Literal["CN", "HK", "US"]
Rating = Literal["A", "B", "C", "D"]
RuleSeverity = Literal["pass", "warning", "risk", "red_flag"]