"""Rule helpers for capital-flow scoring."""

from typing import Iterable, Optional


def present_metric_names(items: Iterable[tuple[str, Optional[float]]]) -> list[str]:
    return [name for name, value in items if value is not None]


def missing_metric_names(items: Iterable[tuple[str, Optional[float]]]) -> list[str]:
    return [name for name, value in items if value is None]


def any_positive(*values: Optional[float]) -> bool:
    return any(value is not None and value > 0 for value in values)


def all_negative_present(*values: Optional[float]) -> bool:
    present_values = [value for value in values if value is not None]
    return bool(present_values) and all(value < 0 for value in present_values)