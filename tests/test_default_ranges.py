from datetime import datetime

from chanlun.default_ranges import default_structure_start


def test_default_structure_start_day_is_conservative() -> None:
    start = default_structure_start("day", now=datetime(2026, 6, 19, 16, 0))
    assert start == "2023-09-23"


def test_default_structure_start_60m_is_conservative() -> None:
    start = default_structure_start("60m", now=datetime(2026, 6, 19, 16, 0))
    assert start == "2025-08-23 09:30"


def test_default_structure_start_15m_is_conservative() -> None:
    start = default_structure_start("15m", now=datetime(2026, 6, 19, 16, 0))
    assert start == "2026-02-19 09:30"


def test_default_structure_start_30m_is_conservative() -> None:
    start = default_structure_start("30m", now=datetime(2026, 6, 19, 16, 0))
    assert start == "2025-12-21 09:30"


def test_default_structure_start_5m_is_conservative() -> None:
    start = default_structure_start("5m", now=datetime(2026, 6, 19, 16, 0))
    assert start == "2026-05-20 09:30"