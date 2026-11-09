"""轻量通知模块：把缠论买卖点信号推送到飞书自定义机器人。

- `feishu`：飞书自定义机器人 webhook 发送器（支持签名校验、超时与重试）。
- `signal_notifier`：从技术面 tech.json 提取买卖点信号、去重、生成飞书卡片并推送。
"""

from .feishu import FeishuConfigError, send_feishu_message, sign_feishu_request
from .signal_notifier import (
    SignalEvent,
    build_signal_card,
    collect_signal_events_from_reports,
    event_key,
    extract_signal_events,
    load_market_index_advice,
    load_state,
    notify_from_reports,
    notify_new_signals,
    save_state,
)

__all__ = [
    "FeishuConfigError",
    "send_feishu_message",
    "sign_feishu_request",
    "SignalEvent",
    "build_signal_card",
    "collect_signal_events_from_reports",
    "event_key",
    "extract_signal_events",
    "load_market_index_advice",
    "load_state",
    "notify_from_reports",
    "notify_new_signals",
    "save_state",
]
