from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time as time_module
from typing import Literal
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_GRACE_SECONDS = 150
DEFAULT_POLL_SECONDS = 30
SchedulerProfile = Literal["intraday", "m5_intraday", "eod"]
DEFAULT_INTRADAY_COMMAND = (
    "python",
    str(ROOT / "scripts" / "refresh_holdings_publish_to_cloudbase.py"),
    "--latest-only",
    "--sync-kline-cache-restore-before-regenerate",
    "--local-store-read-only",
    "--skip-gen-base",
    "--skip-gen-fund",
    "--tech-timeframes",
    "30m",
    "5m",
    "1m",
    "--publish-timeframes",
    "30m",
    "5m",
    "1m",
    "day",
)
DEFAULT_EOD_COMMAND = (
    "python",
    str(ROOT / "scripts" / "refresh_holdings_publish_to_cloudbase.py"),
    "--latest-only",
    "--sync-kline-cache-restore-before-regenerate",
    "--local-store-read-only",
)
DEFAULT_M5_INTRADAY_COMMAND = (
    "python",
    str(ROOT / "scripts" / "run_scheduled_technical_refresh.py"),
    "--refresh-mode",
    "m5_intraday",
    "--tech-timeframes",
    "5m",
    "1m",
    "--publish-timeframes",
    "5m",
    "1m",
)
DEFAULT_INTRADAY_SLOTS = (
    time(9, 30),
    time(10, 0),
    time(10, 30),
    time(11, 0),
    time(11, 30),
    time(12, 0),
    time(13, 0),
    time(13, 30),
    time(14, 0),
    time(14, 30),
    time(15, 0),
    time(15, 30),
)
DEFAULT_EOD_SLOTS = (time(16, 10),)
DEFAULT_M5_INTRADAY_SLOTS = tuple(
    time(hour, minute)
    for hour, minutes in (
        (9, (35, 40, 45, 50, 55)),
        (10, (5, 10, 15, 20, 25, 35, 40, 45, 50, 55)),
        (11, (5, 10, 15, 20, 25, 35, 40, 45, 50, 55)),
        (13, (5, 10, 15, 20, 25, 35, 40, 45, 50, 55)),
        (14, (5, 10, 15, 20, 25, 35, 40, 45, 50, 55)),
        (15, (5, 10, 15, 20, 25, 35, 40, 45, 50, 55)),
    )
    for minute in minutes
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a configured refresh command on trading-day schedule slots.",
    )
    parser.add_argument(
        "--profile",
        choices=("intraday", "m5_intraday", "eod"),
        default=os.environ.get("SCHEDULER_PROFILE", "intraday"),
        help="Which built-in schedule profile to use when slots or command are not overridden.",
    )
    parser.add_argument("--timezone", default=os.environ.get("INTRADAY_SCHEDULER_TIMEZONE", DEFAULT_TIMEZONE))
    parser.add_argument(
        "--grace-seconds",
        type=int,
        default=int(os.environ.get("INTRADAY_SCHEDULER_GRACE_SECONDS", DEFAULT_GRACE_SECONDS)),
        help="How long after a slot boundary the scheduler still treats it as due.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.environ.get("INTRADAY_SCHEDULER_POLL_SECONDS", DEFAULT_POLL_SECONDS)),
        help="Maximum sleep interval while waiting for the next slot.",
    )
    parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        default=None,
        help="Optional explicit command override. When omitted the scheduler runs the built-in profile command.",
    )
    parser.add_argument(
        "--slots",
        nargs="+",
        default=None,
        help="Optional HH:MM slot list. When omitted the scheduler uses the built-in profile slots.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional log label override.",
    )
    return parser.parse_args()


def log(message: str, *, label: str) -> None:
    print(f"[{label}] {message}", flush=True)


def is_trading_day(moment: datetime) -> bool:
    return moment.weekday() < 5


def parse_slot(value: str) -> time:
    hour_text, minute_text = value.split(":", 1)
    return time(int(hour_text), int(minute_text))


def resolve_slots(args: argparse.Namespace) -> tuple[time, ...]:
    if args.slots:
        return tuple(parse_slot(value) for value in args.slots)
    if args.profile == "eod":
        return DEFAULT_EOD_SLOTS
    if args.profile == "m5_intraday":
        return DEFAULT_M5_INTRADAY_SLOTS
    return DEFAULT_INTRADAY_SLOTS


