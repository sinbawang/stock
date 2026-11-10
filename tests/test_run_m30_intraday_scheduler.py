from __future__ import annotations

import importlib.util
import argparse
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


def test_most_recent_due_slot_rolls_back_to_previous_trading_day() -> None:
    slots = module.DEFAULT_EOD_SLOTS

    assert module.most_recent_due_slot(_dt("2026-08-17T15:40:00"), slots) == _dt("2026-08-14T16:10:00")
    assert module.most_recent_due_slot(_dt("2026-08-17T16:20:00"), slots) == _dt("2026-08-17T16:10:00")
    assert module.most_recent_due_slot(_dt("2026-08-16T20:00:00"), slots) == _dt("2026-08-14T16:10:00")


def test_most_recent_due_slot_handles_multiple_slots() -> None:
    assert module.most_recent_due_slot(_dt("2026-08-17T11:05:00"), module.DEFAULT_INTRADAY_SLOTS) == _dt("2026-08-17T11:00:00")
    assert module.most_recent_due_slot(_dt("2026-08-17T09:20:00"), module.DEFAULT_INTRADAY_SLOTS) == _dt("2026-08-14T15:30:00")


def test_resolve_trigger_slot_supports_eod_catchup() -> None:
    now = _dt("2026-08-17T20:00:00")

    slot, reason = module.resolve_trigger_slot(
        now,
        grace_seconds=300,
        catchup=True,
        slots=module.DEFAULT_EOD_SLOTS,
    )

    assert slot == _dt("2026-08-17T16:10:00")
    assert reason == "catch-up"

    already_done, _ = module.resolve_trigger_slot(
        now,
        grace_seconds=300,
        catchup=True,
        slots=module.DEFAULT_EOD_SLOTS,
        last_triggered_slot=slot,
    )
    assert already_done is None

    disabled, _ = module.resolve_trigger_slot(
        now,
        grace_seconds=300,
        catchup=False,
        slots=module.DEFAULT_EOD_SLOTS,
    )
    assert disabled is None


def test_resolve_trigger_slot_prefers_scheduled_slot_over_catchup() -> None:
    slot, reason = module.resolve_trigger_slot(
        _dt("2026-08-17T16:12:00"),
        grace_seconds=300,
        catchup=True,
        slots=module.DEFAULT_EOD_SLOTS,
    )

    assert slot == _dt("2026-08-17T16:10:00")
    assert reason == "scheduled"


def test_last_triggered_slot_state_roundtrip(tmp_path) -> None:
    state_path = tmp_path / "state" / "eod-last-run.txt"
    slot = _dt("2026-08-17T16:10:00")

    module.save_last_triggered_slot(state_path, slot)

    assert module.load_last_triggered_slot(state_path, TZ) == slot
    assert module.load_last_triggered_slot(None, TZ) is None
    assert module.load_last_triggered_slot(tmp_path / "missing.txt", TZ) is None


def test_next_slot_after_supports_m5_intraday_profile_around_session_boundaries() -> None:
    assert module.next_slot_after(_dt("2026-08-17T09:31:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T09:35:00")
    assert module.next_slot_after(_dt("2026-08-17T12:01:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T13:05:00")
    assert module.next_slot_after(_dt("2026-08-17T15:31:00"), module.DEFAULT_M5_INTRADAY_SLOTS) == _dt("2026-08-17T15:35:00")


def test_build_command_for_intraday_profile_requests_30m_generation(monkeypatch) -> None:
    monkeypatch.delenv("INTRADAY_SCHEDULER_EXTRA_ARGS", raising=False)
    monkeypatch.delenv("INTRADAY_SCHEDULER_PYTHON", raising=False)

    args = argparse.Namespace(
        command=None,
        profile="intraday",
    )

    command = module.build_command(args)

    assert "--local-store-read-only" not in command
    assert command[1].endswith("run_scheduled_technical_refresh.py")
    assert "--refresh-mode" in command
    assert command[command.index("--refresh-mode") + 1] == "m30_intraday"
    assert "--sync-kline-cache-restore-before-regenerate" not in command
    assert "--publish-json-only" in command
    assert "--no-export-structure-images" in command
    assert "--tech-timeframes" in command
    tech_index = command.index("--tech-timeframes")
    publish_index = command.index("--publish-timeframes")
    publish_json_only_index = command.index("--publish-json-only")
    assert command[tech_index + 1 : publish_index] == ["30m", "5m", "1m"]
    assert command[publish_index + 1 : publish_json_only_index] == ["30m", "5m", "1m", "day"]


def test_build_command_for_eod_profile_allows_fresh_fetch(monkeypatch) -> None:
    monkeypatch.delenv("EOD_SCHEDULER_EXTRA_ARGS", raising=False)
    monkeypatch.delenv("INTRADAY_SCHEDULER_PYTHON", raising=False)

    args = argparse.Namespace(
        command=None,
        profile="eod",
    )

    command = module.build_command(args)

    assert "--local-store-read-only" not in command


def test_build_command_for_m5_profile_disables_structure_images(monkeypatch) -> None:
    monkeypatch.delenv("M5_INTRADAY_SCHEDULER_EXTRA_ARGS", raising=False)
    monkeypatch.delenv("INTRADAY_SCHEDULER_PYTHON", raising=False)

    args = argparse.Namespace(
        command=None,
        profile="m5_intraday",
    )

    command = module.build_command(args)

    assert command[1].endswith("run_scheduled_technical_refresh.py")
    assert "--publish-json-only" in command
    assert "--no-export-structure-images" in command

def test_intraday_profiles_enable_feishu_notify(monkeypatch) -> None:
    for env_name in (
        "INTRADAY_SCHEDULER_EXTRA_ARGS",
        "M5_INTRADAY_SCHEDULER_EXTRA_ARGS",
        "M1_INTRADAY_SCHEDULER_EXTRA_ARGS",
        "EOD_SCHEDULER_EXTRA_ARGS",
        "INTRADAY_SCHEDULER_PYTHON",
    ):
        monkeypatch.delenv(env_name, raising=False)

    for profile in ("intraday", "m5_intraday", "m1_intraday"):
        command = module.build_command(argparse.Namespace(command=None, profile=profile))
        assert "--notify" in command, profile
        assert command[1].endswith("run_scheduled_technical_refresh.py")

    eod_command = module.build_command(argparse.Namespace(command=None, profile="eod"))
    assert "--notify" not in eod_command
