"""Immutable configuration objects for submodel scoring."""

from dataclasses import dataclass, field
from typing import Dict, Literal, Tuple


@dataclass(frozen=True)
class DimensionConfig:
    name: str
    weight: int
    primary_metrics: Tuple[str, ...]
    optional_metrics: Tuple[str, ...] = ()
    inherited_from_common: bool = True
    notes: str = ""


@dataclass(frozen=True)
class FieldPolicy:
    required_core: Tuple[str, ...]
    optional_manual: Tuple[str, ...] = ()
    deferred_v2: Tuple[str, ...] = ()
    disabled_or_deweighted: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskRuleConfig:
    rule_id: str
    severity: Literal["red_flag", "risk", "warning"]
    enabled: bool
    automated: bool
    required_metrics: Tuple[str, ...]
    description: str
    notes: str = ""


@dataclass(frozen=True)
class ExplanationConfig:
    focus_questions: Tuple[str, ...] = ()
    strength_messages: Dict[str, str] = field(default_factory=dict)
    risk_messages: Dict[str, str] = field(default_factory=dict)
    bundled_risk_messages: Dict[Tuple[str, ...], str] = field(default_factory=dict)
    summary_when_stable: str = "当前综合评级为 {rating}，基本面整体处于可跟踪区间。"
    summary_when_red_flag: str = "当前综合评级为 {rating}，需要优先处理红线风险。"
    fallback_highlight: str = "整体评分仍处于可跟踪区间。"
    fallback_risk: str = "后续基本面兑现能否延续当前评分。"


@dataclass(frozen=True)
class SubmodelConfig:
    industry_bucket: str
    submodel_id: str
    display_name: str
    version: str
    applicable_symbols: Tuple[str, ...]
    output_style: str
    field_policy: FieldPolicy
    dimensions: Tuple[DimensionConfig, ...]
    risk_rules: Tuple[RiskRuleConfig, ...]
    score_overrides: Dict[str, str] = field(default_factory=dict)
    explanation: ExplanationConfig = field(default_factory=ExplanationConfig)
