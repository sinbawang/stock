from __future__ import annotations

import json
from pathlib import Path

import pytest

from notify.feishu import FeishuConfigError, send_feishu_message, sign_feishu_request
from notify.signal_notifier import (
    SignalEvent,
    build_signal_card,
    collect_signal_events_from_reports,
    event_key,
    extract_signal_events,
    load_market_index_advice,
    notify_from_reports,
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


def test_build_signal_card_includes_hstech_1m_advice() -> None:
    events = extract_signal_events(_tech_payload())
    advice = "【恒生科技指数 1M 操作建议】\n结论：观察，等待确认。\n建议：先按观察态处理。"
    card = build_signal_card(events, title="买卖点", market_advice=advice)

    contents = [
        element.get("text", {}).get("content", "")
        for element in card["card"]["elements"]
        if isinstance(element, dict)
    ]
    assert any("恒生科技指数 1M 操作建议" in content for content in contents)
    assert any("观察，等待确认" in content for content in contents)


def test_load_market_index_advice_from_hstech_1m(tmp_path: Path) -> None:
    tech_dir = tmp_path / "HSTECH" / "1m"
    tech_dir.mkdir(parents=True)
    payload = {
        "symbol": "HSTECH",
        "name": "恒生科技指数",
        "timeframe": "1m",
        "generated_at": "2026-10-31T11:45:02+08:00",
        "advice_text": "【恒生科技指数 1M 操作建议】\n结论：观察，等待确认。",
    }
    (tech_dir / "tech.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    advice = load_market_index_advice(tmp_path)

    assert advice is not None
    assert "恒生科技指数 1M 操作建议" in advice
    assert "数据时间：2026-10-31 11:45" in advice


def test_load_market_index_advice_falls_back_to_summary(tmp_path: Path) -> None:
    tech_dir = tmp_path / "HSTECH" / "1m"
    tech_dir.mkdir(parents=True)
    payload = {
        "symbol": "HSTECH",
        "name": "恒生科技指数",
        "timeframe": "1m",
        "summary": {"conclusion": "观察，等待确认。", "suggestion": "先按观察态处理。"},
    }
    (tech_dir / "tech.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    advice = load_market_index_advice(tmp_path)

    assert advice is not None
    assert "结论：观察，等待确认。" in advice
    assert "建议：先按观察态处理。" in advice


def test_load_market_index_advice_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_market_index_advice(tmp_path) is None


def test_load_market_index_advice_keeps_only_conclusion_reason_suggestion(tmp_path: Path) -> None:
    tech_dir = tmp_path / "HSTECH" / "1m"
    tech_dir.mkdir(parents=True)
    payload = {
        "symbol": "HSTECH",
        "name": "恒生科技指数",
        "timeframe": "1m",
        "generated_at": "2026-10-31T11:45:02+08:00",
        "advice_text": (
            "【恒生科技指数 1M 操作建议】\n"
            "结论：偏强，持有为主。\n"
            "理由：价格运行在中枢上沿 31.68 附近或上方。\n"
            "建议：已有仓位可继续持有，回踩不破 31.68 再考虑加仓。\n"
            "结构说明：当前中枢由线段构成。\n"
            "监视器：中枢中线 31.49，当前偏强，预警状态 无预警。\n"
            "信号说明：三买已确认。\n"
            "消费说明：当前同级别结构处于 已确认，所有高层结论按确认处理。\n"
            "转场说明：结构已完成转场。\n"
            "节奏监视：节奏偏强，当前只作辅助观察，不单独升级主结论。\n"
            "补充：已有顶背驰迹象，若后续反弹无力，应优先考虑保护利润。\n"
            "说明：以上仅基于缠论结构与 MACD 强弱，不构成投资建议。"
        ),
    }
    (tech_dir / "tech.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    advice = load_market_index_advice(tmp_path)

    assert advice is not None
    lines = advice.splitlines()
    assert lines[0] == "【恒生科技指数 1M 操作建议】"
    assert lines[1].startswith("结论：")
    assert lines[2].startswith("理由：")
    assert lines[3].startswith("建议：")
    assert lines[-1].startswith("数据时间：")
    assert len(lines) == 5
    for dropped in ("结构说明", "监视器", "信号说明", "消费说明", "转场说明", "节奏监视", "补充", "说明："):
        assert dropped not in advice


def test_build_signal_card_trims_long_market_advice() -> None:
    events = extract_signal_events(_tech_payload())
    advice = (
        "【恒生科技指数 1M 操作建议】\n"
        "结论：震荡，等待方向选择。\n"
        "理由：当前主要围绕中枢 31.30-31.68 波动。\n"
        "建议：中枢内少折腾，等离开或跌破后再做决策。\n"
        "结构说明：中枢由线段构成。\n"
        "监视器：中枢中线 31.49，当前中性，预警状态 无预警。"
    )
    card = build_signal_card(events, title="买卖点", market_advice=advice)

    contents = [
        element.get("text", {}).get("content", "")
        for element in card["card"]["elements"]
        if isinstance(element, dict)
    ]
    advice_content = contents[-1]
    assert "结论：震荡，等待方向选择。" in advice_content
    assert "理由：" in advice_content
    assert "建议：" in advice_content
    assert "结构说明" not in advice_content
    assert "监视器" not in advice_content


def test_notify_from_reports_attaches_hstech_1m_advice(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    signal_dir = reports / "000591" / "30m"
    signal_dir.mkdir(parents=True)
    (signal_dir / "tech.json").write_text(json.dumps(_tech_payload(), ensure_ascii=False), encoding="utf-8")
    hstech_dir = reports / "HSTECH" / "1m"
    hstech_dir.mkdir(parents=True)
    (hstech_dir / "tech.json").write_text(
        json.dumps(
            {
                "symbol": "HSTECH",
                "name": "恒生科技指数",
                "timeframe": "1m",
                "advice_text": "【恒生科技指数 1M 操作建议】\n结论：观察，等待确认。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sent: list = []

    notify_from_reports(
        reports,
        state_path=tmp_path / "state.json",
        sender=lambda payload, **kwargs: sent.append(payload),
    )

    assert len(sent) == 1
    contents = [
        element.get("text", {}).get("content", "")
        for element in sent[0]["card"]["elements"]
        if isinstance(element, dict)
    ]
    assert any("恒生科技指数 1M 操作建议" in content for content in contents)


def test_collect_signal_events_from_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    tech_dir = reports / "000591" / "30m"
    tech_dir.mkdir(parents=True)
    (tech_dir / "tech.json").write_text(json.dumps(_tech_payload(), ensure_ascii=False), encoding="utf-8")
    events = collect_signal_events_from_reports(reports, timeframes=["30m"])
    assert len(events) == 3
    assert collect_signal_events_from_reports(reports, timeframes=["5m"]) == []


def _tech_payload_with_event_fields() -> dict:
    return {
        "symbol": "000591",
        "name": "太阳能",
        "timeframe": "30m",
        "summary": {
            "signal_points": [
                {
                    "point": "buy1",
                    "lifecycle_state": "confirmed",
                    "time": "2026-08-05T14:00:00",
                    "price": 4.2,
                    "forming_at": "2026-08-05T13:45:00",
                    "forming_price": 4.18,
                    "confirmed_at": "2026-08-05T14:05:00",
                    "confirmed_price": 4.26,
                },
                {
                    "point": "sell3",
                    "lifecycle_state": "forming",
                    "time": "2026-08-06T10:30:00",
                    "price": 4.63,
                    "forming_at": "2026-08-06T10:15:00",
                    "forming_price": 4.59,
                    "confirmed_at": None,
                    "confirmed_price": None,
                },
            ],
            "forming_points": [],
            "invalidated_points": [],
        },
    }


def test_extract_signal_events_carries_forming_and_confirmed_event_fields() -> None:
    events = {event.point: event for event in extract_signal_events(_tech_payload_with_event_fields())}

    confirmed = events["buy1"]
    assert (confirmed.forming_at, confirmed.forming_price) == ("2026-08-05T13:45:00", 4.18)
    assert (confirmed.confirmed_at, confirmed.confirmed_price) == ("2026-08-05T14:05:00", 4.26)

    forming = events["sell3"]
    assert (forming.forming_at, forming.forming_price) == ("2026-08-06T10:15:00", 4.59)
    assert (forming.confirmed_at, forming.confirmed_price) == ("", None)


def test_build_signal_card_renders_forming_and_confirmed_times_with_prices() -> None:
    card = build_signal_card(extract_signal_events(_tech_payload_with_event_fields()), title="买卖点")
    content = card["card"]["elements"][0]["text"]["content"]

    # 锚点信息仍在（买卖点自身时间 + 极值）
    assert "价4.2 @ 2026-08-05 14:00" in content
    # 六字段：forming / confirmed 各自「事件时间 + 该 K 线收盘价」，成对出现
    assert "检出 4.18 @ 2026-08-05 13:45" in content
    assert "确认 4.26 @ 2026-08-05 14:05" in content
    # 预备态信号只有 forming 一组，不渲染确认段
    assert "检出 4.59 @ 2026-08-06 10:15" in content


def test_build_signal_card_omits_snapshot_line_for_legacy_payload() -> None:
    card = build_signal_card(extract_signal_events(_tech_payload()), title="买卖点")
    content = card["card"]["elements"][0]["text"]["content"]

    assert " @ 2026-08-05 13:45" not in content
    assert "检出 " not in content


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
