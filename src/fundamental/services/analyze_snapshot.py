"""Analyze one fundamental snapshot against a configured submodel."""

from typing import Any, Mapping, Union

from fundamental.config.models import SubmodelConfig
from fundamental.config.registry import get_submodel
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.scoring.base_engine import score_snapshot
from fundamental.validation.snapshot_validator import validate_snapshot_against_policy


def analyze_snapshot(
    snapshot: Union[FundamentalSnapshot, Mapping[str, Any]],
    submodel: Union[SubmodelConfig, str],
) -> FundamentalScoreCard:
    if isinstance(snapshot, FundamentalSnapshot):
        snapshot_model = snapshot
    else:
        snapshot_model = FundamentalSnapshot(**dict(snapshot))

    if isinstance(submodel, SubmodelConfig):
        submodel_config = submodel
    else:
        submodel_config = get_submodel(submodel)

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
