"""结构化 JSON 日志封装。

- 统一字段规范（ts/level/service/msg + 条件字段），stdout 与 CLS 使用同一份字典。
- ``setup_logger`` / ``get_run_logger`` 返回预绑定上下文的 ``LoggerAdapter``。
- ``log_exc`` 把异常转换为 ``err`` 对象并以 ERROR 级别输出。
- ``mask`` 用于小程序日志脱敏（sha256 前 8 位）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import traceback
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import datetime
from typing import Any

VALID_SERVICES = frozenset({"eod-runner", "intraday-runner", "miniapp-api"})
VALID_PERIODS = frozenset({"m1", "m5", "m30", "day", "eod"})

MAIN_FIELDS = frozenset(
    {
        "ts",
        "level",
        "service",
        "msg",
        "period",
        "run_id",
        "trace_id",
        "err",
        "symbol",
        "signal_id",
        "trade_type",
        "state",
        "duration_ms",
        "extra",
    }
)

# 需要整体脱敏的 extra 键（小写）。
SENSITIVE_EXTRA_KEYS = frozenset(
    {
        "openid",
        "open_id",
        "unionid",
        "union_id",
        "phone",
        "mobile",
        "phone_number",
        "tel",
        "telephone",
        "id_card",
        "idcard",
        "password",
        "token",
        "access_token",
    }
)

MAX_STACK_CHARS = 2000

_LEVEL_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "FATAL",
}

# 中国大陆手机号（允许常见分隔符）与微信 openid 的粗粒度匹配，用于消息文本脱敏。
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_OPENID_RE = re.compile(r"\bo[A-Za-z0-9_-]{20,}\b")

# service -> 已配置的底层 Logger，避免重复挂载 Handler / 启动后台线程。
_LOGGERS: dict[str, logging.Logger] = {}

# 小程序请求级 trace_id，供同一上下文内的日志自动补全。
_TRACE_ID: ContextVar[str | None] = ContextVar("chanlun_trace_id", default=None)


def bind_trace_id(trace_id: str) -> Token[str | None]:
    return _TRACE_ID.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    _TRACE_ID.reset(token)


def current_trace_id() -> str | None:
    return _TRACE_ID.get()


def mask(value: Any) -> str:
    """返回 sha256 十六进制摘要的前 8 位。"""

    text = "" if value is None else str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def redact_text(text: str) -> str:
    """对文本中的手机号 / openid 做脱敏，其余内容保持不变。"""

    redacted = _PHONE_RE.sub(lambda match: mask(match.group(0)), str(text))
    return _OPENID_RE.sub(lambda match: mask(match.group(0)), redacted)


def exception_to_err(exc: BaseException, retryable: bool = False) -> dict[str, Any]:
    """把异常转换为规范化的 ``err`` 对象。"""

    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "stack": stack[:MAX_STACK_CHARS],
        "retryable": bool(retryable),
    }


def normalize_err(err: Any) -> dict[str, Any]:
    """把 dict / Exception 统一成 ``err`` 对象，并截断 stack。"""

    if isinstance(err, BaseException):
        return exception_to_err(err, retryable=False)
    if isinstance(err, Mapping):
        return {
            "type": str(err.get("type") or "Exception"),
            "message": str(err.get("message") or ""),
            "stack": str(err.get("stack") or "")[:MAX_STACK_CHARS],
            "retryable": bool(err.get("retryable", False)),
        }
    return {
        "type": type(err).__name__,
        "message": str(err),
        "stack": "",
        "retryable": False,
    }


def _normalize_key(key: Any) -> str:
    text = re.sub(r"[^0-9a-zA-Z]+", "_", str(key).strip()).strip("_").lower()
    return text or "field"


def _warn_stdout(message: str) -> None:
    # 诊断信息走 stderr，避免破坏 stdout 上“每行一个 JSON”的约定。
    print(f"[json-logger] WARN {message}", file=sys.stderr, flush=True)


def _sanitize_value(key: str, value: Any, *, mask_values: bool) -> Any:
    if mask_values and key in SENSITIVE_EXTRA_KEYS:
        if isinstance(value, (Mapping, list, tuple)):
            return mask(json.dumps(value, ensure_ascii=False, default=str))
        return mask(value)
    if isinstance(value, Mapping):
        nested: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            nested_key = _normalize_key(raw_key)
            nested[nested_key] = _sanitize_value(nested_key, raw_value, mask_values=mask_values)
        return nested
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(key, item, mask_values=mask_values) for item in value]
    if isinstance(value, str) and mask_values:
        return redact_text(value)
    return value


def sanitize_extra(extra: Mapping[Any, Any] | None, *, mask_values: bool = False) -> dict[str, Any]:
    """规范化 extra 键名，丢弃与主字段重名的键，并按需脱敏。"""

    if not isinstance(extra, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_key, raw_value in extra.items():
        key = _normalize_key(raw_key)
        if key in MAIN_FIELDS:
            _warn_stdout(f"extra key {raw_key!r} conflicts with main field {key!r}; dropped")
            continue
        if key in result:
            _warn_stdout(f"extra key {raw_key!r} duplicated after normalization; dropped")
            continue
        result[key] = _sanitize_value(key, raw_value, mask_values=mask_values)
    return result


def _format_ts(created: float) -> str:
    return datetime.fromtimestamp(created).astimezone().isoformat(timespec="milliseconds")


def build_log_dict(record: logging.LogRecord) -> dict[str, Any]:
    """把 ``LogRecord`` 转换为单行 JSON 对应的字典。"""

    level = _LEVEL_MAP.get(record.levelno, record.levelname)
    raw_service = getattr(record, "service", None)
    service = str(raw_service) if raw_service else "unknown"
    message = record.getMessage()

    payload: dict[str, Any] = {
        "ts": _format_ts(record.created),
        "level": level,
        "service": service,
        "msg": message,
    }

    for field in ("period", "run_id", "trace_id", "symbol", "signal_id", "trade_type", "state"):
        value = getattr(record, field, None)
        if value is not None and value != "":
            payload[field] = value

    if service == "miniapp-api" and "trace_id" not in payload:
        trace_id = current_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id

    duration_ms = getattr(record, "duration_ms", None)
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms

    err = getattr(record, "err", None)
    if err is None and record.exc_info and record.exc_info[0] is not None:
        err = exception_to_err(record.exc_info[1], retryable=False)
    if err is None and level in {"ERROR", "FATAL"}:
        # 规范要求 level >= ERROR 时 err 必填。
        err = {"type": "LogError", "message": message, "stack": "", "retryable": False}
    if err is not None:
        payload["err"] = normalize_err(err)

    extra = getattr(record, "extra", None)
    if extra:
        cleaned = sanitize_extra(extra, mask_values=service == "miniapp-api")
        if cleaned:
            payload["extra"] = cleaned

    if service == "miniapp-api":
        payload["msg"] = redact_text(payload["msg"])

    return payload


class StructuredFormatter(logging.Formatter):
    """把日志记录渲染为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        try:
            payload = build_log_dict(record)
        except Exception:  # noqa: BLE001 - 格式化失败不能影响业务
            payload = {
                "ts": _format_ts(record.created),
                "level": _LEVEL_MAP.get(record.levelno, record.levelname),
                "service": "unknown",
                "msg": record.getMessage(),
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


class ContextAdapter(logging.LoggerAdapter):
    """合并适配器上下文与调用方传入的 extra，而不是覆盖。"""

    def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        merged: dict[str, Any] = dict(self.extra or {})
        extra = kwargs.get("extra")
        if isinstance(extra, Mapping):
            merged.update(extra)
        kwargs["extra"] = merged
        return msg, kwargs


def _resolve_level() -> int:
    name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if name == "WARN":
        name = "WARNING"
    return getattr(logging, name, logging.INFO)


def _cls_enabled() -> bool:
    return os.getenv("ENABLE_CLS_LOG", "").strip().lower() in {"1", "true", "yes", "on"}


def _install_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, "_chanlun_managed", False):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # noqa: BLE001 - 清理旧 handler 不应影响启动
                pass

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(StructuredFormatter())
    stream._chanlun_managed = True  # type: ignore[attr-defined]
    logger.addHandler(stream)

    if _cls_enabled():
        from cls_handler import CLSHandler

        cls_handler = CLSHandler()
        cls_handler.setFormatter(StructuredFormatter())
        cls_handler._chanlun_managed = True  # type: ignore[attr-defined]
        logger.addHandler(cls_handler)


