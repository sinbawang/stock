from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "run_m30_intraday_scheduler",
    SCRIPTS / "run_m30_intraday_scheduler.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


TZ = ZoneInfo("Asia/Shanghai")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


def test_resolve_due_slot_matches_half_hour_openings() -> None:
    due = module.resolve_due_slot(_dt("2026-08-17T09:31:20"), 150)

    assert due == _dt("2026-08-17T09:30:00")


def test_resolve_due_slot_skips_late_checks_and_lunch_gap() -> None:
    assert module.resolve_due_slot(_dt("2026-08-17T09:33:01"), 150) is None
    assert module.resolve_due_slot(_dt("2026-08-17T12:30:00"), 150) is None


def test_resolve_due_slot_skips_weekends() -> None:
    assert module.resolve_due_slot(_dt("2026-08-16T09:30:30"), 150) is None


def test_next_slot_after_advances_within_day_and_across_weekend() -> None:
    assert module.next_slot_after(_dt("2026-08-17T09:45:00")) == _dt("2026-08-17T10:00:00")
    assert module.next_slot_after(_dt("2026-08-14T15:40:00")) == _dt("2026-08-17T09:30:00")


def test_resolve_due_slot_supports_eod_profile_slot() -> None:
    due = module.resolve_due_slot(_dt("2026-08-17T16:12:00"), 300, module.DEFAULT_EOD_SLOTS)

    assert due == _dt("2026-08-17T16:10:00")


def test_resolve_due_slot_supports_m5_intraday_profile_slots_and_skips_half_hour() -> None:
    due = module.resolve_due_slot(_dt("2026-08-17T09:36:00"), 150, module.DEFAULT_M5_INTRADAY_SLOTS)

    assert due == _dt("2026-08-17T09:35:00")
    assert module.resolve_due_slot(_dt("2026-08-17T09:31:00"), 150, module.DEFAULT_M5_INTRADAY_SLOTS) is None
    assert module.resolve_due_slot(_dt("2026-08-17T15:56:00"), 150, module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T15:55:00")


def test_next_slot_after_supports_eod_profile_weekday_and_weekend() -> None:
    assert module.next_slot_after(_dt("2026-08-17T15:40:00"), module.DEFAULT_EOD_SLOTS) == _dt("2026-08-17T16:10:00")
    assert module.next_slot_after(_dt("2026-08-14T16:20:00"), module.DEFAULT_EOD_SLOTS) == _dt("2026-08-17T16:10:00")


def test_next_slot_after_supports_m5_intraday_profile_around_session_boundaries() -> None:
    assert module.next_slot_after(_dt("2026-08-17T09:31:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T09:35:00")
    assert module.next_slot_after(_dt("2026-08-17T12:01:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T13:05:00")
    assert module.next_slot_after(_dt("2026-08-17T15:31:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T15:35:00")