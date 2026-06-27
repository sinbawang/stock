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
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be uploaded")
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
) -> tuple[list[LocalFile], list[dict[str, Any]]]:
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
    )

    print(f"source={source_dir}")
    print(f"files={len(files)}")
    print(f"uploading={len(upload_plan)}")
    print(f"skipped={len(skipped_uploads)}")
    print(f"cloud_prefix={args.cloud_prefix}")

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
            print(f"uploaded {item.relative_path} -> {metadata['fileId']}")
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