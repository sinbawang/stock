"""Validate a snapshot against a submodel field policy."""

from typing import List

from pydantic import BaseModel, Field

from fundamental.config.models import FieldPolicy
from fundamental.models.snapshot import FundamentalSnapshot


class SnapshotValidationResult(BaseModel):
    is_valid: bool
    required_missing: List[str] = Field(default_factory=list)
    optional_missing: List[str] = Field(default_factory=list)
    deferred_missing: List[str] = Field(default_factory=list)


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    return False


def validate_snapshot_against_policy(
    snapshot: FundamentalSnapshot, policy: FieldPolicy
) -> SnapshotValidationResult:
    required_missing = [
        metric for metric in policy.required_core if _is_missing(getattr(snapshot, metric, None))
    ]
    optional_missing = [
        metric for metric in policy.optional_manual if _is_missing(getattr(snapshot, metric, None))
    ]
    deferred_missing = [
        metric for metric in policy.deferred_v2 if _is_missing(getattr(snapshot, metric, None))
    ]
    return SnapshotValidationResult(
        is_valid=not required_missing,
        required_missing=required_missing,
        optional_missing=optional_missing,
        deferred_missing=deferred_missing,
    )
