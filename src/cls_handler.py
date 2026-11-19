"""腾讯云 CLS 直写 Handler（不依赖 CloudBase 日志投递）。

将结构化日志在本地缓冲，由后台线程按「满 N 条」或「超过 T 秒」批量上传到 CLS。
上传失败时写入 ``logs/cls_fallback_YYYYMMDD.jsonl``，绝不阻塞或抛出到业务主流程。

环境变量：
    CLOUDBASE_REGION / TENCENTCLS_TOPIC_ID / TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import logging

DEFAULT_BATCH_SIZE = 100
DEFAULT_FLUSH_INTERVAL = 5.0
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_FALLBACK_DIR = Path("logs")
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BASE_DELAY = 1.0

NON_RETRYABLE_ERROR_HINTS = (
    "authfailure",
    "unauthorizedoperation",
    "invalidsecretid",
    "secretidnotfound",
    "signaturefailure",
    "signatureexpired",
    "invalidparameter",
)
RETRYABLE_ERROR_HINTS = (
    "network",
    "timeout",
    "connection",
    "internalerror",
    "requestlimitexceeded",
    "serviceunavailable",
    "throttl",
    "temporarily",
)


@dataclass
class _QueuedLog:
    ts_ms: int
    payload: dict[str, Any]


def _warn(message: str, *, stream: Any = None) -> None:
    try:
        print(f"[cls-handler] WARN {message}", file=stream or sys.stdout, flush=True)
    except Exception:  # noqa: BLE001 - 诊断输出失败不应该影响业务
        pass


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    if value is None:
        return ""
    return str(value)


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _encode_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_length_delimited(field_number: int, payload: bytes) -> bytes:
    return _encode_tag(field_number, 2) + _encode_varint(len(payload)) + payload


def _encode_content(key: str, value: str) -> bytes:
    return _encode_length_delimited(1, key.encode("utf-8")) + _encode_length_delimited(
        2, value.encode("utf-8")
    )


def _encode_log(ts_ms: int, contents: Sequence[tuple[str, str]]) -> bytes:
    out = bytearray()
    out += _encode_tag(1, 0) + _encode_varint(ts_ms)
    for key, value in contents:
        out += _encode_length_delimited(2, _encode_content(key, value))
    return bytes(out)


def _payload_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for key, value in payload.items():
        fields.append((key, _stringify(value)))
    return fields


def _cls_fields(record: _QueuedLog) -> list[tuple[str, str]]:
    """PutLogs（旧版 SDK）使用的字段，含 ``__TIMESTAMP__``。"""

    return [("__TIMESTAMP__", str(record.ts_ms)), *_payload_fields(record.payload)]


def _upload_contents(record: _QueuedLog) -> list[tuple[str, str]]:
    """UploadLog 的 Content 不允许以下划线开头，时间戳通过 Log.time 传递。"""

    return _payload_fields(record.payload)


def encode_log_group_list(records: Sequence[_QueuedLog]) -> bytes:
    """按 CLS ``cls.proto`` 手工编码 LogGroupList（无需引入 protobuf）。"""

    log_group = bytearray()
    for record in records:
        encoded_log = _encode_log(record.ts_ms, _upload_contents(record))
        log_group += _encode_length_delimited(1, encoded_log)
    return _encode_length_delimited(1, bytes(log_group))


class CLSHandler(logging.Handler):
    """异步把结构化日志批量写入腾讯云 CLS。"""

    def __init__(
        self,
        region: str | None = None,
        topic_id: str | None = None,
        secret_id: str | None = None,
        secret_key: str | None = None,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        fallback_dir: str | Path | None = None,
        client: Any | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    ) -> None:
        super().__init__()
        self.region = region or os.getenv("CLOUDBASE_REGION") or DEFAULT_REGION
        self.topic_id = topic_id or os.getenv("TENCENTCLS_TOPIC_ID") or ""
        self.secret_id = secret_id or os.getenv("TENCENTCLOUD_SECRET_ID") or ""
        self.secret_key = secret_key or os.getenv("TENCENTCLOUD_SECRET_KEY") or ""
        self.batch_size = max(1, int(batch_size))
        self.flush_interval = max(0.01, float(flush_interval))
        self.fallback_dir = Path(fallback_dir) if fallback_dir is not None else (
            Path(os.getenv("CLS_FALLBACK_DIR") or DEFAULT_FALLBACK_DIR)
        )
        self.max_retries = max(0, int(max_retries))
        self.retry_base_delay = max(0.0, float(retry_base_delay))

        self._client = client
        self._enabled = True
        if self._client is None:
            if not (self.topic_id and self.secret_id and self.secret_key):
                _warn(
                    "CLS disabled: TENCENTCLS_TOPIC_ID / TENCENTCLOUD_SECRET_ID / "
                    "TENCENTCLOUD_SECRET_KEY is not fully configured"
                )
                self._enabled = False
            else:
                self._client = self._build_client()
                if self._client is None:
                    self._enabled = False

        self._buffer: list[_QueuedLog] = []
        self._lock = threading.Lock()
        self._fallback_lock = threading.Lock()
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        if self._enabled:
            self._thread = threading.Thread(
                target=self._worker_loop, name="cls-log-sender", daemon=True
            )
            self._thread.start()

    # ------------------------------------------------------------------ client
    def _build_client(self) -> Any | None:
        try:
            from tencentcloud.cls.v20201016.cls_client import ClsClient
            from tencentcloud.common.credential import Credential
        except ImportError as exc:  # pragma: no cover - 依赖缺失时的兜底
            _warn(f"CLS SDK is not installed: {exc}")
            return None
        return ClsClient(Credential(self.secret_id, self.secret_key), self.region)

    # ------------------------------------------------------------------ thread
    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            self._flush_event.wait(self.flush_interval)
            self._flush_event.clear()
            if self._stop_event.is_set():
                break
            self.flush()

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return
        try:
            payload = self._record_to_payload(record)
        except Exception:  # noqa: BLE001 - 单条日志转换失败不应影响业务
            self.handleError(record)
            return

        with self._lock:
            self._buffer.append(payload)
            reached_batch = len(self._buffer) >= self.batch_size
        if reached_batch:
            self._flush_event.set()

    def _record_to_payload(self, record: logging.LogRecord) -> _QueuedLog:
        from json_logger import build_log_dict

        return _QueuedLog(ts_ms=int(round(record.created * 1000)), payload=build_log_dict(record))

    def flush(self) -> None:
        with self._lock:
            records = self._buffer
            self._buffer = []
        if records:
            self._send_batch(records)

    def close(self) -> None:
        try:
            self._stop_event.set()
            self._flush_event.set()
            if self._thread is not None:
                self._thread.join(timeout=max(10.0, self.flush_interval * 2))
            self.flush()
        finally:
            super().close()

    # ------------------------------------------------------------------ sending
    def _send_batch(self, records: Sequence[_QueuedLog]) -> None:
        if not records:
            return
        attempt = 0
        while True:
            try:
                self._upload_once(records)
                return
            except Exception as exc:  # noqa: BLE001 - 上传失败只做降级
                attempt += 1
                code = str(getattr(exc, "code", "") or "")
                retryable = self._is_retryable(exc)
                if retryable and attempt <= self.max_retries:
                    time.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
                    continue
                if retryable:
                    _warn(
                        f"upload failed after {attempt} attempt(s) (code={code or '-'}): {exc}",
                        stream=sys.stderr,
                    )
                else:
                    _warn(f"upload rejected, not retrying (code={code or '-'}): {exc}")
                self._write_fallback(records)
                return

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        text = f"{type(exc).__name__}:{getattr(exc, 'code', '')}".lower()
        if any(hint in text for hint in NON_RETRYABLE_ERROR_HINTS):
            return False
        if any(hint in text for hint in RETRYABLE_ERROR_HINTS):
            return True
        # 未知异常按网络类处理，最多重试 max_retries 次。
        return True

    def _upload_once(self, records: Sequence[_QueuedLog]) -> None:
        client = self._client
        if hasattr(client, "PutLogs"):
            self._upload_via_put_logs(client, records)
            return
        if hasattr(client, "UploadLog"):
            self._upload_via_upload_log(client, records)
            return
        raise RuntimeError("CLS client exposes neither PutLogs nor UploadLog")

    def _upload_via_put_logs(self, client: Any, records: Sequence[_QueuedLog]) -> None:
        from tencentcloud.cls.v20201016 import models as cls_models

        request = cls_models.PutLogsRequest()
        request.TopicId = self.topic_id
        log_item_cls = getattr(cls_models, "LogItem")
        logs = []
        for record in records:
            logs.append([_make_item(log_item_cls, key, value) for key, value in _cls_fields(record)])
        request.Logs = logs
        client.PutLogs(request)

    def _upload_via_upload_log(self, client: Any, records: Sequence[_QueuedLog]) -> None:
        from tencentcloud.cls.v20201016 import models as cls_models

        request = cls_models.UploadLogRequest()
        request.TopicId = self.topic_id
        client.UploadLog(request, encode_log_group_list(records))

    def _write_fallback(self, records: Iterable[_QueuedLog]) -> None:
        try:
            self.fallback_dir.mkdir(parents=True, exist_ok=True)
            path = self.fallback_dir / f"cls_fallback_{datetime.now():%Y%m%d}.jsonl"
            with self._fallback_lock, path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record.payload, ensure_ascii=False, separators=(",", ":")))
                    handle.write("\n")
        except OSError as exc:
            _warn(f"fallback write failed: {exc}", stream=sys.stderr)


def _make_item(cls: Any, key: str, value: str) -> Any:
    item = cls()
    item.Key = key
    item.Value = value
    return item
