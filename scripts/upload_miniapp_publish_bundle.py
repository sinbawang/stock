from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import fnmatch
import random
import re
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "build" / "miniapp-publish" / "latest"
DEFAULT_API_KEY_CACHE_PATH = ROOT / "build" / ".cloudbase-apikey-cache.json"
DEFAULT_UPLOAD_CONCURRENCY = int(os.environ.get("CLOUDBASE_UPLOAD_CONCURRENCY") or 8)
DEFAULT_VERIFY_CONCURRENCY = int(os.environ.get("CLOUDBASE_VERIFY_CONCURRENCY") or 8)

# Cache the (action, payload-shape) combo that successfully returns a download URL
# so post-upload verification does not re-probe every losing candidate per file.
_download_combo_index: int | None = None
_download_combo_lock = threading.Lock()
DEFAULT_MANIFEST_PATH = ROOT / "build" / "miniapp-publish" / "cloudbase-upload-manifest.json"
ALWAYS_UPLOAD_PATTERNS = (
    "index.json",
    "groups/*.json",
    "stocks/*/base.json",
    "stocks/*/detail.json",
    "stocks/*/summary.json",
    # 图表 JSON 必须随最新 K 线刷新，不能依赖 manifest 哈希（manifest 与云端易漂移导致图表长期不更新）。
    "stocks/*/charts/*.json",
)
INCREMENTAL_INDEX_GROUP_PATTERNS = (
    "index.json",
    "groups/*.json",
)
INCREMENTAL_ALERT_PATTERNS = (
    "alerts/*.json",
)
CHART_FILE_RE = re.compile(r"^stocks/([^/]+)/charts/([^/.]+)\.json$")
STOCK_META_FILE_RE = re.compile(r"^stocks/([^/]+)/(base|summary|detail)\.json$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload the miniapp publish bundle to CloudBase storage.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Local bundle directory to upload")
    parser.add_argument("--cloud-prefix", default="miniapp-publish/latest", help="Cloud storage prefix")
    parser.add_argument("--env-id", default=os.environ.get("CLOUDBASE_ENV_ID") or os.environ.get("TCB_ENV_ID"), help="CloudBase environment ID")
    parser.add_argument("--region", default=os.environ.get("CLOUDBASE_REGION") or os.environ.get("TCB_REGION") or "ap-guangzhou", help="CloudBase region")
    parser.add_argument("--api-key", default=os.environ.get("CLOUDBASE_APIKEY"), help="CloudBase admin API key")
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH), help="Output manifest path")
    parser.add_argument("--api-key-name", default="miniapp-publish-uploader", help="Name for a temporary API key when created automatically")
    parser.add_argument("--api-key-expire-in", type=int, default=7200, help="Temporary API key lifetime in seconds")
    parser.add_argument("--delete-created-api-key", action="store_true", help="Delete the temporary API key after upload")
    parser.add_argument("--force-upload", action="store_true", help="Upload all files and bypass manifest-diff skip logic")
    parser.add_argument(
        "--chart-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=None,
        help="Upload only selected chart JSON timeframes and minimal index/group metadata.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional symbols to scope incremental chart uploads, e.g. 01024 00700.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be uploaded")
    parser.add_argument(
        "--verify-upload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After upload, read cloud files back and verify SHA256 matches local payload.",
    )
    parser.add_argument(
        "--verify-retries",
        type=int,
        default=8,
        help="Retry count for cloud readback verification when checksum mismatches.",
    )
    parser.add_argument(
        "--verify-retry-wait-seconds",
        type=float,
        default=2.0,
        help="Wait seconds between verification retries.",
    )
    parser.add_argument(
        "--include-stock-meta",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether incremental uploads should include stocks/*/(base|summary|detail).json.",
    )
    parser.add_argument(
        "--include-index-groups",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether incremental uploads should include index.json and groups/*.json.",
    )
    parser.add_argument(
        "--upload-concurrency",
        type=int,
        default=DEFAULT_UPLOAD_CONCURRENCY,
        help="Number of concurrent worker threads for uploading files (default 8).",
    )
    parser.add_argument(
        "--verify-concurrency",
        type=int,
        default=DEFAULT_VERIFY_CONCURRENCY,
        help="Number of concurrent worker threads for post-upload readback verification (default 8).",
    )
    parser.add_argument(
        "--verify-sample-ratio",
        type=float,
        default=1.0,
        help=(
            "Fraction (0..1) of uploaded files to read back and verify. "
            "Critical entry files (index.json, groups/*) are always verified. "
            "Use <1.0 to sample for faster intraday runs; 0 skips readback entirely."
        ),
    )
    parser.add_argument(
        "--reuse-api-key",
        action="store_true",
        help=(
            "Reuse a cached temporary API key across runs instead of creating and deleting one each run. "
            "The key is cached (with its expiry) under build/ which is gitignored."
        ),
    )
    parser.add_argument(
        "--api-key-cache-path",
        default=str(DEFAULT_API_KEY_CACHE_PATH),
        help="Path to the cached temporary API key when --reuse-api-key is set.",
    )
    return parser.parse_args(argv)


@dataclass(frozen=True)
class LocalFile:
    relative_path: str
    local_path: Path
    cloud_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CreatedApiKey:
    key_id: str
    api_key: str


class CloudBaseUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationResult:
    relative_path: str
    cloud_path: str
    local_sha256: str
    cloud_sha256: str
    matched: bool
    attempts: int
    local_summary: str = ""
    cloud_summary: str = ""


@dataclass(frozen=True)
class UploadedItem:
    file: LocalFile
    file_id: str


def load_previous_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    files = payload.get("files")
    if not isinstance(files, list):
        return None
    return payload


def file_should_always_upload(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in ALWAYS_UPLOAD_PATTERNS)


def previous_upload_index(previous_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if previous_manifest is None:
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for item in previous_manifest.get("files") or []:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path") or "").strip()
        if not relative_path:
            continue
        indexed[relative_path] = item
    return indexed


def plan_uploads(
    files: list[LocalFile],
    previous_manifest: dict[str, Any] | None,
    *,
    env_id: str | None,
    region: str,
    cloud_prefix: str,
    force_upload: bool = False,
) -> tuple[list[LocalFile], list[dict[str, Any]]]:
    if force_upload:
        return files, []

    previous_files = previous_upload_index(previous_manifest)
    same_target = bool(
        previous_manifest
        and previous_manifest.get("env_id") == (env_id or "")
        and previous_manifest.get("region") == region
        and previous_manifest.get("cloud_prefix") == cloud_prefix
    )

    deferred: list[LocalFile] = []
    immediate: list[LocalFile] = []
    skipped: list[dict[str, Any]] = []
    for item in files:
        if file_should_always_upload(item.relative_path):
            deferred.append(item)
            continue

        previous = previous_files.get(item.relative_path) if same_target else None
        if previous and str(previous.get("sha256") or "") == item.sha256:
            skipped.append(
                {
                    "relative_path": item.relative_path,
                    "cloud_path": item.cloud_path,
                    "file_id": previous.get("file_id"),
                    "size": item.size,
                    "sha256": item.sha256,
                    "status": "skipped",
                }
            )
            continue
        immediate.append(item)
    return immediate + deferred, skipped


def iter_local_files(source_dir: Path, cloud_prefix: str) -> list[LocalFile]:
    files: list[LocalFile] = []
    normalized_prefix = cloud_prefix.strip("/")
    for path in sorted(item for item in source_dir.rglob("*") if item.is_file()):
        relative_path = path.relative_to(source_dir).as_posix()
        cloud_path = f"{normalized_prefix}/{relative_path}" if normalized_prefix else relative_path
        payload = path.read_bytes()
        files.append(
            LocalFile(
                relative_path=relative_path,
                local_path=path,
                cloud_path=cloud_path,
                size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    return files


def _symbol_variants(symbol: str) -> set[str]:
    value = str(symbol or "").strip()
    if not value:
        return set()
    variants = {value}
    digits = value.replace("HK", "").replace("hk", "")
    if digits.isdigit():
        variants.add(digits.zfill(5))
        variants.add(digits.zfill(6))
    return variants


def filter_incremental_files(
    files: list[LocalFile],
    *,
    chart_timeframes: set[str] | None,
    symbols: set[str] | None,
    include_stock_meta: bool = True,
    include_index_groups: bool = True,
) -> list[LocalFile]:
    if not chart_timeframes and not symbols:
        return files

    normalized_timeframes = {str(value).strip().lower() for value in (chart_timeframes or set()) if str(value).strip()}
    normalized_symbols = {str(value).strip() for value in (symbols or set()) if str(value).strip()}
    symbol_variants: set[str] = set()
    for symbol in normalized_symbols:
        symbol_variants.update(_symbol_variants(symbol))

    selected: list[LocalFile] = []
    for item in files:
        relative_path = item.relative_path.replace("\\", "/")
        if any(fnmatch.fnmatch(relative_path, pattern) for pattern in INCREMENTAL_ALERT_PATTERNS):
            selected.append(item)
            continue
        if include_index_groups and any(fnmatch.fnmatch(relative_path, pattern) for pattern in INCREMENTAL_INDEX_GROUP_PATTERNS):
            selected.append(item)
            continue

        stock_meta_match = STOCK_META_FILE_RE.match(relative_path)
        if stock_meta_match:
            if not include_stock_meta:
                continue
            symbol = stock_meta_match.group(1)
            if symbol_variants and symbol not in symbol_variants:
                continue
            selected.append(item)
            continue

        chart_match = CHART_FILE_RE.match(relative_path)
        if not chart_match:
            continue

        symbol = chart_match.group(1)
        timeframe = chart_match.group(2).lower()
        if normalized_timeframes and timeframe not in normalized_timeframes:
            continue
        if symbol_variants and symbol not in symbol_variants:
            continue
        selected.append(item)

    return selected


def validate_source_bundle(
    files: list[LocalFile],
    *,
    include_stock_meta: bool,
    include_index_groups: bool,
) -> None:
    relative_paths = {item.relative_path.replace("\\", "/") for item in files}
    has_stock_payloads = any(STOCK_META_FILE_RE.match(path) for path in relative_paths)
    has_chart_payloads = any(CHART_FILE_RE.match(path) for path in relative_paths)
    has_publish_payloads = has_stock_payloads or has_chart_payloads

    if include_index_groups and has_publish_payloads:
        missing_index_group_paths = [
            path
            for path in ("index.json", "groups/portfolio.json")
            if path not in relative_paths
        ]
        if missing_index_group_paths:
            raise CloudBaseUploadError(
                "source bundle is incomplete: missing required publish entry files "
                + ", ".join(missing_index_group_paths)
            )

    if include_stock_meta and has_chart_payloads and not has_stock_payloads:
        raise CloudBaseUploadError(
            "source bundle is incomplete: chart payloads exist but stocks/*/(base|summary|detail).json are missing"
        )


