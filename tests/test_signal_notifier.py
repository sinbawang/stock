from __future__ import annotations

import json
from pathlib import Path

import pytest

from notify.feishu import FeishuConfigError, send_feishu_message, sign_feishu_request
from notify.signal_notifier import (
    IndexBrief,
    SignalEvent,
    build_signal_card,
    collect_signal_events_from_reports,
    event_key,
    extract_index_brief,
    extract_signal_events,
    load_index_brief,
    notify_new_signals,
)


def _tech_payload() -> dict:
    return {
        "symbol": "000591",
        "name": "太阳能",
        "timeframe": "30m",
        "summary": {
            "signal_points": [
                {"point": "sell3", "lifecycle_state": "confirmed", "time": "2026-08-04T10:00:00", "price": 4.63, "invalidated_reason": None},
                {"point": "buy1", "lifecycle_state": "confirmed", "time": "2026-08-05T14:00:00", "price": 4.2, "invalidated_reason": None},
                {"point": "buy2", "lifecycle_state": "confirmed", "time": "2026-08-06T10:30:00", "price": 4.1, "invalidated_reason": "first_class_extreme_broken"},
            ],
            "forming_points": [
                {"point": "buy3", "lifecycle_state": "forming", "time": "2026-08-07T11:00:00", "price": 4.5},
            ],
            "invalidated_points": [],
        },
    }


def _index_tech_payload() -> dict:
    return {
        "symbol": "HSTECH",
        "name": "恒生科技指数",
        "timeframe": "1m",
        "summary": {
            "operation_level": "1M",
            "conclusion": "跌破中枢后反抽下沿失败，当前按三卖确认处理。",
            "suggestion": "反抽不过 430.00 以减仓为主，不逆势加仓。",
            "bias": "跌破中枢后反抽下沿失败",
            "score": 67,
            "rating": "B",
            "oscillation_rhythm_state": "down_bias",
            "divergence": {
                "top": {"active": False},
                "bottom": {"active": True, "time": "2026-09-11T14:57:00"},
            },
        },
    }


def test_extract_index_brief_reads_core_fields() -> None:
    brief = extract_index_brief(_index_tech_payload())
    assert brief is not None
    assert brief.symbol == "HSTECH"
    assert brief.name == "恒生科技指数"
    assert brief.level_label == "1M"
    assert brief.rating == "B"
    assert brief.score == 67
    assert brief.oscillation_label == "偏空节奏"
    assert brief.bottom_divergence is True
    assert brief.top_divergence is False


def test_load_index_brief_from_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    index_dir = reports / "HSTECH" / "1m"
    index_dir.mkdir(parents=True)
    (index_dir / "tech.json").write_text(
        json.dumps(_index_tech_payload(), ensure_ascii=False), encoding="utf-8"
    )
    brief = load_index_brief(reports, symbol="HSTECH", timeframe="1m")
    assert brief is not None and brief.name == "恒生科技指数"
    # 缺失报告时返回 None，不影响推送
    assert load_index_brief(reports, symbol="HSTECH", timeframe="5m") is None


def test_build_signal_card_includes_index_brief() -> None:
    events = extract_signal_events(_tech_payload())
    brief = extract_index_brief(_index_tech_payload())
    card = build_signal_card(events, title="买卖点", index_brief=brief)
    elements = card["card"]["elements"]
    # 顶部应为大盘简报 + 分隔线，其后才是买卖点
    head = elements[0]["text"]["content"]
    assert "恒生科技指数 1M 大盘技术面建议" in head
    assert "底背驰" in head
    assert elements[1]["tag"] == "hr"
    assert "三卖" in elements[-1]["text"]["content"]


def test_build_signal_card_without_brief_keeps_single_div() -> None:
    events = extract_signal_events(_tech_payload())
    card = build_signal_card(events)
    assert len(card["card"]["elements"]) == 1