def _ensure_logger(service: str) -> logging.Logger:
    logger = _LOGGERS.get(service)
    if logger is not None:
        return logger
    logger = logging.getLogger(f"chanlun.{service}")
    logger.setLevel(_resolve_level())
    logger.propagate = False
    _install_handlers(logger)
    _LOGGERS[service] = logger
    return logger


def _validate_service(service: str) -> None:
    if service not in VALID_SERVICES:
        raise ValueError(f"unknown service {service!r}; expected one of {sorted(VALID_SERVICES)}")


def setup_logger(service: str, period: str | None = None) -> ContextAdapter:
    """配置并返回预绑定 service/period 的 logger。"""

    _validate_service(service)
    if period is not None:
        if service == "miniapp-api":
            raise ValueError("miniapp-api must not bind period")
        if period not in VALID_PERIODS:
            raise ValueError(f"unknown period {period!r}; expected one of {sorted(VALID_PERIODS)}")

    logger = _ensure_logger(service)
    extra: dict[str, Any] = {"service": service}
    if period is not None:
        extra["period"] = period
    return ContextAdapter(logger, extra)


def get_run_logger(service: str, period: str | None = None, run_id: str | None = None) -> ContextAdapter:
    """返回额外预绑定 run_id 的 logger。"""

    adapter = setup_logger(service, period)
    extra = dict(adapter.extra or {})
    if run_id:
        extra["run_id"] = run_id
    return ContextAdapter(adapter.logger, extra)


def log_exc(logger: logging.Logger | logging.LoggerAdapter, msg: str, exc: BaseException, retryable: bool) -> None:
    """把异常转成 err 对象后以 ERROR 级别输出。"""

    logger.error(msg, extra={"err": exception_to_err(exc, retryable=retryable)})


def _reset_loggers() -> None:
    """测试辅助：释放缓存的 logger 与托管 handler。"""

    for logger in _LOGGERS.values():
        for handler in list(logger.handlers):
            if getattr(handler, "_chanlun_managed", False):
                logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:  # noqa: BLE001
                    pass
    _LOGGERS.clear()