def resolve_label(args: argparse.Namespace) -> str:
    if args.label:
        return args.label
    if args.profile == "eod":
        return "eod-scheduler"
    if args.profile == "m5_intraday":
        return "m5-intraday-scheduler"
    return "intraday-scheduler"


def iter_session_slots(day: datetime, slots: tuple[time, ...]) -> list[datetime]:
    tzinfo = day.tzinfo
    return [datetime.combine(day.date(), slot, tzinfo=tzinfo) for slot in slots]


def resolve_due_slot(moment: datetime, grace_seconds: int, slots: tuple[time, ...] | None = None) -> datetime | None:
    if not is_trading_day(moment):
        return None
    active_slots = slots or DEFAULT_INTRADAY_SLOTS
    for slot in reversed(iter_session_slots(moment, active_slots)):
        delta = (moment - slot).total_seconds()
        if 0 <= delta <= grace_seconds:
            return slot
        if delta > grace_seconds:
            return None
    return None


def next_slot_after(moment: datetime, slots: tuple[time, ...] | None = None) -> datetime:
    active_slots = slots or DEFAULT_INTRADAY_SLOTS
    cursor = moment
    while True:
        if is_trading_day(cursor):
            for slot in iter_session_slots(cursor, active_slots):
                if slot > moment:
                    return slot
        next_day = (cursor + timedelta(days=1)).date()
        cursor = datetime.combine(next_day, active_slots[0], tzinfo=moment.tzinfo)


def build_command(args: argparse.Namespace) -> list[str]:
    if args.command:
        return list(args.command)

    python_bin = os.environ.get("INTRADAY_SCHEDULER_PYTHON") or sys.executable
    if args.profile == "eod":
        template = DEFAULT_EOD_COMMAND
    elif args.profile == "m5_intraday":
        template = DEFAULT_M5_INTRADAY_COMMAND
    else:
        template = DEFAULT_INTRADAY_COMMAND
    command = [python_bin if token == "python" else token for token in template]
    if args.profile == "eod":
        extra_env = "EOD_SCHEDULER_EXTRA_ARGS"
    elif args.profile == "m5_intraday":
        extra_env = "M5_INTRADAY_SCHEDULER_EXTRA_ARGS"
    else:
        extra_env = "INTRADAY_SCHEDULER_EXTRA_ARGS"
    extra_args = os.environ.get(extra_env, "").strip()
    if extra_args:
        command.extend(shlex.split(extra_args))
    return command


def run_scheduler(args: argparse.Namespace) -> int:
    tz = ZoneInfo(args.timezone)
    slots = resolve_slots(args)
    label = resolve_label(args)
    command = build_command(args)
    poll_seconds = max(1, int(args.poll_seconds))
    grace_seconds = max(0, int(args.grace_seconds))
    last_triggered_slot: datetime | None = None

    log(f"profile={args.profile}", label=label)
    log(f"timezone={args.timezone}", label=label)
    log(f"grace_seconds={grace_seconds}", label=label)
    log(f"poll_seconds={poll_seconds}", label=label)
    log(f"slots={','.join(slot.strftime('%H:%M') for slot in slots)}", label=label)
    log(f"command={shlex.join(command)}", label=label)

    while True:
        now = datetime.now(tz)
        due_slot = resolve_due_slot(now, grace_seconds, slots)
        if due_slot is not None and due_slot != last_triggered_slot:
            log(f"triggering slot {due_slot.isoformat(timespec='minutes')}", label=label)
            completed = subprocess.run(command, cwd=ROOT)
            log(f"slot finished with exit code {completed.returncode}", label=label)
            last_triggered_slot = due_slot
            continue

        next_slot = next_slot_after(now, slots)
        sleep_seconds = min(poll_seconds, max(1.0, (next_slot - now).total_seconds()))
        log(f"next_slot={next_slot.isoformat(timespec='minutes')} sleep={sleep_seconds:.0f}s", label=label)
        time_module.sleep(sleep_seconds)


def main() -> int:
    args = parse_args()
    return run_scheduler(args)


if __name__ == "__main__":
    raise SystemExit(main())