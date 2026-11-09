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

# 大盘参考指数：默认恒生科技指数（恒科），用于在个股买卖点提醒里附带大盘走势建议。
DEFAULT_INDEX_SYMBOL = "HSTECH"
DEFAULT_INDEX_TIMEFRAME = "1m"


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


@dataclass(frozen=True)
class IndexBrief:
    """大盘参考指数（如恒生科技指数）的技术面简报，用于辅助判断个股买卖点。"""

    symbol: str
    name: str
    timeframe: str
    level_label: str  # 操作级别标签，如 "1M"
    conclusion: str
    suggestion: str
    bias: str
    score: Optional[float]
    rating: str
    oscillation_label: str
    top_divergence: bool  # 顶背驰
    bottom_divergence: bool  # 底背驰


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


_OSCILLATION_LABELS = {
    "up_bias": "偏多节奏",
    "down_bias": "偏空节奏",
    "balanced": "多空均衡",
    "neutral": "多空均衡",
}


def extract_index_brief(tech_payload: dict[str, Any]) -> Optional[IndexBrief]:
    """从大盘指数的技术面 payload 提取一条简报（结论/建议/评级/背驰）。"""

    if not isinstance(tech_payload, dict):
        return None
    summary = tech_payload.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}
    symbol = str(tech_payload.get("symbol") or summary.get("symbol") or "")
    name = str(tech_payload.get("name") or summary.get("name") or "")
    timeframe = str(tech_payload.get("timeframe") or summary.get("timeframe") or "")
    level_label = str(summary.get("operation_level") or timeframe.upper() or "")

    divergence = summary.get("divergence")
    if not isinstance(divergence, dict):
        divergence = tech_payload.get("divergence") if isinstance(tech_payload.get("divergence"), dict) else {}
    top = divergence.get("top") if isinstance(divergence, dict) else None
    bottom = divergence.get("bottom") if isinstance(divergence, dict) else None
    top_divergence = bool(isinstance(top, dict) and top.get("active"))
    bottom_divergence = bool(isinstance(bottom, dict) and bottom.get("active"))

    oscillation = str(summary.get("oscillation_rhythm_state") or "").strip().lower()
    oscillation_label = _OSCILLATION_LABELS.get(oscillation, "")

    return IndexBrief(
        symbol=symbol,
        name=name,
        timeframe=timeframe,
        level_label=level_label,
        conclusion=str(summary.get("conclusion") or "").strip(),
        suggestion=str(summary.get("suggestion") or "").strip(),
        bias=str(summary.get("bias") or "").strip(),
        score=_coerce_float(summary.get("score")),
        rating=str(summary.get("rating") or "").strip(),
        oscillation_label=oscillation_label,
        top_divergence=top_divergence,
        bottom_divergence=bottom_divergence,
    )


def load_index_brief(
    reports_dir: Path | str,
    *,
    symbol: str = DEFAULT_INDEX_SYMBOL,
    timeframe: str = DEFAULT_INDEX_TIMEFRAME,
) -> Optional[IndexBrief]:
    """读取 ``reports_dir/<symbol>/<timeframe>/tech.json`` 并提取大盘简报，缺失则返回 None。"""

    tech_path = Path(reports_dir) / symbol.strip() / timeframe.strip() / "tech.json"
    if not tech_path.exists():
        return None
    try:
        payload = json.loads(tech_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return extract_index_brief(payload)


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


def _format_index_brief(brief: IndexBrief) -> str:
    """把大盘指数简报渲染成飞书 lark_md 文本块。"""

    name = brief.name or brief.symbol or "大盘指数"
    level = brief.level_label or brief.timeframe.upper()
    head = f"📊 **{name} {level} 大盘技术面建议**（辅助判断，仅供参考）"

    tags: list[str] = []
    if brief.rating:
        tags.append(f"评级 {brief.rating}")
    if brief.score is not None:
        tags.append(f"{brief.score:g} 分")
    if brief.oscillation_label:
        tags.append(brief.oscillation_label)
    meta = "｜".join(tags)

    lines = [head]
    if meta:
        lines.append(meta)
    if brief.conclusion:
        lines.append(f"结论：{brief.conclusion}")
    elif brief.bias:
        lines.append(f"研判：{brief.bias}")
    if brief.suggestion:
        lines.append(f"建议：{brief.suggestion}")
    if brief.bottom_divergence:
        lines.append("⚠️ 大盘出现**底背驰**，关注止跌反弹，个股卖点可放缓执行。")
    if brief.top_divergence:
        lines.append("⚠️ 大盘出现**顶背驰**，上行或遇压力，个股买点留意上涨空间。")
    return "\n".join(lines)


def build_signal_card(
    events: list[SignalEvent],
    *,
    title: str = "缠论买卖点提醒",
    index_brief: Optional[IndexBrief] = None,
) -> dict[str, Any]:
    """把买卖点事件渲染成飞书交互卡片。

    :param index_brief: 可选的大盘指数（如恒生科技指数）技术面简报，附在卡片顶部辅助判断。
    """

    content = "\n".join(_format_event_line(event) for event in events)
    elements: list[dict[str, Any]] = []
    if index_brief is not None:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": _format_index_brief(index_brief)}})
        elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content or "暂无新信号"}})
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
    dry_run: bool = False,
    seed_only: bool = False,
    index_brief: Optional[IndexBrief] = None,
    **send_kwargs: Any,
) -> list[SignalEvent]:
    """扫描报告目录收集买卖点并推送新信号的一站式封装。"""

    events = collect_signal_events_from_reports(
        reports_dir,
        timeframes=timeframes,
        include_forming=include_forming,
    )
    return notify_new_signals(
        events,
        state_path=state_path,
        sender=sender,
        title=title,
        dry_run=dry_run,
        seed_only=seed_only,
        index_brief=index_brief,
        **send_kwargs,
    )


def notify_new_signals(
    events: list[SignalEvent],
    *,
    state_path: Path | str,
    sender: Callable[..., Any] = send_feishu_message,
    title: str = "缠论买卖点提醒",
    dry_run: bool = False,
    seed_only: bool = False,
    index_brief: Optional[IndexBrief] = None,
    max_state_keys: int = DEFAULT_MAX_STATE_KEYS,
    **send_kwargs: Any,
) -> list[SignalEvent]:
    """过滤出未通知过的事件并推送，返回本次新增事件。

    :param dry_run: 只返回将要推送的新事件，不发送、不改状态。
    :param seed_only: 只把当前信号标记为「已通知」用于建立基线，不实际推送（首次运行防刷屏）。
    :param index_brief: 可选的大盘指数技术面简报，附在卡片顶部辅助判断。
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
        sender(build_signal_card(new_events, title=title, index_brief=index_brief), **send_kwargs)

    if new_events:
        merged = sent_keys + [event_key(event) for event in new_events]
        state["sent_keys"] = merged[-max_state_keys:]
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_state(state_path, state)

    return new_events
