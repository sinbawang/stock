"""Shared helpers for resolving and applying manual supplements."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from fundamental.config.models import SubmodelConfig
from fundamental.data.hk_snapshot_fetcher import FundamentalSnapshotFetchResult
from fundamental.models.snapshot import FundamentalSnapshot

from .manual_supplement_loader import load_manual_supplement_file


def apply_manual_supplement(
    fetched: FundamentalSnapshotFetchResult,
    submodel: SubmodelConfig,
    manual_supplement: Optional[Mapping[str, Any]],
) -> FundamentalSnapshotFetchResult:
    if not manual_supplement:
        return fetched

    updates = {field_name: value for field_name, value in manual_supplement.items() if value is not None}
    if not updates:
        return fetched

    allowed_fields = set(submodel.field_policy.required_core)
    allowed_fields.update(submodel.field_policy.optional_manual)
    allowed_fields.update(submodel.field_policy.deferred_v2)
    allowed_fields.add("notes")

    unknown_fields = sorted(field_name for field_name in updates if field_name not in FundamentalSnapshot.model_fields)
    if unknown_fields:
        raise ValueError(f"Manual supplement contains unknown snapshot fields: {', '.join(unknown_fields)}")

    disallowed_fields = sorted(field_name for field_name in updates if field_name not in allowed_fields)
    if disallowed_fields:
        raise ValueError(
            "Manual supplement fields are not allowed for {}: {}".format(
                submodel.submodel_id,
                ", ".join(disallowed_fields),
            )
        )

    updated_snapshot = fetched.snapshot.model_copy(update=updates)
    field_sources = dict(fetched.field_sources or {})
    field_sources.update({field_name: "manual.supplement" for field_name in updates})
    return replace(
        fetched,
        snapshot=updated_snapshot,
        assumptions=fetched.assumptions
        + (
            "Manual supplement applied before analysis for fields: {}.".format(
                ", ".join(sorted(updates))
            ),
        ),
        raw_payload_refs=fetched.raw_payload_refs + (f"manual-supplement:{fetched.snapshot.symbol}",),
        field_sources=field_sources,
    )


def resolve_manual_supplement(
    manual_supplement: Optional[Mapping[str, Any]],
    manual_supplement_path: Optional[str],
) -> Optional[dict[str, Any]]:
    merged: dict[str, Any] = {}
    if manual_supplement_path:
        merged.update(load_manual_supplement_file(manual_supplement_path))
    if manual_supplement:
        merged.update(dict(manual_supplement))
    return merged or None