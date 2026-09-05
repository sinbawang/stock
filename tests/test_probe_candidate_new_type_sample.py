from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build" / "probe_candidate_new_type_sample.py"

spec = importlib.util.spec_from_file_location("probe_candidate_new_type_sample", MODULE_PATH)
assert spec is not None and spec.loader is not None
probe_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe_module
spec.loader.exec_module(probe_module)


def test_scan_candidate_new_type_builds_payload_and_writes_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(probe_module, "_load_rows", lambda symbol, timeframe: [{"ts": "2026-08-01 09:31"}, {"ts": "2026-08-01 09:32"}])
    monkeypatch.setattr(probe_module, "_select_cutoffs", lambda rows, start, end, step: ["2026-08-01 09:31", "2026-08-01 09:32"])
    replay_rows = [
        {"cutoff": "2026-08-01 09:31", "rows": 1, "relationship_kind": "undetermined", "transition_state": "none", "ongoing_zs_count": 0, "current_structure_status": "ongoing_same_type", "error": "skip"},
        {"cutoff": "2026-08-01 09:32", "rows": 2, "relationship_kind": "completed_then_new_type_ongoing", "transition_state": "candidate_new_type", "ongoing_zs_count": 1, "current_structure_status": "candidate_completed_waiting_stability", "last_completed_exists": True},
    ]
    iterator = iter(replay_rows)
    monkeypatch.setattr(probe_module, "_replay", lambda symbol, name, timeframe, cutoff, rows: next(iterator))
    monkeypatch.setattr(probe_module, "_state_matches", lambda item, target_state: item.get("transition_state") == "candidate_new_type")

    output_path = tmp_path / "probe.json"
    payload, written_path = probe_module.scan_candidate_new_type(
        symbol="000651",
        name="格力电器",
        timeframe="5m",
        target_state="exact_candidate_new_type",
        output=output_path,
    )

    assert written_path == output_path
    assert payload == {
        "symbol": "000651",
        "name": "格力电器",
        "timeframe": "5m",
        "target_state": "exact_candidate_new_type",
        "scanned": 2,
        "matches": [
            {"cutoff": "2026-08-01 09:32", "rows": 2, "relationship_kind": "completed_then_new_type_ongoing", "transition_state": "candidate_new_type", "ongoing_zs_count": 1, "current_structure_status": "candidate_completed_waiting_stability", "last_completed_exists": True}
        ],
    }
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_scan_candidate_new_type_respects_limit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(probe_module, "_load_rows", lambda symbol, timeframe: [{"ts": "2026-08-01 09:31"}, {"ts": "2026-08-01 09:32"}, {"ts": "2026-08-01 09:33"}])
    monkeypatch.setattr(probe_module, "_select_cutoffs", lambda rows, start, end, step: ["2026-08-01 09:31", "2026-08-01 09:32", "2026-08-01 09:33"])
    replay_rows = [
        {"cutoff": "2026-08-01 09:31", "rows": 1, "relationship_kind": "completed_then_new_type_ongoing", "transition_state": "candidate_new_type", "ongoing_zs_count": 1, "current_structure_status": "candidate_completed_waiting_stability", "last_completed_exists": True},
        {"cutoff": "2026-08-01 09:32", "rows": 2, "relationship_kind": "completed_then_new_type_ongoing", "transition_state": "candidate_new_type", "ongoing_zs_count": 1, "current_structure_status": "candidate_completed_waiting_stability", "last_completed_exists": True},
        {"cutoff": "2026-08-01 09:33", "rows": 3, "relationship_kind": "completed_then_new_type_ongoing", "transition_state": "candidate_new_type", "ongoing_zs_count": 1, "current_structure_status": "candidate_completed_waiting_stability", "last_completed_exists": True},
    ]
    iterator = iter(replay_rows)
    monkeypatch.setattr(probe_module, "_replay", lambda symbol, name, timeframe, cutoff, rows: next(iterator))
    monkeypatch.setattr(probe_module, "_state_matches", lambda item, target_state: True)

    payload, _ = probe_module.scan_candidate_new_type(
        symbol="000651",
        name="格力电器",
        timeframe="5m",
        target_state="exact_candidate_new_type",
        limit=2,
        output=tmp_path / "probe-limit.json",
    )

    assert payload["scanned"] == 3
    assert len(payload["matches"]) == 2