def test_notify_new_signals_passes_index_brief(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    sent: list = []

    def fake_sender(payload, **kwargs):
        sent.append(payload)
        return {"code": 0}

    events = extract_signal_events(_tech_payload())
    brief = extract_index_brief(_index_tech_payload())
    notify_new_signals(events, state_path=state, sender=fake_sender, index_brief=brief)
    assert len(sent) == 1
    head = sent[0]["card"]["elements"][0]["text"]["content"]
    assert "恒生科技指数" in head


def test_extract_signal_events_skips_invalidated_and_labels_points() -> None:
    events = extract_signal_events(_tech_payload())
    # buy2 被标记失效应跳过；保留 sell3(确认)/buy1(确认)/buy3(预备)
    assert len(events) == 3
    by_point = {e.point: e for e in events}
    assert by_point["sell3"].direction == "sell"
    assert by_point["sell3"].point_label == "三卖"
    assert by_point["sell3"].lifecycle_label == "确认"
    assert by_point["buy1"].direction == "buy"
    assert by_point["buy3"].lifecycle == "forming"
    assert by_point["buy3"].lifecycle_label == "预备"
    assert "buy2" not in by_point


def test_extract_signal_events_can_exclude_forming() -> None:
    events = extract_signal_events(_tech_payload(), include_forming=False)
    assert all(e.lifecycle != "forming" for e in events)
    assert {e.point for e in events} == {"sell3", "buy1"}


def test_event_key_separates_forming_and_confirmed() -> None:
    forming = SignalEvent("x", "", "30m", "buy1", "一买", "buy", "forming", "预备", "t", None)
    confirmed = SignalEvent("x", "", "30m", "buy1", "一买", "buy", "confirmed", "确认", "t", None)
    assert event_key(forming) != event_key(confirmed)


def test_notify_dedupes_across_runs(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    sent: list = []

    def fake_sender(payload, **kwargs):
        sent.append(payload)
        return {"code": 0}

    events = extract_signal_events(_tech_payload())
    first = notify_new_signals(events, state_path=state, sender=fake_sender)
    assert len(first) == 3
    assert len(sent) == 1  # 一张卡片汇总多条

    # 同样的事件再跑一次，应全部去重，不再发送
    second = notify_new_signals(events, state_path=state, sender=fake_sender)
    assert second == []
    assert len(sent) == 1


def test_notify_seed_only_marks_without_sending(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    sent: list = []
    events = extract_signal_events(_tech_payload())
    new = notify_new_signals(events, state_path=state, sender=lambda *a, **k: sent.append(a), seed_only=True)
    assert len(new) == 3
    assert sent == []  # 未发送
    # 基线已写入，后续不再推送
    again = notify_new_signals(events, state_path=state, sender=lambda *a, **k: sent.append(a))
    assert again == []
    assert sent == []


def test_notify_dry_run_does_not_send_or_persist(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    sent: list = []
    events = extract_signal_events(_tech_payload())
    new = notify_new_signals(events, state_path=state, sender=lambda *a, **k: sent.append(a), dry_run=True)
    assert len(new) == 3
    assert sent == []
    assert not state.exists()  # dry-run 不写状态


def test_build_signal_card_structure() -> None:
    events = extract_signal_events(_tech_payload())
    card = build_signal_card(events, title="买卖点")
    assert card["msg_type"] == "interactive"
    assert "买卖点（3）" == card["card"]["header"]["title"]["content"]
    assert card["card"]["header"]["template"] == "blue"  # 买卖混合
    content = card["card"]["elements"][0]["text"]["content"]
    assert "三卖" in content and "一买" in content


def test_collect_signal_events_from_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    tech_dir = reports / "000591" / "30m"
    tech_dir.mkdir(parents=True)
    (tech_dir / "tech.json").write_text(json.dumps(_tech_payload(), ensure_ascii=False), encoding="utf-8")
    events = collect_signal_events_from_reports(reports, timeframes=["30m"])
    assert len(events) == 3
    assert collect_signal_events_from_reports(reports, timeframes=["5m"]) == []


def test_sign_feishu_request_is_deterministic() -> None:
    first = sign_feishu_request("1700000000", "secret")
    second = sign_feishu_request("1700000000", "secret")
    assert first == second
    assert sign_feishu_request("1700000001", "secret") != first


def test_send_feishu_message_requires_webhook(monkeypatch) -> None:
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    with pytest.raises(FeishuConfigError):
        send_feishu_message({"msg_type": "text"}, webhook_url=None)


def test_send_feishu_message_retries_then_succeeds() -> None:
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0}

    class _Session:
        def post(self, url, json=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return _Resp()

    data = send_feishu_message(
        {"msg_type": "text"},
        webhook_url="https://example.com/hook",
        retries=2,
        session_factory=_Session,
    )
    assert data == {"code": 0}
    assert calls["n"] == 2
