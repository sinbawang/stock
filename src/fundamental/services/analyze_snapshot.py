"""Analyze one fundamental snapshot against a configured submodel."""

from typing import Any, Mapping, Optional, Union

from fundamental.config.models import SubmodelConfig
from fundamental.config.registry import get_submodel, get_submodel_for_symbol
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.scoring.base_engine import score_snapshot
from fundamental.validation.snapshot_validator import validate_snapshot_against_policy


def resolve_submodel_for_symbol(
    symbol: str,
    submodel: Optional[Union[SubmodelConfig, str]] = None,
) -> SubmodelConfig:
    if isinstance(submodel, SubmodelConfig):
        return submodel
    if isinstance(submodel, str):
        return get_submodel(submodel)

    resolved = get_submodel_for_symbol(symbol)
    if resolved is None:
        raise ValueError(f"未能根据代码 {symbol} 自动匹配基本面子模型")
    return resolved


def analyze_snapshot(
    snapshot: Union[FundamentalSnapshot, Mapping[str, Any]],
    submodel: Optional[Union[SubmodelConfig, str]] = None,
) -> FundamentalScoreCard:
    if isinstance(snapshot, FundamentalSnapshot):
        snapshot_model = snapshot
    else:
        snapshot_model = FundamentalSnapshot(**dict(snapshot))

    submodel_config = resolve_submodel_for_symbol(snapshot_model.symbol, submodel)

    validation = validate_snapshot_against_policy(snapshot_model, submodel_config.field_policy)
    if not validation.is_valid:
        raise ValueError(
            "Snapshot is missing required fields for {}: {}".format(
                submodel_config.submodel_id,
                ", ".join(validation.required_missing),
            )
        )

    missing_metrics = validation.optional_missing + validation.deferred_missing
    return score_snapshot(snapshot_model, submodel_config, missing_metrics=missing_metrics)
