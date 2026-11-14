"""把买卖点信号迁移历史（forming / confirmed / invalidated）同步到 CloudBase 文档数据库。

口径见 `docs/chanlun/signal-realtime-lifecycle-design.md` §6.2 与
`docs/chanlun/buy-sell-multi-level-spec.md` §2.8.4。

输入：`data/reports/<symbol>/<timeframe>/tech.json`（由 `batch_prepare_chanlun_reports.py` 产出）。
输出：
1. `build/miniapp-publish/signal-history.jsonl`（始终写，便于审计 / 断点重放）；
2. 可选：POST 到云函数 `signalHistory` 的 HTTP 访问服务（`SIGNAL_HISTORY_URL`）。

幂等：每条事件 `_id = <symbol>|<timeframe>|<point>|<anchor_key>|<event>`（非法字符替换为 `-`，
与 `westock/cloudfunctions/signalHistory/index.js` 约定一致），重复上传只覆盖不新增。

用法：
    python scripts/sync_signal_history_cloudbase.py --dry-run
    $env:SIGNAL_HISTORY_URL="https://<env>.service.tcloudbase.com/signalHistory"
    $env:SIGNAL_HISTORY_TOKEN="<token>"
    python scripts/sync_signal_history_cloudbase.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.analysis_contract import SIGNAL_POINT_LABELS  # noqa: E402

DEFAULT_REPORTS_ROOT = ROOT / "data" / "reports"
DEFAULT_OUTPUT_PATH = ROOT / "build" / "miniapp-publish" / "signal-history.jsonl"
DEFAULT_BATCH_SIZE = 100

_ID_SANITIZER = re.compile(r"[^0-9A-Za-z_-]")


class SignalHistorySyncError(RuntimeError):
    """同步失败（网络 / 云函数返回错误）。"""


def safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def maybe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def sanitize_id_part(value: Any) -> str:
    raw = safe_text(value)
    return _ID_SANITIZER.sub("-", raw)


def build_event_id(symbol: str, timeframe: str, point: str, anchor_key: Any, event: str) -> str:
    return "|".join(
        (
            sanitize_id_part(symbol),
            sanitize_id_part(timeframe),
            sanitize_id_part(point),
            sanitize_id_part(anchor_key),
            sanitize_id_part(event),
        )
    )


def _anchor_key(point: dict[str, Any]) -> Any:
    anchor = point.get("signal_bi_id")
    # 0 是合法笔号，判空只能用 is None（design §6.2.2 零值陷阱）。
    if anchor is not None:
        return anchor
    return point.get("time") or point.get("forming_at")


def _base_record(
    payload: dict[str, Any],
    point: dict[str, Any],
    *,
    event: str,
    from_state: str | None,
    event_at: Any,
    event_price: Any,
    run_id: str,
) -> dict[str, Any]:
    symbol = safe_text(payload.get("symbol"))
    timeframe = safe_text(payload.get("timeframe"))
    point_name = safe_text(point.get("point"))
    anchor_key = _anchor_key(point)
    # 旧 tech.json 无 market：按代码位数推导（5 位 = 港股，6 位 = A 股），非数字代码留空。
    market = safe_text(payload.get("market")) or ("HK" if len(symbol) == 5 else "CN" if len(symbol) == 6 else "")
    # 旧 tech.json 无 forming_at：回退 detected_at（同口径，spec §2.8.4）。
    forming_at = safe_text(point.get("forming_at") or point.get("detected_at")) or None
    confirmed_at = safe_text(point.get("confirmed_at")) or (
        safe_text(event_at) if event == "confirmed" else ""
    ) or None
    confirmed_price = point.get("confirmed_price")
    # spec §2.8.4 不变量：确认不得早于检出（引擎已夹紧；这里兜住旧 tech.json）。
    # 夹紧后两者同属一根事件 K 线，价格改取 forming_price 保持配对。
    if forming_at and confirmed_at and confirmed_at < forming_at:
        confirmed_at = forming_at
        confirmed_price = point.get("forming_price")
    return {
        "_id": build_event_id(symbol, timeframe, point_name, anchor_key, event),
        "symbol": symbol,
        "name": safe_text(payload.get("name")),
        "market": market,
        "timeframe": timeframe,
        "point": point_name,
        "label": safe_text(point.get("label")) or SIGNAL_POINT_LABELS.get(point_name, ""),
        "event": event,
        "from_state": from_state,
        "to_state": event if event != "invalidated" else "invalidated",
        "anchor_key": safe_text(anchor_key),
        "event_at": safe_text(event_at) or None,
        "event_price": maybe_float(event_price),
        "anchor_time": safe_text(point.get("time")) or None,
        "anchor_price": maybe_float(point.get("price")),
        "detected_at": safe_text(point.get("detected_at")) or None,
        "forming_at": forming_at,
        "forming_price": maybe_float(point.get("forming_price")),
        "confirmed_at": confirmed_at,
        "confirmed_price": maybe_float(confirmed_price),
        "invalidated_at": safe_text(point.get("invalidated_at")) or None,
        "invalidated_price": maybe_float(point.get("invalidated_price")),
        "invalidated_reason": safe_text(point.get("invalidated_reason")) or None,
        "invalidated_premise": safe_text(point.get("invalidated_premise")) or None,
        "basis": safe_text(point.get("basis")) or None,
        "related_zs_id": point.get("related_zs_id"),
        "related_zs_low": maybe_float(point.get("related_zs_low")),
        "related_zs_high": maybe_float(point.get("related_zs_high")),
        "data_window": safe_text(payload.get("_data_window")) or None,
        "code_fingerprint": safe_text(payload.get("code_fingerprint")) or None,
        "run_id": run_id,
    }


def build_event_records(
    payload: dict[str, Any],
    *,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """从单份 tech.json 载荷构造事件列表（forming / confirmed / invalidated）。

    纯函数，供单测直接调用。`forming_at` 缺失时回退 `detected_at`（两者同口径，spec §2.8.4）。
    """
    effective_run_id = run_id or safe_text(payload.get("generated_at")) or datetime.now(timezone.utc).isoformat()
    summary = payload.get("summary") or {}
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append(record: dict[str, Any]) -> None:
        record_id = str(record.get("_id"))
        if record_id in seen:
            return
        seen.add(record_id)
        records.append(record)

    for point in summary.get("signal_points") or []:
        if not isinstance(point, dict):
            continue
        state = safe_text(point.get("lifecycle_state")).lower()
        forming_at = point.get("forming_at") or point.get("detected_at")
        if state in ("forming", "confirmed") and forming_at:
            _append(
                _base_record(
                    payload,
                    point,
                    event="forming",
                    from_state=None,
                    event_at=forming_at,
                    event_price=point.get("forming_price"),
                    run_id=effective_run_id,
                )
            )
        if state == "confirmed" and point.get("confirmed_at"):
            _append(
                _base_record(
                    payload,
                    point,
                    event="confirmed",
                    from_state="forming",
                    event_at=point.get("confirmed_at"),
                    event_price=point.get("confirmed_price"),
                    run_id=effective_run_id,
                )
            )

    for point in summary.get("invalidated_points") or []:
        if not isinstance(point, dict):
            continue
        _append(
            _base_record(
                payload,
                point,
                event="invalidated",
                from_state=safe_text(point.get("from_state")) or "confirmed",
                event_at=point.get("invalidated_at"),
                event_price=point.get("invalidated_price"),
                run_id=effective_run_id,
            )
        )

    return records


def iter_tech_payloads(reports_root: Path, symbols: Iterable[str] | None = None) -> Iterable[dict[str, Any]]:
    allowed = {safe_text(symbol) for symbol in symbols or [] if safe_text(symbol)}
    for tech_path in sorted(reports_root.glob("*/*/tech.json")):
        symbol = tech_path.parent.parent.name
        if allowed and symbol not in allowed:
            continue
        try:
            payload = json.loads(tech_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        payload.setdefault("symbol", symbol)
        payload.setdefault("timeframe", tech_path.parent.name)
        # 供事件记录保留窗口标识（tech.json 顶层未必有该字段）。
        lifecycle_frame = (payload.get("summary") or {}).get("lifecycle_frame") or {}
        payload.setdefault("_data_window", lifecycle_frame.get("data_window"))
        yield payload


def collect_records(
    reports_root: Path,
    symbols: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in iter_tech_payloads(reports_root, symbols):
        for record in build_event_records(payload):
            record_id = str(record.get("_id"))
            if record_id in seen:
                continue
            seen.add(record_id)
            records.append(record)
    records.sort(key=lambda item: (safe_text(item.get("symbol")), safe_text(item.get("timeframe")), safe_text(item.get("event_at"))))
    return records


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def post_batch(url: str, token: str, records: list[dict[str, Any]], *, timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps({"action": "upsertBatch", "records": records}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 受信 URL 由调用方提供
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        raise SignalHistorySyncError(f"HTTP {error.code}: {error.reason}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SignalHistorySyncError(str(error)) from error
    if isinstance(payload, dict) and payload.get("success") is False:
        raise SignalHistorySyncError(safe_text(payload.get("errMsg")) or "云函数返回失败")
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else {}


def upload_records(url: str, token: str, records: list[dict[str, Any]], *, batch_size: int) -> dict[str, int]:
    upserted = 0
    failed = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        data = post_batch(url, token, batch)
        upserted += int(data.get("upserted") or 0)
        failed += len(data.get("failed") or [])
    return {"upserted": upserted, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync buy/sell signal migration history to CloudBase document DB.")
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT), help="tech.json 根目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="jsonl 输出路径")
    parser.add_argument("--symbols", nargs="*", default=None, help="仅同步指定标的")
    parser.add_argument("--url", default=os.environ.get("SIGNAL_HISTORY_URL"), help="云函数 HTTP 地址")
    parser.add_argument("--token", default=os.environ.get("SIGNAL_HISTORY_TOKEN"), help="写入 token")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="只生成 jsonl，不上传")
    parser.add_argument("--skip-upload", action="store_true", help="不上传（与 dry-run 的区别：不打印跳过原因）")
    args = parser.parse_args(argv)

    reports_root = Path(args.reports_root)
    if not reports_root.exists():
        print(f"reports root not found: {reports_root}", file=sys.stderr)
        return 1

    records = collect_records(reports_root, args.symbols)
    output_path = Path(args.output)
    write_jsonl(records, output_path)
    counts: dict[str, int] = {}
    for record in records:
        event = safe_text(record.get("event"))
        counts[event] = counts.get(event, 0) + 1
    print(f"records={len(records)} output={output_path}")
    print("events=" + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))

    if args.dry_run or args.skip_upload:
        print("upload skipped")
        return 0
    if not args.url:
        print("SIGNAL_HISTORY_URL / --url 未提供，跳过上传（只落 jsonl）", file=sys.stderr)
        return 0

    try:
        result = upload_records(args.url, args.token or "", records, batch_size=max(1, args.batch_size))
    except SignalHistorySyncError as error:
        print(f"signal history upload failed: {error}", file=sys.stderr)
        return 2
    print(f"upload upserted={result['upserted']} failed={result['failed']}")
    return 0 if result["failed"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
