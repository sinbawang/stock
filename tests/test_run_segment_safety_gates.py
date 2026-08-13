import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

_spec = importlib.util.spec_from_file_location(
    "run_segment_safety_gates",
    SCRIPTS / "run_segment_safety_gates.py",
)
module = importlib.util.module_from_spec(_spec) if _spec and _spec.loader else None
if module is not None:
    sys.modules[_spec.name] = module
    _spec.loader.exec_module(module)
else:
    raise RuntimeError("failed to load run_segment_safety_gates.py for tests")


def test_select_gates_returns_all_when_only_is_empty() -> None:
    gates = module._select_gates(None)

    assert len(gates) == len(module.SEGMENT_SAFETY_GATES)
    assert {gate.name for gate in gates} == {"core", "regression", "consumer"}


def test_select_gates_raises_for_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown gate name"):
        module._select_gates(["unknown"])


def test_run_gate_dry_run_returns_zero() -> None:
    gate = module.SafetyGate(name="dry", command=["python", "-m", "pytest", "-q"])

    code = module._run_gate(gate, dry_run=True)

    assert code == 0
