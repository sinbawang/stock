"""从技术面 tech.json 提取缠论买卖点、去重并推送飞书卡片。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from chanlun.analysis_contract import SIGNAL_LIFECYCLE_STATE_LABELS, SIGNAL_POINT_LABELS

from .feishu import send_feishu_message


DIRECTION_EMOJI = {"buy": "🟢", "sell": "🔴"}
DEFAULT_MAX_STATE_KEYS = 3000


@dataclass(frozen=True)
class SignalEvent:
    """一条可推送的买卖点事件。"""

    symbol: str
    name: str
    timeframe: str
    point: str
    point_label: str
    direction: str  # "buy" / "sell"
    lifecycle: str  # "confirmed" / "forming"
    lifecycle_label: str
    time: str
    price: Optional[float]


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _format_point_label(point: str) -> str:
    normalized = point if point in SIGNAL_POINT_LABELS else point.replace("buy", "buy_").replace("sell", "sell_")
    return SIGNAL_POINT_LABELS.get(normalized, point)


def _format_generated_at(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("T", " ")[:16]


def load_market_index_advice(
    reports_dir: Path | str,
    *,
    symbol: str = "HSTECH",
    timeframe: str = "1m",
) -> Optional[str]:
    """读取恒生科技指数 1M 技术面最新建议（tech.json 的 advice_text）。

    读取失败或缺少建议时返回 ``None``，不影响买卖点通知本身。
    """

    tech_path = Path(reports_dir) / symbol / timeframe / "tech.json"
    try:
        payload = json.loads(tech_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    advice = str(payload.get("advice_text") or "").strip()
    if not advice:
        summary = payload.get("summary") or {}
        conclusion = str(summary.get("conclusion") or "").strip()
        suggestion = str(summary.get("suggestion") or "").strip()
        name = str(payload.get("name") or "恒生科技指数").strip()
        level = str(payload.get("timeframe") or timeframe).upper()
        lines = [f"【{name} {level} 操作建议】"]
        if conclusion:
            lines.append(f"结论：{conclusion}")
        if suggestion:
            lines.append(f"建议：{suggestion}")
        if len(lines) > 1:
            advice = "\n".join(lines)

    if not advice:
        return None

    generated_at = _format_generated_at(payload.get("generated_at"))
    if generated_at:
        advice = f"{advice}\n数据时间：{generated_at}"
    return advice


def _event_from_point(
    symbol: str,
    name: str,
    timeframe: str,
    raw: dict[str, Any],
    default_lifecycle: Optional[str],
) -> Optional[SignalEvent]:
    if not isinstance(raw, dict):
        return None
    point = str(raw.get("point") or "").strip()
    if not point:
        return None
    if raw.get("invalidated_reason"):
        return None
    lower = point.lower()
    direction = "buy" if lower.startswith("buy") else "sell" if lower.startswith("sell") else ""
    if not direction:
        return None
    lifecycle = str(raw.get("lifecycle_state") or default_lifecycle or "confirmed").strip().lower()
    if lifecycle == "invalidated":
        return None
    lifecycle_label = SIGNAL_LIFECYCLE_STATE_LABELS.get(
        lifecycle, "确认" if lifecycle == "confirmed" else lifecycle
    )
    return SignalEvent(
        symbol=symbol,
        name=name,
        timeframe=timeframe,
        point=point,
        point_label=_format_point_label(point),
        direction=direction,
        lifecycle=lifecycle,
        lifecycle_label=lifecycle_label,
        time=str(raw.get("time") or ""),
        price=_coerce_float(raw.get("price")),
    )


def extract_signal_events(tech_payload: dict[str, Any], *, include_forming: bool = True) -> list[SignalEvent]:
    """从单个技术面 payload 提取买卖点事件（已跳过失效信号）。"""

    if not isinstance(tech_payload, dict):
        return []
    summary = tech_payload.get("summary") or {}
    symbol = str(tech_payload.get("symbol") or summary.get("symbol") or "")
    name = str(tech_payload.get("name") or summary.get("name") or "")
    timeframe = str(tech_payload.get("timeframe") or summary.get("timeframe") or "")

    events: list[SignalEvent] = []
    seen: set[str] = set()

    def _add(raw: dict[str, Any], default_lifecycle: Optional[str]) -> None:
        event = _event_from_point(symbol, name, timeframe, raw, default_lifecycle)
        if event is None:
            return
        if not include_forming and event.lifecycle == "forming":
            return
        key = event_key(event)
        if key in seen:
            return
        seen.add(key)
        events.append(event)

    for raw in summary.get("signal_points") or []:
        _add(raw, None)
    if include_forming:
        for raw in summary.get("forming_points") or []:
            _add(raw, "forming")
    return events


def collect_signal_events_from_reports(
    reports_dir: Path | str,
    *,
    timeframes: Optional[Iterable[str]] = None,
    include_forming: bool = True,
) -> list[SignalEvent]:
    """扫描 ``reports_dir/<symbol>/<timeframe>/tech.json`` 收集买卖点事件。"""

    allowed = {str(value).strip().lower() for value in timeframes} if timeframes else None
    events: list[SignalEvent] = []
    for tech_path in sorted(Path(reports_dir).glob("*/*/tech.json")):
        timeframe = tech_path.parent.name
        if allowed is not None and timeframe.lower() not in allowed:
            continue
        try:
            payload = json.loads(tech_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        events.extend(extract_signal_events(payload, include_forming=include_forming))
    return events


def event_key(event: SignalEvent) -> str:
    """去重键：同一标的/周期/方向/点类型/锚点时间/生命周期只通知一次。

    生命周期纳入键，使「预备」与「确认」各推送一次（预备预警 + 确认提醒）。
    """

    return "|".join(
        (event.symbol, event.timeframe, event.direction, event.point, event.time, event.lifecycle)
    )


def load_state(state_path: Path | str) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        return {"sent_keys": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sent_keys": []}
    if not isinstance(data, dict):
        return {"sent_keys": []}
    data.setdefault("sent_keys", [])
    return data


def save_state(state_path: Path | str, state: dict[str, Any]) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _header_template(events: list[SignalEvent]) -> str:
    has_buy = any(event.direction == "buy" for event in events)
    has_sell = any(event.direction == "sell" for event in events)
    if has_buy and not has_sell:
        return "green"
    if has_sell and not has_buy:
        return "red"
    return "blue"


def _format_event_line(event: SignalEvent) -> str:
    emoji = DIRECTION_EMOJI.get(event.direction, "🔵")
    name = event.name or event.symbol
    price = f" 价{event.price:g}" if event.price is not None else ""
    moment = event.time.replace("T", " ")
    tail = f" @ {moment}" if moment else ""
    return (
        f"{emoji} **{name} {event.symbol}** {event.timeframe.upper()}"
        f"｜{event.lifecycle_label}·{event.point_label}{price}{tail}"
    )


def build_signal_card(
    events: list[SignalEvent],
    *,
    title: str = "缠论买卖点提醒",
    market_advice: Optional[str] = None,
) -> dict[str, Any]:
    """把买卖点事件渲染成飞书交互卡片。"""

    content = "\n".join(_format_event_line(event) for event in events)
    elements: list[dict[str, Any]] = [
        {"tag": "div", "text": {"tag": "lark_md", "content": content or "暂无新信号"}}
    ]
    if market_advice:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": market_advice}})
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{title}（{len(events)}）"},
                "template": _header_template(events),
            },
            "elements": elements,
        },
    }


def notify_from_reports(
    reports_dir: Path | str,
    *,
    state_path: Path | str,
    timeframes: Optional[Iterable[str]] = None,
    include_forming: bool = True,
    sender: Callable[..., Any] = send_feishu_message,
    title: str = "缠论买卖点提醒",
    market_advice: Optional[str] = None,
    dry_run: bool = False,
    seed_only: bool = False,
    **send_kwargs: Any,
) -> list[SignalEvent]:
    """扫描报告目录收集买卖点并推送新信号的一站式封装。

    默认附带 ``reports_dir/HSTECH/1m/tech.json`` 的恒生科技指数 1M 技术面建议；
    显式传入 ``market_advice`` 时以传入值为准。
    """

    events = collect_signal_events_from_reports(
        reports_dir,
        timeframes=timeframes,
        include_forming=include_forming,
    )
    if market_advice is None:
        market_advice = load_market_index_advice(reports_dir)
    return notify_new_signals(
        events,
        state_path=state_path,
        sender=sender,
        title=title,
        market_advice=market_advice,
        dry_run=dry_run,
        seed_only=seed_only,
        **send_kwargs,
    )


def notify_new_signals(
    events: list[SignalEvent],
    *,
    state_path: Path | str,
    sender: Callable[..., Any] = send_feishu_message,
    title: str = "缠论买卖点提醒",
    market_advice: Optional[str] = None,
    dry_run: bool = False,
    seed_only: bool = False,
    max_state_keys: int = DEFAULT_MAX_STATE_KEYS,
    **send_kwargs: Any,
) -> list[SignalEvent]:
    """过滤出未通知过的事件并推送，返回本次新增事件。

    :param dry_run: 只返回将要推送的新事件，不发送、不改状态。
    :param seed_only: 只把当前信号标记为「已通知」用于建立基线，不实际推送（首次运行防刷屏）。
    """

    state = load_state(state_path)
    sent_keys: list[str] = list(state.get("sent_keys") or [])
    sent = set(sent_keys)

    new_events: list[SignalEvent] = []
    seen: set[str] = set()
    for event in events:
        key = event_key(event)
        if key in sent or key in seen:
            continue
        seen.add(key)
        new_events.append(event)

    if dry_run:
        return new_events

    if new_events and not seed_only:
        sender(
            build_signal_card(new_events, title=title, market_advice=market_advice),
            **send_kwargs,
        )

    if new_events:
        merged = sent_keys + [event_key(event) for event in new_events]
        state["sent_keys"] = merged[-max_state_keys:]
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_state(state_path, state)

    return new_events
