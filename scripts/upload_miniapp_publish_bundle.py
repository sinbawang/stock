from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import fnmatch
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "build" / "miniapp-publish" / "latest"
DEFAULT_MANIFEST_PATH = ROOT / "build" / "miniapp-publish" / "cloudbase-upload-manifest.json"
ALWAYS_UPLOAD_PATTERNS = (
    "index.json",
    "groups/*.json",
    "stocks/*/base.json",
    "stocks/*/detail.json",
    "stocks/*/summary.json",
)


def parse_args() -> argparse.Namespace:
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
        default=4,
        help="Retry count for cloud readback verification when checksum mismatches.",
    )
    parser.add_argument(
        "--verify-retry-wait-seconds",
        type=float,
        default=1.5,
        help="Wait seconds between verification retries.",
    )
    return parser.parse_args()


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


def build_admin_url(env_id: str, region: str) -> str:
    seq_id = uuid.uuid4().hex
    return f"https://{env_id}.{region}.tcb-api.tencentcloudapi.com/admin?env={env_id}&seqId={seq_id}"


def new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


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

    response: dict[str, Any] | None = None
    last_error: Exception | None = None
    for action in actions:
        for payload in payload_candidates:
            try:
                response = admin_request(
                    session,
                    env_id=env_id,
                    region=region,
                    api_key=api_key,
                    action=action,
                    payload=payload,
                )
                break
            except CloudBaseUploadError as exc:
                last_error = exc
                continue
        if response is not None:
            break

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


def verify_uploaded_files(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    uploaded_items: list[UploadedItem],
    retries: int,
    retry_wait_seconds: float,
) -> list[VerificationResult]:
    results: list[VerificationResult] = []
    verify_attempts = max(1, int(retries))

    for uploaded in uploaded_items:
        item = uploaded.file
        local_payload = item.local_path.read_bytes()
        local_summary = _json_summary_for_compare(item.relative_path, local_payload)
        cloud_payload = b""
        cloud_sha256 = ""
        cloud_summary = ""
        matched = False
        attempts = 0

        for attempt in range(1, verify_attempts + 1):
            attempts = attempt
            cloud_payload = download_cloud_bytes(
                session,
                env_id=env_id,
                region=region,
                api_key=api_key,
                cloud_path=uploaded.file_id or item.cloud_path,
            )
            cloud_sha256 = hashlib.sha256(cloud_payload).hexdigest()
            cloud_summary = _json_summary_for_compare(item.relative_path, cloud_payload)

            if cloud_sha256 == item.sha256:
                matched = True
                break

            if attempt < verify_attempts:
                time.sleep(max(0.0, float(retry_wait_seconds)))

        results.append(
            VerificationResult(
                relative_path=item.relative_path,
                cloud_path=item.cloud_path,
                local_sha256=item.sha256,
                cloud_sha256=cloud_sha256,
                matched=matched,
                attempts=attempts,
                local_summary=local_summary,
                cloud_summary=cloud_summary,
            )
        )

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


def main() -> int:
    args = parse_args()
    source_dir = require_path(Path(args.source_dir).resolve(), "source dir")
    manifest_path = Path(args.manifest_path).resolve()
    if not args.env_id and not args.dry_run:
        raise CloudBaseUploadError("Missing --env-id or CLOUDBASE_ENV_ID/TCB_ENV_ID.")

    files = iter_local_files(source_dir, args.cloud_prefix)
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

    api_key = args.api_key
    created_api_key: CreatedApiKey | None = None
    if not api_key:
        created_api_key = create_temporary_api_key(
            env_id=args.env_id,
            region=args.region,
            key_name=args.api_key_name,
            expire_in=args.api_key_expire_in,
        )
        api_key = created_api_key.api_key
        print(f"created_api_key={created_api_key.key_id}")

    session = new_session()
    uploads: list[dict[str, Any]] = list(skipped_uploads)
    uploaded_items: list[UploadedItem] = []
    try:
        for item in upload_plan:
            metadata = get_upload_metadata(
                session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                cloud_path=item.cloud_path,
            )
            upload_bytes(session, cloud_path=item.cloud_path, local_path=item.local_path, metadata=metadata)
            uploads.append(
                {
                    "relative_path": item.relative_path,
                    "cloud_path": item.cloud_path,
                    "file_id": metadata["fileId"],
                    "size": item.size,
                    "sha256": item.sha256,
                    "status": "uploaded",
                }
            )
            uploaded_items.append(UploadedItem(file=item, file_id=str(metadata["fileId"])))
            print(f"uploaded {item.relative_path} -> {metadata['fileId']}")

        verification_payload: list[dict[str, Any]] = []
        if args.verify_upload and uploaded_items:
            verification_results = verify_uploaded_files(
                session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                uploaded_items=uploaded_items,
                retries=args.verify_retries,
                retry_wait_seconds=args.verify_retry_wait_seconds,
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
            print(f"verified={len(verification_results)}")
        else:
            verification_payload = []
    finally:
        session.close()
        if created_api_key and args.delete_created_api_key:
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