def build_admin_url(env_id: str, region: str) -> str:
    seq_id = uuid.uuid4().hex
    return f"https://{env_id}.{region}.tcb-api.tencentcloudapi.com/admin?env={env_id}&seqId={seq_id}"


def new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


class _SessionPool:
    """Provides one requests.Session per worker thread (requests.Session is not
    guaranteed thread-safe), and tracks them so they can all be closed at the end."""

    def __init__(self) -> None:
        self._local = threading.local()
        self._sessions: list[requests.Session] = []
        self._lock = threading.Lock()

    def get(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = new_session()
            self._local.session = session
            with self._lock:
                self._sessions.append(session)
        return session

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions)
            self._sessions.clear()
        for session in sessions:
            try:
                session.close()
            except Exception:
                pass


def _api_key_cache_min_remaining() -> int:
    return 600


def load_cached_api_key(cache_path: Path, *, env_id: str, region: str) -> CreatedApiKey | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("env_id") != env_id or payload.get("region") != region:
        return None
    api_key = payload.get("api_key")
    expires_at = payload.get("expires_at")
    if not api_key or not isinstance(expires_at, (int, float)):
        return None
    if expires_at - time.time() < _api_key_cache_min_remaining():
        return None
    return CreatedApiKey(key_id=str(payload.get("key_id") or ""), api_key=str(api_key))


