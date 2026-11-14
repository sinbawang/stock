"""买卖点信号迁移历史同步脚本的单测（design §6.2）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
module_spec = importlib.util.spec_from_file_location(
    "sync_signal_history_cloudbase",
    SCRIPTS / "sync_signal_history_cloudbase.py",
)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("failed to load sync_signal_history_cloudbase.py for tests")
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def _payload() -> dict:
    return {
        "symbol": "600900",
        "name": "长江电力",
        "market": "CN",
        "timeframe": "1m",
        "generated_at": "2026-11-14T15:30:00",
        "code_fingerprint": "fp-1",
        "summary": {
            "lifecycle_frame": {"data_window": "2026-11-01T09:30:00"},
            "signal_points": [
                {
                    "point": "buy_1",
                    "signal_bi_id": 0,
                    "lifecycle_state": "forming",
                    "time": "2026-11-14T10:00:00",
                    "price": 27.01,
                    "forming_at": "2026-11-14T10:06:00",
                    "forming_price": 27.08,
                },
                {
                    "point": "buy_3",
                    "signal_bi_id": 12,
                    "lifecycle_state": "confirmed",
                    "time": "2026-11-14T11:00:00",
                    "price": 27.2,
                    "forming_at": "2026-11-14T11:06:00",
                    "forming_price": 27.25,
                    "confirmed_at": "2026-11-14T11:30:00",
                    "confirmed_price": 27.31,
                },
            ],
            "invalidated_points": [
                {
                    "point": "sell_1",
                    "signal_bi_id": 9,
                    "price": 27.9,
                    "lifecycle_state": "invalidated",
                    "invalidated_reason": "first_class_extreme_broken",
                    "invalidated_premise": "price",
                    "from_state": "forming",
                    "forming_at": "2026-11-14T10:40:00",
                    "forming_price": 27.88,
                    "invalidated_at": "2026-11-14T11:02:00",
                    "invalidated_price": 27.95,
                }
            ],
        },
    }


def test_build_event_records_emits_forming_confirmed_and_invalidated() -> None:
    records = module.build_event_records(_payload(), run_id="run-1")

    assert [record["event"] for record in records] == ["forming", "forming", "confirmed", "invalidated"]
    confirmed = next(record for record in records if record["event"] == "confirmed")
    assert confirmed["confirmed_at"] == "2026-11-14T11:30:00"
    assert confirmed["confirmed_price"] == 27.31
    assert confirmed["forming_price"] == 27.25
    assert confirmed["from_state"] == "forming"

    invalidated = records[-1]
    assert invalidated["invalidated_at"] == "2026-11-14T11:02:00"
    assert invalidated["invalidated_price"] == 27.95
    assert invalidated["from_state"] == "forming"
    assert invalidated["invalidated_reason"] == "first_class_extreme_broken"


def test_event_id_is_stable_across_runs_and_sanitized() -> None:
    first = module.build_event_records(_payload(), run_id="run-1")
    second = module.build_event_records(_payload(), run_id="run-2")

    assert [record["_id"] for record in first] == [record["_id"] for record in second]
    assert all("|" in record["_id"] for record in first)
    # 秒级时间戳里的冒号必须被替换，避免作为文档 _id 非法字符。
    assert all(":" not in record["_id"] for record in first)


def test_anchor_key_zero_is_not_treated_as_missing() -> None:
    records = module.build_event_records(_payload(), run_id="run-1")

    forming = [record for record in records if record["event"] == "forming"]
    assert forming[0]["anchor_key"] == "0"
    assert forming[0]["_id"].split("|")[3] == "0"


def test_invalidated_event_falls_back_to_confirmed_from_state() -> None:
    payload = _payload()
    payload["summary"]["invalidated_points"][0].pop("from_state")

    records = module.build_event_records(payload, run_id="run-1")
    invalidated = records[-1]

    assert invalidated["from_state"] == "confirmed"


def test_records_clamp_confirmed_at_before_forming_at() -> None:
    """spec §2.8.4 不变量：确认不得早于检出（旧 tech.json 倒挂时夹紧 + 价格同源）。"""
    payload = _payload()
    payload["summary"]["signal_points"] = [
        {
            "point": "sell_3",
            "signal_bi_id": 21,
            "lifecycle_state": "confirmed",
            "time": "2026-09-01T11:00:00",
            "price": 36.02,
            "forming_at": "2026-09-02T13:30:00",
            "forming_price": 33.7,
            "confirmed_at": "2026-09-02T10:30:00",
            "confirmed_price": 33.58,
        }
    ]

    records = module.build_event_records(payload, run_id="run-1")
    confirmed = next(record for record in records if record["event"] == "confirmed")

    assert confirmed["forming_at"] == "2026-09-02T13:30:00"
    assert confirmed["confirmed_at"] == "2026-09-02T13:30:00"
    assert confirmed["confirmed_price"] == 33.7
