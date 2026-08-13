from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyGate:
    name: str
    command: list[str]


SEGMENT_SAFETY_GATES = [
    SafetyGate(
        name="core",
        command=[
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_segment.py",
            "tests/test_segment_rediscrimination_matrix.py",
        ],
    ),
    SafetyGate(
        name="regression",
        command=[
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_segment_regression_suite.py",
            "tests/test_segment_bootstrap_anchor.py",
            "tests/test_segment_regression_000591.py",
            "tests/test_segment_regression_00700.py",
            "tests/test_segment_regression_03690.py",
            "tests/test_segment_lesson_boundary_fixtures.py",
        ],
    ),
    SafetyGate(
        name="consumer",
        command=[
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_segment_consumer_mode_smoke.py",
        ],
    ),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run segment safety gates via a single entry.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only without execution.")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional gate names to run. Choices: core regression consumer",
    )
    return parser.parse_args()


def _select_gates(only: list[str] | None) -> list[SafetyGate]:
    if not only:
        return SEGMENT_SAFETY_GATES

    allowed = {gate.name: gate for gate in SEGMENT_SAFETY_GATES}
    selected: list[SafetyGate] = []
    for name in only:
        gate = allowed.get(name)
        if gate is None:
            raise ValueError(f"Unknown gate name: {name}")
        selected.append(gate)
    return selected


def _run_gate(gate: SafetyGate, dry_run: bool) -> int:
    printable = " ".join(gate.command)
    print(f"[segment-safety] {gate.name}: {printable}")
    if dry_run:
        return 0

    completed = subprocess.run(gate.command)
    return int(completed.returncode)


def main() -> int:
    args = _parse_args()
    try:
        gates = _select_gates(args.only)
    except ValueError as exc:
        print(f"[segment-safety] {exc}", file=sys.stderr)
        return 2

    for gate in gates:
        code = _run_gate(gate, args.dry_run)
        if code != 0:
            print(f"[segment-safety] failed gate={gate.name} exit_code={code}", file=sys.stderr)
            return code

    print("[segment-safety] all selected gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