def save_cached_api_key(
    cache_path: Path,
    *,
    env_id: str,
    region: str,
    created: CreatedApiKey,
    expire_in: int,
) -> None:
    payload = {
        "env_id": env_id,
        "region": region,
        "key_id": created.key_id,
        "api_key": created.api_key,
        "expires_at": time.time() + max(0, int(expire_in)),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(cache_path, 0o600)
    except OSError:
        pass


def resolve_api_key(
    *,
    provided_api_key: str | None,
    reuse_api_key: bool,
    cache_path: Path,
    env_id: str,
    region: str,
    key_name: str,
    expire_in: int,
) -> tuple[str, CreatedApiKey | None, bool]:
    """Return (api_key, created_api_key, created_new).

    created_api_key is non-None only when this call created (or reused) a temporary
    key; created_new is True only when a brand new key was created this run."""
    if provided_api_key:
        return provided_api_key, None, False

    if reuse_api_key:
        cached = load_cached_api_key(cache_path, env_id=env_id, region=region)
        if cached is not None:
            print(f"reused_cached_api_key={cached.key_id}")
            return cached.api_key, cached, False

    created = create_temporary_api_key(
        env_id=env_id,
        region=region,
        key_name=key_name,
        expire_in=expire_in,
    )
    print(f"created_api_key={created.key_id}")
    if reuse_api_key:
        save_cached_api_key(
            cache_path,
            env_id=env_id,
            region=region,
            created=created,
            expire_in=expire_in,
        )
    return created.api_key, created, True


def run_uploads_parallel(
    upload_plan: list[LocalFile],
    *,
    env_id: str,
    region: str,
    api_key: str,
    concurrency: int,
    pool: _SessionPool,
) -> tuple[list[dict[str, Any]], list[UploadedItem]]:
    records: list[dict[str, Any] | None] = [None] * len(upload_plan)
    uploaded: list[UploadedItem | None] = [None] * len(upload_plan)

    def _work(index: int, item: LocalFile) -> int:
        session = pool.get()
        metadata = get_upload_metadata(
            session,
            env_id=env_id,
            region=region,
            api_key=api_key,
            cloud_path=item.cloud_path,
        )
        upload_bytes(session, cloud_path=item.cloud_path, local_path=item.local_path, metadata=metadata)
        records[index] = {
            "relative_path": item.relative_path,
            "cloud_path": item.cloud_path,
            "file_id": metadata["fileId"],
            "size": item.size,
            "sha256": item.sha256,
            "status": "uploaded",
        }
        uploaded[index] = UploadedItem(file=item, file_id=str(metadata["fileId"]))
        print(f"uploaded {item.relative_path} -> {metadata['fileId']}", flush=True)
        return index

    workers = max(1, min(int(concurrency), len(upload_plan)))
    if workers == 1:
        for index, item in enumerate(upload_plan):
            _work(index, item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_work, index, item) for index, item in enumerate(upload_plan)]
            for future in as_completed(futures):
                future.result()

    return (
        [record for record in records if record is not None],
        [item for item in uploaded if item is not None],
    )


