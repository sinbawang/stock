from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

import pytest

import json_logger
from cls_handler import CLSHandler, _QueuedLog, _cls_fields, encode_log_group_list
from json_logger import (
    ContextAdapter,
    StructuredFormatter,
    build_log_dict,
    exception_to_err,
    get_run_logger,
    log_exc,
    mask,
    normalize_err,
    sanitize_extra,
    setup_logger,
)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _FakeCLSClient:
    """模拟 CLS SDK 客户端，只实现当前 SDK 的 UploadLog 接口。"""

    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Any, bytes]] = []
        self.uploaded = threading.Event()

    def UploadLog(self, request: Any, body: bytes) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append((request, body))
        self.uploaded.set()


class _AuthError(Exception):
    code = "AuthFailure.SignatureFailure"


def _make_logger(name: str, handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def _capture_logger(name: str) -> tuple[logging.Logger, _CaptureHandler]:
    capture = _CaptureHandler()
    return _make_logger(name, capture), capture


def _new_handler(tmp_path: Path, client: Any, **kwargs: Any) -> CLSHandler:
    defaults = {
        "topic_id": "topic-test",
        "client": client,
        "flush_interval": 3600.0,
        "fallback_dir": tmp_path,
    }
    defaults.update(kwargs)
    return CLSHandler(**defaults)


# --------------------------------------------------------------------------- buffering


def test_handler_buffers_until_batch_size(tmp_path: Path) -> None:
    client = _FakeCLSClient()
    handler = _new_handler(tmp_path, client, batch_size=3)
    logger = _make_logger("clstest.batch", handler)
    try:
        logger.info("one")
        logger.info("two")
        assert client.calls == []

        logger.info("three")
        assert client.uploaded.wait(timeout=2.0)
        assert len(client.calls) == 1
        assert isinstance(client.calls[0][1], bytes)
    finally:
        handler.close()


def test_handler_flushes_buffered_records_on_close(tmp_path: Path) -> None:
    client = _FakeCLSClient()
    handler = _new_handler(tmp_path, client, batch_size=100)
    logger = _make_logger("clstest.close", handler)
    logger.info("only-one")
    handler.close()

    assert len(client.calls) == 1


# --------------------------------------------------------------------------- failure


def test_handler_writes_fallback_when_upload_fails(tmp_path: Path) -> None:
    client = _FakeCLSClient(error=RuntimeError("boom"))
    handler = _new_handler(tmp_path, client, batch_size=1, max_retries=0, retry_base_delay=0)
    logger = _make_logger("clstest.fallback", handler)
    try:
        logger.error("failed-task", extra={"extra": {"attempt": 1}})
    finally:
        handler.close()

    files = list(tmp_path.glob("cls_fallback_*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["level"] == "ERROR"
    assert payload["msg"] == "failed-task"
    assert payload["extra"] == {"attempt": 1}
    assert payload["err"]["type"] == "LogError"


def test_handler_retries_retryable_error_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("cls_handler.time.sleep", lambda seconds: sleeps.append(seconds))
    client = _FakeCLSClient(error=RuntimeError("connection reset"))
    handler = _new_handler(tmp_path, client, batch_size=1, max_retries=2, retry_base_delay=1.0)
    logger = _make_logger("clstest.retry", handler)
    try:
        logger.info("retry-me")
        handler.flush()
    finally:
        handler.close()

    assert sleeps == [1.0, 2.0]
    assert list(tmp_path.glob("cls_fallback_*.jsonl"))


def test_handler_does_not_retry_auth_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("cls_handler.time.sleep", lambda seconds: sleeps.append(seconds))
    client = _FakeCLSClient(error=_AuthError("bad secret"))
    handler = _new_handler(tmp_path, client, batch_size=1, max_retries=2, retry_base_delay=1.0)
    logger = _make_logger("clstest.auth", handler)
    try:
        logger.info("no-retry")
        handler.flush()
    finally:
        handler.close()

    assert sleeps == []
    assert list(tmp_path.glob("cls_fallback_*.jsonl"))


# --------------------------------------------------------------------------- schema


def test_cls_fields_include_timestamp() -> None:
    queued = _QueuedLog(
        ts_ms=1_700_000_000_123,
        payload={"ts": "2026-11-19T20:00:48.123+08:00", "level": "INFO", "service": "eod-runner", "msg": "x"},
    )
    fields = dict(_cls_fields(queued))
    assert fields["__TIMESTAMP__"] == "1700000000123"
    assert fields["msg"] == "x"


def test_encode_log_group_list_returns_protobuf_bytes() -> None:
    body = encode_log_group_list(
        [_QueuedLog(ts_ms=1_700_000_000_123, payload={"msg": "hello", "level": "INFO"})]
    )
    assert isinstance(body, bytes)
    assert body


def test_normalize_err_truncates_stack_to_2000_chars() -> None:
    err = normalize_err({"type": "X", "message": "m", "stack": "a" * 5000, "retryable": True})
    assert err["stack"] == "a" * 2000
    assert err["retryable"] is True


def test_exception_to_err_builds_structured_error() -> None:
    def recurse(depth: int) -> None:
        if depth:
            recurse(depth - 1)
        else:
            raise ValueError("deep")

    try:
        recurse(300)
    except ValueError as exc:
        err = exception_to_err(exc, retryable=True)

    assert err["type"] == "ValueError"
    assert err["message"] == "deep"
    assert err["retryable"] is True
    assert 0 < len(err["stack"]) <= 2000


def test_mask_is_stable_sha256_prefix() -> None:
    expected = hashlib.sha256("13800138000".encode("utf-8")).hexdigest()[:8]
    assert mask("13800138000") == expected
    assert len(mask("anything")) == 8


def test_sanitize_extra_normalizes_and_drops_main_field_conflicts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = sanitize_extra(
        {"User ID": 1, "msg": "duplicate", "Phone": "13800138000"},
        mask_values=True,
    )

    assert result["user_id"] == 1
    assert "msg" not in result
    assert result["phone"] == mask("13800138000")
    assert "conflicts" in capsys.readouterr().err


def test_miniapp_payload_masks_msg_and_extra() -> None:
    record = logging.LogRecord(
        "clstest.mask",
        logging.INFO,
        __file__,
        1,
        "call 13800138000 openid oABCDEFGHIJKLMNOPQRSTUVWX",
        None,
        None,
    )
    record.service = "miniapp-api"
    record.trace_id = "trace-1"
    record.extra = {"openid": "oABCDEFGHIJKLMNOPQRSTUVWX", "note": "phone 13912345678"}

    payload = build_log_dict(record)

    assert "13800138000" not in payload["msg"]
    assert "oABCDEFGHIJKLMNOPQRSTUVWX" not in payload["msg"]
    assert payload["extra"]["openid"] == mask("oABCDEFGHIJKLMNOPQRSTUVWX")
    assert "13912345678" not in json.dumps(payload["extra"])
    assert payload["trace_id"] == "trace-1"


def test_miniapp_payload_uses_bound_trace_id() -> None:
    token = json_logger.bind_trace_id("ctx-trace")
    try:
        record = logging.LogRecord("clstest.trace", logging.INFO, __file__, 1, "hello", None, None)
        record.service = "miniapp-api"
        payload = build_log_dict(record)
    finally:
        json_logger.reset_trace_id(token)

    assert payload["trace_id"] == "ctx-trace"


# --------------------------------------------------------------------------- adapters


def test_context_adapter_injects_service_period_run_id() -> None:
    logger, capture = _capture_logger("clstest.adapter")
    adapter = ContextAdapter(
        logger, {"service": "intraday-runner", "period": "m30", "run_id": "run-1"}
    )

    adapter.info("hello", extra={"symbol": "SH600519"})

    record = capture.records[0]
    assert record.service == "intraday-runner"
    assert record.period == "m30"
    assert record.run_id == "run-1"
    assert record.symbol == "SH600519"

    payload = build_log_dict(record)
    assert payload["service"] == "intraday-runner"
    assert payload["period"] == "m30"
    assert payload["run_id"] == "run-1"


def test_setup_and_get_run_logger_bind_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_CLS_LOG", raising=False)
    json_logger._reset_loggers()
    try:
        logger = setup_logger("intraday-runner", "m5")
        assert logger.extra == {"service": "intraday-runner", "period": "m5"}

        run_logger = get_run_logger("intraday-runner", "m5", "run-9")
        assert run_logger.extra == {
            "service": "intraday-runner",
            "period": "m5",
            "run_id": "run-9",
        }
    finally:
        json_logger._reset_loggers()


def test_setup_logger_rejects_period_for_miniapp() -> None:
    with pytest.raises(ValueError):
        setup_logger("miniapp-api", "m1")


def test_log_exc_emits_error_with_err_object() -> None:
    logger, capture = _capture_logger("clstest.exc")
    adapter = ContextAdapter(logger, {"service": "eod-runner", "period": "eod"})

    try:
        raise RuntimeError("bad")
    except RuntimeError as exc:
        log_exc(adapter, "task_failed", exc, retryable=True)

    record = capture.records[-1]
    assert record.levelno == logging.ERROR
    assert record.err["type"] == "RuntimeError"
    assert record.err["message"] == "bad"
    assert record.err["retryable"] is True


def test_structured_formatter_emits_single_line_json() -> None:
    record = logging.LogRecord("clstest.formatter", logging.INFO, __file__, 1, "hello", None, None)
    record.service = "eod-runner"
    record.period = "eod"
    record.duration_ms = 12.5

    line = StructuredFormatter().format(record)

    assert "\n" not in line
    payload = json.loads(line)
    assert payload["msg"] == "hello"
    assert payload["duration_ms"] == 12.5
    assert payload["level"] == "INFO"
