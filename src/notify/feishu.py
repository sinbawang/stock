"""飞书自定义机器人 webhook 发送器。

个人可用、免费、无需企业认证：在飞书群里添加「自定义机器人」即可得到 webhook URL。
凭据通过环境变量注入，不入库：

- ``FEISHU_WEBHOOK_URL``：机器人 webhook 地址（必填）
- ``FEISHU_SIGN_SECRET``：可选，开启「签名校验」时的密钥
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Any, Callable, Optional

import requests


class FeishuConfigError(RuntimeError):
    """飞书配置缺失（如未设置 webhook URL）。"""


def sign_feishu_request(timestamp: str, secret: str) -> str:
    """按飞书自定义机器人签名算法生成签名。

    string_to_sign = f"{timestamp}\n{secret}" 作为 HMAC-SHA256 的密钥，消息体为空，
    最终做 base64 编码。
    """

    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_feishu_message(
    payload: dict[str, Any],
    *,
    webhook_url: Optional[str] = None,
    sign_secret: Optional[str] = None,
    timeout: float = 10.0,
    retries: int = 2,
    session_factory: Callable[[], Any] = requests.Session,
) -> dict[str, Any]:
    """向飞书自定义机器人推送一条消息。

    :param payload: 飞书消息体（如 interactive 卡片）。
    :param webhook_url: webhook 地址，缺省读 ``FEISHU_WEBHOOK_URL``。
    :param sign_secret: 签名密钥，缺省读 ``FEISHU_SIGN_SECRET``；为空则不签名。
    :param session_factory: 便于测试注入的 requests 会话工厂。
    :raises FeishuConfigError: 未配置 webhook。
    :raises RuntimeError: 多次重试后仍失败，或飞书返回非 0 错误码。
    """

    url = webhook_url if webhook_url is not None else os.environ.get("FEISHU_WEBHOOK_URL")
    if not url:
        raise FeishuConfigError("未配置飞书 webhook（请设置环境变量 FEISHU_WEBHOOK_URL）")

    body = dict(payload)
    secret = sign_secret if sign_secret is not None else os.environ.get("FEISHU_SIGN_SECRET")
    if secret:
        timestamp = str(int(time.time()))
        body["timestamp"] = timestamp
        body["sign"] = sign_feishu_request(timestamp, secret)

    last_exc: Optional[Exception] = None
    session = session_factory()
    for _ in range(max(1, retries + 1)):
        try:
            response = session.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            code = data.get("code", data.get("StatusCode", 0))
            if code not in (0, None):
                raise RuntimeError(f"飞书返回错误码 {code}: {data.get('msg') or data}")
            return data
        except Exception as exc:  # noqa: BLE001 - 汇总后统一抛出
            last_exc = exc
    raise RuntimeError(f"飞书推送失败: {last_exc}")