def admin_headers(api_key: str, region: str) -> dict[str, str]:
    timestamp_ms = str(int(time.time() * 1000))
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "chanlun-stock-cloudbase-uploader/0.1",
        "X-Client-Timestamp": timestamp_ms,
        "X-SDK-Version": "chanlun-stock-cloudbase-uploader/0.1",
        "X-TCB-Region": region,
        "X-TCB-Source": "stock-miniapp-publish,local",
    }


def admin_request(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = {"action": action, "envName": env_id, **payload}
    response = session.post(
        build_admin_url(env_id, region),
        headers=admin_headers(api_key, region),
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    parsed = response.json()
    if parsed.get("code"):
        raise CloudBaseUploadError(f"{parsed.get('code')}: {parsed.get('message')}")
    return parsed


def get_upload_metadata(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    cloud_path: str,
) -> dict[str, Any]:
    response = admin_request(
        session,
        env_id=env_id,
        region=region,
        api_key=api_key,
        action="storage.getUploadMetadata",
        payload={"path": cloud_path, "method": "put"},
    )
    data = response.get("data") or {}
    required_keys = ("url", "token", "authorization", "fileId", "cosFileId")
    missing = [key for key in required_keys if not data.get(key)]
    if missing:
        raise CloudBaseUploadError(f"upload metadata missing fields: {', '.join(missing)}")
    return data


def get_download_url(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    cloud_path: str,
) -> str:
    global _download_combo_index
    payload_candidates: list[dict[str, Any]] = [
        {"file_list": [cloud_path]},
        {"fileList": [cloud_path]},
        {"fileid_list": [cloud_path]},
        {"fileIdList": [cloud_path]},
        {"file_list": [{"fileid": cloud_path}]},
        {"fileList": [{"fileid": cloud_path}]},
        {"fileList": [{"fileId": cloud_path}]},
        {"fileList": [{"fileID": cloud_path}]},
        {"fileid_list": [{"fileid": cloud_path}]},
        {"fileIdList": [{"fileID": cloud_path}]},
    ]
    actions = [
        "storage.batchGetDownloadUrl",
        "storage.batchGetTempFileURL",
        "storage.getTempFileURL",
    ]

    # Flatten (action, payload) combos in the original action-major order, then
    # try the previously successful combo first so repeated verification reads
    # don't re-probe every losing candidate for each file.
    combos = [(action, payload) for action in actions for payload in payload_candidates]
    order = list(range(len(combos)))
    with _download_combo_lock:
        cached_index = _download_combo_index
    if cached_index is not None and 0 <= cached_index < len(combos):
        order = [cached_index] + [index for index in order if index != cached_index]

    response: dict[str, Any] | None = None
    last_error: Exception | None = None
    winning_index: int | None = None
    for index in order:
        action, payload = combos[index]
        try:
            response = admin_request(
                session,
                env_id=env_id,
                region=region,
                api_key=api_key,
                action=action,
                payload=payload,
            )
            winning_index = index
            break
        except CloudBaseUploadError as exc:
            last_error = exc
            continue

    if winning_index is not None and winning_index != cached_index:
        with _download_combo_lock:
            _download_combo_index = winning_index

    if response is None:
        if last_error is not None:
            raise CloudBaseUploadError(str(last_error))
        raise CloudBaseUploadError(f"Cannot request download metadata for {cloud_path}")

    data = response.get("data")
    items: list[Any] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("download_list", "downloadList", "fileList", "DownloadList", "list"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
    if not items:
        raise CloudBaseUploadError(f"No download metadata returned for {cloud_path}.")

    first = items[0]
    if isinstance(first, str) and first.strip():
        return first
    if isinstance(first, dict):
        for key in (
            "tempFileURL",
            "tempFileUrl",
            "download_url",
            "downloadUrl",
            "url",
            "fileUrl",
        ):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value
    raise CloudBaseUploadError(f"Cannot parse download URL for {cloud_path}: {first}")


def download_cloud_bytes(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    cloud_path: str,
) -> bytes:
    download_url = get_download_url(
        session,
        env_id=env_id,
        region=region,
        api_key=api_key,
        cloud_path=cloud_path,
    )
    response = session.get(
        download_url,
        params={"_ts": str(time.time_ns())},
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def _json_summary_for_compare(relative_path: str, payload: bytes) -> str:
    if not relative_path.endswith(".json"):
        return ""
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid-json"

    if isinstance(parsed, dict) and "/charts/" in relative_path:
        segments = parsed.get("segments") or []
        first = segments[0] if segments else {}
        return (
            f"source_csv={parsed.get('source_csv')} "
            f"segments={len(segments)} "
            f"first={first.get('start_ts')}->{first.get('end_ts')}"
        )

    if relative_path == "index.json" and isinstance(parsed, dict):
        return f"generated_at={parsed.get('generated_at')} stocks={len(parsed.get('stocks') or [])}"

    return ""


def _verify_single_item(
    session: requests.Session,
    uploaded: UploadedItem,
    *,
    env_id: str,
    region: str,
    api_key: str,
    verify_attempts: int,
    retry_wait_seconds: float,
) -> VerificationResult:
    item = uploaded.file
    local_payload = item.local_path.read_bytes()
    local_summary = _json_summary_for_compare(item.relative_path, local_payload)
    cloud_sha256 = ""
    cloud_summary = ""
    matched = False
    attempts = 0

    for attempt in range(1, verify_attempts + 1):
        attempts = attempt
        try:
            cloud_payload = download_cloud_bytes(
                session,
                env_id=env_id,
                region=region,
                api_key=api_key,
                cloud_path=uploaded.file_id or item.cloud_path,
            )
        except requests.RequestException as exc:
            cloud_sha256 = ""
            cloud_summary = f"download_error:{type(exc).__name__}"
            if attempt < verify_attempts:
                time.sleep(max(0.0, float(retry_wait_seconds)))
                continue
            break
        cloud_sha256 = hashlib.sha256(cloud_payload).hexdigest()
        cloud_summary = _json_summary_for_compare(item.relative_path, cloud_payload)

        if cloud_sha256 == item.sha256:
            matched = True
            break

        if attempt < verify_attempts:
            time.sleep(max(0.0, float(retry_wait_seconds)))

    return VerificationResult(
        relative_path=item.relative_path,
        cloud_path=item.cloud_path,
        local_sha256=item.sha256,
        cloud_sha256=cloud_sha256,
        matched=matched,
        attempts=attempts,
        local_summary=local_summary,
        cloud_summary=cloud_summary,
    )


def _select_items_to_verify(
    uploaded_items: list[UploadedItem],
    sample_ratio: float,
) -> list[UploadedItem]:
    if sample_ratio >= 1.0:
        return list(uploaded_items)

    critical: list[UploadedItem] = []
    optional: list[UploadedItem] = []
    for uploaded in uploaded_items:
        relative_path = uploaded.file.relative_path.replace("\\", "/")
        if (
            relative_path == "index.json"
            or relative_path.startswith("groups/")
            or file_should_always_upload(relative_path)
        ):
            critical.append(uploaded)
        else:
            optional.append(uploaded)

    if sample_ratio <= 0.0 or not optional:
        return critical

    sample_size = max(0, min(len(optional), round(len(optional) * sample_ratio)))
    sampled = random.sample(optional, sample_size) if sample_size < len(optional) else optional
    return critical + sampled


def verify_uploaded_files(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    uploaded_items: list[UploadedItem],
    retries: int,
    retry_wait_seconds: float,
    concurrency: int = 1,
    sample_ratio: float = 1.0,
) -> list[VerificationResult]:
    verify_attempts = max(1, int(retries))
    selected = _select_items_to_verify(uploaded_items, sample_ratio)

    results: list[VerificationResult] = []
    workers = max(1, min(int(concurrency), len(selected))) if selected else 1
    if workers == 1:
        for uploaded in selected:
            results.append(
                _verify_single_item(
                    session,
                    uploaded,
                    env_id=env_id,
                    region=region,
                    api_key=api_key,
                    verify_attempts=verify_attempts,
                    retry_wait_seconds=retry_wait_seconds,
                )
            )
    else:
        pool = _SessionPool()
        ordered: list[VerificationResult | None] = [None] * len(selected)

        def _verify_worker(index: int, uploaded: UploadedItem) -> int:
            ordered[index] = _verify_single_item(
                pool.get(),
                uploaded,
                env_id=env_id,
                region=region,
                api_key=api_key,
                verify_attempts=verify_attempts,
                retry_wait_seconds=retry_wait_seconds,
            )
            return index

        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(_verify_worker, index, uploaded)
                    for index, uploaded in enumerate(selected)
                ]
                for future in as_completed(futures):
                    future.result()
        finally:
            pool.close_all()
        results = [result for result in ordered if result is not None]

    mismatches = [result for result in results if not result.matched]
    if mismatches:
        details = []
        for result in mismatches[:6]:
            details.append(
                (
                    f"{result.relative_path} local={result.local_sha256[:12]} "
                    f"cloud={result.cloud_sha256[:12]} attempts={result.attempts} "
                    f"local_summary=({result.local_summary}) cloud_summary=({result.cloud_summary})"
                )
            )
        raise CloudBaseUploadError(
            "Post-upload verification failed for one or more files: " + " | ".join(details)
        )

    return results


def upload_bytes(session: requests.Session, *, cloud_path: str, local_path: Path, metadata: dict[str, Any]) -> None:
    content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    headers = {
        "Signature": str(metadata["authorization"]),
        "authorization": str(metadata["authorization"]),
        "x-cos-security-token": str(metadata["token"]),
        "x-cos-meta-fileid": str(metadata["cosFileId"]),
        "key": quote(cloud_path, safe="-_.!~*'()"),
        "Content-Type": content_type,
    }
    with local_path.open("rb") as handle:
        response = session.put(str(metadata["url"]), headers=headers, data=handle, timeout=120)
    if response.status_code != 200:
        raise CloudBaseUploadError(f"COS upload failed for {cloud_path}: HTTP {response.status_code} {response.text[:200]}")
    body = response.text.strip()
    if not body:
        return
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return
    if root.tag == "Error":
        code = root.findtext("Code") or "COSUploadError"
        message = root.findtext("Message") or body
        raise CloudBaseUploadError(f"COS upload failed for {cloud_path}: {code}: {message}")


def create_temporary_api_key(
    *,
    env_id: str,
    region: str,
    key_name: str,
    expire_in: int,
) -> CreatedApiKey:
    secret_id = os.environ.get("TENCENT_SECRET_ID") or os.environ.get("TENCENTCLOUD_SECRETID")
    secret_key = os.environ.get("TENCENT_SECRET_KEY") or os.environ.get("TENCENTCLOUD_SECRETKEY")
    if not secret_id or not secret_key:
        raise CloudBaseUploadError(
            "Missing CLOUDBASE_APIKEY and no Tencent secret credentials are available to create one. "
            "Set CLOUDBASE_APIKEY or TENCENT_SECRET_ID/TENCENT_SECRET_KEY."
        )

    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.tcb.v20180608 import models, tcb_client

    cred = credential.Credential(secret_id, secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = "tcb.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = tcb_client.TcbClient(cred, region, client_profile)
    client.request.conn._session.trust_env = False

    request = models.CreateApiKeyRequest()
    request.EnvId = env_id
    request.KeyType = "api_key"
    request.KeyName = key_name
    request.ExpireIn = max(expire_in, 7200)
    response = client.CreateApiKey(request)
    if not response.ApiKey or not response.KeyId:
        raise CloudBaseUploadError("CreateApiKey succeeded but no ApiKey/KeyId was returned.")
    return CreatedApiKey(key_id=response.KeyId, api_key=response.ApiKey)


def delete_temporary_api_key(*, env_id: str, region: str, key_id: str) -> None:
    secret_id = os.environ.get("TENCENT_SECRET_ID") or os.environ.get("TENCENTCLOUD_SECRETID")
    secret_key = os.environ.get("TENCENT_SECRET_KEY") or os.environ.get("TENCENTCLOUD_SECRETKEY")
    if not secret_id or not secret_key:
        return

    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.tcb.v20180608 import models, tcb_client

    cred = credential.Credential(secret_id, secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = "tcb.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = tcb_client.TcbClient(cred, region, client_profile)
    client.request.conn._session.trust_env = False

    request = models.DeleteApiKeyRequest()
    request.EnvId = env_id
    request.KeyId = key_id
    client.DeleteApiKey(request)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_manifest(
    *,
    env_id: str,
    region: str,
    source_dir: Path,
    cloud_prefix: str,
    uploads: list[dict[str, Any]],
    verification: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    index_item = next((item for item in uploads if item["relative_path"] == "index.json"), None)
    return {
        "schema_version": "v1",
        "env_id": env_id,
        "region": region,
        "source_dir": str(source_dir),
        "cloud_prefix": cloud_prefix,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_count": len(uploads),
        "index": {
            "relative_path": index_item["relative_path"] if index_item else None,
            "cloud_path": index_item["cloud_path"] if index_item else None,
            "file_id": index_item["file_id"] if index_item else None,
        },
        "files": uploads,
        "verification": verification or [],
    }


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise CloudBaseUploadError(f"{label} does not exist: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_dir = require_path(Path(args.source_dir).resolve(), "source dir")
    manifest_path = Path(args.manifest_path).resolve()
    if not args.env_id and not args.dry_run:
        raise CloudBaseUploadError("Missing --env-id or CLOUDBASE_ENV_ID/TCB_ENV_ID.")

    files = iter_local_files(source_dir, args.cloud_prefix)
    validate_source_bundle(
        files,
        include_stock_meta=bool(args.include_stock_meta),
        include_index_groups=bool(args.include_index_groups),
    )
    chart_timeframes = {str(value).strip() for value in (args.chart_timeframes or []) if str(value).strip()}
    symbol_selector: set[str] = set()
    for raw_symbol in args.symbols or []:
        symbol_selector.update(_symbol_variants(raw_symbol))
    files = filter_incremental_files(
        files,
        chart_timeframes=chart_timeframes if chart_timeframes else None,
        symbols=symbol_selector if symbol_selector else None,
        include_stock_meta=bool(args.include_stock_meta),
        include_index_groups=bool(args.include_index_groups),
    )
    if not files:
        raise CloudBaseUploadError(f"No files found under {source_dir}")

    previous_manifest = load_previous_manifest(manifest_path)
    upload_plan, skipped_uploads = plan_uploads(
        files,
        previous_manifest,
        env_id=args.env_id,
        region=args.region,
        cloud_prefix=args.cloud_prefix,
        force_upload=args.force_upload,
    )

    print(f"source={source_dir}")
    print(f"files={len(files)}")
    if chart_timeframes:
        print(f"chart_timeframes={','.join(sorted(chart_timeframes))}")
    if symbol_selector:
        print(f"symbols={','.join(sorted(symbol_selector))}")
    print(f"uploading={len(upload_plan)}")
    print(f"skipped={len(skipped_uploads)}")
    print(f"cloud_prefix={args.cloud_prefix}")
    if args.force_upload:
        print("force_upload=true; previous manifest diff skipping is disabled")

    if args.dry_run:
        manifest = build_manifest(
            env_id=args.env_id or "",
            region=args.region,
            source_dir=source_dir,
            cloud_prefix=args.cloud_prefix,
            uploads=skipped_uploads + [
                {
                    "relative_path": item.relative_path,
                    "cloud_path": item.cloud_path,
                    "file_id": None,
                    "size": item.size,
                    "sha256": item.sha256,
                    "status": "planned",
                }
                for item in upload_plan
            ],
        )
        write_manifest(manifest_path, manifest)
        print(f"dry_run_manifest={manifest_path}")
        return 0

    api_key, created_api_key, created_new = resolve_api_key(
        provided_api_key=args.api_key,
        reuse_api_key=bool(args.reuse_api_key),
        cache_path=Path(args.api_key_cache_path).resolve(),
        env_id=args.env_id,
        region=args.region,
        key_name=args.api_key_name,
        expire_in=args.api_key_expire_in,
    )

    pool = _SessionPool()
    verify_session = new_session()
    uploads: list[dict[str, Any]] = list(skipped_uploads)
    uploaded_items: list[UploadedItem] = []
    try:
        upload_started = time.perf_counter()
        upload_records, uploaded_items = run_uploads_parallel(
            upload_plan,
            env_id=args.env_id,
            region=args.region,
            api_key=api_key,
            concurrency=args.upload_concurrency,
            pool=pool,
        )
        uploads.extend(upload_records)
        print(
            f"upload_stage_seconds={time.perf_counter() - upload_started:.2f} "
            f"files={len(upload_records)} concurrency={max(1, min(int(args.upload_concurrency), len(upload_plan) or 1))}",
            flush=True,
        )

        verification_payload: list[dict[str, Any]] = []
        if args.verify_upload and uploaded_items:
            verify_started = time.perf_counter()
            verification_results = verify_uploaded_files(
                verify_session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                uploaded_items=uploaded_items,
                retries=args.verify_retries,
                retry_wait_seconds=args.verify_retry_wait_seconds,
                concurrency=args.verify_concurrency,
                sample_ratio=args.verify_sample_ratio,
            )
            verification_payload = [
                {
                    "relative_path": result.relative_path,
                    "cloud_path": result.cloud_path,
                    "matched": result.matched,
                    "attempts": result.attempts,
                    "local_sha256": result.local_sha256,
                    "cloud_sha256": result.cloud_sha256,
                    "local_summary": result.local_summary,
                    "cloud_summary": result.cloud_summary,
                }
                for result in verification_results
            ]
            print(
                f"verified={len(verification_results)}/{len(uploaded_items)} "
                f"sample_ratio={args.verify_sample_ratio} "
                f"verify_stage_seconds={time.perf_counter() - verify_started:.2f}",
                flush=True,
            )
        else:
            verification_payload = []
    finally:
        pool.close_all()
        verify_session.close()
        # Only delete a key we created this run, and never when caching it for reuse.
        if created_api_key and created_new and args.delete_created_api_key and not args.reuse_api_key:
            delete_temporary_api_key(env_id=args.env_id, region=args.region, key_id=created_api_key.key_id)
            print(f"deleted_api_key={created_api_key.key_id}")

    manifest = build_manifest(
        env_id=args.env_id,
        region=args.region,
        source_dir=source_dir,
        cloud_prefix=args.cloud_prefix,
        uploads=uploads,
        verification=verification_payload,
    )
    write_manifest(manifest_path, manifest)
    print(f"manifest={manifest_path}")
    for item in skipped_uploads:
        print(f"skipped {item['relative_path']}")
    if manifest["index"]["file_id"]:
        print(f"index_file_id={manifest['index']['file_id']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CloudBaseUploadError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)