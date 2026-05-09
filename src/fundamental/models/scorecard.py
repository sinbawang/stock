"""Structured output models for fundamental scoring."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from .common import MarketCode, Rating, RuleSeverity


class TriggeredRule(BaseModel):
    rule_id: str
    severity: RuleSeverity
    message: str
    automated: bool = True


class FundamentalDimensionScore(BaseModel):
    dimension: str
    score: float
    weight: int
    max_score: float
    used_metrics: List[str] = Field(default_factory=list)
    missing_metrics: List[str] = Field(default_factory=list)
    passed_rules: List[TriggeredRule] = Field(default_factory=list)
    failed_rules: List[TriggeredRule] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class FundamentalScoreCard(BaseModel):
    symbol: str
    name: str
    market: MarketCode
    report_period: date

    industry_bucket: str
    submodel_id: str
    submodel_version: str

    total_score: float
    rating: Rating
    red_flag: bool = False

    dimension_scores: List[FundamentalDimensionScore]

    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    focus_questions: List[str] = Field(default_factory=list)
    missing_metrics: List[str] = Field(default_factory=list)

    triggered_rules: List[TriggeredRule] = Field(default_factory=list)
    combined_comment: Optional[str] = None
